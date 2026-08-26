"""
Runtime configuration for Brain UI backend.

Load order (applied per field):
  1. Environment variable (BRAIN_UI_VAULT_PATH / BRAIN_UI_BRAIN_CMD) — highest priority.
  2. Persisted config file  (backend/data/brain-ui-config.json).
  3. Built-in defaults      — lowest priority.

PUT /api/config updates the runtime singleton AND writes brain-ui-config.json so
the choice survives a backend restart. The file is never auto-written on startup;
only explicit user saves trigger a write.

If brain-ui-config.json is corrupt, the backend falls back to env/defaults and
exposes a warning via GET /api/config. The corrupt file is left untouched so the
user can inspect or fix it manually.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_VAULT_DEFAULT: str = r"D:\Hasnain\Personal\OneDrive - University of Toronto\AI-Command-Center"
_BRAIN_CMD_DEFAULT: str = r"D:\Hasnain\Personal\bin\brain.cmd"
# PRD §8.4 / §43. Reference only: the old repo is where the `brain` CLI itself
# lives, and its path is worth surfacing in Settings. Nothing in this app reads
# or writes inside it — it is not a second vault, and no code path targets it.
_OLD_REPO_DEFAULT: str = r"D:\Hasnain\Personal\dev\ai-command-tools"

CONFIG_FILE: Path = Path(__file__).parent.parent / "data" / "brain-ui-config.json"


@dataclass
class RuntimeConfig:
    vault_path: str
    brain_cmd: str
    old_repo_path: str = ""
    # "env" | "file" | "defaults" | "runtime"  (runtime = updated via API this session)
    source: str = "defaults"
    persisted: bool = False
    warning: Optional[str] = None


def _read_config_file() -> tuple[Optional[dict], Optional[str]]:
    """
    Read brain-ui-config.json.

    Returns (data_dict, None) on success, (None, None) if missing,
    or (None, warning_str) if the file is present but corrupt.
    The corrupt file is never deleted.
    """
    if not CONFIG_FILE.exists():
        return None, None
    try:
        raw = CONFIG_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Root value is not a JSON object.")
        return data, None
    except Exception as exc:
        warning = f"Config file corrupted — falling back to env/defaults. ({exc})"
        logger.warning("Corrupt config file %s: %s", CONFIG_FILE, exc)
        return None, warning


def _load_startup_config() -> RuntimeConfig:
    """Build the startup RuntimeConfig from env → file → defaults."""
    env_vault = os.environ.get("BRAIN_UI_VAULT_PATH", "").strip()
    env_brain = os.environ.get("BRAIN_UI_BRAIN_CMD", "").strip()

    file_data, file_warning = _read_config_file()

    # Per-field resolution: env > file > default
    vault = env_vault or (file_data.get("vaultPath", "") if file_data else "") or _VAULT_DEFAULT
    brain = env_brain or (file_data.get("brainCmd", "") if file_data else "") or _BRAIN_CMD_DEFAULT
    old_repo = (
        os.environ.get("OLD_BRAIN_REPO_PATH", "").strip()
        or (file_data.get("oldRepoPath", "") if file_data else "")
        or _OLD_REPO_DEFAULT
    )

    # Source tag describes the dominant origin
    if env_vault or env_brain:
        source = "env"
    elif file_data is not None:
        source = "file"
    else:
        source = "defaults"

    return RuntimeConfig(
        vault_path=vault,
        brain_cmd=brain,
        old_repo_path=old_repo,
        source=source,
        persisted=file_data is not None,
        warning=file_warning,
    )


def _write_config_file(vault_path: str, brain_cmd: str) -> None:
    """Write brain-ui-config.json. Parent directory is created if absent."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "vaultPath": vault_path,
            "brainCmd":  brain_cmd,
            "updatedAt": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        }
        CONFIG_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Config persisted to %s", CONFIG_FILE)
    except Exception as exc:
        logger.error("Failed to persist config to %s: %s", CONFIG_FILE, exc)


# Module-level singleton — initialised from env → file → defaults on import.
_runtime: RuntimeConfig = _load_startup_config()


def get_config() -> RuntimeConfig:
    return _runtime


def update_config(vault_path: str, brain_cmd: str) -> RuntimeConfig:
    """Update runtime config and persist to brain-ui-config.json."""
    _runtime.vault_path = vault_path
    _runtime.brain_cmd  = brain_cmd
    _runtime.source     = "runtime"
    _runtime.warning    = None
    _write_config_file(vault_path, brain_cmd)
    _runtime.persisted  = True
    return _runtime
