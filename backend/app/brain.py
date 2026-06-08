import logging
import re
import subprocess
import sys
import time
from pathlib import Path

from app.config import get_config
from app.models import BrainRunResponse
from app.security import is_allowed

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_CMD_META_RE = re.compile(r"[&|<>^%!\"()]")

_ARG_SCHEMAS: dict[str, tuple[str, ...]] = {
    "new-project": ("name", "repoPath"),
    "new-course": ("code", "name"),
    "new-hackathon": ("name", "date"),
}

_REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    "new-project": ("name",),
    "new-course": ("code",),
    "new-hackathon": ("name",),
}

_UNSUPPORTED_NONEMPTY_ARGS: dict[str, dict[str, str]] = {
    "new-project": {
        "repoPath": "Current brain new-project accepts only a project name; repoPath is not supported by the CLI.",
    },
    "new-hackathon": {
        "date": "Current brain new-hackathon accepts only a hackathon name; date is not supported by the CLI.",
    },
}


def _brain_base_args(brain_path: Path) -> list[str]:
    # .cmd files on Windows require cmd.exe; keep shell=False for safety.
    if sys.platform == "win32" and str(brain_path).lower().endswith(".cmd"):
        return ["cmd.exe", "/c", str(brain_path)]
    return [str(brain_path)]


def _missing_brain_response(command: str, brain_cmd: str) -> BrainRunResponse:
    logger.warning("brain.cmd not found at %s", brain_cmd)
    return BrainRunResponse(
        command=command,
        ok=False,
        exitCode=1,
        stdout="",
        stderr=f"brain.cmd not found at: {brain_cmd}",
        durationMs=0.0,
    )


def _run_args(command: str, args: list[str]) -> BrainRunResponse:
    logger.info("Running: %s", args)
    start = time.monotonic()
    try:
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        duration_ms = (time.monotonic() - start) * 1000
        ok = result.returncode == 0
        logger.info("Done: exit=%d  %.0fms  cmd=%r", result.returncode, duration_ms, command)
        return BrainRunResponse(
            command=command,
            ok=ok,
            exitCode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            durationMs=round(duration_ms, 1),
        )
    except subprocess.TimeoutExpired:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error("Timeout after %ds: %r", TIMEOUT_SECONDS, command)
        return BrainRunResponse(
            command=command,
            ok=False,
            exitCode=-1,
            stdout="",
            stderr=f"Command timed out after {TIMEOUT_SECONDS}s.",
            durationMs=round(duration_ms, 1),
        )
    except Exception as exc:
        logger.error("Unexpected error running %r: %s", command, exc)
        return BrainRunResponse(
            command=command,
            ok=False,
            exitCode=-1,
            stdout="",
            stderr=str(exc),
            durationMs=0.0,
        )


def run_brain_command(command: str) -> BrainRunResponse:
    """Execute a single allowlisted brain subcommand safely."""
    if not is_allowed(command):
        logger.warning("Rejected non-allowlisted command: %r", command)
        return BrainRunResponse(
            command=command,
            ok=False,
            exitCode=1,
            stdout="",
            stderr=f"Command '{command}' is not in the allowlist.",
            durationMs=0.0,
        )

    cfg = get_config()
    brain_path = Path(cfg.brain_cmd)
    if not brain_path.exists():
        return _missing_brain_response(command, cfg.brain_cmd)

    return _run_args(command, _brain_base_args(brain_path) + [command])


def _validate_arg_value(command: str, key: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Argument '{key}' for {command} must be a string or null.")
    cleaned = value.strip()
    if not cleaned:
        return None
    if _CONTROL_RE.search(cleaned):
        raise ValueError(f"Argument '{key}' for {command} contains control characters.")
    if _CMD_META_RE.search(cleaned):
        raise ValueError(f"Argument '{key}' for {command} contains unsafe shell metacharacters.")
    return cleaned


def _build_command_args(command: str, cleaned: dict[str, str | None]) -> list[str]:
    for key, message in _UNSUPPORTED_NONEMPTY_ARGS.get(command, {}).items():
        if cleaned.get(key):
            raise ValueError(message)

    if command == "new-project":
        return [cleaned["name"] or ""]
    if command == "new-hackathon":
        return [cleaned["name"] or ""]
    if command == "new-course":
        args = [cleaned["code"] or ""]
        if cleaned.get("name"):
            args += ["--title", cleaned["name"] or ""]
        return args

    raise ValueError(f"Command '{command}' does not support API arguments.")


def run_brain_command_args(command: str, args_payload: dict) -> BrainRunResponse:
    """Execute an allowlisted brain command with a command-specific argument schema."""
    if not is_allowed(command):
        logger.warning("Rejected non-allowlisted command: %r", command)
        return BrainRunResponse(
            command=command,
            ok=False,
            exitCode=1,
            stdout="",
            stderr=f"Command '{command}' is not in the allowlist.",
            durationMs=0.0,
        )
    if command not in _ARG_SCHEMAS:
        return BrainRunResponse(
            command=command,
            ok=False,
            exitCode=1,
            stdout="",
            stderr=f"Command '{command}' does not support API arguments.",
            durationMs=0.0,
        )

    allowed = set(_ARG_SCHEMAS[command])
    unknown = sorted(set(args_payload.keys()) - allowed)
    if unknown:
        return BrainRunResponse(
            command=command,
            ok=False,
            exitCode=1,
            stdout="",
            stderr=f"Unknown argument(s) for {command}: {', '.join(unknown)}.",
            durationMs=0.0,
        )

    try:
        cleaned = {
            key: _validate_arg_value(command, key, args_payload.get(key))
            for key in _ARG_SCHEMAS[command]
        }
        for key in _REQUIRED_ARGS[command]:
            if not cleaned.get(key):
                raise ValueError(f"Argument '{key}' for {command} is required.")
        command_args = _build_command_args(command, cleaned)
    except ValueError as exc:
        return BrainRunResponse(
            command=command,
            ok=False,
            exitCode=1,
            stdout="",
            stderr=str(exc),
            durationMs=0.0,
        )

    cfg = get_config()
    brain_path = Path(cfg.brain_cmd)
    if not brain_path.exists():
        return _missing_brain_response(command, cfg.brain_cmd)

    return _run_args(command, _brain_base_args(brain_path) + [command] + command_args)
