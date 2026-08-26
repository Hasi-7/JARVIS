"""
Approved Google Calendar event creation (D2) — THE ONLY EXTERNAL WRITE.

Deliberately a separate module from `gcal.py` so that read module stays provably
write-free (its source-guard test asserts it never references `.insert(`).

    create_event(spec) -> {eventId, htmlLink, summary, start, end}

Safety model (this module never relaxes it):
- CREATE ONLY. There is no update, patch, delete, or move here, and there never
  will be — a source-guard test asserts those methods are absent. An event created
  by mistake is corrected by the user in Google Calendar, not by this app.
- REQUIRES THE calendar.events SCOPE. If the granted credential lacks it, the call
  refuses. The scope is only requested when the operator opts in via
  BRAIN_UI_CALENDAR_WRITE_ENABLED, which needs a fresh browser consent.
- REACHED ONLY THROUGH THE APPROVAL QUEUE. `tool_approvals` dispatches this after
  the A3 flow: Assist mode → operator token → privileged kill switch → explicit
  approve → separate explicit execute. Nothing here can be triggered from chat.
- NO ATTENDEES, NO INVITES, NO EMAIL. `sendUpdates` is forced to "none" and any
  attendee field is dropped, so creating an event can never message another person.
- Field values are bounded and validated; a candidate row cannot inject arbitrary
  API parameters because the request body is rebuilt from a fixed allowlist.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from app.gcal import (
    CalendarError,
    DEFAULT_CALENDAR_ID,
    parse_candidate_window,
    parse_duration_minutes,
)
from app.google_auth import CALENDAR_WRITE_SCOPE, GoogleAuthSetupError, authorize_google

logger = logging.getLogger(__name__)

CALENDAR_CREATE_TOOL = "calendar.create_event"

MAX_SUMMARY_CHARS = 300
MAX_DESCRIPTION_CHARS = 4_000
MAX_LOCATION_CHARS = 300
MAX_YEARS_AHEAD = 2

_TZ_RE = re.compile(r"^[A-Za-z_]+/[A-Za-z_+\-0-9]+$")


class CalendarWriteError(CalendarError):
    """Raised when an event cannot be created safely."""


# ══════════════════════════════════════════════════════════════════════════════
# Readiness
# ══════════════════════════════════════════════════════════════════════════════

def write_scope_granted(credentials: Any) -> bool:
    scopes = list(getattr(credentials, "scopes", None) or [])
    return CALENDAR_WRITE_SCOPE in scopes


def build_write_service(
    *,
    credentials_factory: Optional[Callable[[], Any]] = None,
    service_builder: Optional[Callable[..., Any]] = None,
) -> Any:
    """Build a Calendar client that is permitted to create events."""
    factory = credentials_factory or authorize_google
    try:
        credentials = factory()
    except GoogleAuthSetupError as exc:
        raise CalendarWriteError(str(exc)) from exc

    if not write_scope_granted(credentials):
        raise CalendarWriteError(
            "The granted Google credentials do not include the Calendar events scope, "
            "so event creation is refused. Set BRAIN_UI_CALENDAR_WRITE_ENABLED=true and "
            "re-run: python -m app.google_auth authorize"
        )

    if service_builder is None:
        try:
            from googleapiclient.discovery import build as service_builder  # type: ignore
        except ImportError as exc:
            raise CalendarWriteError(
                "Google API client is missing. Run: pip install -r requirements.txt"
            ) from exc

    return service_builder("calendar", "v3", credentials=credentials, cache_discovery=False)


# ══════════════════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════════════════

def _clean(value: Optional[str], limit: int, field: str) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise CalendarWriteError(f"{field} is too long (max {limit} characters).")
    return text


def build_event_body(spec: Dict[str, Any], *, now: Optional[datetime] = None) -> dict:
    """Build the Calendar API request body from a fixed allowlist of fields.

    Rebuilding rather than forwarding means a candidate row cannot smuggle extra
    API parameters (attendees, reminders overrides, conferencing, …) into the call.
    """
    if not isinstance(spec, dict):
        raise CalendarWriteError("An event specification object is required.")

    summary = _clean(spec.get("title") or spec.get("summary"), MAX_SUMMARY_CHARS, "Title")
    if not summary:
        raise CalendarWriteError("An event title is required.")

    date = _clean(spec.get("date"), 40, "Date")
    if not date:
        raise CalendarWriteError("An event date is required.")

    window = parse_candidate_window({
        "date": date,
        "time": spec.get("time"),
        "duration": spec.get("duration"),
    })
    if window is None:
        raise CalendarWriteError(f"Could not parse the event date '{date}'.")

    start, end, timed = window
    reference = now or datetime.now()
    if start > reference + timedelta(days=365 * MAX_YEARS_AHEAD):
        raise CalendarWriteError(
            f"Event start is more than {MAX_YEARS_AHEAD} years in the future; refusing."
        )
    if end <= start:
        end = start + timedelta(minutes=parse_duration_minutes(spec.get("duration")))

    body: Dict[str, Any] = {
        "summary": summary,
        "description": _clean(spec.get("reason") or spec.get("description"),
                              MAX_DESCRIPTION_CHARS, "Description") or None,
        "location": _clean(spec.get("location"), MAX_LOCATION_CHARS, "Location") or None,
    }

    if timed:
        body["start"] = {"dateTime": start.isoformat()}
        body["end"] = {"dateTime": end.isoformat()}
        timezone_name = _clean(spec.get("timeZone"), 60, "Time zone")
        if timezone_name:
            if not _TZ_RE.match(timezone_name):
                raise CalendarWriteError(f"Invalid time zone '{timezone_name}'.")
            body["start"]["timeZone"] = timezone_name
            body["end"]["timeZone"] = timezone_name
    else:
        # All-day event; Calendar treats `end.date` as exclusive.
        body["start"] = {"date": start.strftime("%Y-%m-%d")}
        body["end"] = {"date": (start + timedelta(days=1)).strftime("%Y-%m-%d")}

    # Never carry attendees through: creating an event must not email anyone.
    return {k: v for k, v in body.items() if v is not None}


# ══════════════════════════════════════════════════════════════════════════════
# Create
# ══════════════════════════════════════════════════════════════════════════════

def create_event(
    spec: Dict[str, Any],
    *,
    calendar_id: str = DEFAULT_CALENDAR_ID,
    service: Optional[Any] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Create ONE Google Calendar event. Reached only via the approval queue."""
    body = build_event_body(spec, now=now)
    client = service or build_write_service()

    try:
        created = (
            client.events()
            .insert(
                calendarId=calendar_id,
                body=body,
                sendUpdates="none",     # never notify anyone
            )
            .execute()
        )
    except CalendarWriteError:
        raise
    except Exception as exc:
        raise CalendarWriteError(f"Calendar event creation failed: {str(exc)[:200]}") from exc

    if not isinstance(created, dict) or not created.get("id"):
        raise CalendarWriteError("Calendar did not return a created event.")

    start = created.get("start") or {}
    end = created.get("end") or {}
    logger.info(
        "Calendar event created: id=%s (approval-gated, no attendees notified)",
        created.get("id"),
    )
    return {
        "eventId": str(created.get("id")),
        "htmlLink": str(created.get("htmlLink") or "") or None,
        "summary": str(created.get("summary") or body.get("summary") or ""),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "calendarId": calendar_id,
    }
