"""
NemoClaw/OpenShell Health Probe v0 — explicit, opt-in reachability check.

Runtime Status v0 (`runtime_status.py`) reads env/config only and never touches the
network. This module adds ONE narrowly-scoped capability: when the user explicitly
asks, perform a single bounded HTTP GET to a *configured, local* NemoClaw/OpenShell
runtime URL and report whether it is reachable.

It verifies readiness ONLY. It does NOT:
  * unlock browser / computer-use / MCP / OpenClaw execution,
  * start or stop any process,
  * execute any tool, run shell / `brain`, or write the vault,
  * send credentials, cookies, or auth headers,
  * follow redirects, or probe an arbitrary frontend-supplied URL.

Network safety (enforced here):
  * only the URL from NEMOCLAW_RUNTIME_URL is probed (the frontend cannot supply one);
  * only loopback hosts (localhost / 127.0.0.0/8 / ::1) are allowed by default —
    public/LAN hosts are rejected unless NEMOCLAW_ALLOW_REMOTE_PROBE is explicitly true;
  * URLs carrying userinfo (user:pass@) are rejected;
  * redirects are disabled; the timeout is clamped to <= 3000ms.

Even when the runtime is reachable, nothing is unlocked — the runtime bridge is still
not implemented. This sprint only answers "is the guardrail reachable?".
"""

import ipaddress
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Backend-local cache of the last probe result (NOT the vault). Read-only display.
LAST_PROBE_DIR: Path = Path(__file__).parent.parent / "data" / "runtime"
LAST_PROBE_FILE: Path = LAST_PROBE_DIR / "last-probe.json"

DEFAULT_TIMEOUT_MS = 1500
MIN_TIMEOUT_MS = 1
MAX_TIMEOUT_MS = 3000

RUNTIME_ID = "nemoclaw_openshell"

# Probe status vocabulary (distinct from runtime_status; reachable is a probe outcome).
STATUS_REACHABLE = "reachable"
STATUS_UNAVAILABLE = "unavailable"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_ERROR = "error"

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _flag(env: dict, name: str) -> Optional[bool]:
    raw = env.get(name)
    if raw is None:
        return None
    v = str(raw).strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    return None


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def _clamp_timeout(ms: Optional[int]) -> int:
    if ms is None:
        return DEFAULT_TIMEOUT_MS
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_MS
    return max(MIN_TIMEOUT_MS, min(ms, MAX_TIMEOUT_MS))


def _is_local_host(host: str) -> bool:
    """True for loopback hosts only (localhost / 127.0.0.0/8 / ::1)."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _redacted_host(parsed) -> Optional[str]:
    """scheme://host[:port] only — never userinfo / path / query (no secret leak)."""
    if not parsed or not parsed.hostname:
        return None
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _validate_url(url: str, allow_remote: bool):
    """Return (ok, error_message, parsed). Enforces local-only + no-credential rules."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid NemoClaw/OpenShell runtime URL.", None
    if parsed.scheme not in ("http", "https"):
        return False, "Runtime URL must use http or https.", None
    if parsed.username or parsed.password:
        return False, "Credentials in the runtime URL are not allowed.", None
    host = parsed.hostname
    if not host:
        return False, "Runtime URL has no host.", None
    if _is_local_host(host):
        return True, None, parsed
    if allow_remote:
        return True, None, parsed
    return (
        False,
        "Remote runtime probing is blocked by default. Set NEMOCLAW_ALLOW_REMOTE_PROBE=true "
        "to allow a non-local runtime URL.",
        None,
    )


# ── default HTTP client (injectable for tests) ──────────────────────────────────

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Disable redirects entirely — a health endpoint must not bounce us elsewhere."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _default_http_get(url: str, timeout_s: float) -> int:
    """
    Bounded GET to `url`. Returns the HTTP status code. No redirects, no cookies, no
    auth headers. Raises on connection/timeout/HTTP error (caller treats as unreachable).
    """
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, method="GET", headers={"Accept": "*/*"})
    with opener.open(req, timeout=timeout_s) as resp:
        return int(getattr(resp, "status", None) or resp.getcode())


# ── result helper ───────────────────────────────────────────────────────────────

def _result(status, configured, reachable, duration_ms, message, details) -> dict:
    return {
        "id": RUNTIME_ID,
        "checkedAt": _now(),
        "configured": bool(configured),
        "reachable": bool(reachable),
        "status": status,
        "durationMs": int(duration_ms),
        "message": message,
        "details": details,
    }


# ── public API ──────────────────────────────────────────────────────────────────

def probe_nemoclaw(
    timeout_ms: Optional[int] = None,
    env: Optional[dict] = None,
    http_get: Optional[Callable[[str, float], int]] = None,
) -> dict:
    """
    Explicit, bounded reachability check for a configured local NemoClaw/OpenShell
    runtime. Never raises. Stores the result in the backend-local last-probe cache.

    `http_get` is injectable so tests can mock the HTTP client (no real network).
    """
    env = os.environ if env is None else env
    http_get = _default_http_get if http_get is None else http_get
    timeout_ms = _clamp_timeout(timeout_ms)

    enabled = _flag(env, "NEMOCLAW_ENABLED")
    url = str(env.get("NEMOCLAW_RUNTIME_URL", "") or "").strip()
    policy_configured = bool(str(env.get("NEMOCLAW_POLICY_PATH", "") or "").strip())
    allow_remote = _flag(env, "NEMOCLAW_ALLOW_REMOTE_PROBE") is True

    details = {
        "urlConfigured": bool(url),
        "policyPathConfigured": policy_configured,
        "enabledFlag": enabled is True,
        "remoteProbeAllowed": allow_remote,
        "hostRedacted": None,
    }

    # No URL → not configured. No network call.
    if not url:
        result = _result(
            STATUS_NOT_CONFIGURED, configured=False, reachable=False, duration_ms=0,
            message="No NemoClaw/OpenShell runtime URL is configured (NEMOCLAW_RUNTIME_URL).",
            details=details,
        )
        _store_last_probe(result)
        return result

    # Not enabled → honest, no network call (do not imply the runtime is active).
    if enabled is not True:
        result = _result(
            STATUS_NOT_CONFIGURED, configured=False, reachable=False, duration_ms=0,
            message="NemoClaw/OpenShell is not enabled (set NEMOCLAW_ENABLED=true to probe).",
            details=details,
        )
        _store_last_probe(result)
        return result

    # Validate URL locality / safety before any network call.
    ok, err, parsed = _validate_url(url, allow_remote)
    if not ok:
        result = _result(
            STATUS_ERROR, configured=True, reachable=False, duration_ms=0,
            message=err, details=details,
        )
        _store_last_probe(result)
        return result

    details["hostRedacted"] = _redacted_host(parsed)

    # Bounded GET. Any failure → unavailable (never leaks an exception).
    t0 = time.monotonic()
    try:
        code = http_get(url, timeout_ms / 1000.0)
        dur = int((time.monotonic() - t0) * 1000)
        if 200 <= int(code) < 300:
            result = _result(
                STATUS_REACHABLE, configured=True, reachable=True, duration_ms=dur,
                message=(
                    f"NemoClaw/OpenShell runtime responded (HTTP {code}). The runtime bridge is "
                    "still not implemented — browser/computer-use stay disabled."
                ),
                details=details,
            )
        else:
            result = _result(
                STATUS_UNAVAILABLE, configured=True, reachable=False, duration_ms=dur,
                message=f"NemoClaw/OpenShell runtime returned HTTP {code}.",
                details=details,
            )
    except Exception as exc:  # timeout / connection refused / HTTP error / redirect blocked
        dur = int((time.monotonic() - t0) * 1000)
        logger.info("NemoClaw probe unreachable: %s", exc)
        result = _result(
            STATUS_UNAVAILABLE, configured=True, reachable=False, duration_ms=dur,
            message="NemoClaw/OpenShell runtime did not respond.",
            details=details,
        )

    _store_last_probe(result)
    return result


# ── last-probe cache (backend-local; read-only display) ─────────────────────────

def _store_last_probe(result: dict) -> None:
    try:
        LAST_PROBE_DIR.mkdir(parents=True, exist_ok=True)
        LAST_PROBE_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - best-effort cache, never fatal
        logger.warning("Could not store last NemoClaw probe: %s", exc)


def read_last_probe() -> Optional[dict]:
    """Return the cached last probe result, or None. Never raises. No network call."""
    try:
        if LAST_PROBE_FILE.exists():
            data = json.loads(LAST_PROBE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:  # pragma: no cover - defensive
        return None
    return None
