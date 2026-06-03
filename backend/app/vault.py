"""
vault.py — Read-only vault inspection + safe task status editing.

Read-only operations:
- Scans wiki/raw directories for projects, courses, hackathons, business entities.
- Reads ops files (resume-pipeline, backfill, tasks).
- Parses task files (Markdown table or checklist).

Write operation (task status only):
- update_task_status(): updates a single task's status field.
- Creates a timestamped backup before every write.
- Only writes to ops/task-db.md or ops/tasks.md.

Safety rules strictly enforced:
- READ ONLY for all operations except update_task_status().
- All paths resolved and validated to stay inside the configured vault root.
- Traversal prevented via Path.is_relative_to().
- Previews capped at 2000 chars; full file content never forwarded.
- Only allowed task statuses accepted; unknown IDs rejected.
- Conflict detection: re-reads + re-parses file before writing; verifies target line.
- Backup created before every write; backups never overwritten.
- No other vault files touched.
- Encoding errors handled safely via errors='replace'.
"""

import logging
import random
import re
import shutil
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PREVIEW_CHARS = 2000
_PARSE_CHARS   = 50_000   # max chars fed to the task parser

_OPS_ALLOWED: frozenset = frozenset({"resume-pipeline", "backfill", "tasks"})
_TASK_CANDIDATES = ("ops/task-db.md", "ops/tasks.md")

# Allowed statuses for the status-update endpoint.
ALLOWED_TASK_STATUSES: frozenset = frozenset({"todo", "in progress", "blocked", "done"})

# Public task fields exposed via the API.  Internal _* keys are stripped before returning.
_PUBLIC_TASK_FIELDS = frozenset({"id", "title", "status", "area", "priority", "due", "source", "raw"})

# Backup directory: backend/data/backups/tasks/
_BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups" / "tasks"


# ── helpers ───────────────────────────────────────────────────────────────────

def _last_modified_iso(path: Path) -> Optional[str]:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


def _preview(path: Path, max_chars: int = _PREVIEW_CHARS) -> Optional[str]:
    """Read first max_chars characters. Handles encoding errors. Returns None on failure."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars]
    except Exception as exc:
        logger.debug("Could not preview %s: %s", path, exc)
        return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "item"


def _safe_subpath(vault_root: Path, *parts: str) -> Optional[Path]:
    """
    Resolve vault_root / parts and verify the result stays inside vault_root.
    Returns None if traversal is detected or resolution fails.
    """
    try:
        resolved_root  = vault_root.resolve()
        resolved_child = vault_root.joinpath(*parts).resolve()
        if resolved_child.is_relative_to(resolved_root):
            return resolved_child
    except Exception:
        pass
    logger.warning("Path traversal rejected: %s / %s", vault_root, parts)
    return None


# ── scanner helpers ───────────────────────────────────────────────────────────

def _scan_wiki(vault_root: Path, subpath: str) -> dict:
    """
    Scan vault_root/subpath for top-level .md files.
    Returns {normalized_stem: {display_name, path, last_modified, preview}}.
    """
    items: dict = {}
    folder = _safe_subpath(vault_root, subpath)
    if folder is None or not folder.is_dir():
        return items
    try:
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.suffix.lower() == ".md":
                stem = p.stem
                key  = stem.lower()
                rel  = p.relative_to(vault_root).as_posix()
                items[key] = {
                    "display_name":  stem,
                    "path":          rel,
                    "last_modified": _last_modified_iso(p),
                    "preview":       _preview(p),
                }
    except Exception as exc:
        logger.warning("Could not scan wiki folder %s: %s", folder, exc)
    return items


def _scan_raw(vault_root: Path, subpath: str) -> dict:
    """
    Scan vault_root/subpath for top-level subdirectories.
    Returns {normalized_name: {display_name, path, last_modified}}.
    """
    items: dict = {}
    folder = _safe_subpath(vault_root, subpath)
    if folder is None or not folder.is_dir():
        return items
    try:
        for p in sorted(folder.iterdir()):
            if p.is_dir():
                name = p.name
                key  = name.lower()
                rel  = p.relative_to(vault_root).as_posix() + "/"
                items[key] = {
                    "display_name":  name,
                    "path":          rel,
                    "last_modified": _last_modified_iso(p),
                }
    except Exception as exc:
        logger.warning("Could not scan raw folder %s: %s", folder, exc)
    return items


def _merge(wiki_items: dict, raw_items: dict) -> list:
    """
    Merge wiki (.md) and raw (directory) items by normalized name.
    Items with the same lowercase key are combined; unmatched items appear alone.
    Result is sorted alphabetically by display name.
    """
    all_keys  = sorted(set(wiki_items.keys()) | set(raw_items.keys()))
    seen_ids: dict = {}
    result   = []

    for key in all_keys:
        wiki = wiki_items.get(key)
        raw  = raw_items.get(key)
        display_name = wiki["display_name"] if wiki else raw["display_name"]

        base_id = _slug(display_name)
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            item_id = f"{base_id}-{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1
            item_id = base_id

        result.append({
            "id":           item_id,
            "name":         display_name,
            "wikiPath":     wiki["path"]          if wiki else None,
            "rawPath":      raw["path"]           if raw  else None,
            "lastModified": wiki["last_modified"] if wiki else (raw["last_modified"] if raw else None),
            "preview":      wiki["preview"]       if wiki else None,
        })

    return result


# ── public API (read-only domain scans) ──────────────────────────────────────

def get_vault_summary(vault_path: str) -> dict:
    """Return vault availability and presence of standard top-level folders."""
    root   = Path(vault_path)
    exists = root.is_dir()
    folders: dict = {}
    if exists:
        for name in ("raw", "wiki", "ops", "schema", "templates"):
            folders[name] = (root / name).is_dir()
    return {
        "ok":        exists,
        "vaultPath": vault_path,
        "exists":    exists,
        "folders":   folders,
    }


def get_projects(vault_path: str) -> list:
    root = Path(vault_path)
    if not root.is_dir():
        return []
    wiki = _scan_wiki(root, "wiki/projects")
    raw  = _scan_raw(root,  "raw/projects")
    items = _merge(wiki, raw)
    for item in items:
        item["status"] = "unknown"
    return items


def get_courses(vault_path: str) -> list:
    root = Path(vault_path)
    if not root.is_dir():
        return []
    wiki = _scan_wiki(root, "wiki/courses")
    raw  = _scan_raw(root,  "raw/courses")
    return _merge(wiki, raw)


def get_hackathons(vault_path: str) -> list:
    root = Path(vault_path)
    if not root.is_dir():
        return []
    wiki = _scan_wiki(root, "wiki/projects/hackathons")
    if not wiki:
        wiki = _scan_wiki(root, "wiki/hackathons")
    raw = _scan_raw(root, "raw/hackathons")
    return _merge(wiki, raw)


def get_business(vault_path: str) -> list:
    root = Path(vault_path)
    if not root.is_dir():
        return []
    wiki = _scan_wiki(root, "wiki/business")
    raw  = _scan_raw(root,  "raw/business")
    return _merge(wiki, raw)


# ── task parsing ──────────────────────────────────────────────────────────────

_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
_SEP_RE = re.compile(r"^\s*\|[-| :]+\|\s*$")
_CB_RE  = re.compile(r"^[-*]\s+\[( |x|X)\]\s+(.+)", re.MULTILINE)

_COL_ALIASES: dict = {
    "title": "title", "task": "title", "name": "title",
    "status": "status", "state": "status",
    "area": "area", "project": "area", "domain": "area", "category": "area",
    "priority": "priority", "pri": "priority",
    "due": "due", "date": "due", "deadline": "due",
    "source": "source", "link": "source", "origin": "source",
}


def _norm_col(name: str) -> str:
    return _COL_ALIASES.get(name.strip().lower(), name.strip().lower())


def _parse_table_tasks(lines: list) -> list:
    """
    Parse a Markdown pipe table.
    Returns list of task dicts including internal _lineNum, _statusColIdx, _colMap.
    Internal _* fields are stripped before the public API returns.
    """
    header_idx = None
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            header_idx = i
            break
    if header_idx is None:
        return []

    raw_cols        = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    col_map         = [_norm_col(c) for c in raw_cols]
    status_col_idx  = col_map.index("status") if "status" in col_map else -1
    tasks: list     = []

    for row_idx, line in enumerate(lines[header_idx + 2:]):
        if not _ROW_RE.match(line):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        while len(cells) < len(col_map):
            cells.append("")

        task: dict = {
            "id":              f"t{len(tasks) + 1}",
            "title":           "",
            "status":          "",
            "area":            None,
            "priority":        None,
            "due":             None,
            "source":          None,
            "raw":             line.strip(),
            # Internal location metadata — stripped before public API returns.
            "_lineNum":        header_idx + 2 + row_idx,
            "_statusColIdx":   status_col_idx,
            "_colMap":         list(col_map),
        }
        title_set = False
        for i, col in enumerate(col_map):
            val = cells[i] if i < len(cells) else ""
            if col == "title":
                task["title"] = val
                title_set = True
            elif col in ("status", "area", "priority", "due", "source"):
                task[col] = val or None

        if not title_set or not task["title"]:
            for cell in cells:
                if cell:
                    task["title"] = cell
                    break

        if task["title"]:
            tasks.append(task)

    return tasks


def _parse_checklist_tasks(content: str) -> list:
    """
    Parse Markdown checkbox lines.
    Returns list of task dicts including internal _lineNum.
    Internal _* fields are stripped before the public API returns.
    """
    tasks: list = []
    for m in _CB_RE.finditer(content):
        checked  = m.group(1).lower() == "x"
        line_num = content[:m.start()].count('\n')
        tasks.append({
            "id":       f"t{len(tasks) + 1}",
            "title":    m.group(2).strip(),
            "status":   "done" if checked else "todo",
            "area":     None,
            "priority": None,
            "due":      None,
            "source":   None,
            "raw":      m.group(0).strip(),
            # Internal location metadata.
            "_lineNum": line_num,
        })
    return tasks


def _parse_tasks(content: str) -> tuple:
    """
    Try table parsing, then checklist, then fall back to preview-only.
    Returns (tasks_with_internal_fields, parse_mode).
    """
    lines  = content[:_PARSE_CHARS].splitlines()
    tasks  = _parse_table_tasks(lines)
    if tasks:
        return tasks, "markdown-table"
    tasks = _parse_checklist_tasks(content[:_PARSE_CHARS])
    if tasks:
        return tasks, "checklist"
    return [], "preview-only"


def _strip_internal(tasks: list) -> list:
    """Return tasks with only public fields; internal _* keys removed."""
    return [{k: v for k, v in t.items() if k in _PUBLIC_TASK_FIELDS} for t in tasks]


def get_tasks(vault_path: str) -> dict:
    """
    Read and parse the vault task file.

    Tries ops/task-db.md first, then ops/tasks.md.
    Parses Markdown tables, checklists, or falls back to preview-only.

    Safety: read-only, path validated, preview capped, no writes.
    Internal location metadata is stripped before returning.
    """
    root = Path(vault_path)

    task_path: Optional[Path] = None
    rel_path = _TASK_CANDIDATES[0]

    for candidate in _TASK_CANDIDATES:
        p = _safe_subpath(root, candidate)
        if p is not None and p.is_file():
            task_path = p
            rel_path  = candidate
            break

    if task_path is None:
        return {
            "path":         rel_path,
            "exists":       False,
            "lastModified": None,
            "preview":      None,
            "tasks":        [],
            "parseMode":    "preview-only",
        }

    content = _preview(task_path, max_chars=_PARSE_CHARS)
    preview = content[:_PREVIEW_CHARS] if content else None

    if not content:
        return {
            "path":         rel_path,
            "exists":       True,
            "lastModified": _last_modified_iso(task_path),
            "preview":      None,
            "tasks":        [],
            "parseMode":    "preview-only",
        }

    tasks, parse_mode = _parse_tasks(content)

    return {
        "path":         rel_path,
        "exists":       True,
        "lastModified": _last_modified_iso(task_path),
        "preview":      preview,
        "tasks":        _strip_internal(tasks),  # never expose _lineNum etc.
        "parseMode":    parse_mode,
    }


def get_ops_file(vault_path: str, kind: str) -> dict:
    """
    Read a single known ops file: resume-pipeline, backfill, or tasks.
    The kind parameter is validated against an allowlist before any path is constructed.
    Returns path, exists, preview, lastModified.
    Raises ValueError for unknown kinds (caller converts to HTTP 400).
    """
    if kind not in _OPS_ALLOWED:
        raise ValueError(f"Unknown ops kind: {kind!r}. Allowed: {sorted(_OPS_ALLOWED)}")

    rel  = f"ops/{kind}.md"
    root = Path(vault_path)
    p    = _safe_subpath(root, rel)

    if p is None:
        return {"path": rel, "exists": False, "preview": None, "lastModified": None}

    return {
        "path":         rel,
        "exists":       p.is_file(),
        "preview":      _preview(p)           if p.is_file() else None,
        "lastModified": _last_modified_iso(p) if p.is_file() else None,
    }


# ── task status write ─────────────────────────────────────────────────────────

def _backup_task_file(task_path: Path) -> Path:
    """
    Create a timestamped backup of the task file under backend/data/backups/tasks/.
    Backup filenames include the stem, a UTC timestamp, and a 4-character random suffix.
    Backups are never overwritten.

    Returns the backup path on success. Raises on any I/O failure.
    """
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stem      = task_path.stem
    ts        = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix    = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    bak_name  = f"{stem}_{ts}_{suffix}.md"
    bak_path  = _BACKUP_DIR / bak_name

    # Safety: never overwrite an existing backup.
    if bak_path.exists():
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        bak_path = _BACKUP_DIR / f"{stem}_{ts}_{suffix}.md"

    shutil.copy2(task_path, bak_path)
    logger.info("Task backup created: %s", bak_path)
    return bak_path


def update_task_status(vault_path: str, task_id: str, new_status: str) -> dict:
    """
    Update a single task's status in the vault task file.

    Safety contract:
    - Only writes to ops/task-db.md or ops/tasks.md (path validated).
    - Only ALLOWED_TASK_STATUSES are accepted.
    - Task ID must match t<positive-integer> pattern.
    - File is re-read and re-parsed on every call (no stale state).
    - Target line is verified against the original task raw content before write.
    - Backup is created before every write; backup never overwrites existing file.
    - If ANY check fails, the file is NOT modified.
    - No other vault files are touched.

    Raises ValueError with a descriptive message on any safety check failure.
    Returns {"ok": True, "task": {...public task dict...}, "path": str, "updatedAt": str}.
    """
    # ── validate inputs ───────────────────────────────────────────────────────
    if new_status not in ALLOWED_TASK_STATUSES:
        raise ValueError(
            f"Invalid status {new_status!r}. Allowed: {sorted(ALLOWED_TASK_STATUSES)}"
        )

    if not (task_id.startswith("t") and task_id[1:].isdigit() and len(task_id) > 1):
        raise ValueError(f"Invalid task id {task_id!r}. Expected format: t<number> (e.g. t1).")
    task_index = int(task_id[1:]) - 1   # "t1" → 0
    if task_index < 0:
        raise ValueError(f"Invalid task id {task_id!r}.")

    # ── locate task file ──────────────────────────────────────────────────────
    root: Path = Path(vault_path)
    task_path: Optional[Path] = None
    rel_path = _TASK_CANDIDATES[0]

    for candidate in _TASK_CANDIDATES:
        p = _safe_subpath(root, candidate)
        if p is not None and p.is_file():
            task_path = p
            rel_path  = candidate
            break

    if task_path is None:
        raise ValueError("No task file found in vault ops/.")

    # ── read full file ────────────────────────────────────────────────────────
    try:
        full_content = task_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read task file: {exc}") from exc

    # ── parse (with internal location metadata) ───────────────────────────────
    parse_content = full_content[:_PARSE_CHARS]
    lines         = parse_content.splitlines()
    table_tasks   = _parse_table_tasks(lines)

    if table_tasks:
        parse_mode = "markdown-table"
        tasks      = table_tasks
    else:
        cl_tasks = _parse_checklist_tasks(parse_content)
        if cl_tasks:
            parse_mode = "checklist"
            tasks      = cl_tasks
        else:
            raise ValueError(
                "Task file format is preview-only — status editing requires a "
                "Markdown table or checklist format."
            )

    # ── find the target task ──────────────────────────────────────────────────
    if task_index >= len(tasks):
        raise ValueError(
            f"Task '{task_id}' not found. File has {len(tasks)} task(s). "
            "Refresh the page and try again."
        )

    task = tasks[task_index]

    # ── split full content into lines (preserving line endings for write-back) ─
    all_lines = full_content.splitlines(keepends=True)

    line_num: int = task["_lineNum"]
    if line_num >= len(all_lines):
        raise ValueError(
            f"Task line {line_num} not found (file has {len(all_lines)} lines). "
            "File may have changed — refresh and try again."
        )

    orig_line = all_lines[line_num]

    # ── apply the edit based on parse mode ────────────────────────────────────
    if parse_mode == "markdown-table":
        status_col_idx: int = task["_statusColIdx"]
        col_map: list       = task["_colMap"]

        if status_col_idx < 0:
            raise ValueError("No status column found in the task table.")

        # Verify the line is still a table row.
        if not _ROW_RE.match(orig_line.rstrip('\r\n')):
            raise ValueError(
                f"Line {line_num} no longer looks like a table row. "
                "File may have changed — refresh and try again."
            )

        # Split into cells and verify title matches (conflict detection).
        cells = [c.strip() for c in orig_line.strip().rstrip('\r\n').strip('|').split('|')]
        if status_col_idx >= len(cells):
            raise ValueError(
                f"Status column index {status_col_idx} is out of range "
                f"(row has {len(cells)} cells). File may have changed."
            )

        if "title" in col_map:
            title_idx = col_map.index("title")
            if title_idx < len(cells) and cells[title_idx] != task["title"]:
                raise ValueError(
                    "Task title mismatch — file has changed since last load. "
                    "Refresh and try again."
                )

        # Update only the status cell.
        cells[status_col_idx] = new_status
        while len(cells) < len(col_map):
            cells.append("")

        # Reconstruct row, preserving the original line ending.
        new_row    = '| ' + ' | '.join(cells) + ' |'
        line_end   = _line_ending(orig_line)
        new_line   = new_row + line_end

        updated_raw = new_row

    elif parse_mode == "checklist":
        # Verify the line is still a checkbox line.
        stripped = orig_line.rstrip('\r\n')
        if not re.match(r"^[-*]\s+\[( |x|X)\]", stripped):
            raise ValueError(
                f"Line {line_num} no longer looks like a checkbox. "
                "File may have changed — refresh and try again."
            )

        # Verify title (conflict detection).
        m = _CB_RE.match(stripped)
        if m and m.group(2).strip() != task["title"]:
            raise ValueError(
                "Task title mismatch — file has changed since last load. "
                "Refresh and try again."
            )

        # Replace checkbox marker; preserve the rest of the line exactly.
        new_check  = 'x' if new_status == 'done' else ' '
        new_stripped = re.sub(r'\[( |x|X)\]', f'[{new_check}]', stripped, count=1)
        line_end   = _line_ending(orig_line)
        new_line   = new_stripped + line_end

        updated_raw = new_stripped.strip()

    else:
        raise ValueError("Unsupported parse mode for editing.")

    # ── backup then write ─────────────────────────────────────────────────────
    try:
        _backup_task_file(task_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines[line_num] = new_line
    try:
        task_path.write_text(''.join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write task file: {exc}") from exc

    logger.info(
        "Task status updated: id=%s  title=%r  status=%r→%r  file=%s",
        task_id, task["title"], task["status"], new_status, rel_path,
    )

    updated_task = {
        "id":       task_id,
        "title":    task["title"],
        "status":   new_status,
        "area":     task["area"],
        "priority": task["priority"],
        "due":      task["due"],
        "source":   task["source"],
        "raw":      updated_raw,
    }

    return {
        "ok":        True,
        "task":      updated_task,
        "path":      rel_path,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _line_ending(line: str) -> str:
    """Extract the line ending from a raw line string."""
    if line.endswith('\r\n'):
        return '\r\n'
    if line.endswith('\r'):
        return '\r'
    if line.endswith('\n'):
        return '\n'
    return ''
