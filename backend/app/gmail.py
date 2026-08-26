"""
Gmail read intake (B1) — READ-ONLY.

Provides exactly two Gmail capabilities, both read-only:

    search_threads(query, max_results)  → thread metadata (subject/from/date/snippet)
    get_message(message_id)             → one message, headers + decoded body

Results feed `email_intake.py` drafts through `build_intake_draft()`, which reuses
the existing manual-intake draft path (backend JSON only, NO vault write).

Safety model (this module never relaxes it):
- The ONLY OAuth scopes used are the read-only ones declared in `google_auth.py`
  (`gmail.readonly`, `calendar.readonly`). This module re-asserts the Gmail scope
  before every call and refuses to run if a non-readonly scope is present.
- Gmail MUTATIONS ARE PERMANENTLY DISABLED AND UNREACHABLE. This module never
  references send / trash / delete / modify / batchModify / labels / drafts /
  insert / import. A source-guard test asserts those names do not appear here.
- Every message body and header is UNTRUSTED external content (PRD §44): it is
  decoded, size-capped, and returned for storage/display only. It is never
  executed, never interpreted as instructions, and never auto-routed to a tool.
- Callers must classify through `permission_gateway.evaluate_tool_request()` and
  log before invoking these functions. This module performs no authorization of
  its own beyond the scope assertion.
- Network calls happen ONLY through an injected/service-built Google client. Tests
  inject a fake service and never touch the network.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from app.google_auth import (
    CALENDAR_WRITE_SCOPE,
    DRIVE_READONLY_SCOPE,
    GOOGLE_READONLY_SCOPES,
    GoogleAuthSetupError,
    authorize_google,
    oauth_status,
)

logger = logging.getLogger(__name__)

# Gmail tool ids as they appear in the permission gateway policy table.
GMAIL_SEARCH_TOOL = "gmail.search"
GMAIL_READ_TOOL = "gmail.read"

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

# Bounds. Search fans out to one metadata fetch per thread, so keep it small.
DEFAULT_MAX_RESULTS = 10
MAX_MAX_RESULTS = 50
MAX_QUERY_LEN = 500

# Untrusted body/preview caps.
MAX_BODY_CHARS = 100_000
MAX_SNIPPET_CHARS = 400
MAX_HEADER_VALUE_CHARS = 500

_METADATA_HEADERS = ("Subject", "From", "To", "Date")


class GmailError(RuntimeError):
    """Raised when a Gmail read cannot be performed safely."""


# ══════════════════════════════════════════════════════════════════════════════
# Readiness
# ══════════════════════════════════════════════════════════════════════════════

def gmail_configured() -> bool:
    """True when an OAuth client and token file are both present on disk.

    This is a *configuration* check only — it reads no token contents and proves
    nothing about whether the token still refreshes. It exists so the permission
    gateway can report `not_wired` honestly before B0 setup is done.
    """
    try:
        status = oauth_status()
    except Exception:  # defensive: readiness must never raise
        return False
    return bool(status.get("clientConfigured")) and bool(status.get("tokenPresent"))


def _assert_readonly_scopes(scopes: Optional[List[str]]) -> None:
    """Refuse to proceed unless the credential carries read-only scopes only."""
    granted = list(scopes or [])
    if not granted:
        raise GmailError("Google credentials report no scopes. Re-run the authorize command.")

    # calendar.events is the ONE write scope this app may hold (D2). It does not
    # grant any Gmail capability, so it must not block Gmail reads — but anything
    # else, especially a Gmail mutation scope, still refuses the call.
    allowed = set(GOOGLE_READONLY_SCOPES) | {CALENDAR_WRITE_SCOPE, DRIVE_READONLY_SCOPE}
    extra = [s for s in granted if s not in allowed]
    if extra:
        raise GmailError(
            "Google credentials carry unexpected scopes; Gmail reads are blocked. "
            f"Unexpected scopes: {', '.join(sorted(extra))}."
        )
    gmail_writes = [s for s in granted if "gmail" in s and not s.endswith("gmail.readonly")]
    if gmail_writes:
        raise GmailError(
            "Google credentials carry a Gmail write scope, which this app never uses. "
            "Re-authorize with read-only Gmail access."
        )
    if GMAIL_READONLY_SCOPE not in granted:
        raise GmailError(
            "Google credentials do not include the Gmail read-only scope. "
            "Re-run the authorize command."
        )


def build_gmail_service(
    *,
    credentials_factory: Optional[Callable[[], Any]] = None,
    service_builder: Optional[Callable[..., Any]] = None,
) -> Any:
    """Build a read-only Gmail client. Both dependencies are injectable for tests."""
    factory = credentials_factory or authorize_google
    try:
        credentials = factory()
    except GoogleAuthSetupError as exc:
        raise GmailError(str(exc)) from exc

    _assert_readonly_scopes(getattr(credentials, "scopes", None))

    if service_builder is None:
        try:
            from googleapiclient.discovery import build as service_builder  # type: ignore
        except ImportError as exc:
            raise GmailError(
                "Google API client is missing. Run: pip install -r requirements.txt"
            ) from exc

    return service_builder("gmail", "v1", credentials=credentials, cache_discovery=False)


# ══════════════════════════════════════════════════════════════════════════════
# Untrusted-content helpers
# ══════════════════════════════════════════════════════════════════════════════

def _clamp_max_results(value: Optional[int]) -> int:
    try:
        n = int(value) if value is not None else DEFAULT_MAX_RESULTS
    except (TypeError, ValueError):
        return DEFAULT_MAX_RESULTS
    return max(1, min(MAX_MAX_RESULTS, n))


def _clean_query(query: Optional[str]) -> str:
    """Gmail search operators are passed through as a plain query string.

    The query is user-supplied, never interpolated into code, and only ever
    handed to the Gmail client as the `q` parameter.
    """
    q = (query or "").strip()
    if not q:
        raise GmailError("A non-empty Gmail search query is required.")
    if len(q) > MAX_QUERY_LEN:
        raise GmailError(f"Gmail search query is too long (max {MAX_QUERY_LEN} characters).")
    if "\n" in q or "\r" in q:
        raise GmailError("Gmail search query must be a single line.")
    return q


def _truncate(value: str, limit: int) -> str:
    text = value or ""
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _headers_map(payload: Optional[dict]) -> Dict[str, str]:
    """Collect headers into a dict, size-capped. Header values are untrusted."""
    out: Dict[str, str] = {}
    for header in (payload or {}).get("headers") or []:
        if not isinstance(header, dict):
            continue
        name = str(header.get("name") or "").strip()
        if not name:
            continue
        value = _truncate(str(header.get("value") or ""), MAX_HEADER_VALUE_CHARS)
        out.setdefault(name.lower(), value)
    return out


def _decode_b64url(data: str) -> str:
    """Decode Gmail's base64url body data; never raises on malformed input."""
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii", errors="ignore"))
    except (binascii.Error, ValueError):
        return ""
    return raw.decode("utf-8", errors="replace")


def _walk_parts(payload: Optional[dict]) -> List[dict]:
    """Flatten a MIME part tree breadth-first, with a hard node budget."""
    out: List[dict] = []
    queue: List[dict] = [payload] if isinstance(payload, dict) else []
    budget = 200
    while queue and budget > 0:
        node = queue.pop(0)
        budget -= 1
        if not isinstance(node, dict):
            continue
        out.append(node)
        children = node.get("parts")
        if isinstance(children, list):
            queue.extend([c for c in children if isinstance(c, dict)])
    return out


def extract_body_text(payload: Optional[dict]) -> str:
    """Best-effort plain-text body. Prefers text/plain, falls back to text/html.

    The result is UNTRUSTED content. It is returned verbatim (size-capped) and is
    never parsed for instructions.
    """
    parts = _walk_parts(payload)

    for wanted in ("text/plain", "text/html"):
        chunks: List[str] = []
        for node in parts:
            mime = str(node.get("mimeType") or "").lower()
            if not mime.startswith(wanted):
                continue
            data = ((node.get("body") or {}).get("data")) or ""
            decoded = _decode_b64url(data)
            if decoded.strip():
                chunks.append(decoded)
        if chunks:
            return _truncate("\n\n".join(chunks), MAX_BODY_CHARS)

    # Single-part message with no explicit mimeType match.
    data = ((payload or {}).get("body") or {}).get("data") or ""
    return _truncate(_decode_b64url(data), MAX_BODY_CHARS)


def _strip_html(text: str) -> str:
    """Crude tag strip used only to build a readable preview, never for storage."""
    without_tags = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", without_tags).strip()


# ══════════════════════════════════════════════════════════════════════════════
# Read operations
# ══════════════════════════════════════════════════════════════════════════════

def search_threads(
    query: str,
    max_results: Optional[int] = None,
    *,
    service: Optional[Any] = None,
) -> List[dict]:
    """Search Gmail threads and return metadata only. READ-ONLY.

    Returns a list of {threadId, messageId, subject, sender, to, date, snippet},
    all of which are untrusted values echoed from Gmail.
    """
    q = _clean_query(query)
    limit = _clamp_max_results(max_results)
    client = service or build_gmail_service()

    try:
        listing = (
            client.users()
            .threads()
            .list(userId="me", q=q, maxResults=limit)
            .execute()
        )
    except GmailError:
        raise
    except Exception as exc:
        raise GmailError(f"Gmail search failed: {exc}") from exc

    threads = (listing or {}).get("threads") or []
    results: List[dict] = []

    for entry in threads[:limit]:
        if not isinstance(entry, dict):
            continue
        thread_id = str(entry.get("id") or "").strip()
        if not thread_id:
            continue

        try:
            detail = (
                client.users()
                .threads()
                .get(
                    userId="me",
                    id=thread_id,
                    format="metadata",
                    metadataHeaders=list(_METADATA_HEADERS),
                )
                .execute()
            )
        except Exception as exc:  # one bad thread must not fail the whole search
            logger.warning("Gmail thread metadata fetch failed for %s: %s", thread_id, exc)
            results.append({
                "threadId": thread_id,
                "messageId": None,
                "subject": "(metadata unavailable)",
                "sender": None,
                "to": None,
                "date": None,
                "snippet": _truncate(str(entry.get("snippet") or ""), MAX_SNIPPET_CHARS),
            })
            continue

        messages = (detail or {}).get("messages") or []
        first = messages[0] if messages and isinstance(messages[0], dict) else {}
        headers = _headers_map(first.get("payload"))

        results.append({
            "threadId": thread_id,
            "messageId": str(first.get("id") or "") or None,
            "subject": headers.get("subject") or "(no subject)",
            "sender": headers.get("from"),
            "to": headers.get("to"),
            "date": headers.get("date"),
            "snippet": _truncate(
                str(first.get("snippet") or entry.get("snippet") or ""), MAX_SNIPPET_CHARS
            ),
        })

    logger.info(
        "Gmail search returned %d thread(s) (read-only; no mutation possible)", len(results)
    )
    return results


def get_message(message_id: str, *, service: Optional[Any] = None) -> dict:
    """Fetch ONE Gmail message, headers + decoded body. READ-ONLY.

    The returned `body` is untrusted external content.
    """
    mid = (message_id or "").strip()
    if not mid:
        raise GmailError("A Gmail message id is required.")

    client = service or build_gmail_service()

    try:
        message = (
            client.users()
            .messages()
            .get(userId="me", id=mid, format="full")
            .execute()
        )
    except GmailError:
        raise
    except Exception as exc:
        raise GmailError(f"Gmail message fetch failed: {exc}") from exc

    if not isinstance(message, dict) or not message.get("id"):
        raise GmailError(f"Gmail message '{mid}' was not found.")

    payload = message.get("payload") or {}
    headers = _headers_map(payload)
    body = extract_body_text(payload)

    return {
        "messageId": str(message.get("id")),
        "threadId": str(message.get("threadId") or "") or None,
        "subject": headers.get("subject") or "(no subject)",
        "sender": headers.get("from"),
        "to": headers.get("to"),
        "date": headers.get("date"),
        "snippet": _truncate(str(message.get("snippet") or ""), MAX_SNIPPET_CHARS),
        "body": body,
        "bodyTruncated": body.endswith("…"),
        "labelIds": [str(l) for l in (message.get("labelIds") or []) if isinstance(l, str)][:50],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Email Intake bridge
# ══════════════════════════════════════════════════════════════════════════════

def build_intake_draft(
    message: dict,
    *,
    domain: str = "unknown",
    entity: Optional[str] = None,
    create_draft_fn: Optional[Callable[..., Any]] = None,
) -> Any:
    """Create an Email Intake draft from a fetched Gmail message.

    Reuses `email_intake.create_draft` unchanged, so every existing guarantee
    holds: backend JSON only, NO vault write here, body stored untrusted and
    fenced at render time. The summary is left empty so email_intake's existing
    deterministic no-AI fallback produces it.
    """
    if not isinstance(message, dict):
        raise GmailError("A fetched Gmail message is required.")

    creator = create_draft_fn
    if creator is None:
        from app.email_intake import create_draft as creator  # local import avoids a cycle

    raw = message.get("body") or ""
    if not raw.strip():
        # Never create an empty draft: fall back to the snippet so the user still
        # gets something reviewable, clearly marked as a preview.
        raw = _strip_html(str(message.get("snippet") or "")) or "(no readable body)"

    header_block = "\n".join([
        f"From: {message.get('sender') or '—'}",
        f"To: {message.get('to') or '—'}",
        f"Date: {message.get('date') or '—'}",
        f"Subject: {message.get('subject') or '(no subject)'}",
    ])

    return creator(
        subject=str(message.get("subject") or "(no subject)"),
        sender=message.get("sender"),
        received_at=message.get("date"),
        domain=domain,
        entity=entity,
        summary=None,          # deterministic fallback in email_intake, no AI
        action_required=None,
        due_date=None,
        confidence=None,
        raw_email=f"{header_block}\n\n{raw}",
        proposed_task_rows=None,
        proposed_calendar_rows=None,
    )
