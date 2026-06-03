"""
Read-only vault inspection module for Brain UI.

Safety rules — strictly enforced:
- READ ONLY. No writes, deletes, moves, renames, or modifications.
- All paths are resolved and validated to stay inside the configured vault root.
- Traversal is prevented via Path.is_relative_to(); no user input reaches path resolution.
- Previews are capped at 2000 chars; full file content is never forwarded.
- Missing folders return empty results rather than raising.
- Encoding errors are handled safely via errors='replace'.
- No vault contents are parsed, executed, or indexed.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PREVIEW_CHARS = 2000
_PARSE_CHARS   = 50_000   # max chars fed to the task parser

# Ops files the UI is allowed to read.
_OPS_ALLOWED: frozenset = frozenset({"resume-pipeline", "backfill", "tasks"})

# Task file candidates, in priority order.
_TASK_CANDIDATES = ("ops/task-db.md", "ops/tasks.md")


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


# ── public API ────────────────────────────────────────────────────────────────

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
    # Try wiki/projects/hackathons first, fall back to wiki/hackathons
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
    """Parse a Markdown pipe table. Returns list of task dicts, or [] if no table found."""
    header_idx = None
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            header_idx = i
            break
    if header_idx is None:
        return []

    raw_cols   = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    col_map    = [_norm_col(c) for c in raw_cols]
    tasks: list = []

    for line in lines[header_idx + 2:]:
        if not _ROW_RE.match(line):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        while len(cells) < len(col_map):
            cells.append("")

        task: dict = {
            "id":       f"t{len(tasks) + 1}",
            "title":    "",
            "status":   "",
            "area":     None,
            "priority": None,
            "due":      None,
            "source":   None,
            "raw":      line.strip(),
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
    """Parse Markdown checkbox lines. Returns list of task dicts."""
    tasks: list = []
    for m in _CB_RE.finditer(content):
        checked = m.group(1).lower() == "x"
        tasks.append({
            "id":       f"t{len(tasks) + 1}",
            "title":    m.group(2).strip(),
            "status":   "done" if checked else "todo",
            "area":     None,
            "priority": None,
            "due":      None,
            "source":   None,
            "raw":      m.group(0).strip(),
        })
    return tasks


def _parse_tasks(content: str) -> tuple:  # (list[dict], str)
    """
    Try table parsing, then checklist, then fall back to preview-only.
    Returns (tasks, parse_mode).
    """
    lines  = content[:_PARSE_CHARS].splitlines()
    tasks  = _parse_table_tasks(lines)
    if tasks:
        return tasks, "markdown-table"
    tasks = _parse_checklist_tasks(content[:_PARSE_CHARS])
    if tasks:
        return tasks, "checklist"
    return [], "preview-only"


def get_tasks(vault_path: str) -> dict:
    """
    Read and parse the vault task file.

    Tries ops/task-db.md first, then ops/tasks.md.
    Parses Markdown tables, checklists, or falls back to preview-only.

    Safety: read-only, path validated, preview capped, no writes.
    """
    root = Path(vault_path)

    task_path: Optional[Path] = None
    rel_path = _TASK_CANDIDATES[0]  # default for "not found" response

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
        "tasks":        tasks,
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
