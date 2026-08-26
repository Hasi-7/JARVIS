"""
Computer-use harness (MVP v7, PRD §13.3/§13.4) — PRIVILEGED, FULL DESKTOP.

This module can click and type on the user's real desktop. That is a deliberate,
explicitly chosen capability (PRD §41 Q5/Q6 were resolved in favour of full
desktop control over browser-only). Because there is no sandbox boundary around
host control, the guards below ARE the safety, and none of them is optional.

    start_session(task, allowed_windows[], budget_seconds) -> session
    observe(session_id)                                    -> screenshot + window state
    click(session_id, x, y)  /  type_text(session_id, text)
    stop_session(session_id)

Five gates, ALL required before any action (mirrors the A3 approval flow):
  1. Assist mode
  2. operator token (`X-Brain-Approval-Token`, enforced by the API layer)
  3. `BRAIN_UI_COMPUTER_USE_ENABLED=true` kill switch, default OFF
  4. an active session whose wall-clock budget has not expired
  5. the FOREGROUND WINDOW matches the session's allowlist

Gate 5 is the load-bearing one. If focus has moved off an allowlisted window the
action is REFUSED, never retargeted — that is what stops a mis-aimed click landing
in another application.

PRD §13.4 risky categories require a separate per-action confirmation and are
never covered by a blanket session approval. Typing into a window that looks like
a credential/login surface is REFUSED OUTRIGHT rather than confirmed: a tool that
can type into a password box is a class of mistake worth removing, not gating.

Other hard limits: typed text is length-capped and control characters rejected;
a key-combination denylist blocks system dialogs; screenshots are downscaled,
capped, and stored backend-local — NEVER in the vault; `pyautogui.FAILSAFE` stays
on so slamming the pointer into a screen corner aborts.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SESSIONS_DIR: Path = Path(__file__).parent.parent / "data" / "computer-use"
SESSIONS_FILE: Path = SESSIONS_DIR / "sessions.json"
SHOTS_DIR: Path = SESSIONS_DIR / "screenshots"

_lock = threading.Lock()

ENABLED_ENV = "BRAIN_UI_COMPUTER_USE_ENABLED"

DEFAULT_BUDGET_SECONDS = 300
MIN_BUDGET_SECONDS = 10
MAX_BUDGET_SECONDS = 1800
MAX_ACTIONS_PER_SESSION = 200
MAX_STORED_SESSIONS = 50

MAX_TASK_CHARS = 300
MAX_TYPE_CHARS = 2_000
MAX_WINDOWS = 10
SCREENSHOT_MAX_WIDTH = 1280
MAX_STORED_SHOTS = 50

STATUS_ACTIVE = "active"
STATUS_STOPPED = "stopped"
STATUS_BUDGET_EXHAUSTED = "budget_exhausted"

# PRD §13.4 — actions that must never proceed on a blanket session approval.
RISKY_CATEGORIES: Dict[str, str] = {
    "send_message": "sending a message",
    "submit_form": "submitting a form",
    "delete": "deleting content",
    "download": "downloading a file",
    "upload": "uploading a file",
    "settings": "changing settings",
    "purchase": "making a purchase",
    "credentials": "a password or credential surface",
    "permissions": "granting permissions to an external app",
}

# Window-title signals. Deliberately broad: a false positive costs one extra
# confirmation, a false negative costs an unintended real-world action.
_RISK_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # NOTE: bare "vault" is deliberately NOT here. This app is built around an
    # Obsidian *vault*, so matching that word would flag every ordinary window as
    # a credential surface and block the tool's primary use case. Password
    # managers are matched by name instead, plus the explicit phrase.
    ("credentials", re.compile(r"\b(sign[ -]?in|log[ -]?in|password|passphrase|credential|"
                               r"authenticat|2fa|two[- ]factor|one[- ]time code|keychain|"
                               r"bitwarden|1password|lastpass|dashlane|keepass)\b"
                               r"|password vault", re.I)),
    ("purchase", re.compile(r"\b(checkout|payment|billing|purchase|buy now|card number|invoice)\b", re.I)),
    ("permissions", re.compile(r"\b(permission|authorize|grant access|oauth|consent)\b", re.I)),
    ("settings", re.compile(r"\b(settings|preferences|control panel|configuration)\b", re.I)),
    ("delete", re.compile(r"\b(delete|remove|trash|erase|uninstall)\b", re.I)),
    ("send_message", re.compile(r"\b(compose|new message|send mail|reply)\b", re.I)),
    ("upload", re.compile(r"\b(upload|choose file|file upload)\b", re.I)),
    ("download", re.compile(r"\b(download|save as)\b", re.I)),
]

# Key combinations that can reach system-level dialogs or window management.
DENIED_HOTKEYS = frozenset({
    "ctrl+alt+delete", "win+r", "win+l", "win+x", "alt+f4",
    "ctrl+shift+esc", "win+e", "win+i",
})


class ComputerUseError(ValueError):
    """Raised when a computer-use action is rejected."""


class ComputerUseDisabled(RuntimeError):
    """Raised when the kill switch is off. Fails closed."""


class WindowNotAllowed(ComputerUseError):
    """Raised when the foreground window is not in the session allowlist."""


class RiskyActionRequiresConfirmation(ComputerUseError):
    """Raised when a PRD §13.4 category needs an explicit per-action confirmation."""


# ══════════════════════════════════════════════════════════════════════════════
# Kill switch / configuration
# ══════════════════════════════════════════════════════════════════════════════

def computer_use_enabled(env: Optional[dict] = None) -> bool:
    """OFF by default. Must be explicitly turned on in the backend process."""
    source = os.environ if env is None else env
    return str(source.get(ENABLED_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}


def _require_enabled(env: Optional[dict] = None) -> None:
    if not computer_use_enabled(env):
        raise ComputerUseDisabled(
            f"Computer-use is disabled. Start the backend with {ENABLED_ENV}=true to "
            f"enable it. It is off by default because it can act on the real desktop."
        )


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def _truncate(value: str, limit: int) -> str:
    text = value or ""
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _clamp_budget(seconds: Optional[int]) -> int:
    try:
        value = int(seconds) if seconds is not None else DEFAULT_BUDGET_SECONDS
    except (TypeError, ValueError):
        return DEFAULT_BUDGET_SECONDS
    return max(MIN_BUDGET_SECONDS, min(MAX_BUDGET_SECONDS, value))


# ══════════════════════════════════════════════════════════════════════════════
# Window targeting — gate 5
# ══════════════════════════════════════════════════════════════════════════════

def _default_foreground_title() -> str:
    """Read the active window title. Never raises."""
    try:
        import pygetwindow
        window = pygetwindow.getActiveWindow()
        return str(getattr(window, "title", "") or "")
    except Exception:
        return ""


def window_matches(title: str, allowed: List[str]) -> bool:
    """Case-insensitive substring match. An empty allowlist matches NOTHING."""
    haystack = (title or "").strip().lower()
    if not haystack or not allowed:
        return False
    return any(entry.strip().lower() in haystack
               for entry in allowed if entry and entry.strip())


def classify_risk(window_title: str, action: str, text: Optional[str] = None) -> Optional[str]:
    """Return a PRD §13.4 category for this action, or None if it is ordinary."""
    haystack = f"{window_title or ''} {text or ''}"
    for category, pattern in _RISK_PATTERNS:
        if pattern.search(haystack):
            return category
    if action == "type" and text and len(text) > 500:
        return "send_message"      # bulk typing is most often composing something
    return None


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
        raise ComputerUseError(f"Corrupted computer-use session file: {exc}") from exc


def _write_sessions(sessions: List[dict]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(
        json.dumps(sessions[-MAX_STORED_SESSIONS:], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def remaining_seconds(session: dict, now_fn: Callable[[], float] = time.time) -> float:
    elapsed = now_fn() - float(session.get("startedAtEpoch", 0.0))
    return max(0.0, float(session.get("budgetSeconds", 0)) - elapsed)


def _refresh_status(session: dict, now_fn: Callable[[], float]) -> dict:
    if session.get("status") == STATUS_ACTIVE and remaining_seconds(session, now_fn) <= 0:
        session["status"] = STATUS_BUDGET_EXHAUSTED
        session["endedAt"] = _now()
    return session


def _record(session: dict, action: str, detail: dict) -> None:
    session.setdefault("actions", []).append({
        "at": _now(), "action": action, **detail,
    })


# ══════════════════════════════════════════════════════════════════════════════
# Session lifecycle
# ══════════════════════════════════════════════════════════════════════════════

def start_session(
    task_description: str,
    allowed_windows: List[str],
    budget_seconds: Optional[int] = None,
    *,
    env: Optional[dict] = None,
    now_fn: Callable[[], float] = time.time,
) -> dict:
    """Begin a scoped computer-use session. Performs no action by itself."""
    _require_enabled(env)

    task = " ".join(str(task_description or "").split())
    if not task:
        raise ComputerUseError("A task description is required (PRD §13.3 scoped task).")
    if len(task) > MAX_TASK_CHARS:
        raise ComputerUseError(f"Task description is too long (max {MAX_TASK_CHARS}).")

    windows = [w.strip() for w in (allowed_windows or []) if w and w.strip()]
    if not windows:
        raise ComputerUseError(
            "At least one allowed window title is required. An empty allowlist "
            "would permit acting on any window."
        )
    if len(windows) > MAX_WINDOWS:
        raise ComputerUseError(f"Too many allowed windows (max {MAX_WINDOWS}).")

    session = {
        "id": str(uuid.uuid4()),
        "task": task,
        "allowedWindows": windows,
        "budgetSeconds": _clamp_budget(budget_seconds),
        "status": STATUS_ACTIVE,
        "startedAt": _now(),
        "startedAtEpoch": now_fn(),
        "endedAt": None,
        "actions": [],
    }
    with _lock:
        sessions = _read_sessions()
        sessions.append(session)
        _write_sessions(sessions)

    logger.warning(
        "COMPUTER-USE SESSION STARTED id=%s task=%r windows=%s budget=%ss — "
        "this session can act on the real desktop",
        session["id"], task, windows, session["budgetSeconds"],
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
    """Stop immediately (PRD §13.3 user interrupt). Idempotent, never gated."""
    with _lock:
        sessions = _read_sessions()
        for session in sessions:
            if session.get("id") != session_id:
                continue
            if session.get("status") == STATUS_ACTIVE:
                session["status"] = STATUS_STOPPED
                session["endedAt"] = _now()
                _record(session, "stop", {"ok": True})
                _write_sessions(sessions)
                logger.warning("COMPUTER-USE SESSION STOPPED id=%s", session_id)
            return dict(session)
    raise ComputerUseError(f"Computer-use session '{session_id}' not found.")


def active_session(*, now_fn: Callable[[], float] = time.time) -> Optional[dict]:
    """The live session, if any — used by the UI to show the visible indicator."""
    for session in list_sessions(now_fn=now_fn):
        if session.get("status") == STATUS_ACTIVE:
            return session
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Pre-action gate
# ══════════════════════════════════════════════════════════════════════════════

def _gate(
    session_id: str,
    action: str,
    *,
    env: Optional[dict],
    now_fn: Callable[[], float],
    foreground_fn: Callable[[], str],
    text: Optional[str] = None,
    confirmed_risk: Optional[str] = None,
) -> Tuple[dict, str]:
    """Run all five gates. Returns (session, foreground_title) or raises."""
    _require_enabled(env)

    with _lock:
        sessions = _read_sessions()
        session = next((s for s in sessions if s.get("id") == session_id), None)
        if session is None:
            raise ComputerUseError(f"Computer-use session '{session_id}' not found.")
        _refresh_status(session, now_fn)
        status = session.get("status")
        if status == STATUS_STOPPED:
            raise ComputerUseError("This computer-use session was stopped.")
        if status == STATUS_BUDGET_EXHAUSTED:
            raise ComputerUseError("This computer-use session's time budget is exhausted.")
        if len(session.get("actions") or []) >= MAX_ACTIONS_PER_SESSION:
            session["status"] = STATUS_BUDGET_EXHAUSTED
            session["endedAt"] = _now()
            _write_sessions(sessions)
            raise ComputerUseError(f"Action limit reached ({MAX_ACTIONS_PER_SESSION}).")
        allowed = list(session.get("allowedWindows") or [])
        snapshot = dict(session)

    # Gate 5 — the load-bearing one.
    title = foreground_fn() or ""
    if not window_matches(title, allowed):
        _log_refusal(session_id, action, "window_not_allowed", title)
        raise WindowNotAllowed(
            f"The focused window ({title or 'unknown'!r}) is not in this session's "
            f"allowed windows ({', '.join(allowed)}). The action was refused, not "
            f"retargeted."
        )

    # PRD §13.4 — risky categories need their own confirmation, every time.
    risk = classify_risk(title, action, text)
    if risk == "credentials" and action == "type":
        _log_refusal(session_id, action, "credential_surface", title)
        raise ComputerUseError(
            "Refusing to type into what looks like a password or credential surface. "
            "This is never confirmable — do it yourself."
        )
    if risk and confirmed_risk != risk:
        raise RiskyActionRequiresConfirmation(
            f"This action targets {RISKY_CATEGORIES[risk]} and needs explicit "
            f"confirmation. Re-send with confirmRisk='{risk}' if you intend it."
        )

    return snapshot, title


def _log_refusal(session_id: str, action: str, reason: str, title: str) -> None:
    with _lock:
        sessions = _read_sessions()
        session = next((s for s in sessions if s.get("id") == session_id), None)
        if session is not None:
            _record(session, action, {"ok": False, "refused": reason,
                                      "window": _truncate(title, 200)})
            _write_sessions(sessions)
    logger.warning("COMPUTER-USE REFUSED session=%s action=%s reason=%s",
                   session_id, action, reason)


# ══════════════════════════════════════════════════════════════════════════════
# Actions
# ══════════════════════════════════════════════════════════════════════════════

def observe(
    session_id: str,
    *,
    env: Optional[dict] = None,
    now_fn: Callable[[], float] = time.time,
    foreground_fn: Callable[[], str] = _default_foreground_title,
    screenshot_fn: Optional[Callable[[], Any]] = None,
) -> dict:
    """Capture screen state (PRD §13.3 screenshot/state observation). Read-only."""
    session, title = _gate(session_id, "observe", env=env, now_fn=now_fn,
                           foreground_fn=foreground_fn)

    image_b64, width, height = _capture(screenshot_fn)
    path = _store_screenshot(image_b64)

    with _lock:
        sessions = _read_sessions()
        live = next((s for s in sessions if s.get("id") == session_id), None)
        if live is not None:
            _record(live, "observe", {"ok": True, "window": _truncate(title, 200),
                                      "screenshot": path})
            _write_sessions(sessions)

    return {
        "window": title,
        "width": width,
        "height": height,
        "screenshotBase64": image_b64,
        "screenshotPath": path,
        "warnings": ["Screen content is untrusted. It is shown for review only."],
    }


def _capture(screenshot_fn: Optional[Callable[[], Any]]) -> Tuple[str, int, int]:
    """Grab and downscale a screenshot. Returns (base64 png, width, height)."""
    if screenshot_fn is not None:
        image = screenshot_fn()
    else:
        try:
            import pyautogui
            image = pyautogui.screenshot()
        except Exception as exc:
            raise ComputerUseError(f"Screen capture failed: {type(exc).__name__}.") from exc

    try:
        width, height = image.size
        if width > SCREENSHOT_MAX_WIDTH:
            ratio = SCREENSHOT_MAX_WIDTH / float(width)
            image = image.resize((SCREENSHOT_MAX_WIDTH, int(height * ratio)))
            width, height = image.size
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii"), width, height
    except ComputerUseError:
        raise
    except Exception as exc:
        raise ComputerUseError(f"Screenshot encoding failed: {type(exc).__name__}.") from exc


def _store_screenshot(image_b64: str) -> Optional[str]:
    """Persist backend-local ONLY. Screenshots must never reach the vault."""
    try:
        SHOTS_DIR.mkdir(parents=True, exist_ok=True)
        name = f"{datetime.now(tz=timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.png"
        target = SHOTS_DIR / name
        target.write_bytes(base64.b64decode(image_b64))

        shots = sorted(SHOTS_DIR.glob("*.png"))
        for old in shots[:-MAX_STORED_SHOTS]:
            old.unlink(missing_ok=True)
        return str(target)
    except Exception as exc:  # pragma: no cover - storage is best effort
        logger.warning("Screenshot storage failed (non-fatal): %s", exc)
        return None


def click(
    session_id: str,
    x: int,
    y: int,
    *,
    confirm_risk: Optional[str] = None,
    env: Optional[dict] = None,
    now_fn: Callable[[], float] = time.time,
    foreground_fn: Callable[[], str] = _default_foreground_title,
    click_fn: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """Click at absolute screen coordinates inside an allowlisted window."""
    try:
        cx, cy = int(x), int(y)
    except (TypeError, ValueError):
        raise ComputerUseError("Click coordinates must be integers.")
    if cx < 0 or cy < 0:
        raise ComputerUseError("Click coordinates must be non-negative.")

    session, title = _gate(session_id, "click", env=env, now_fn=now_fn,
                           foreground_fn=foreground_fn, confirmed_risk=confirm_risk)

    if click_fn is not None:
        click_fn(cx, cy)
    else:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.click(cx, cy)

    with _lock:
        sessions = _read_sessions()
        live = next((s for s in sessions if s.get("id") == session_id), None)
        if live is not None:
            _record(live, "click", {"ok": True, "x": cx, "y": cy,
                                    "window": _truncate(title, 200)})
            _write_sessions(sessions)

    logger.warning("COMPUTER-USE CLICK session=%s at=(%d,%d) window=%r",
                   session_id, cx, cy, _truncate(title, 80))
    return {"ok": True, "x": cx, "y": cy, "window": title}


def type_text(
    session_id: str,
    text: str,
    *,
    confirm_risk: Optional[str] = None,
    env: Optional[dict] = None,
    now_fn: Callable[[], float] = time.time,
    foreground_fn: Callable[[], str] = _default_foreground_title,
    type_fn: Optional[Callable[[str], None]] = None,
) -> dict:
    """Type literal text into an allowlisted window. Never a key combination."""
    payload = str(text or "")
    if not payload:
        raise ComputerUseError("Text to type is required.")
    if len(payload) > MAX_TYPE_CHARS:
        raise ComputerUseError(f"Text is too long (max {MAX_TYPE_CHARS} characters).")
    if any(ord(ch) < 0x20 and ch not in "\t\n" for ch in payload):
        raise ComputerUseError("Control characters are not permitted in typed text.")
    if payload.strip().lower() in DENIED_HOTKEYS:
        raise ComputerUseError("System key combinations are not permitted.")

    session, title = _gate(session_id, "type", env=env, now_fn=now_fn,
                           foreground_fn=foreground_fn, text=payload,
                           confirmed_risk=confirm_risk)

    if type_fn is not None:
        type_fn(payload)
    else:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.typewrite(payload, interval=0.01)

    with _lock:
        sessions = _read_sessions()
        live = next((s for s in sessions if s.get("id") == session_id), None)
        if live is not None:
            # Log the LENGTH, not the content: typed text may be personal.
            _record(live, "type", {"ok": True, "chars": len(payload),
                                   "window": _truncate(title, 200)})
            _write_sessions(sessions)

    logger.warning("COMPUTER-USE TYPE session=%s chars=%d window=%r",
                   session_id, len(payload), _truncate(title, 80))
    return {"ok": True, "chars": len(payload), "window": title}


def session_summary(session: dict, *, now_fn: Callable[[], float] = time.time) -> dict:
    """Compact status for the visible indicator."""
    actions = session.get("actions") or []
    return {
        "id": session.get("id"),
        "task": session.get("task"),
        "status": session.get("status"),
        "budgetSeconds": session.get("budgetSeconds"),
        "remainingSeconds": round(remaining_seconds(session, now_fn), 1),
        "allowedWindows": list(session.get("allowedWindows") or []),
        "actionCount": len(actions),
        "refusedCount": sum(1 for a in actions if a.get("refused")),
        "startedAt": session.get("startedAt"),
        "endedAt": session.get("endedAt"),
    }
