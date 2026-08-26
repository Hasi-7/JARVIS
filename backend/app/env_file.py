"""Load `backend/.env` into the process environment.

Until this existed, `.env` was documented throughout `.env.example` and read by
nothing: every module calls `os.environ.get` directly, and nothing populated it.
A `backend/.env` sitting on disk full of correct settings did absolutely nothing,
which is a bad way to find out that your kill switch was never enabled.

Two rules:

**A real environment variable always wins.** `override=False` means anything
already exported in the shell — or set by a service manager, or injected by CI —
beats the file. That keeps the documented precedence (env > .env > config file >
defaults) and means a temporary `set X=...` still works for a one-off run.

**Import this before anything reads config.** Module-level constants like
`agent.LOCAL_MODEL` and `config._runtime` are resolved at import time, so loading
after them would silently have no effect on those values.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

ENV_FILE = Path(__file__).parent.parent / ".env"


def load_env_file(path: Path | None = None) -> dict:
    """Load .env if present. Never raises — a bad file must not stop the backend.

    Returns a small summary for logging/diagnostics. Values are NEVER included:
    this file holds the operator token and API tokens.
    """
    target = path or ENV_FILE
    result = {"path": str(target), "exists": target.is_file(), "loaded": 0, "skipped": 0}
    if not target.is_file():
        return result

    try:
        from dotenv import dotenv_values
    except ImportError:  # pragma: no cover - dependency is declared
        logger.warning(
            "python-dotenv is not installed, so %s was ignored. "
            "Install requirements or export the variables in your shell.", target,
        )
        result["error"] = "python-dotenv not installed"
        return result

    try:
        values = dotenv_values(target, encoding="utf-8")
    except Exception as exc:
        logger.error("Could not parse %s: %s. Falling back to the shell environment.", target, exc)
        result["error"] = str(exc)[:200]
        return result

    for key, value in values.items():
        if value is None:
            continue
        if key in os.environ:
            # A real environment variable outranks the file.
            result["skipped"] += 1
            continue
        os.environ[key] = value
        result["loaded"] += 1

    logger.info(
        "Loaded %d setting(s) from %s (%d already set in the environment and left alone).",
        result["loaded"], target, result["skipped"],
    )
    return result
