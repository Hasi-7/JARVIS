import logging
import subprocess
import sys
import time
from pathlib import Path

from app.config import get_config
from app.models import BrainRunResponse
from app.security import is_allowed

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60


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

    # Read runtime config fresh each call so PUT /api/config takes effect immediately.
    cfg = get_config()
    brain_path = Path(cfg.brain_cmd)

    if not brain_path.exists():
        logger.warning("brain.cmd not found at %s", cfg.brain_cmd)
        return BrainRunResponse(
            command=command,
            ok=False,
            exitCode=1,
            stdout="",
            stderr=f"brain.cmd not found at: {cfg.brain_cmd}",
            durationMs=0.0,
        )

    # .cmd files on Windows require cmd.exe; keep shell=False for safety.
    if sys.platform == "win32" and str(brain_path).lower().endswith(".cmd"):
        args = ["cmd.exe", "/c", str(brain_path), command]
    else:
        args = [str(brain_path), command]

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
        logger.info(
            "Done: exit=%d  %.0fms  cmd=%r",
            result.returncode, duration_ms, command,
        )
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
