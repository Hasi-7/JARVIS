"""
Google Calendar read + reconciliation (B2) — READ-ONLY.

Two capabilities, both read-only:

    list_events(time_min, time_max)      → real Google Calendar events in a window
    reconcile(candidates, events)        → compares vault calendar-candidates to
                                           real events and surfaces the differences

Reconciliation answers: which approved candidates are already on the real
calendar, which are missing from it, and which collide with something already
scheduled. It is a PURE function — no I/O, no network, no writes — so it is fully
testable without Google.

Safety model (this module never relaxes it):
- The ONLY OAuth scopes used are the read-only ones in `google_auth.py`. The Gmail
  scope assertion is shared; a non-readonly scope refuses the call.
- CALENDAR WRITES ARE UNREACHABLE HERE. This module never references insert /
  update / patch / delete / move / import. A source-guard test asserts it. Event
  creation is Phase D2 and requires a separate scope plus re-consent.
- Event titles and descriptions are UNTRUSTED external content: surfaced for
  display only, never executed, never followed as instructions.
- Callers must classify through `permission_gateway.evaluate_tool_request()` and
  log before invoking these functions.
- Reconciliation NEVER mutates the vault. It reports; the user acts.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.gmail import _assert_readonly_scopes  # shared scope guard
from app.google_auth import GoogleAuthSetupError, authorize_google

logger = logging.getLogger(__name__)

CALENDAR_READ_TOOL = "calendar.read"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

DEFAULT_CALENDAR_ID = "primary"
DEFAULT_WINDOW_DAYS = 14
MAX_WINDOW_DAYS = 180
MAX_EVENTS = 250
DEFAULT_DURATION_MINUTES = 60
MAX_TITLE_CHARS = 300

# Two candidates/events "match" when titles normalize equal and they fall on the
# same calendar date.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class CalendarError(RuntimeError):
    """Raised when a Calendar read cannot be performed safely."""


# ══════════════════════════════════════════════════════════════════════════════
# Readiness / client
# ══════════════════════════════════════════════════════════════════════════════

def calendar_configured() -> bool:
    """Configuration-only readiness check; reads no token contents, never raises."""
    try:
        from app.gmail import gmail_configured
        return gmail_configured()   # same client + token file
    except Exception:
        return False


def build_calendar_service(
    *,
    credentials_factory: Optional[Callable[[], Any]] = None,
    service_builder: Optional[Callable[..., Any]] = None,
) -> Any:
    """Build a read-only Calendar client. Both dependencies are injectable."""
    factory = credentials_factory or authorize_google
    try:
        credentials = factory()
    except GoogleAuthSetupError as exc:
        raise CalendarError(str(exc)) from exc

    try:
        _assert_readonly_scopes(getattr(credentials, "scopes", None))
    except Exception as exc:
        raise CalendarError(str(exc)) from exc

    scopes = list(getattr(credentials, "scopes", None) or [])
    if CALENDAR_READONLY_SCOPE not in scopes:
        raise CalendarError(
            "Google credentials do not include the Calendar read-only scope. "
            "Re-run the authorize command."
        )

    if service_builder is None:
        try:
            from googleapiclient.discovery import build as service_builder  # type: ignore
        except ImportError as exc:
            raise CalendarError(
                "Google API client is missing. Run: pip install -r requirements.txt"
            ) from exc

    return service_builder("calendar", "v3", credentials=credentials, cache_discovery=False)


# ══════════════════════════════════════════════════════════════════════════════
# Parsing helpers (pure)
# ══════════════════════════════════════════════════════════════════════════════

def _truncate(value: str, limit: int = MAX_TITLE_CHARS) -> str:
    text = value or ""
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def normalize_title(title: Optional[str]) -> str:
    """Lowercase alphanumeric-only form used for match comparison."""
    return _NON_ALNUM.sub(" ", (title or "").strip().lower()).strip()


def parse_duration_minutes(value: Optional[str]) -> int:
    """Parse '1h', '90m', '1h30m', '1.5h', '45' → minutes. Falls back to 60."""
    text = (value or "").strip().lower().replace(" ", "")
    if not text:
        return DEFAULT_DURATION_MINUTES

    hours = re.search(r"([\d.]+)\s*h", text)
    minutes = re.search(r"([\d.]+)\s*m(?!s)", text)
    total = 0.0
    if hours:
        try:
            total += float(hours.group(1)) * 60
        except ValueError:
            pass
    if minutes:
        try:
            total += float(minutes.group(1))
        except ValueError:
            pass

    if total <= 0:
        bare = re.fullmatch(r"[\d.]+", text)
        if bare:
            try:
                total = float(bare.group(0))
            except ValueError:
                total = 0.0

    if total <= 0:
        return DEFAULT_DURATION_MINUTES
    return int(min(total, 24 * 60))


def parse_candidate_window(candidate: dict) -> Optional[Tuple[datetime, datetime, bool]]:
    """Resolve a candidate row to (start, end, timed).

    Returns None when the date cannot be parsed. `timed` is False for date-only
    candidates, which are compared by date rather than by overlap.
    """
    raw_date = (candidate.get("date") or "").strip()
    if not raw_date:
        return None

    day: Optional[datetime] = None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            day = datetime.strptime(raw_date[:10], fmt)
            break
        except ValueError:
            continue
    if day is None:
        return None

    raw_time = (candidate.get("time") or "").strip()
    if not raw_time:
        return day, day + timedelta(days=1), False

    parsed_time = None
    for fmt in ("%H:%M", "%H%M", "%I:%M%p", "%I%p", "%I:%M %p", "%I %p"):
        try:
            parsed_time = datetime.strptime(raw_time.upper().replace(".", ""), fmt)
            break
        except ValueError:
            continue
    if parsed_time is None:
        return day, day + timedelta(days=1), False

    start = day.replace(hour=parsed_time.hour, minute=parsed_time.minute)
    end = start + timedelta(minutes=parse_duration_minutes(candidate.get("duration")))
    return start, end, True


def parse_event_window(event: dict) -> Optional[Tuple[datetime, datetime, bool]]:
    """Resolve a normalized event to (start, end, timed). All-day → timed False."""
    start_raw = event.get("start")
    end_raw = event.get("end")
    if not start_raw:
        return None

    if event.get("allDay"):
        try:
            start = datetime.strptime(str(start_raw)[:10], "%Y-%m-%d")
        except ValueError:
            return None
        try:
            end = datetime.strptime(str(end_raw)[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            end = start + timedelta(days=1)
        return start, end, False

    def _iso(value) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        # Compare wall-clock times; the calendar's own offset is authoritative.
        return parsed.replace(tzinfo=None)

    start = _iso(start_raw)
    if start is None:
        return None
    end = _iso(end_raw) or (start + timedelta(minutes=DEFAULT_DURATION_MINUTES))
    return start, end, True


def _overlaps(a: Tuple[datetime, datetime], b: Tuple[datetime, datetime]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


# ══════════════════════════════════════════════════════════════════════════════
# Read operation
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_event(raw: dict) -> Optional[dict]:
    if not isinstance(raw, dict) or not raw.get("id"):
        return None
    start = raw.get("start") or {}
    end = raw.get("end") or {}
    all_day = bool(start.get("date") and not start.get("dateTime"))
    return {
        "eventId": str(raw.get("id")),
        "title": _truncate(str(raw.get("summary") or "(no title)")),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "allDay": all_day,
        "status": str(raw.get("status") or ""),
        "htmlLink": str(raw.get("htmlLink") or "") or None,
    }


_OFFSET_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def _rfc3339(value) -> str:
    """Render a timestamp Google will accept.

    The Calendar API rejects timestamps without a UTC offset with HTTP 400, so a
    naive datetime or an offset-less string is normalized to UTC rather than sent
    through as-is.
    """
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.isoformat()

    text = str(value).strip()
    if not text:
        return text
    return text if _OFFSET_SUFFIX.search(text) else text + "Z"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def list_events(
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    *,
    calendar_id: str = DEFAULT_CALENDAR_ID,
    service: Optional[Any] = None,
    now_fn: Callable[[], datetime] = _utc_now,
) -> List[dict]:
    """List real Calendar events in a window. READ-ONLY.

    `time_min`/`time_max` are RFC3339 strings. Omitted values default to a window
    starting now and running DEFAULT_WINDOW_DAYS forward. Both are normalized so
    they always carry a UTC offset.
    """
    now = now_fn()
    start = _rfc3339(time_min) if time_min else _rfc3339(now)
    if time_max:
        end = _rfc3339(time_max)
    else:
        end = _rfc3339(now + timedelta(days=DEFAULT_WINDOW_DAYS))

    client = service or build_calendar_service()

    try:
        response = (
            client.events()
            .list(
                calendarId=calendar_id,
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime",
                maxResults=MAX_EVENTS,
            )
            .execute()
        )
    except CalendarError:
        raise
    except Exception as exc:
        raise CalendarError(f"Calendar read failed: {exc}") from exc

    items = (response or {}).get("items") or []
    events: List[dict] = []
    for raw in items[:MAX_EVENTS]:
        normalized = _normalize_event(raw)
        if normalized and normalized["status"] != "cancelled":
            events.append(normalized)

    logger.info("Calendar read returned %d event(s) (read-only)", len(events))
    return events


# ══════════════════════════════════════════════════════════════════════════════
# Reconciliation (pure — no I/O, no writes)
# ══════════════════════════════════════════════════════════════════════════════

def reconcile(candidates: List[dict], events: List[dict]) -> dict:
    """Compare vault calendar candidates against real Calendar events.

    Only APPROVED candidates are reconciled — unapproved rows are proposals the
    user has not accepted, so their absence from the calendar is not a finding.

    Every candidate lands in exactly one bucket:
      matched      — an event with the same normalized title on the same date
      conflicting  — no title match, but the time window overlaps a real event
      missing      — approved, parseable, and nothing on the calendar matches
      unparseable  — the date/time could not be read from the row

    Returns counts plus per-bucket detail. Mutates nothing.
    """
    matched: List[dict] = []
    conflicting: List[dict] = []
    missing: List[dict] = []
    unparseable: List[dict] = []

    parsed_events: List[Tuple[dict, Optional[Tuple[datetime, datetime, bool]]]] = [
        (e, parse_event_window(e)) for e in (events or [])
    ]

    for candidate in candidates or []:
        approved = str(candidate.get("approved") or "").strip().lower()
        if approved not in ("yes", "y", "true", "approved"):
            continue

        window = parse_candidate_window(candidate)
        base = {
            "candidateId": candidate.get("id"),
            "title": _truncate(str(candidate.get("title") or "")),
            "date": candidate.get("date"),
            "time": candidate.get("time"),
            "duration": candidate.get("duration"),
        }

        if window is None:
            unparseable.append({
                **base,
                "note": "Date or time could not be parsed from this row.",
            })
            continue

        cand_start, cand_end, cand_timed = window
        cand_title = normalize_title(candidate.get("title"))

        match = None
        overlap = None
        for event, event_window in parsed_events:
            if event_window is None:
                continue
            ev_start, ev_end, _ = event_window

            same_day = ev_start.date() == cand_start.date()
            if same_day and cand_title and normalize_title(event["title"]) == cand_title:
                match = event
                break
            if cand_timed and overlap is None and _overlaps(
                (cand_start, cand_end), (ev_start, ev_end)
            ):
                overlap = event

        if match is not None:
            matched.append({
                **base,
                "eventId": match["eventId"],
                "eventTitle": match["title"],
                "eventStart": match["start"],
                "htmlLink": match["htmlLink"],
            })
        elif overlap is not None:
            conflicting.append({
                **base,
                "eventId": overlap["eventId"],
                "eventTitle": overlap["title"],
                "eventStart": overlap["start"],
                "htmlLink": overlap["htmlLink"],
                "note": "Approved candidate overlaps an existing calendar event.",
            })
        else:
            missing.append({
                **base,
                "note": "Approved candidate is not on the real calendar.",
            })

    return {
        "counts": {
            "matched": len(matched),
            "conflicting": len(conflicting),
            "missing": len(missing),
            "unparseable": len(unparseable),
            "events": len(events or []),
        },
        "matched": matched,
        "conflicting": conflicting,
        "missing": missing,
        "unparseable": unparseable,
        "notes": [
            "Reconciliation is read-only. No calendar event is created, moved, or "
            "deleted, and no vault file is written.",
            "Only approved candidates are reconciled.",
            "Event titles are untrusted content and are displayed only.",
        ],
    }
