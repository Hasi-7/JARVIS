"""
Canvas / Quercus intake (MVP v10) — READ-ONLY.

Quercus is the University of Toronto's Canvas LMS, so this is a Canvas REST
client. It surfaces courses, assignments, and announcements as coursework
context that can be promoted into the existing Email Intake / Research drafts.

    list_courses(limit)                    -> active courses
    list_assignments(course_id, limit)     -> assignments with due dates
    list_announcements(course_id, limit)   -> recent announcements
    build_intake_payload(item)             -> Email Intake draft fields

Safety model (this module never relaxes it):
- READ-ONLY. Only HTTP GET is ever issued. There is no submit, upload, enroll,
  grade, or comment path, and a source-guard test asserts those verbs are absent.
  Assignment SUBMISSION is explicitly out of scope — the PRD's non-goals rule out
  job/coursework submission automation.
- THE TOKEN IS NEVER EXPOSED. Read from the environment, sent only as an
  Authorization header to the configured host, never logged, echoed, returned, or
  included in an error message.
- HOST IS PINNED to the configured Canvas host. Callers supply ids, never URLs, so
  a request cannot be redirected to an attacker-chosen host. Redirects disabled.
- Course ids are validated as integers, so a crafted value cannot escape the path.
- Assignment descriptions and announcement bodies are UNTRUSTED external content:
  HTML-stripped, size-capped, stored/displayed only, never executed or followed.
- No vault write, no shell, no `brain`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

TOKEN_ENV = "BRAIN_UI_QUERCUS_TOKEN"
HOST_ENV = "BRAIN_UI_QUERCUS_HOST"
DEFAULT_HOST = "q.utoronto.ca"

DEFAULT_LIMIT = 25
MAX_LIMIT = 100
REQUEST_TIMEOUT_S = 20.0
MAX_TEXT_CHARS = 20_000
MAX_NAME_CHARS = 300

_HOST_RE = re.compile(r"^[A-Za-z0-9.-]{3,253}$")
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class QuercusError(RuntimeError):
    """Raised when a Canvas read cannot be performed safely."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A pinned-host API client must not follow redirects off that host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

def _env(source: Optional[dict]) -> dict:
    return os.environ if source is None else source


def _token(env: Optional[dict] = None) -> str:
    return str(_env(env).get(TOKEN_ENV, "") or "").strip()


def quercus_host(env: Optional[dict] = None) -> str:
    host = str(_env(env).get(HOST_ENV, "") or "").strip() or DEFAULT_HOST
    if not _HOST_RE.match(host):
        raise QuercusError(f"Invalid Canvas host '{host}'.")
    return host


def quercus_configured(env: Optional[dict] = None) -> bool:
    """True when a token is present. Never returns or logs the token itself."""
    return bool(_token(env))


def quercus_status(env: Optional[dict] = None) -> dict:
    configured = quercus_configured(env)
    try:
        host = quercus_host(env)
    except QuercusError:
        host = DEFAULT_HOST
    return {
        "configured": configured,
        "host": host,
        "readOnly": True,
        "message": (
            f"Canvas/Quercus read-only access is configured for {host}. Only GET "
            f"requests are issued; there is no submit, upload, or grade path."
            if configured else
            f"Canvas/Quercus is not configured. Create a token at https://{host}"
            f"/profile/settings and set {TOKEN_ENV}."
        ),
    }


def _course_id(value: Any) -> str:
    """Canvas course ids are integers; anything else cannot enter the path."""
    text = str(value if value is not None else "").strip()
    if not text.isdigit() or len(text) > 12:
        raise QuercusError(f"Invalid course id '{text}'. Expected a number.")
    return text


def _clamp(limit: Optional[int]) -> int:
    try:
        value = int(limit) if limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, value))


def strip_html(value: Any, limit: Optional[int] = None) -> str:
    """Canvas returns HTML bodies. Reduce to text; never render or execute.

    The cap is resolved at call time rather than bound as a default, so it stays
    configurable (a default argument would freeze the value at import).
    """
    limit = MAX_TEXT_CHARS if limit is None else limit
    without_scripts = _TAG_RE.sub(" ", str(value or ""))
    text = _ANY_TAG_RE.sub(" ", without_scripts)
    for entity, char in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                         ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(entity, char)
    text = _WS_RE.sub(" ", text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _truncate(value: Any, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


# ══════════════════════════════════════════════════════════════════════════════
# Transport (GET only, pinned host)
# ══════════════════════════════════════════════════════════════════════════════

def _get(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    env: Optional[dict] = None,
    opener: Optional[Callable[..., Any]] = None,
) -> Any:
    token = _token(env)
    if not token:
        raise QuercusError(
            f"Canvas/Quercus is not configured. Set {TOKEN_ENV} to a read-only token."
        )
    if not path.startswith("/"):
        raise QuercusError("Internal error: Canvas path must be relative.")

    host = quercus_host(env)
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"https://{host}/api/v1{path}{query}"

    # Defence in depth: re-verify the host actually being called.
    if urllib.parse.urlparse(url).hostname != host:
        raise QuercusError("Refusing to call a non-Canvas host.")

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "brain-ui-readonly",
        },
    )
    client = opener or urllib.request.build_opener(_NoRedirect).open
    try:
        with client(request, timeout=REQUEST_TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        # Never let the token reach an error string.
        raise QuercusError(f"Canvas request failed with HTTP {exc.code}.") from None
    except QuercusError:
        raise
    except Exception as exc:
        raise QuercusError(f"Canvas request failed: {type(exc).__name__}.") from None


# ══════════════════════════════════════════════════════════════════════════════
# Read operations
# ══════════════════════════════════════════════════════════════════════════════

def list_courses(limit: Optional[int] = None, *, env: Optional[dict] = None,
                 opener: Optional[Callable[..., Any]] = None) -> List[dict]:
    """Active courses the token can see."""
    data = _get("/courses",
                {"per_page": _clamp(limit), "enrollment_state": "active"},
                env=env, opener=opener)
    courses: List[dict] = []
    for item in (data if isinstance(data, list) else [])[:_clamp(limit)]:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        courses.append({
            "courseId": str(item.get("id")),
            "name": _truncate(item.get("name"), MAX_NAME_CHARS),
            "courseCode": _truncate(item.get("course_code"), 60),
            "term": _truncate((item.get("term") or {}).get("name")
                              if isinstance(item.get("term"), dict) else None, 60) or None,
        })
    return courses


def list_assignments(course_id: Any, limit: Optional[int] = None, *,
                     env: Optional[dict] = None,
                     opener: Optional[Callable[..., Any]] = None) -> List[dict]:
    """Assignments for one course. Descriptions are untrusted content."""
    cid = _course_id(course_id)
    data = _get(f"/courses/{cid}/assignments",
                {"per_page": _clamp(limit), "order_by": "due_at"},
                env=env, opener=opener)
    out: List[dict] = []
    for item in (data if isinstance(data, list) else [])[:_clamp(limit)]:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        out.append({
            "assignmentId": str(item.get("id")),
            "courseId": cid,
            "name": _truncate(item.get("name"), MAX_NAME_CHARS),
            "dueAt": _truncate(item.get("due_at"), 40) or None,
            "pointsPossible": item.get("points_possible"),
            "htmlUrl": _truncate(item.get("html_url"), 400) or None,
            "description": strip_html(item.get("description")),
        })
    return out


def list_announcements(course_id: Any, limit: Optional[int] = None, *,
                       env: Optional[dict] = None,
                       opener: Optional[Callable[..., Any]] = None) -> List[dict]:
    """Recent announcements for one course. Bodies are untrusted content."""
    cid = _course_id(course_id)
    data = _get("/announcements",
                {"context_codes[]": f"course_{cid}", "per_page": _clamp(limit)},
                env=env, opener=opener)
    out: List[dict] = []
    for item in (data if isinstance(data, list) else [])[:_clamp(limit)]:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        out.append({
            "announcementId": str(item.get("id")),
            "courseId": cid,
            "title": _truncate(item.get("title"), MAX_NAME_CHARS),
            "postedAt": _truncate(item.get("posted_at"), 40) or None,
            "htmlUrl": _truncate(item.get("html_url"), 400) or None,
            "message": strip_html(item.get("message")),
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# Email Intake bridge
# ══════════════════════════════════════════════════════════════════════════════

def build_intake_payload(item: dict, *, course_name: Optional[str] = None) -> dict:
    """Shape an assignment or announcement into Email Intake draft fields.

    Creates no draft and writes no vault file — the user reviews and saves through
    the existing Email Intake flow, which keeps every write guarantee.
    """
    if not isinstance(item, dict):
        raise QuercusError("A fetched Canvas item is required.")

    is_assignment = "assignmentId" in item
    subject = item.get("name") if is_assignment else item.get("title")
    body = item.get("description") if is_assignment else item.get("message")

    header = "\n".join([
        f"Course: {course_name or item.get('courseId') or '—'}",
        f"Type: {'Assignment' if is_assignment else 'Announcement'}",
        f"Due: {item.get('dueAt') or '—'}" if is_assignment
        else f"Posted: {item.get('postedAt') or '—'}",
        f"Link: {item.get('htmlUrl') or '—'}",
    ])

    return {
        "subject": _truncate(subject or "Untitled Canvas item", MAX_NAME_CHARS),
        "sender": f"Quercus ({course_name or 'course'})",
        "received_at": item.get("dueAt") if is_assignment else item.get("postedAt"),
        # Canvas items are coursework, which maps to the existing course domain.
        "domain": "course",
        "entity": course_name,
        "raw_email": f"{header}\n\n{body or '(no content)'}",
        "proposed_task_rows": (
            [f"{subject} by {item.get('dueAt')[:10]}"]
            if is_assignment and item.get("dueAt") else []
        ),
    }
