"""
Time-boxed browser research (C1) — GUARDRAILED, DENY-BY-DEFAULT.

A research session fetches a bounded number of pages within a wall-clock budget
and turns what it finds into capture records that feed `research.py` drafts.

    start_session(topic, budget_seconds, allowed_domains) -> session
    open_page(session_id, url)                            -> capture
    stop_session(session_id)                              -> session
    get_session(session_id) / list_sessions()

Safety model (this module never relaxes it):
- NO SANDBOX, NO BROWSING. The default page driver refuses to run unless the
  NVIDIA OpenShell gateway reports healthy. There is deliberately no unguarded
  fallback: a missing guardrail fails CLOSED, it does not silently fetch direct.
- DOMAIN ALLOWLIST IS MANDATORY. An empty allowlist denies everything. Hosts are
  matched exactly or as a registrable suffix; userinfo, non-http(s) schemes, and
  IP-literal/loopback/private targets are rejected (SSRF guard).
- WALL-CLOCK BUDGET. Every action re-checks the deadline; an exhausted session
  refuses further fetches and reports `budget_exhausted`. Page count is capped too.
- PAGE CONTENT IS UNTRUSTED (PRD §44). It is size-capped, stripped to text, stored,
  and surfaced for review. It is never executed, never followed as instructions,
  and never auto-routed to a tool or to an LLM by this module.
- NO DOWNLOADS, NO FORM SUBMISSION, NO CREDENTIALS. Only page reads.
- Sessions are backend-local JSON (`backend/data/research-sessions/`). Nothing here
  writes the vault — promoting a capture into a Research draft stays the user's
  explicit action through the existing `research.py` flow.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SESSIONS_DIR: Path = Path(__file__).parent.parent / "data" / "research-sessions"
SESSIONS_FILE: Path = SESSIONS_DIR / "sessions.json"

_lock = threading.Lock()

DEFAULT_BUDGET_SECONDS = 300
MIN_BUDGET_SECONDS = 10
MAX_BUDGET_SECONDS = 1800
MAX_PAGES_PER_SESSION = 40
MAX_STORED_SESSIONS = 100

MAX_PAGE_CHARS = 200_000
MAX_SNIPPET_CHARS = 1_200
MAX_TITLE_CHARS = 300
MAX_TOPIC_CHARS = 200
FETCH_TIMEOUT_S = 20.0

STATUS_ACTIVE = "active"
STATUS_STOPPED = "stopped"
STATUS_BUDGET_EXHAUSTED = "budget_exhausted"

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class BrowserError(ValueError):
    """Raised when a research action is rejected."""


class GuardrailUnavailableError(RuntimeError):
    """Raised when the sandbox guardrail is not healthy. Browsing fails CLOSED."""


# ══════════════════════════════════════════════════════════════════════════════
# URL / domain safety
# ══════════════════════════════════════════════════════════════════════════════

def normalize_domain(value: str) -> str:
    return (value or "").strip().lower().lstrip(".")


def host_allowed(host: str, allowed: List[str]) -> bool:
    """Exact host match, or a dot-boundary suffix match. Empty allowlist = deny."""
    target = normalize_domain(host)
    if not target or not allowed:
        return False
    for entry in allowed:
        candidate = normalize_domain(entry)
        if not candidate:
            continue
        if target == candidate or target.endswith("." + candidate):
            return True
    return False


def _reject_private_target(host: str) -> None:
    """Block loopback/private/link-local literals so research cannot probe the LAN."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return  # a name, not a literal — allowlist is the control
    if (address.is_loopback or address.is_private or address.is_link_local
            or address.is_reserved or address.is_multicast):
        raise BrowserError("Refusing to fetch a loopback, private, or reserved address.")


def validate_url(url: str, allowed_domains: List[str]) -> str:
    """Validate a target URL against scheme, credential, SSRF, and allowlist rules."""
    raw = (url or "").strip()
    if not raw:
        raise BrowserError("A URL is required.")
    if len(raw) > 2000:
        raise BrowserError("URL is too long.")

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise BrowserError(f"Only http(s) URLs may be fetched (got '{parsed.scheme or 'none'}').")
    if parsed.username or parsed.password:
        raise BrowserError("URLs containing credentials are rejected.")

    host = parsed.hostname or ""
    if not host:
        raise BrowserError("URL has no host.")
    _reject_private_target(host)

    if not host_allowed(host, allowed_domains):
        raise BrowserError(
            f"'{host}' is not in this session's allowed domains. "
            f"Allowed: {', '.join(allowed_domains) or '(none)'}."
        )
    return raw


# ══════════════════════════════════════════════════════════════════════════════
# Content handling (untrusted)
# ══════════════════════════════════════════════════════════════════════════════

def extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    title = _WS_RE.sub(" ", match.group(1)).strip() if match else ""
    return _truncate(title or "(no title)", MAX_TITLE_CHARS)


def decode_entities(text: str) -> str:
    """Decode the common HTML entities. Shared by page text and search titles so
    both render the same way — decoding is presentation only, never execution."""
    out = text or ""
    for entity, char in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                         ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        out = out.replace(entity, char)
    return out


def html_to_text(html: str) -> str:
    """Strip markup to readable text. Never executes anything."""
    without_scripts = _TAG_RE.sub(" ", html or "")
    text = decode_entities(_ANY_TAG_RE.sub(" ", without_scripts))
    return _truncate(_WS_RE.sub(" ", text).strip(), MAX_PAGE_CHARS)


def _truncate(value: str, limit: int) -> str:
    text = value or ""
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


# ══════════════════════════════════════════════════════════════════════════════
# Page driver — sandboxed, fails CLOSED
# ══════════════════════════════════════════════════════════════════════════════

def guardrail_healthy(env: Optional[dict] = None) -> bool:
    """True only when the OpenShell gateway reports healthy. Never raises."""
    try:
        from app.openshell_client import health
        return bool(health(env).get("healthy"))
    except Exception:
        return False


def sandboxed_fetch(url: str, timeout_s: float = FETCH_TIMEOUT_S,
                    env: Optional[dict] = None) -> dict:
    """Default page driver.

    Refuses when the guardrail is unavailable. There is NO direct fetch fallback:
    unguarded browsing is worse than no browsing, so this fails closed. The real
    fetch runs INSIDE the OpenShell sandbox (C1b), and refuses again if the sandbox
    policy would not actually enforce isolation.
    """
    if not guardrail_healthy(env):
        raise GuardrailUnavailableError(
            "The OpenShell sandbox guardrail is not healthy, so browsing is disabled. "
            "Research never fetches pages outside the sandbox."
        )

    # Executed INSIDE the sandbox. This refuses on its own if the sandbox policy
    # would not actually enforce isolation (best_effort Landlock).
    from app.openshell_exec import FailOpenPolicyError, SandboxExecError, fetch_page_in_sandbox

    try:
        return fetch_page_in_sandbox(url, timeout_s, env)
    except FailOpenPolicyError as exc:
        raise GuardrailUnavailableError(str(exc)) from exc
    except SandboxExecError as exc:
        raise GuardrailUnavailableError(
            f"Sandboxed fetch is unavailable: {exc}"
        ) from exc


# ══════════════════════════════════════════════════════════════════════════════
# Storage
# ══════════════════════════════════════════════════════════════════════════════

def _read_sessions() -> List[dict]:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not SESSIONS_FILE.exists():
        return []
    try:
        return list(json.loads(SESSIONS_FILE.read_text(encoding="utf-8")))
    except Exception as exc:
        raise RuntimeError(f"Corrupted research-sessions file: {exc}") from exc


def _write_sessions(sessions: List[dict]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    trimmed = sessions[-MAX_STORED_SESSIONS:]
    SESSIONS_FILE.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# Budget
# ══════════════════════════════════════════════════════════════════════════════

def _clamp_budget(seconds: Optional[int]) -> int:
    try:
        value = int(seconds) if seconds is not None else DEFAULT_BUDGET_SECONDS
    except (TypeError, ValueError):
        return DEFAULT_BUDGET_SECONDS
    return max(MIN_BUDGET_SECONDS, min(MAX_BUDGET_SECONDS, value))


def remaining_seconds(session: dict, now_fn: Callable[[], float] = time.time) -> float:
    elapsed = now_fn() - float(session.get("startedAtEpoch", 0.0))
    return max(0.0, float(session.get("budgetSeconds", 0)) - elapsed)


def _refresh_status(session: dict, now_fn: Callable[[], float]) -> dict:
    """Flip an active session to budget_exhausted once its deadline passes."""
    if session.get("status") == STATUS_ACTIVE and remaining_seconds(session, now_fn) <= 0:
        session["status"] = STATUS_BUDGET_EXHAUSTED
        session["endedAt"] = _now()
    return session


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def start_session(
    topic: str,
    allowed_domains: List[str],
    budget_seconds: Optional[int] = None,
    *,
    now_fn: Callable[[], float] = time.time,
) -> dict:
    """Begin a time-boxed research session. Fetches nothing by itself."""
    clean_topic = (topic or "").strip()
    if not clean_topic:
        raise BrowserError("A research topic is required.")
    if len(clean_topic) > MAX_TOPIC_CHARS:
        raise BrowserError(f"Topic is too long (max {MAX_TOPIC_CHARS} characters).")

    domains = [normalize_domain(d) for d in (allowed_domains or []) if normalize_domain(d)]
    if not domains:
        raise BrowserError(
            "At least one allowed domain is required. An empty allowlist denies everything."
        )
    if len(domains) > 25:
        raise BrowserError("Too many allowed domains (max 25).")

    session = {
        "id": str(uuid.uuid4()),
        "topic": clean_topic,
        "allowedDomains": domains,
        "budgetSeconds": _clamp_budget(budget_seconds),
        "status": STATUS_ACTIVE,
        "startedAt": _now(),
        "startedAtEpoch": now_fn(),
        "endedAt": None,
        "captures": [],
        "errors": [],
    }

    with _lock:
        sessions = _read_sessions()
        sessions.append(session)
        _write_sessions(sessions)

    logger.info(
        "Research session started: id=%s budget=%ss domains=%d (no page fetched yet)",
        session["id"], session["budgetSeconds"], len(domains),
    )
    return dict(session)


def get_session(session_id: str, *, now_fn: Callable[[], float] = time.time) -> Optional[dict]:
    with _lock:
        sessions = _read_sessions()
        for session in sessions:
            if session.get("id") == session_id:
                before = session.get("status")
                _refresh_status(session, now_fn)
                if session.get("status") != before:
                    _write_sessions(sessions)
                return dict(session)
    return None


def list_sessions(*, now_fn: Callable[[], float] = time.time) -> List[dict]:
    with _lock:
        sessions = _read_sessions()
        changed = False
        for session in sessions:
            before = session.get("status")
            _refresh_status(session, now_fn)
            changed = changed or session.get("status") != before
        if changed:
            _write_sessions(sessions)
        return [dict(s) for s in reversed(sessions)]


def stop_session(session_id: str) -> dict:
    """Stop a session immediately. Idempotent."""
    with _lock:
        sessions = _read_sessions()
        for session in sessions:
            if session.get("id") != session_id:
                continue
            if session.get("status") == STATUS_ACTIVE:
                session["status"] = STATUS_STOPPED
                session["endedAt"] = _now()
                _write_sessions(sessions)
            return dict(session)
    raise BrowserError(f"Research session '{session_id}' not found.")


def open_page(
    session_id: str,
    url: str,
    *,
    fetch: Optional[Callable[..., dict]] = None,
    now_fn: Callable[[], float] = time.time,
    env: Optional[dict] = None,
) -> dict:
    """Fetch one page inside the session's budget and allowlist. Returns a capture.

    `fetch` is injectable so tests can serve a local fixture; the default driver
    requires a healthy sandbox guardrail and never fetches directly.
    """
    with _lock:
        sessions = _read_sessions()
        session = next((s for s in sessions if s.get("id") == session_id), None)
        if session is None:
            raise BrowserError(f"Research session '{session_id}' not found.")

        _refresh_status(session, now_fn)
        status = session.get("status")
        if status == STATUS_STOPPED:
            raise BrowserError("This research session was stopped.")
        if status == STATUS_BUDGET_EXHAUSTED:
            raise BrowserError("This research session's time budget is exhausted.")
        if len(session.get("captures") or []) >= MAX_PAGES_PER_SESSION:
            session["status"] = STATUS_BUDGET_EXHAUSTED
            session["endedAt"] = _now()
            _write_sessions(sessions)
            raise BrowserError(f"Page limit reached ({MAX_PAGES_PER_SESSION}).")

        target = validate_url(url, session.get("allowedDomains") or [])
        remaining = remaining_seconds(session, now_fn)
        allowed_domains = list(session.get("allowedDomains") or [])

    # Fetch OUTSIDE the lock so a slow page never blocks status/stop.
    driver = fetch or sandboxed_fetch
    timeout = max(1.0, min(FETCH_TIMEOUT_S, remaining))
    try:
        result = driver(target, timeout, env) if fetch is None else driver(target, timeout)
    except GuardrailUnavailableError:
        raise
    except Exception as exc:
        with _lock:
            sessions = _read_sessions()
            session = next((s for s in sessions if s.get("id") == session_id), None)
            if session is not None:
                session.setdefault("errors", []).append({
                    "url": target, "at": _now(), "error": _truncate(str(exc), 300),
                })
                _write_sessions(sessions)
        raise BrowserError(f"Page fetch failed: {_truncate(str(exc), 200)}") from exc

    html = str((result or {}).get("html") or "")
    text = html_to_text(html) if html else _truncate(str((result or {}).get("text") or ""), MAX_PAGE_CHARS)
    capture = {
        "url": target,
        "title": str((result or {}).get("title") or "") or extract_title(html),
        "timestamp": _now(),
        "snippet": _truncate(text, MAX_SNIPPET_CHARS),
        "textChars": len(text),
        "httpStatus": int((result or {}).get("status") or 0) or None,
    }

    with _lock:
        sessions = _read_sessions()
        session = next((s for s in sessions if s.get("id") == session_id), None)
        if session is None:
            raise BrowserError(f"Research session '{session_id}' not found.")
        session.setdefault("captures", []).append(capture)
        _refresh_status(session, now_fn)
        _write_sessions(sessions)

    logger.info(
        "Research capture stored: session=%s host=%s chars=%d (content untrusted)",
        session_id, urlparse(target).hostname, len(text),
    )
    return dict(capture)


def session_summary(session: dict, *, now_fn: Callable[[], float] = time.time) -> dict:
    """Compact status for the UI."""
    return {
        "id": session.get("id"),
        "topic": session.get("topic"),
        "status": session.get("status"),
        "budgetSeconds": session.get("budgetSeconds"),
        "remainingSeconds": round(remaining_seconds(session, now_fn), 1),
        "captureCount": len(session.get("captures") or []),
        "errorCount": len(session.get("errors") or []),
        "allowedDomains": list(session.get("allowedDomains") or []),
        "startedAt": session.get("startedAt"),
        "endedAt": session.get("endedAt"),
    }


def captures_for_research_draft(session: dict) -> dict:
    """Shape a session's captures for the existing `research.py` draft flow.

    Returns plain fields only — this does NOT create a draft and writes no vault
    file. The user promotes it explicitly.
    """
    captures = list(session.get("captures") or [])
    return {
        "title": f"Research: {session.get('topic') or 'untitled'}",
        "topic": session.get("topic") or "",
        "sources": [
            {"title": c.get("title") or c.get("url"), "url": c.get("url"),
             "notes": c.get("snippet") or ""}
            for c in captures
        ],
        "rawNotes": "\n\n".join(
            f"# {c.get('title')}\n{c.get('url')}\n{c.get('snippet')}" for c in captures
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Search (C1 / PRD §13.2 "open/search/navigate")
# ══════════════════════════════════════════════════════════════════════════════
# Searching and opening are deliberately separated:
#   * the query goes to ONE fixed, privacy-respecting provider — the provider host
#     is a constant here, never caller-supplied, so a search cannot be redirected
#     to an arbitrary host;
#   * every RESULT is then subjected to the session's domain allowlist through the
#     same validate_url() that guards open_page(). Appearing in search results
#     grants a URL nothing.
# Results are untrusted content: titles are echoed for display only.

SEARCH_PROVIDER_URL = "https://html.duckduckgo.com/html/"
SEARCH_PROVIDER_HOST = "html.duckduckgo.com"

MAX_SEARCH_RESULTS = 25
MAX_QUERY_CHARS = 300

_RESULT_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_ANY_LINK_RE = re.compile(r'<a[^>]+href="(http[^"]+)"[^>]*>(.*?)</a>', re.I | re.S)


def _clean_query(query: str) -> str:
    text = " ".join(str(query or "").split())
    if not text:
        raise BrowserError("A search query is required.")
    if len(text) > MAX_QUERY_CHARS:
        raise BrowserError(f"Search query is too long (max {MAX_QUERY_CHARS} characters).")
    return text


def _unwrap_redirect(href: str) -> str:
    """DuckDuckGo wraps results as /l/?uddg=<encoded>. Recover the real target."""
    from urllib.parse import parse_qs, unquote, urlparse as _parse

    raw = (href or "").strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    try:
        parsed = _parse(raw)
        if "uddg" in (parsed.query or ""):
            values = parse_qs(parsed.query).get("uddg") or []
            if values:
                return unquote(values[0])
    except Exception:
        pass
    return raw


def parse_search_results(html: str, limit: int = MAX_SEARCH_RESULTS) -> List[dict]:
    """Extract {url, title} pairs from a provider results page. Never executes it."""
    matches = _RESULT_LINK_RE.findall(html or "")
    if not matches:
        matches = _ANY_LINK_RE.findall(html or "")

    results: List[dict] = []
    seen: set = set()
    for href, label in matches:
        url = _unwrap_redirect(href)
        if not url.lower().startswith(("http://", "https://")):
            continue
        host = urlparse(url).hostname or ""
        if host == SEARCH_PROVIDER_HOST or host.endswith("duckduckgo.com"):
            continue        # provider's own navigation links are not results
        if url in seen:
            continue
        seen.add(url)
        results.append({
            "url": url,
            "title": _truncate(
                _WS_RE.sub(" ", decode_entities(_ANY_TAG_RE.sub("", label))).strip(),
                MAX_TITLE_CHARS,
            ) or "(no title)",
        })
        if len(results) >= limit:
            break
    return results


def search(
    session_id: str,
    query: str,
    limit: Optional[int] = None,
    *,
    fetch: Optional[Callable[..., dict]] = None,
    now_fn: Callable[[], float] = time.time,
    env: Optional[dict] = None,
) -> dict:
    """Search within a session. Returns results tagged with whether each is openable."""
    text = _clean_query(query)
    try:
        wanted = int(limit) if limit is not None else 10
    except (TypeError, ValueError):
        wanted = 10
    wanted = max(1, min(MAX_SEARCH_RESULTS, wanted))

    with _lock:
        sessions = _read_sessions()
        session = next((s for s in sessions if s.get("id") == session_id), None)
        if session is None:
            raise BrowserError(f"Research session '{session_id}' not found.")
        _refresh_status(session, now_fn)
        status = session.get("status")
        if status == STATUS_STOPPED:
            raise BrowserError("This research session was stopped.")
        if status == STATUS_BUDGET_EXHAUSTED:
            raise BrowserError("This research session's time budget is exhausted.")
        remaining = remaining_seconds(session, now_fn)
        allowed_domains = list(session.get("allowedDomains") or [])

    from urllib.parse import urlencode
    target = f"{SEARCH_PROVIDER_URL}?{urlencode({'q': text})}"

    driver = fetch or sandboxed_fetch
    timeout = max(1.0, min(FETCH_TIMEOUT_S, remaining))
    try:
        result = driver(target, timeout, env) if fetch is None else driver(target, timeout)
    except GuardrailUnavailableError:
        raise
    except Exception as exc:
        raise BrowserError(f"Search failed: {_truncate(str(exc), 200)}") from exc

    raw_results = parse_search_results(str((result or {}).get("html") or ""), wanted)

    # A result is only openable if it passes the SAME allowlist/SSRF checks that
    # guard open_page. Being in search results is not permission.
    out: List[dict] = []
    for item in raw_results:
        try:
            validate_url(item["url"], allowed_domains)
            openable, reason = True, None
        except BrowserError as exc:
            openable, reason = False, str(exc)
        out.append({**item, "openable": openable, "blockedReason": reason})

    logger.info(
        "Research search: %d result(s), %d openable under the session allowlist",
        len(out), sum(1 for r in out if r["openable"]),
    )
    return {
        "query": text,
        "results": out,
        "count": len(out),
        "openableCount": sum(1 for r in out if r["openable"]),
        "warnings": [
            "Search results are untrusted content. A result is only openable if its "
            "host is in this session's allowed domains.",
        ],
    }
