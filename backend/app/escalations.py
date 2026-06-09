"""
escalations.py — Escalation queue read/write for ops/escalation-queue.md.

Read operations:
- get_escalations(): parses Markdown table; falls back to preview-only or missing.

Write operations:
- create_escalation_queue_file(): creates the starter table when missing.
- add_escalation_item(): appends one escalation row.
- update_escalation_status(): updates a single item's status cell.
- update_escalation_item(): updates the editable fields of an existing item.

Safety rules strictly enforced:
- All paths resolved and validated to stay inside the configured vault root.
- Traversal prevented via Path.is_relative_to().
- Previews capped at 2000 chars; full file content never forwarded.
- Only allowed escalation statuses and targets accepted.
- Conflict detection: re-reads + re-parses file before writing; verifies task title.
- Backup created before every write; backups never overwritten.
- No shell commands launched.
- No Claude Code/OpenCode processes launched.
- No repo files are modified (path field is metadata only).
"""

import logging
import random
import re
import shutil
import string
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ESCALATION_FILE = "ops/escalation-queue.md"
_PREVIEW_CHARS   = 2000
_PARSE_CHARS     = 50_000
_BACKUP_DIR      = Path(__file__).parent.parent / "data" / "backups" / "escalations"

ALLOWED_ESCALATION_STATUSES: frozenset = frozenset({
    "new", "ready", "in-progress", "done", "blocked", "skipped"
})

ALLOWED_ESCALATION_TARGETS: frozenset = frozenset({
    "claude-code", "opencode", "manual"
})

_ESCALATION_COL_ALIASES: dict = {
    # task
    "task": "task", "title": "task", "name": "task", "request": "task",
    # target
    "target": "target", "agent": "target", "tool": "target",
    # status
    "status": "status", "state": "status",
    # priority
    "priority": "priority", "value": "priority", "importance": "priority",
    # source
    "source": "source", "from": "source", "origin": "source",
    # path
    "path": "path", "repo": "path", "folder": "path", "link": "path",
    # notes
    "notes": "notes", "summary": "notes", "description": "notes",
    # created
    "created": "created", "date": "created",
}

_PUBLIC_ESCALATION_FIELDS = frozenset({
    "id", "task", "target", "status", "priority",
    "source", "path", "notes", "created", "raw",
})

_STARTER_CONTENT = (
    "# Escalation Queue\n\n"
    "| Task | Target | Status | Priority | Source | Path | Notes | Created |\n"
    "|---|---|---|---|---|---|---|---|\n"
)

_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
_SEP_RE = re.compile(r"^\s*\|[-| :]+\|\s*$")


# ── helpers ───────────────────────────────────────────────────────────────────

def _last_modified_iso(path: Path) -> Optional[str]:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


def _preview(path: Path, max_chars: int = _PREVIEW_CHARS) -> Optional[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars]
    except Exception as exc:
        logger.debug("Could not preview %s: %s", path, exc)
        return None


def _safe_subpath(vault_root: Path, *parts: str) -> Optional[Path]:
    try:
        resolved_root  = vault_root.resolve()
        resolved_child = vault_root.joinpath(*parts).resolve()
        if resolved_child.is_relative_to(resolved_root):
            return resolved_child
    except Exception:
        pass
    logger.warning("Path traversal rejected: %s / %s", vault_root, parts)
    return None


def _norm_esc_col(name: str) -> str:
    return _ESCALATION_COL_ALIASES.get(name.strip().lower(), name.strip().lower())


def _sanitize_cell(value: str) -> str:
    """Replace pipe chars and strip newlines for a safe Markdown table cell."""
    return (
        value
        .replace("|", "∣")
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def _line_ending(line: str) -> str:
    if line.endswith('\r\n'):
        return '\r\n'
    if line.endswith('\r'):
        return '\r'
    if line.endswith('\n'):
        return '\n'
    return ''


def _has_table_header(lines: list) -> bool:
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            return True
    return False


def _read_col_map(lines: list) -> list:
    """Return the normalized column order from the Markdown table header."""
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            raw_cols = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            return [_norm_esc_col(c) for c in raw_cols]
    return ["task", "target", "status", "priority", "source", "path", "notes", "created"]


# ── parsing ───────────────────────────────────────────────────────────────────

def _parse_table_escalations(lines: list) -> list:
    """
    Parse a Markdown pipe table for escalation items.
    Returns list of item dicts including internal _lineNum, _statusColIdx,
    _taskColIdx, and _colMap. Internal _* keys are stripped before the public
    API returns.
    """
    header_idx = None
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            header_idx = i
            break
    if header_idx is None:
        return []

    raw_cols       = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    col_map        = [_norm_esc_col(c) for c in raw_cols]
    status_col_idx = col_map.index("status") if "status" in col_map else -1
    task_col_idx   = col_map.index("task")   if "task"   in col_map else -1
    items: list    = []

    for row_idx, line in enumerate(lines[header_idx + 2:]):
        if not _ROW_RE.match(line):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        while len(cells) < len(col_map):
            cells.append("")

        esc: dict = {
            "id":       f"e{len(items) + 1}",
            "task":     "",
            "target":   None,
            "status":   "new",
            "priority": None,
            "source":   None,
            "path":     None,
            "notes":    None,
            "created":  None,
            "raw":      line.strip(),
            "_lineNum":      header_idx + 2 + row_idx,
            "_statusColIdx": status_col_idx,
            "_taskColIdx":   task_col_idx,
            "_colMap":       list(col_map),
        }

        for i, col in enumerate(col_map):
            val = cells[i] if i < len(cells) else ""
            if col == "task":
                esc["task"] = val
            elif col in ("target", "status", "priority", "source", "path", "notes", "created"):
                esc[col] = val or None

        if not esc["task"]:
            for cell in cells:
                if cell:
                    esc["task"] = cell
                    break

        if esc["task"]:
            items.append(esc)

    return items


def _strip_esc_internal(items: list) -> list:
    return [{k: v for k, v in it.items() if k in _PUBLIC_ESCALATION_FIELDS} for it in items]


# ── read ──────────────────────────────────────────────────────────────────────

def get_escalations(vault_path: str) -> dict:
    """
    Read and parse ops/escalation-queue.md.

    Safety: read-only, path validated, preview capped, no writes.
    Internal location metadata is stripped before returning.
    """
    root: Path = Path(vault_path)
    esc_path   = _safe_subpath(root, _ESCALATION_FILE)

    if esc_path is None or not esc_path.is_file():
        return {
            "path": _ESCALATION_FILE, "exists": False,
            "lastModified": None, "preview": None,
            "items": [], "parseMode": "missing",
        }

    content = _preview(esc_path, max_chars=_PARSE_CHARS)
    preview = content[:_PREVIEW_CHARS] if content else None

    if not content:
        return {
            "path": _ESCALATION_FILE, "exists": True,
            "lastModified": _last_modified_iso(esc_path),
            "preview": None, "items": [], "parseMode": "preview-only",
        }

    lines = content[:_PARSE_CHARS].splitlines()
    items = _parse_table_escalations(lines)

    return {
        "path":         _ESCALATION_FILE,
        "exists":       True,
        "lastModified": _last_modified_iso(esc_path),
        "preview":      preview,
        "items":        _strip_esc_internal(items),
        "parseMode":    "markdown-table" if items else "preview-only",
    }


# ── create starter file ───────────────────────────────────────────────────────

def create_escalation_queue_file(vault_path: str) -> dict:
    """
    Create ops/escalation-queue.md with the starter table if it is missing.

    Does not overwrite an existing file. No backup needed because no existing
    file is being modified.
    """
    root      = Path(vault_path)
    file_path = _safe_subpath(root, _ESCALATION_FILE)
    if file_path is None:
        raise ValueError("Invalid escalation queue path.")

    if file_path.exists():
        return get_escalations(vault_path)

    ops_dir = _safe_subpath(root, "ops")
    if ops_dir is None:
        raise ValueError("Invalid vault ops path.")

    try:
        ops_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_text(_STARTER_CONTENT, encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not create escalation queue file: {exc}") from exc

    logger.info("Escalation queue starter file created: %s", file_path)
    return get_escalations(vault_path)


# ── backup ────────────────────────────────────────────────────────────────────

def _backup_escalation_file(esc_path: Path) -> Path:
    """
    Create a timestamped backup under backend/data/backups/escalations/.
    Never overwrites an existing backup. Raises on I/O failure.
    """
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stem     = esc_path.stem
    ts       = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix   = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    bak_name = f"{stem}_{ts}_{suffix}.md"
    bak_path = _BACKUP_DIR / bak_name
    if bak_path.exists():
        suffix   = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        bak_path = _BACKUP_DIR / f"{stem}_{ts}_{suffix}.md"
    shutil.copy2(esc_path, bak_path)
    logger.info("Escalation queue backup created: %s", bak_path)
    return bak_path


# ── append item ───────────────────────────────────────────────────────────────

def add_escalation_item(
    vault_path: str,
    task:       str,
    target:     str,
    priority:   Optional[str] = None,
    source:     Optional[str] = None,
    path:       Optional[str] = None,
    notes:      Optional[str] = None,
) -> dict:
    """
    Append one escalation item to ops/escalation-queue.md.

    Safety contract:
    - File must already exist and contain a Markdown table header.
    - task must be non-empty.
    - target must be one of ALLOWED_ESCALATION_TARGETS.
    - priority must be high|medium|low or None/empty.
    - Pipe characters and newlines are sanitized from all cell values.
    - Backup is created before writing.
    - Only appends; never rewrites existing rows.
    - Only writes to ops/escalation-queue.md.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.

    Raises ValueError on any validation failure.
    Returns the updated escalation queue dict.
    """
    # ── validate ──────────────────────────────────────────────────────────────
    task = (task or "").strip()
    if not task:
        raise ValueError("task is required and cannot be empty.")

    for field_name, field_val in (
        ("task", task), ("source", source), ("path", path), ("notes", notes)
    ):
        if field_val and ("\n" in str(field_val) or "\r" in str(field_val)):
            raise ValueError(f"Field '{field_name}' must not contain newlines.")

    target = (target or "").strip().lower()
    if target not in ALLOWED_ESCALATION_TARGETS:
        raise ValueError(
            f"Invalid target {target!r}. "
            f"Allowed: {sorted(ALLOWED_ESCALATION_TARGETS)}"
        )

    if priority is not None:
        priority = (priority or "").strip().lower()
        if priority and priority not in ("high", "medium", "low"):
            raise ValueError(
                f"Invalid priority {priority!r}. Allowed: high, medium, low."
            )
        if not priority:
            priority = None

    # ── locate file ───────────────────────────────────────────────────────────
    root: Path = Path(vault_path)
    esc_path   = _safe_subpath(root, _ESCALATION_FILE)
    if esc_path is None:
        raise ValueError("Invalid escalation queue path.")
    if not esc_path.is_file():
        raise ValueError(
            "Escalation queue file does not exist. Create it first."
        )

    # ── read + parse ──────────────────────────────────────────────────────────
    try:
        full_content = esc_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read escalation queue file: {exc}") from exc

    lines = full_content[:_PARSE_CHARS].splitlines()
    if not _has_table_header(lines):
        raise ValueError(
            "Escalation queue file does not contain a Markdown table — cannot append. "
            "The file may be malformed."
        )

    col_map = _read_col_map(lines)
    created = date.today().isoformat()

    cell_values: dict = {
        "task":     _sanitize_cell(task),
        "target":   _sanitize_cell(target),
        "status":   "new",
        "priority": _sanitize_cell(priority or ""),
        "source":   _sanitize_cell(source   or ""),
        "path":     _sanitize_cell(path     or ""),
        "notes":    _sanitize_cell(notes    or ""),
        "created":  _sanitize_cell(created),
    }

    cells   = [cell_values.get(col, "") for col in col_map]
    new_row = '| ' + ' | '.join(cells) + ' |'

    # ── backup then append ────────────────────────────────────────────────────
    try:
        _backup_escalation_file(esc_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    append_content = full_content
    if append_content and not append_content.endswith('\n'):
        append_content += '\n'

    try:
        esc_path.write_text(append_content + new_row + '\n', encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write escalation queue file: {exc}") from exc

    logger.info("Escalation item appended: task=%r  target=%r", task, target)
    return get_escalations(vault_path)


# ── update status ─────────────────────────────────────────────────────────────

def update_escalation_status(vault_path: str, item_id: str, new_status: str) -> dict:
    """
    Update a single escalation item's status in ops/escalation-queue.md.

    Safety contract:
    - Only writes to ops/escalation-queue.md (path validated).
    - Only ALLOWED_ESCALATION_STATUSES accepted.
    - Item ID must match e<positive-integer> pattern.
    - File re-read and re-parsed on every call (no stale state).
    - Task title verified before writing (conflict detection).
    - Backup created before every write; aborted if backup fails.
    - Only the status cell is modified; all other cells preserved.
    - No other vault files are touched.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.

    Raises ValueError with a descriptive message on any safety check failure.
    Returns {"ok": True, "item": {...}, "path": str, "updatedAt": str}.
    """
    # ── validate inputs ───────────────────────────────────────────────────────
    if new_status not in ALLOWED_ESCALATION_STATUSES:
        raise ValueError(
            f"Invalid status {new_status!r}. "
            f"Allowed: {sorted(ALLOWED_ESCALATION_STATUSES)}"
        )
    if not (item_id.startswith("e") and item_id[1:].isdigit() and len(item_id) > 1):
        raise ValueError(
            f"Invalid item id {item_id!r}. Expected format: e<number> (e.g. e1)."
        )
    item_index = int(item_id[1:]) - 1
    if item_index < 0:
        raise ValueError(f"Invalid item id {item_id!r}.")

    # ── locate file ───────────────────────────────────────────────────────────
    root: Path = Path(vault_path)
    esc_path   = _safe_subpath(root, _ESCALATION_FILE)
    if esc_path is None or not esc_path.is_file():
        raise ValueError("ops/escalation-queue.md not found in vault.")

    # ── read full file ────────────────────────────────────────────────────────
    try:
        full_content = esc_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read escalation queue file: {exc}") from exc

    # ── parse ─────────────────────────────────────────────────────────────────
    lines = full_content[:_PARSE_CHARS].splitlines()
    items = _parse_table_escalations(lines)
    if not items:
        raise ValueError(
            "Escalation file format is preview-only — "
            "status editing requires a Markdown table with at least one row."
        )
    if item_index >= len(items):
        raise ValueError(
            f"Item '{item_id}' not found. File has {len(items)} item(s). "
            "Refresh and try again."
        )

    item           = items[item_index]
    status_col_idx = item["_statusColIdx"]
    task_col_idx   = item["_taskColIdx"]
    col_map        = item["_colMap"]

    if status_col_idx < 0:
        raise ValueError("No status column found in the escalation table.")

    # ── locate and verify the line ────────────────────────────────────────────
    all_lines = full_content.splitlines(keepends=True)
    line_num: int = item["_lineNum"]
    if line_num >= len(all_lines):
        raise ValueError(
            f"Item line {line_num} not found (file has {len(all_lines)} lines). "
            "File may have changed — refresh and try again."
        )

    orig_line = all_lines[line_num]
    if not _ROW_RE.match(orig_line.rstrip('\r\n')):
        raise ValueError(
            f"Line {line_num} no longer looks like a table row. "
            "File may have changed — refresh and try again."
        )

    cells = [c.strip() for c in orig_line.strip().rstrip('\r\n').strip('|').split('|')]
    if status_col_idx >= len(cells):
        raise ValueError(
            f"Status column {status_col_idx} out of range "
            f"(row has {len(cells)} cells). File may have changed."
        )

    # Conflict detection: verify task title still matches.
    if task_col_idx >= 0 and task_col_idx < len(cells):
        if cells[task_col_idx] != item["task"]:
            raise ValueError(
                "Task title mismatch — file has changed since last load. "
                "Refresh and try again."
            )

    # ── update status cell only ───────────────────────────────────────────────
    cells[status_col_idx] = new_status
    while len(cells) < len(col_map):
        cells.append("")
    new_row  = '| ' + ' | '.join(cells) + ' |'
    line_end = _line_ending(orig_line)
    new_line = new_row + line_end

    # ── backup then write ─────────────────────────────────────────────────────
    try:
        _backup_escalation_file(esc_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines[line_num] = new_line
    try:
        esc_path.write_text(''.join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write escalation queue file: {exc}") from exc

    logger.info(
        "Escalation status updated: id=%s  task=%r  %r→%r  file=%s",
        item_id, item["task"], item.get("status"), new_status, _ESCALATION_FILE,
    )

    updated_item = {
        "id":       item_id,
        "task":     item["task"],
        "target":   item["target"],
        "status":   new_status,
        "priority": item["priority"],
        "source":   item["source"],
        "path":     item["path"],
        "notes":    item["notes"],
        "created":  item["created"],
        "raw":      new_row,
    }
    return {
        "ok":        True,
        "item":      updated_item,
        "path":      _ESCALATION_FILE,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ── update editable fields ────────────────────────────────────────────────────

_EDITABLE_ESC_FIELDS = frozenset({"task", "target", "priority", "source", "path", "notes"})


def update_escalation_item(
    vault_path: str,
    item_id:    str,
    task:       str,
    target:     str,
    priority:   Optional[str] = None,
    source:     Optional[str] = None,
    path:       Optional[str] = None,
    notes:      Optional[str] = None,
) -> dict:
    """
    Update the editable fields of an existing escalation item.

    Editable fields: task, target, priority, source, path, notes.
    Preserved fields: status, created, and any unknown columns.

    Safety contract:
    - Only writes to ops/escalation-queue.md (path validated).
    - task must be non-empty.
    - target must be one of ALLOWED_ESCALATION_TARGETS.
    - priority must be high|medium|low or None/empty.
    - Item ID must match e<positive-integer> pattern.
    - Newlines rejected in all fields.
    - File re-read and re-parsed on every call (no stale state).
    - Task title verified before writing (conflict detection).
    - Backup created before every write; aborted if backup fails.
    - Status and created cells preserved exactly; unknown columns preserved.
    - No other vault files are touched.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.

    Raises ValueError with a descriptive message on any safety check failure.
    Returns {"ok": True, "item": {...}, "path": str, "updatedAt": str}.
    """
    # ── validate inputs ───────────────────────────────────────────────────────
    task = (task or "").strip()
    if not task:
        raise ValueError("task is required and cannot be empty.")

    for field_name, field_val in (
        ("task", task), ("source", source), ("path", path), ("notes", notes)
    ):
        if field_val and ("\n" in str(field_val) or "\r" in str(field_val)):
            raise ValueError(f"Field '{field_name}' must not contain newlines.")

    target = (target or "").strip().lower()
    if target not in ALLOWED_ESCALATION_TARGETS:
        raise ValueError(
            f"Invalid target {target!r}. "
            f"Allowed: {sorted(ALLOWED_ESCALATION_TARGETS)}"
        )

    if priority is not None:
        priority = (priority or "").strip().lower()
        if priority and priority not in ("high", "medium", "low"):
            raise ValueError(
                f"Invalid priority {priority!r}. Allowed: high, medium, low."
            )
        if not priority:
            priority = None

    if not (item_id.startswith("e") and item_id[1:].isdigit() and len(item_id) > 1):
        raise ValueError(
            f"Invalid item id {item_id!r}. Expected format: e<number> (e.g. e1)."
        )
    item_index = int(item_id[1:]) - 1
    if item_index < 0:
        raise ValueError(f"Invalid item id {item_id!r}.")

    # ── locate file ───────────────────────────────────────────────────────────
    root: Path = Path(vault_path)
    esc_path   = _safe_subpath(root, _ESCALATION_FILE)
    if esc_path is None or not esc_path.is_file():
        raise ValueError("ops/escalation-queue.md not found in vault.")

    # ── read full file ────────────────────────────────────────────────────────
    try:
        full_content = esc_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read escalation queue file: {exc}") from exc

    # ── parse ─────────────────────────────────────────────────────────────────
    lines = full_content[:_PARSE_CHARS].splitlines()
    items = _parse_table_escalations(lines)
    if not items:
        raise ValueError(
            "Escalation file format is preview-only — "
            "field editing requires a Markdown table with at least one row."
        )
    if item_index >= len(items):
        raise ValueError(
            f"Item '{item_id}' not found. File has {len(items)} item(s). "
            "Refresh and try again."
        )

    item        = items[item_index]
    task_col_idx = item["_taskColIdx"]
    col_map     = item["_colMap"]

    # ── locate and verify the line ────────────────────────────────────────────
    all_lines = full_content.splitlines(keepends=True)
    line_num: int = item["_lineNum"]
    if line_num >= len(all_lines):
        raise ValueError(
            f"Item line {line_num} not found (file has {len(all_lines)} lines). "
            "File may have changed — refresh and try again."
        )

    orig_line = all_lines[line_num]
    if not _ROW_RE.match(orig_line.rstrip('\r\n')):
        raise ValueError(
            f"Line {line_num} no longer looks like a table row. "
            "File may have changed — refresh and try again."
        )

    orig_cells = [c.strip() for c in orig_line.strip().rstrip('\r\n').strip('|').split('|')]

    # Conflict detection: verify task title still matches.
    if task_col_idx >= 0 and task_col_idx < len(orig_cells):
        if orig_cells[task_col_idx] != item["task"]:
            raise ValueError(
                "Task title mismatch — file has changed since last load. "
                "Refresh and try again."
            )

    # ── build new row, preserving status/created/unknown ─────────────────────
    new_values: dict = {
        "task":     _sanitize_cell(task),
        "target":   _sanitize_cell(target),
        "priority": _sanitize_cell(priority or ""),
        "source":   _sanitize_cell(source   or ""),
        "path":     _sanitize_cell(path     or ""),
        "notes":    _sanitize_cell(notes    or ""),
    }
    new_cells: list = []
    for i, col in enumerate(col_map):
        orig_val = orig_cells[i] if i < len(orig_cells) else ""
        if col in new_values:
            new_cells.append(new_values[col])
        else:
            new_cells.append(orig_val)

    new_row  = '| ' + ' | '.join(new_cells) + ' |'
    line_end = _line_ending(orig_line)
    new_line = new_row + line_end

    # ── backup then write ─────────────────────────────────────────────────────
    try:
        _backup_escalation_file(esc_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines[line_num] = new_line
    try:
        esc_path.write_text(''.join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write escalation queue file: {exc}") from exc

    logger.info(
        "Escalation item updated: id=%s  task=%r  target=%r  file=%s",
        item_id, task, target, _ESCALATION_FILE,
    )

    # Resolve status and created from the preserved cells in the new row.
    status_col_idx  = item["_statusColIdx"]
    created_col_idx = col_map.index("created") if "created" in col_map else -1
    resolved_status  = (
        new_cells[status_col_idx]
        if status_col_idx >= 0 and status_col_idx < len(new_cells)
        else item.get("status", "new")
    )
    resolved_created = (
        new_cells[created_col_idx]
        if created_col_idx >= 0 and created_col_idx < len(new_cells)
        else item.get("created")
    )

    updated_item = {
        "id":       item_id,
        "task":     new_values["task"],
        "target":   new_values["target"] or None,
        "status":   resolved_status or "new",
        "priority": new_values["priority"] or None,
        "source":   new_values["source"]   or None,
        "path":     new_values["path"]     or None,
        "notes":    new_values["notes"]    or None,
        "created":  resolved_created       or None,
        "raw":      new_row,
    }
    return {
        "ok":        True,
        "item":      updated_item,
        "path":      _ESCALATION_FILE,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
