"""
OpenShell sandboxed execution (C1b) — PRIVILEGED, APPROVAL-GATED.

The one place in this app that runs a command inside an OpenShell sandbox. It is
deliberately separate from `openshell_client.py`, which stays provably read-only.

    exec_in_sandbox(sandbox_id, command, timeout_s) -> {exitCode, stdout, stderr}
    fetch_page_in_sandbox(url, timeout_s)           -> {html, status}

Safety model (this module never relaxes it):
- REACHED ONLY THROUGH THE APPROVAL QUEUE. `tool_approvals` dispatches this after
  the A3 flow: Assist mode -> operator token -> privileged kill switch -> explicit
  approve -> separate explicit execute. Nothing here runs from chat.
- REFUSES A FAIL-OPEN POLICY. If the configured sandbox policy sets
  `landlock.compatibility: best_effort`, filesystem isolation may silently not be
  enforced (NVIDIA/OpenShell#803, NemoClaw#1739) — especially under Docker, whose
  default seccomp profile blocks the Landlock syscalls. This module REFUSES to
  execute under that policy and requires `hard_requirement`, which aborts sandbox
  startup instead of running unprotected. Override is deliberate and explicit:
  BRAIN_UI_ALLOW_FAIL_OPEN_SANDBOX=true.
- COMMANDS ARE ALLOWLISTED, NOT ARBITRARY. Only argv vectors built by this module
  are executed; the caller never supplies a shell string. There is no shell, no
  `sh -c`, and no user-controlled interpolation into argv.
- Sandbox stdout is UNTRUSTED external content: size-capped and returned for
  review, never executed and never followed as instructions.
- No vault write, no `brain`, no local subprocess — execution happens inside the
  sandbox, via gRPC, never on the host.
"""

from __future__ import annotations

import logging
import os
import shlex
from typing import Any, Callable, Dict, List, Optional

from app.openshell_client import OpenShellError, _stub, build_channel

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised via monkeypatch
    from app.openshell_pb import openshell_pb2 as _pb
except Exception:  # pragma: no cover
    _pb = None

SANDBOX_ID_ENV = "NEMOCLAW_SANDBOX_ID"
ALLOW_FAIL_OPEN_ENV = "BRAIN_UI_ALLOW_FAIL_OPEN_SANDBOX"

DEFAULT_TIMEOUT_S = 30
MAX_TIMEOUT_S = 120
MAX_OUTPUT_CHARS = 400_000

# Only these program names may ever be the argv[0] of a sandboxed command.
ALLOWED_PROGRAMS = frozenset({"curl"})


class SandboxExecError(OpenShellError):
    """Raised when sandboxed execution cannot proceed safely."""


class FailOpenPolicyError(SandboxExecError):
    """Raised when the sandbox policy would not actually enforce isolation."""


def _env(source: Optional[dict]) -> dict:
    return os.environ if source is None else source


def _clamp_timeout(value: Optional[int]) -> int:
    try:
        seconds = int(value) if value is not None else DEFAULT_TIMEOUT_S
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_S
    return max(1, min(MAX_TIMEOUT_S, seconds))


def _truncate(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT_CHARS else text[:MAX_OUTPUT_CHARS] + "…"


# ══════════════════════════════════════════════════════════════════════════════
# Preconditions
# ══════════════════════════════════════════════════════════════════════════════

def assert_policy_enforces(env: Optional[dict] = None,
                           inspect_fn: Optional[Callable[..., dict]] = None) -> dict:
    """Refuse to execute under a policy whose isolation may not actually apply.

    `best_effort` Landlock applies what the host supports and otherwise only
    warns, so the sandbox can start with filesystem isolation reduced or absent.
    For a privileged execution path that is the wrong default, so this fails
    closed unless the operator explicitly overrides.
    """
    source = _env(env)
    if str(source.get(ALLOW_FAIL_OPEN_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}:
        logger.warning(
            "Sandbox fail-open policy explicitly allowed via %s — isolation may not be enforced.",
            ALLOW_FAIL_OPEN_ENV,
        )
        return {"enforced": False, "overridden": True}

    inspector = inspect_fn
    if inspector is None:
        from app.runtime_policy import inspect_nemoclaw_policy as inspector

    result = inspector(source)
    if result.get("status") != "loaded":
        raise FailOpenPolicyError(
            "No valid sandbox policy is loaded, so sandboxed execution is refused. "
            f"Policy status: {result.get('status')}."
        )

    warnings = " ".join(result.get("warnings") or []).lower()
    if "fails open" in warnings:
        raise FailOpenPolicyError(
            "The sandbox policy sets landlock.compatibility: best_effort, which fails "
            "OPEN — filesystem isolation may silently not be enforced, so privileged "
            "execution is refused. Set it to hard_requirement (which aborts sandbox "
            f"startup instead), or override with {ALLOW_FAIL_OPEN_ENV}=true."
        )
    return {"enforced": True, "overridden": False}


def resolve_sandbox_id(env: Optional[dict] = None) -> str:
    sandbox_id = str(_env(env).get(SANDBOX_ID_ENV, "") or "").strip()
    if not sandbox_id:
        raise SandboxExecError(
            f"No sandbox is configured. Create one with `openshell sandbox create`, "
            f"then set {SANDBOX_ID_ENV}."
        )
    return sandbox_id


def validate_command(command: List[str]) -> List[str]:
    """Accept only an argv vector whose program is allowlisted."""
    if not isinstance(command, list) or not command:
        raise SandboxExecError("A command argv list is required.")
    if any(not isinstance(part, str) or not part for part in command):
        raise SandboxExecError("Every argv element must be a non-empty string.")

    program = os.path.basename(command[0])
    if program not in ALLOWED_PROGRAMS:
        raise SandboxExecError(
            f"'{program}' is not an allowlisted sandbox program. "
            f"Allowed: {', '.join(sorted(ALLOWED_PROGRAMS))}."
        )
    # argv is sent as a repeated string field over gRPC and exec'd directly in the
    # sandbox — no shell is ever involved, so shell metacharacters carry no meaning
    # and must NOT be rejected: `&` is ordinary in a URL query string, and blocking
    # it would break most real pages. What IS rejected is control characters, which
    # could corrupt argv framing or smuggle a second line into a log.
    for part in command[1:]:
        if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in part):
            raise SandboxExecError("Control characters are not permitted in arguments.")
    return list(command)


# ══════════════════════════════════════════════════════════════════════════════
# Execution
# ══════════════════════════════════════════════════════════════════════════════

def exec_in_sandbox(
    command: List[str],
    *,
    sandbox_id: Optional[str] = None,
    timeout_s: Optional[int] = None,
    env: Optional[dict] = None,
    channel: Any = None,
    stub_factory: Any = None,
    messages: Any = None,
    inspect_fn: Optional[Callable[..., dict]] = None,
) -> dict:
    """Run one allowlisted command inside the sandbox and collect its output."""
    pb = messages or _pb
    if pb is None:
        raise SandboxExecError("OpenShell gRPC stubs are missing.")

    assert_policy_enforces(env, inspect_fn)
    argv = validate_command(command)
    target = sandbox_id or resolve_sandbox_id(env)
    timeout = _clamp_timeout(timeout_s)

    stub = _stub(channel or build_channel(env), stub_factory)
    request = pb.ExecSandboxRequest(
        sandbox_id=target,
        command=argv,
        timeout_seconds=timeout,
    )

    stdout_parts: List[str] = []
    stderr_parts: List[str] = []
    exit_code: Optional[int] = None

    try:
        for event in stub.ExecSandbox(request, timeout=timeout + 5):
            which = event.WhichOneof("payload") if hasattr(event, "WhichOneof") else None
            if which == "stdout":
                stdout_parts.append(_decode(event.stdout))
            elif which == "stderr":
                stderr_parts.append(_decode(event.stderr))
            elif which == "exit":
                exit_code = int(getattr(event.exit, "exit_code", 0) or 0)
    except SandboxExecError:
        raise
    except Exception as exc:
        detail = getattr(exc, "details", None)
        message = detail() if callable(detail) else str(exc)
        raise SandboxExecError(f"Sandboxed execution failed: {str(message)[:200]}") from exc

    logger.info(
        "Sandboxed command completed: program=%s exit=%s (output untrusted)",
        os.path.basename(argv[0]), exit_code,
    )
    return {
        "exitCode": exit_code,
        "stdout": _truncate("".join(stdout_parts)),
        "stderr": _truncate("".join(stderr_parts)),
        "sandboxId": target,
    }


def _decode(frame: Any) -> str:
    data = getattr(frame, "data", None)
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return str(data or "")


# ══════════════════════════════════════════════════════════════════════════════
# Browser fetch driver (C1b)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_page_in_sandbox(
    url: str,
    timeout_s: float = 20.0,
    env: Optional[dict] = None,
    **kwargs: Any,
) -> dict:
    """Fetch one page from INSIDE the sandbox. Used as `browser.py`'s page driver.

    The URL has already been validated by `browser.validate_url` (scheme, no
    credentials, no private literals, domain allowlist) before reaching here. It is
    passed as a single argv element to an allowlisted program — never through a
    shell — so it cannot become a command.
    """
    seconds = max(1, int(timeout_s or 1))
    command = [
        "curl",
        "--silent", "--show-error",
        "--location", "--max-redirs", "3",
        "--max-time", str(seconds),
        "--max-filesize", "5000000",
        "--proto", "=https,http",
        # No newline in this value: the argv validator rejects control characters,
        # and rpartition finds the marker without one.
        "--write-out", "__HTTP_STATUS__:%{http_code}",
        url,
    ]
    result = exec_in_sandbox(command, timeout_s=seconds + 5, env=env, **kwargs)

    body = result.get("stdout") or ""
    status = 0
    marker = "__HTTP_STATUS__:"
    if marker in body:
        body, _, tail = body.rpartition(marker)
        body = body.rstrip()
        try:
            status = int(tail.strip())
        except ValueError:
            status = 0

    if result.get("exitCode") not in (0, None):
        raise SandboxExecError(
            f"Sandboxed fetch failed (exit {result.get('exitCode')}): "
            f"{(result.get('stderr') or '')[:200]}"
        )

    return {"html": body, "status": status}
