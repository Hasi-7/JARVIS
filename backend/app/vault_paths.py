"""Shared vault path and cell-sanitizing primitives.

`_safe_subpath` was duplicated verbatim in four modules (vault, calendar,
escalations, entities) and the table-cell sanitizer had drifted between two of
them: vault.py replaced `|` with U+2223 DIVIDES, entities.py replaced it with a
plain `/`, which is lossy and inconsistent for the same threat.

Each module keeps its private alias (`_safe_subpath = safe_subpath`), so every
existing call site and every test that monkeypatches the private name still
works, and the migration needed no call-site edits.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# U+2223 DIVIDES. Visually close to a pipe but cannot terminate a Markdown table
# cell, so an untrusted value can never inject extra columns.
PIPE_SUBSTITUTE = "∣"


def safe_subpath(vault_root: Path, *parts: str) -> Optional[Path]:
    """Resolve `parts` under `vault_root`, or return None if it escapes.

    Returns None rather than raising — every caller must null-check. A None
    reaching open() surfaces as a confusing TypeError, so new callers should
    check explicitly rather than relying on the failure being obvious.
    """
    try:
        resolved_root = vault_root.resolve()
        resolved_child = vault_root.joinpath(*parts).resolve()
    except (OSError, ValueError) as exc:
        logger.warning("Path resolution failed: %s / %s (%s)", vault_root, parts, exc)
        return None
    if resolved_child == resolved_root or resolved_child.is_relative_to(resolved_root):
        return resolved_child
    logger.warning("Path traversal rejected: %s / %s", vault_root, parts)
    return None


def sanitize_cell(value: object, limit: int = 500) -> str:
    """Flatten a value so it cannot break out of a Markdown table row."""
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("|", PIPE_SUBSTITUTE)
    text = " ".join(text.split())
    return text[:limit]


def write_text_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write via a temp file in the same directory, then os.replace.

    Vault writes are backup-then-overwrite, so a crash mid-write left a corrupt
    file plus a good backup — recoverable, but only if someone knew to look.
    This makes the file always either fully old or fully new.

    The temp file must share a directory with the target: os.replace is atomic
    only within a filesystem, and the vault may sit on a different volume from
    the system temp dir (this one lives on OneDrive).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp",
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def precondition_token(path: Path) -> Optional[str]:
    """An opaque token identifying this file's current content state.

    Used for optimistic concurrency on wiki notes. mtime_ns + size, NOT the
    second-granularity ISO timestamp used for display: Obsidian autosaves, and a
    one-second resolution is far too coarse to notice an edit that landed
    between a read and a write.
    """
    try:
        st = path.stat()
    except OSError:
        return None
    return f"{st.st_mtime_ns}:{st.st_size}"
