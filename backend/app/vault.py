"""
vault.py — Read-only vault inspection + safe task status editing + safe task creation.

Read-only operations:
- Scans wiki/raw directories for projects, courses, hackathons, business entities.
- Reads ops files (resume-pipeline, backfill, tasks).
- Parses task files (Markdown table or checklist).

Write operations:
- update_task_status(): updates a single task's status field.
- create_task(): appends a new task row/item to the task file.
  - If no task file exists, creates ops/task-db.md with a default table header.
  - Only appends; never rewrites existing task content.
  - Creates a timestamped backup before every write.
  - Only writes to ops/task-db.md or ops/tasks.md.

Safety rules strictly enforced:
- READ ONLY for all operations except the two write functions above.
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

from app.write_lock import serialized_vault_write
from app.vault_paths import precondition_token, safe_subpath, write_text_atomic

logger = logging.getLogger(__name__)

_PREVIEW_CHARS = 2000
_PARSE_CHARS   = 50_000   # max chars fed to the task parser

_OPS_ALLOWED: frozenset = frozenset({"resume-pipeline", "backfill", "tasks"})
_TASK_CANDIDATES = ("ops/task-db.md", "ops/tasks.md")

# Allowed statuses for the status-update and create endpoints.
# "archived" closes PRD §25's "Archive completed tasks": a done task can be moved
# out of the working view without deleting the row.
ALLOWED_TASK_STATUSES: frozenset = frozenset({
    "todo", "in progress", "blocked", "done", "archived",
})

# Allowed priorities for task creation.
ALLOWED_TASK_PRIORITIES: frozenset = frozenset({"low", "medium", "high"})

# Default table written when no task file exists and the user creates the first task.
_DEFAULT_TABLE_HEADER = (
    "| Title | Status | Area | Priority | Due | Source |\n"
    "|---|---|---|---|---|---|\n"
)
_DEFAULT_TABLE_COLS = ["title", "status", "area", "priority", "due", "source"]

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


def _read_note(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.debug("Could not read %s: %s", path, exc)
        return None


def _preview(path: Path, max_chars: int = _PREVIEW_CHARS) -> Optional[str]:
    """First max_chars characters of the note BODY, excluding frontmatter.

    Previously returned the raw head of the file. The moment a note gains a
    frontmatter block, that would render YAML as the card's preview text on every
    entity page — so stripping it has to land with the first write, not after.
    """
    text = _read_note(path)
    if text is None:
        return None
    return _note_body(text)[:max_chars]


def _note_body(text: str) -> str:
    from app.frontmatter import read_frontmatter
    return read_frontmatter(text).body.lstrip("\n")


def _note_metadata(text: str) -> dict:
    """Entity metadata from a note's frontmatter (PRD §35.1 Work Item).

    Every field is optional. A note without frontmatter — which is every note in
    the vault today — yields all-None and renders exactly as it did before.
    """
    from app.frontmatter import read_frontmatter, get_str

    fm = read_frontmatter(text)
    domain = get_str(fm, "domain")
    status = get_str(fm, "status")
    return {
        "domain":    domain.lower() if domain else None,
        "status":    status.lower() if status else None,
        "repoPath":  get_str(fm, "repo_path", "repo"),
        "githubUrl": get_str(fm, "github_url", "github"),
        "demoUrl":   get_str(fm, "demo_url", "demo"),
        "createdAt": get_str(fm, "created_at", "created"),
        "updatedAt": get_str(fm, "updated_at", "updated"),
        "frontmatterError": fm.error,
    }


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "item"


# Shared with the other vault-writing modules; see app/vault_paths.py.
_safe_subpath = safe_subpath


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
                text = _read_note(p)
                items[key] = {
                    "display_name":  stem,
                    "path":          rel,
                    "last_modified": _last_modified_iso(p),
                    # Read once, derive both — these notes can be large.
                    "preview":       _note_body(text)[:_PREVIEW_CHARS] if text is not None else None,
                    "metadata":      _note_metadata(text) if text is not None else {},
                    "version":       precondition_token(p),
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

        # Additive: every metadata field defaults to None, so a note without
        # frontmatter produces exactly the shape this returned before.
        meta = (wiki or {}).get("metadata") or {}
        result.append({
            "id":           item_id,
            "name":         display_name,
            "wikiPath":     wiki["path"]          if wiki else None,
            "rawPath":      raw["path"]           if raw  else None,
            "lastModified": wiki["last_modified"] if wiki else (raw["last_modified"] if raw else None),
            "preview":      wiki["preview"]       if wiki else None,
            "domain":       meta.get("domain"),
            "status":       meta.get("status"),
            "repoPath":     meta.get("repoPath"),
            "githubUrl":    meta.get("githubUrl"),
            "demoUrl":      meta.get("demoUrl"),
            "createdAt":    meta.get("createdAt"),
            "updatedAt":    meta.get("updatedAt"),
            "frontmatterError": meta.get("frontmatterError"),
            "version":      (wiki or {}).get("version"),
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
        # "unknown" was hardcoded here; it now comes from the note's frontmatter
        # and falls back only when the note does not declare one.
        item.setdefault("status", None)
        if not item.get("status"):
            item["status"] = "unknown"
        item.setdefault("domain", "project")
        if not item.get("domain"):
            item["domain"] = "project"
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


# ══════════════════════════════════════════════════════════════════════════════
# Entity frontmatter writes (PRD §35.1 Work Item)
# ══════════════════════════════════════════════════════════════════════════════

_ENTITY_BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups" / "entities"

ALLOWED_ENTITY_STATUSES: frozenset = frozenset({
    "active", "paused", "blocked", "shipped", "archived", "unknown",
})
# Deliberately the same vocabulary as ALLOWED_BACKFILL_TYPES rather than a
# parallel enum. Spelled out here because that set is defined further down the
# file; test_entity_domains_match_backfill_types keeps the two in lockstep.
ALLOWED_ENTITY_DOMAINS: frozenset = frozenset({
    "project", "repo", "hackathon", "course", "business", "other",
})

_ENTITY_WIKI_FOLDERS = {
    "project":   "wiki/projects",
    "course":    "wiki/courses",
    "hackathon": "wiki/projects/hackathons",
    "business":  "wiki/business",
}

_EDITABLE_ENTITY_FIELDS = ("status", "domain", "repo_path", "github_url", "demo_url")


class EntityVersionConflict(RuntimeError):
    """The note changed on disk between the read and the write."""


def _backup_entity_note(note_path: Path) -> Path:
    _ENTITY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    bak = _ENTITY_BACKUP_DIR / f"{note_path.stem}_{ts}_{suffix}.md"
    if bak.exists():
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        bak = _ENTITY_BACKUP_DIR / f"{note_path.stem}_{ts}_{suffix}.md"
    shutil.copy2(note_path, bak)
    logger.info("Entity note backup created: %s", bak)
    return bak


# ── schema documents (PRD §19) ───────────────────────────────────────────────

_SCHEMA_SOURCE_DIR = Path(__file__).parent.parent / "schema"

# Canonical copies live in the repo so they stay version-controlled next to the
# code that applies them. Installing copies into the vault, never the reverse.
_INSTALLABLE_SCHEMA_DOCS = {
    "classification-rules": "classification-rules.md",
}


def schema_doc_status(vault_path: str, name: str) -> dict:
    """Whether a schema document is installed in the vault. Read-only."""
    if name not in _INSTALLABLE_SCHEMA_DOCS:
        raise ValueError(f"Unknown schema document {name!r}.")
    filename = _INSTALLABLE_SCHEMA_DOCS[name]
    target = _safe_subpath(Path(vault_path), "schema", filename)
    source = _SCHEMA_SOURCE_DIR / filename
    return {
        "name": name,
        "path": f"schema/{filename}",
        "installed": bool(target and target.is_file()),
        "sourceAvailable": source.is_file(),
        "lastModified": _last_modified_iso(target) if target and target.is_file() else None,
    }


@serialized_vault_write
def install_schema_doc(vault_path: str, name: str, overwrite: bool = False) -> dict:
    """Copy a schema document into the vault.

    Refuses to overwrite by default: the user may have edited their copy, and
    silently replacing it would discard their notes. Overwriting is an explicit
    choice, and it backs the existing file up first.
    """
    if name not in _INSTALLABLE_SCHEMA_DOCS:
        raise ValueError(f"Unknown schema document {name!r}.")
    filename = _INSTALLABLE_SCHEMA_DOCS[name]
    source = _SCHEMA_SOURCE_DIR / filename
    if not source.is_file():
        raise ValueError(f"Schema source is missing from the app: {filename}")

    root = Path(vault_path)
    if not root.is_dir():
        raise ValueError(f"Vault path is not a directory: {vault_path}")

    schema_dir = _safe_subpath(root, "schema")
    target = _safe_subpath(root, "schema", filename)
    if schema_dir is None or target is None:
        raise ValueError("Rejected path outside the vault.")

    if target.is_file() and not overwrite:
        return {"ok": True, "installed": False, "path": f"schema/{filename}",
                "reason": "Already present; not overwritten."}

    schema_dir.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        _backup_entity_note(target)

    write_text_atomic(target, source.read_text(encoding="utf-8"))
    logger.info("Schema document installed: schema/%s", filename)
    return {"ok": True, "installed": True, "path": f"schema/{filename}"}


@serialized_vault_write
def update_entity_metadata(
    vault_path: str,
    entity_type: str,
    wiki_path: str,
    updates: dict,
    expected_version: Optional[str] = None,
) -> dict:
    """Update a wiki note's frontmatter. Body text is never touched.

    `expected_version` is the load-bearing guard, not the lock.

    These notes live in the user's Obsidian vault and Obsidian AUTOSAVES. Every
    other writer in this app targets ops/*.md tables the user rarely edits
    mid-session; wiki notes are the opposite. Without a precondition the failure
    is silent and total: the UI reads the note, the user types a paragraph in
    Obsidian, the UI writes back stale content, and the paragraph is gone. The
    backup would hold their good text, but nobody would know to look.

    @serialized_vault_write only serializes OUR writers against each other —
    Obsidian does not take that lock — so the mtime check is what actually
    catches an external edit.
    """
    root = Path(vault_path)
    if not root.is_dir():
        raise ValueError(f"Vault path is not a directory: {vault_path}")

    entity_type = (entity_type or "").strip().lower()
    if entity_type not in _ENTITY_WIKI_FOLDERS:
        raise ValueError(
            f"Unknown entity type {entity_type!r}. "
            f"Allowed: {sorted(_ENTITY_WIKI_FOLDERS)}"
        )

    rel = (wiki_path or "").strip().replace("\\", "/")
    if not rel.endswith(".md"):
        raise ValueError("wikiPath must point at a Markdown note.")
    expected_prefix = _ENTITY_WIKI_FOLDERS[entity_type]
    if not rel.startswith(f"{expected_prefix}/"):
        raise ValueError(
            f"A {entity_type} note must live under {expected_prefix}/ (got {rel!r})."
        )

    note_path = _safe_subpath(root, rel)
    if note_path is None:
        raise ValueError("Rejected path outside the vault.")
    if not note_path.is_file():
        raise ValueError(f"Note not found: {rel}")

    clean: dict = {}
    for field in _EDITABLE_ENTITY_FIELDS:
        if field not in updates:
            continue
        value = updates[field]
        if value is None or (isinstance(value, str) and not value.strip()):
            clean[field] = None
            continue
        value = " ".join(str(value).split())
        if field == "status" and value.lower() not in ALLOWED_ENTITY_STATUSES:
            raise ValueError(
                f"Invalid status {value!r}. Allowed: {sorted(ALLOWED_ENTITY_STATUSES)}"
            )
        if field == "domain" and value.lower() not in ALLOWED_ENTITY_DOMAINS:
            raise ValueError(
                f"Invalid domain {value!r}. Allowed: {sorted(ALLOWED_ENTITY_DOMAINS)}"
            )
        if field in ("github_url", "demo_url") and not value.lower().startswith(("http://", "https://")):
            raise ValueError(f"{field} must be an http(s) URL.")
        clean[field] = value.lower() if field in ("status", "domain") else value

    if not clean:
        raise ValueError("No editable fields supplied.")

    current_version = precondition_token(note_path)
    if expected_version is not None and current_version != expected_version:
        raise EntityVersionConflict(
            "This note changed on disk since it was read — most likely edited in "
            "Obsidian. Reload the entity and re-apply the change so nothing is lost."
        )

    original = _read_note(note_path)
    if original is None:
        raise ValueError(f"Could not read note: {rel}")

    from app.frontmatter import write_frontmatter
    updated = write_frontmatter(original, clean)
    if updated == original:
        return {
            "ok": True, "path": rel, "changed": False,
            "version": current_version,
            "updatedAt": _last_modified_iso(note_path),
        }

    _backup_entity_note(note_path)
    write_text_atomic(note_path, updated)

    logger.info("Entity metadata updated: %s (%s)", rel, ", ".join(sorted(clean)))
    return {
        "ok": True,
        "path": rel,
        "changed": True,
        "fields": sorted(clean),
        "version": precondition_token(note_path),
        "updatedAt": _last_modified_iso(note_path),
    }


@serialized_vault_write
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


# ── backfill parsing + write ───────────────────────────────────────────────────

_BACKFILL_CANDIDATES = ("ops/backfill.md", "ops/backfill-last-year.md")
_BACKFILL_PRIMARY    = "ops/backfill.md"
_BACKFILL_BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups" / "backfill"
_PARSE_CHARS_BF      = 50_000

# PRD §27 names: Not started / Needs inspection / Queued / In progress /
# Archived / Skipped / Escalated. These are the lowercase working equivalents.
# "escalated" was missing despite a live escalation queue, so an item handed to
# Claude Code or OpenCode had no state to sit in.
ALLOWED_BACKFILL_STATUSES: frozenset = frozenset({
    "new", "triaged", "queued", "in-progress", "done", "archived",
    "skipped", "escalated",
})
ALLOWED_BACKFILL_TYPES: frozenset = frozenset({
    "project", "repo", "hackathon", "course", "business", "other"
})
ALLOWED_BACKFILL_VALUES: frozenset = frozenset({"high", "medium", "low"})
ALLOWED_BACKFILL_AGENTS: frozenset = frozenset({"claude-code", "opencode", "manual"})

_BACKFILL_STARTER_CONTENT = (
    "# Backfill\n\n"
    "| Item | Type | Status | Value | Path | Agent | Notes |\n"
    "|---|---|---|---|---|---|---|\n"
)

_BACKFILL_COL_ALIASES: dict = {
    # item
    "item": "item", "name": "item", "title": "item",
    # type
    "type": "type", "kind": "type", "category": "type",
    # status
    "status": "status", "state": "status",
    # value
    "value": "value", "priority": "value", "importance": "value",
    # path
    "path": "path", "repo": "path", "folder": "path", "link": "path",
    # notes
    "notes": "notes", "summary": "notes", "description": "notes",
    # agent
    "agent": "agent", "tool": "agent",
}

_PUBLIC_BACKFILL_FIELDS = frozenset({
    "id", "item", "type", "status", "value", "path", "notes", "agent", "raw"
})


def _norm_bf_col(name: str) -> str:
    return _BACKFILL_COL_ALIASES.get(name.strip().lower(), name.strip().lower())


def _parse_table_backfill(lines: list) -> list:
    """
    Parse a Markdown pipe table for backfill items.
    Returns list of item dicts including internal _lineNum, _statusColIdx,
    _itemColIdx, and _colMap. Internal _* keys are stripped before the public API returns.
    """
    header_idx = None
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            header_idx = i
            break
    if header_idx is None:
        return []

    raw_cols       = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    col_map        = [_norm_bf_col(c) for c in raw_cols]
    status_col_idx = col_map.index("status") if "status" in col_map else -1
    item_col_idx   = col_map.index("item")   if "item"   in col_map else -1
    items: list    = []

    for row_idx, line in enumerate(lines[header_idx + 2:]):
        if not _ROW_RE.match(line):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        while len(cells) < len(col_map):
            cells.append("")

        bfi: dict = {
            "id":     f"b{len(items) + 1}",
            "item":   "",
            "type":   None,
            "status": "new",
            "value":  None,
            "path":   None,
            "notes":  None,
            "agent":  None,
            "raw":    line.strip(),
            "_lineNum":      header_idx + 2 + row_idx,
            "_statusColIdx": status_col_idx,
            "_itemColIdx":   item_col_idx,
            "_colMap":       list(col_map),
        }

        for i, col in enumerate(col_map):
            val = cells[i] if i < len(cells) else ""
            if col == "item":
                bfi["item"] = val
            elif col in ("type", "status", "value", "path", "notes", "agent"):
                bfi[col] = val or None

        # Fallback: use first non-empty cell as item name.
        if not bfi["item"]:
            for cell in cells:
                if cell:
                    bfi["item"] = cell
                    break

        if bfi["item"]:
            items.append(bfi)

    return items


def _strip_bf_internal(items: list) -> list:
    """Return items with only public fields; internal _* keys removed."""
    return [{k: v for k, v in it.items() if k in _PUBLIC_BACKFILL_FIELDS} for it in items]


def get_backfill(vault_path: str) -> dict:
    """
    Read and parse the vault backfill file.

    Tries ops/backfill.md first, then ops/backfill-last-year.md.
    Parses Markdown tables; falls back to preview-only or missing.

    Safety: read-only, path validated, preview capped, no writes.
    Internal location metadata is stripped before returning.
    """
    root: Path = Path(vault_path)
    bf_path: Optional[Path] = None
    rel_path = _BACKFILL_CANDIDATES[0]

    for candidate in _BACKFILL_CANDIDATES:
        p = _safe_subpath(root, candidate)
        if p is not None and p.is_file():
            bf_path  = p
            rel_path = candidate
            break

    if bf_path is None:
        return {
            "path": rel_path, "exists": False,
            "lastModified": None, "preview": None,
            "items": [], "parseMode": "missing",
        }

    content = _preview(bf_path, max_chars=_PARSE_CHARS_BF)
    preview = content[:_PREVIEW_CHARS] if content else None

    if not content:
        return {
            "path": rel_path, "exists": True,
            "lastModified": _last_modified_iso(bf_path),
            "preview": None, "items": [], "parseMode": "preview-only",
        }

    lines = content[:_PARSE_CHARS_BF].splitlines()
    items = _parse_table_backfill(lines)

    return {
        "path":         rel_path,
        "exists":       True,
        "lastModified": _last_modified_iso(bf_path),
        "preview":      preview,
        "items":        _strip_bf_internal(items),
        "parseMode":    "markdown-table" if items else "preview-only",
    }


def _backup_backfill_file(bf_path: Path) -> Path:
    """
    Create a timestamped backup under backend/data/backups/backfill/.
    Never overwrites an existing backup. Raises on I/O failure.
    """
    _BACKFILL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stem     = bf_path.stem
    ts       = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix   = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    bak_name = f"{stem}_{ts}_{suffix}.md"
    bak_path = _BACKFILL_BACKUP_DIR / bak_name
    if bak_path.exists():
        suffix   = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        bak_path = _BACKFILL_BACKUP_DIR / f"{stem}_{ts}_{suffix}.md"
    shutil.copy2(bf_path, bak_path)
    logger.info("Backfill backup created: %s", bak_path)
    return bak_path


def update_backfill_status(vault_path: str, item_id: str, new_status: str) -> dict:
    """
    Update a single backfill item's status in the vault backfill file.

    Safety contract:
    - Only writes to ops/backfill.md or ops/backfill-last-year.md.
    - Only ALLOWED_BACKFILL_STATUSES accepted.
    - Item ID must match b<positive-integer> pattern.
    - File re-read and re-parsed on every call (no stale state).
    - Target row verified by item name before write (conflict detection).
    - Backup created before every write; aborted if backup fails.
    - Only the status cell is modified; all other cells preserved.
    - No other vault files are touched.

    Raises ValueError with a descriptive message on any safety check failure.
    Returns {"ok": True, "item": {...}, "path": str, "updatedAt": str}.
    """
    # ── validate inputs ───────────────────────────────────────────────────────
    if new_status not in ALLOWED_BACKFILL_STATUSES:
        raise ValueError(
            f"Invalid status {new_status!r}. "
            f"Allowed: {sorted(ALLOWED_BACKFILL_STATUSES)}"
        )
    if not (item_id.startswith("b") and item_id[1:].isdigit() and len(item_id) > 1):
        raise ValueError(
            f"Invalid item id {item_id!r}. Expected format: b<number> (e.g. b1)."
        )
    item_index = int(item_id[1:]) - 1
    if item_index < 0:
        raise ValueError(f"Invalid item id {item_id!r}.")

    # ── locate backfill file ──────────────────────────────────────────────────
    root: Path = Path(vault_path)
    bf_path: Optional[Path] = None
    rel_path = _BACKFILL_CANDIDATES[0]
    for candidate in _BACKFILL_CANDIDATES:
        p = _safe_subpath(root, candidate)
        if p is not None and p.is_file():
            bf_path  = p
            rel_path = candidate
            break
    if bf_path is None:
        raise ValueError("No backfill file found in vault ops/.")

    # ── read full file ────────────────────────────────────────────────────────
    try:
        full_content = bf_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read backfill file: {exc}") from exc

    # ── parse ─────────────────────────────────────────────────────────────────
    lines = full_content[:_PARSE_CHARS_BF].splitlines()
    items = _parse_table_backfill(lines)
    if not items:
        raise ValueError(
            "Backfill file format is preview-only — "
            "status editing requires a Markdown table."
        )
    if item_index >= len(items):
        raise ValueError(
            f"Item '{item_id}' not found. File has {len(items)} item(s). "
            "Refresh and try again."
        )

    item           = items[item_index]
    status_col_idx = item["_statusColIdx"]
    item_col_idx   = item["_itemColIdx"]
    col_map        = item["_colMap"]

    if status_col_idx < 0:
        raise ValueError("No status column found in the backfill table.")

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

    # Conflict detection: verify item name still matches.
    if item_col_idx >= 0 and item_col_idx < len(cells):
        if cells[item_col_idx] != item["item"]:
            raise ValueError(
                "Item name mismatch — file has changed since last load. "
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
        _backup_backfill_file(bf_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines[line_num] = new_line
    try:
        bf_path.write_text(''.join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write backfill file: {exc}") from exc

    logger.info(
        "Backfill status updated: id=%s  item=%r  %r→%r  file=%s",
        item_id, item["item"], item.get("status"), new_status, rel_path,
    )

    updated_item = {
        "id":     item_id,
        "item":   item["item"],
        "type":   item["type"],
        "status": new_status,
        "value":  item["value"],
        "path":   item["path"],
        "notes":  item["notes"],
        "agent":  item["agent"],
        "raw":    new_row,
    }
    return {
        "ok":        True,
        "item":      updated_item,
        "path":      rel_path,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def update_backfill_item(
    vault_path: str,
    item_id:    str,
    item:       str,
    item_type:  Optional[str] = None,
    value:      Optional[str] = None,
    path:       Optional[str] = None,
    agent:      Optional[str] = None,
    notes:      Optional[str] = None,
) -> dict:
    """
    Update the non-status fields of a single backfill item in ops/backfill.md.

    Editable fields: item, type, value, path, agent, notes.
    Preserved fields: status, unknown columns.

    Safety contract:
    - Only writes to ops/backfill.md (never to ops/backfill-last-year.md).
    - item must be non-empty.
    - Enum fields validated against allowlists.
    - Rejects raw newlines in all fields.
    - Sanitizes pipe characters in all table cells.
    - File re-read and re-parsed on every call (no stale state).
    - Target row verified by item name before write (conflict detection).
    - Backup created before every write; aborted if backup fails.
    - Reject if ops/backfill.md is missing or malformed.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.

    Raises ValueError with a descriptive message on any safety check failure.
    Returns {"ok": True, "item": {...}, "path": str, "updatedAt": str}.
    """
    # ── validate item_id ─────────────────────────────────────────────────────
    if not (item_id.startswith("b") and item_id[1:].isdigit() and len(item_id) > 1):
        raise ValueError(
            f"Invalid item id {item_id!r}. Expected format: b<number> (e.g. b1)."
        )
    item_index = int(item_id[1:]) - 1
    if item_index < 0:
        raise ValueError(f"Invalid item id {item_id!r}.")

    # ── validate item field ───────────────────────────────────────────────────
    item = (item or "").strip()
    if not item:
        raise ValueError("item is required and cannot be empty.")
    if "\n" in item or "\r" in item:
        raise ValueError("Field 'item' must not contain newlines.")

    # ── validate enum fields ─────────────────────────────────────────────────
    item_type = (item_type or "other").strip().lower()
    if item_type not in ALLOWED_BACKFILL_TYPES:
        raise ValueError(
            f"Invalid type {item_type!r}. Allowed: {sorted(ALLOWED_BACKFILL_TYPES)}"
        )

    if value is not None:
        value = (value or "").strip().lower()
        if value and value not in ALLOWED_BACKFILL_VALUES:
            raise ValueError(
                f"Invalid value {value!r}. Allowed: {sorted(ALLOWED_BACKFILL_VALUES)}"
            )
        if not value:
            value = None

    if agent is not None:
        agent = (agent or "").strip().lower()
        if agent and agent not in ALLOWED_BACKFILL_AGENTS:
            raise ValueError(
                f"Invalid agent {agent!r}. Allowed: {sorted(ALLOWED_BACKFILL_AGENTS)}"
            )
        if not agent:
            agent = None

    # ── validate optional text fields ────────────────────────────────────────
    for field_name, field_val in (("path", path), ("notes", notes)):
        if field_val and ("\n" in str(field_val) or "\r" in str(field_val)):
            raise ValueError(f"Field '{field_name}' must not contain newlines.")

    # ── locate file — only ops/backfill.md ───────────────────────────────────
    root_path: Path = Path(vault_path)
    primary = _safe_subpath(root_path, _BACKFILL_PRIMARY)
    if primary is None:
        raise ValueError("Invalid backfill file path.")

    if not primary.is_file():
        fallback = _safe_subpath(root_path, _BACKFILL_CANDIDATES[1])
        if fallback is not None and fallback.is_file():
            raise ValueError("Backfill edits require ops/backfill.md.")
        raise ValueError("Backfill file does not exist. Create it first.")

    # ── read full file ────────────────────────────────────────────────────────
    try:
        full_content = primary.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read backfill file: {exc}") from exc

    # ── parse ─────────────────────────────────────────────────────────────────
    lines = full_content[:_PARSE_CHARS_BF].splitlines()
    items = _parse_table_backfill(lines)
    if not items:
        raise ValueError(
            "Backfill file does not contain a Markdown table — cannot edit. "
            "The file may be malformed."
        )
    if item_index >= len(items):
        raise ValueError(
            f"Item '{item_id}' not found. File has {len(items)} item(s). "
            "Refresh and try again."
        )

    target        = items[item_index]
    item_col_idx  = target["_itemColIdx"]
    col_map       = target["_colMap"]

    # ── locate and verify the line ────────────────────────────────────────────
    all_lines = full_content.splitlines(keepends=True)
    line_num: int = target["_lineNum"]
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

    # Conflict detection: verify item name still matches.
    if item_col_idx >= 0 and item_col_idx < len(orig_cells):
        if orig_cells[item_col_idx] != target["item"]:
            raise ValueError(
                "Item name mismatch — file has changed since last load. "
                "Refresh and try again."
            )

    # ── build updated cells ───────────────────────────────────────────────────
    new_cell_values: dict = {
        "item":   _sanitize_table_cell(item),
        "type":   _sanitize_table_cell(item_type),
        "value":  _sanitize_table_cell(value or ""),
        "path":   _sanitize_table_cell(path  or ""),
        "agent":  _sanitize_table_cell(agent or ""),
        "notes":  _sanitize_table_cell(notes or ""),
    }

    new_cells: list = []
    for i, col in enumerate(col_map):
        orig_val = orig_cells[i] if i < len(orig_cells) else ""
        if col == "status":
            new_cells.append(orig_val)          # always preserve status
        elif col in new_cell_values:
            new_cells.append(new_cell_values[col])   # update editable field
        else:
            new_cells.append(orig_val)          # preserve unknown column

    new_row  = '| ' + ' | '.join(new_cells) + ' |'
    line_end = _line_ending(orig_line)
    new_line = new_row + line_end

    # ── backup then write ─────────────────────────────────────────────────────
    try:
        _backup_backfill_file(primary)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines[line_num] = new_line
    try:
        primary.write_text(''.join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write backfill file: {exc}") from exc

    logger.info(
        "Backfill item edited: id=%s  item=%r  type=%r  file=%s",
        item_id, item, item_type, _BACKFILL_PRIMARY,
    )

    # Determine preserved status from original cells.
    status_col_idx = target["_statusColIdx"]
    current_status = (
        orig_cells[status_col_idx].strip()
        if status_col_idx >= 0 and status_col_idx < len(orig_cells)
        else target.get("status") or "new"
    )

    updated_item = {
        "id":     item_id,
        "item":   item,
        "type":   item_type,
        "status": current_status,
        "value":  value,
        "path":   path,
        "notes":  notes,
        "agent":  agent,
        "raw":    new_row,
    }
    return {
        "ok":        True,
        "item":      updated_item,
        "path":      _BACKFILL_PRIMARY,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ── backfill creation helpers ─────────────────────────────────────────────────

def _has_bf_table_header(lines: list) -> bool:
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            return True
    return False


def _read_bf_col_map(lines: list) -> list:
    """Return the normalized column order from the backfill Markdown table header."""
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            raw_cols = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            return [_norm_bf_col(c) for c in raw_cols]
    return ["item", "type", "status", "value", "path", "agent", "notes"]


def create_backfill_file(vault_path: str) -> dict:
    """
    Create ops/backfill.md with a starter Markdown table if it is missing.

    Does not overwrite an existing file. Never touches ops/backfill-last-year.md.

    Safety contract:
    - Only writes to ops/backfill.md.
    - Never overwrites an existing file.
    - Creates ops/ directory only if needed.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.

    Returns the same shape as get_backfill().
    Raises ValueError on any I/O failure.
    """
    root     = Path(vault_path)
    bf_path  = _safe_subpath(root, _BACKFILL_PRIMARY)
    if bf_path is None:
        raise ValueError("Invalid backfill file path.")

    if bf_path.exists():
        return get_backfill(vault_path)

    ops_dir = _safe_subpath(root, "ops")
    if ops_dir is None:
        raise ValueError("Invalid vault ops path.")

    try:
        ops_dir.mkdir(parents=True, exist_ok=True)
        bf_path.write_text(_BACKFILL_STARTER_CONTENT, encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not create backfill file: {exc}") from exc

    logger.info("Backfill starter file created: %s", bf_path)
    return get_backfill(vault_path)


def create_backfill_item(
    vault_path: str,
    item:       str,
    item_type:  Optional[str] = None,
    status:     Optional[str] = None,
    value:      Optional[str] = None,
    path:       Optional[str] = None,
    agent:      Optional[str] = None,
    notes:      Optional[str] = None,
) -> dict:
    """
    Append one backfill item row to ops/backfill.md.

    Safety contract:
    - Only writes to ops/backfill.md (never to ops/backfill-last-year.md).
    - File must already exist and contain a Markdown table header.
    - item must be non-empty.
    - Rejects raw newlines in all fields.
    - Sanitizes pipe characters in all table cells.
    - status defaults to 'new'; item_type defaults to 'other'.
    - Enum fields validated against allowlists.
    - Backup created before writing; aborted if backup fails.
    - Only appends; never rewrites existing rows.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.

    Raises ValueError on any validation or I/O failure.
    Returns {"ok": True, "item": {...}, "path": str, "updatedAt": str}.
    """
    # ── validate inputs ───────────────────────────────────────────────────────
    item = (item or "").strip()
    if not item:
        raise ValueError("item is required and cannot be empty.")

    for field_name, field_val in (
        ("item", item), ("path", path), ("notes", notes),
    ):
        if field_val and ("\n" in str(field_val) or "\r" in str(field_val)):
            raise ValueError(f"Field '{field_name}' must not contain newlines.")

    status = (status or "new").strip().lower()
    if status not in ALLOWED_BACKFILL_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. Allowed: {sorted(ALLOWED_BACKFILL_STATUSES)}"
        )

    item_type = (item_type or "other").strip().lower()
    if item_type not in ALLOWED_BACKFILL_TYPES:
        raise ValueError(
            f"Invalid type {item_type!r}. Allowed: {sorted(ALLOWED_BACKFILL_TYPES)}"
        )

    if value is not None:
        value = (value or "").strip().lower()
        if value and value not in ALLOWED_BACKFILL_VALUES:
            raise ValueError(
                f"Invalid value {value!r}. Allowed: {sorted(ALLOWED_BACKFILL_VALUES)}"
            )
        if not value:
            value = None

    if agent is not None:
        agent = (agent or "").strip().lower()
        if agent and agent not in ALLOWED_BACKFILL_AGENTS:
            raise ValueError(
                f"Invalid agent {agent!r}. Allowed: {sorted(ALLOWED_BACKFILL_AGENTS)}"
            )
        if not agent:
            agent = None

    # ── locate file — only ops/backfill.md ───────────────────────────────────
    root_path: Path = Path(vault_path)
    primary   = _safe_subpath(root_path, _BACKFILL_PRIMARY)
    if primary is None:
        raise ValueError("Invalid backfill file path.")

    if not primary.is_file():
        fallback = _safe_subpath(root_path, _BACKFILL_CANDIDATES[1])
        if fallback is not None and fallback.is_file():
            raise ValueError(
                "Create ops/backfill.md before adding new backfill items."
            )
        raise ValueError("Backfill file does not exist. Create it first.")

    # ── read + parse ──────────────────────────────────────────────────────────
    try:
        full_content = primary.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read backfill file: {exc}") from exc

    lines = full_content[:_PARSE_CHARS_BF].splitlines()
    if not _has_bf_table_header(lines):
        raise ValueError(
            "Backfill file does not contain a Markdown table — cannot append. "
            "The file may be malformed."
        )

    existing = _parse_table_backfill(lines)
    col_map  = _read_bf_col_map(lines)
    new_id   = f"b{len(existing) + 1}"

    # ── build new row ─────────────────────────────────────────────────────────
    # _sanitize_table_cell is defined in the task creation helpers section below.
    cell_values: dict = {
        "item":   _sanitize_table_cell(item),
        "type":   _sanitize_table_cell(item_type),
        "status": _sanitize_table_cell(status),
        "value":  _sanitize_table_cell(value  or ""),
        "path":   _sanitize_table_cell(path   or ""),
        "agent":  _sanitize_table_cell(agent  or ""),
        "notes":  _sanitize_table_cell(notes  or ""),
    }
    cells   = [cell_values.get(col, "") for col in col_map]
    new_row = '| ' + ' | '.join(cells) + ' |'

    # ── backup then append ────────────────────────────────────────────────────
    try:
        _backup_backfill_file(primary)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    append_content = full_content
    if append_content and not append_content.endswith('\n'):
        append_content += '\n'

    try:
        primary.write_text(append_content + new_row + '\n', encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write backfill file: {exc}") from exc

    logger.info(
        "Backfill item appended: id=%s  item=%r  type=%r  status=%r",
        new_id, item, item_type, status,
    )

    new_item = {
        "id":     new_id,
        "item":   item,
        "type":   item_type,
        "status": status,
        "value":  value,
        "path":   path,
        "notes":  notes,
        "agent":  agent,
        "raw":    new_row,
    }
    return {
        "ok":        True,
        "item":      new_item,
        "path":      _BACKFILL_PRIMARY,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ── task creation helpers ─────────────────────────────────────────────────────

def _sanitize_table_cell(value: str) -> str:
    """Replace pipe chars and strip newlines for a safe Markdown table cell."""
    return (
        value
        .replace("|", "∣")          # replace with Unicode DIVIDES, visually close
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def _sanitize_meta_value(value: str) -> str:
    """Strip characters that would break a checklist metadata parenthetical."""
    return (
        value
        .replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        .replace("(", "").replace(")", "")
        .replace("|", "")
        .strip()
    )


def _extract_table_col_map(lines: list) -> list:
    """
    Return the normalized column order from an existing Markdown table header.
    Falls back to the default column order if the header cannot be found.
    """
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            raw_cols = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            return [_norm_col(c) for c in raw_cols]
    return list(_DEFAULT_TABLE_COLS)


# ── task creation (append-only) ───────────────────────────────────────────────

@serialized_vault_write
def create_task(
    vault_path: str,
    title: str,
    status: str,
    area: Optional[str] = None,
    priority: Optional[str] = None,
    due: Optional[str] = None,
    source: Optional[str] = None,
) -> dict:
    """
    Append a new task to the vault task file.

    File selection:
    - Tries ops/task-db.md then ops/tasks.md.
    - If neither exists, creates ops/task-db.md with a default Markdown table header.

    Append behavior:
    - markdown-table: appends a new pipe-delimited row matching the existing column order.
    - checklist:      appends a new '- [ ]' or '- [x]' item.
    - preview-only:   raises ValueError — safe append is not possible.

    Safety contract:
    - Validates title (required, non-empty), status (allowlist), priority (allowlist if set).
    - Rejects any field value containing raw newlines.
    - Sanitizes pipe characters in table cells (replaces with Unicode ∣).
    - Creates a backup before every write; aborts if backup fails.
    - Only writes to ops/task-db.md or ops/tasks.md.
    - Creates ops/ only when creating the default task-db.md.
    - Never deletes, moves, or rewrites existing task rows.
    - No other vault files are touched.

    Returns {"ok": True, "task": {...public task dict...}, "path": str, "updatedAt": str}.
    Raises ValueError with a descriptive message on any validation or I/O failure.
    """
    # ── validate inputs ───────────────────────────────────────────────────────
    title = (title or "").strip()
    if not title:
        raise ValueError("title is required and cannot be empty.")
    if "\n" in title or "\r" in title:
        raise ValueError("title must not contain newlines.")

    status = (status or "").strip().lower()
    if status not in ALLOWED_TASK_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. Allowed: {sorted(ALLOWED_TASK_STATUSES)}"
        )

    if priority is not None:
        priority = priority.strip().lower()
        if "\n" in priority or "\r" in priority:
            raise ValueError("priority must not contain newlines.")
        if priority not in ALLOWED_TASK_PRIORITIES:
            raise ValueError(
                f"Invalid priority {priority!r}. Allowed: {sorted(ALLOWED_TASK_PRIORITIES)}"
            )

    for field_name, field_val in [("area", area), ("due", due), ("source", source)]:
        if field_val is not None and ("\n" in field_val or "\r" in field_val):
            raise ValueError(f"{field_name} must not contain newlines.")

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

    parse_mode: str
    col_map: list
    existing_count: int

    # ── new file: create ops/task-db.md with default table header ─────────────
    if task_path is None:
        default_path = _safe_subpath(root, _TASK_CANDIDATES[0])
        if default_path is None:
            raise ValueError("Could not resolve task file path safely.")

        ops_dir = default_path.parent
        try:
            ops_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise ValueError(f"Could not create ops/ directory: {exc}") from exc

        try:
            default_path.write_text(_DEFAULT_TABLE_HEADER, encoding="utf-8")
        except Exception as exc:
            raise ValueError(f"Could not create task file: {exc}") from exc

        task_path      = default_path
        rel_path       = _TASK_CANDIDATES[0]
        parse_mode     = "markdown-table"
        col_map        = list(_DEFAULT_TABLE_COLS)
        existing_count = 0

    else:
        # ── read and parse existing file ──────────────────────────────────────
        try:
            full_content = task_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            raise ValueError(f"Could not read task file: {exc}") from exc

        parse_content = full_content[:_PARSE_CHARS]
        lines         = parse_content.splitlines()
        table_tasks   = _parse_table_tasks(lines)

        if table_tasks:
            parse_mode     = "markdown-table"
            existing_count = len(table_tasks)
            col_map        = _extract_table_col_map(lines)
        else:
            cl_tasks = _parse_checklist_tasks(parse_content)
            if cl_tasks:
                parse_mode     = "checklist"
                existing_count = len(cl_tasks)
                col_map        = []
            else:
                raise ValueError(
                    "Task file format is not structured enough for safe append."
                )

    new_task_id = f"t{existing_count + 1}"

    # ── build the new line ────────────────────────────────────────────────────
    raw_repr: str

    if parse_mode == "markdown-table":
        field_map = {
            "title":    _sanitize_table_cell(title),
            "status":   _sanitize_table_cell(status),
            "area":     _sanitize_table_cell(area or ""),
            "priority": _sanitize_table_cell(priority or ""),
            "due":      _sanitize_table_cell(due or ""),
            "source":   _sanitize_table_cell(source or ""),
        }
        cells    = [field_map.get(col, "") for col in col_map]
        new_line = "| " + " | ".join(cells) + " |\n"
        raw_repr = new_line.strip()

    elif parse_mode == "checklist":
        check      = "x" if status == "done" else " "
        meta_parts: list = []
        if area:     meta_parts.append(f"Area: {_sanitize_meta_value(area)}")
        if priority: meta_parts.append(f"Priority: {priority.capitalize()}")
        if due:      meta_parts.append(f"Due: {_sanitize_meta_value(due)}")
        meta       = f" ({', '.join(meta_parts)})" if meta_parts else ""
        safe_title = title.replace("\n", " ").replace("\r", " ")
        new_line   = f"- [{check}] {safe_title}{meta}\n"
        raw_repr   = new_line.strip()

    else:
        raise ValueError("Unexpected parse mode — cannot append.")

    # ── backup then write ─────────────────────────────────────────────────────
    try:
        _backup_task_file(task_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    # Re-read to get the current file state (handles new file created above too).
    try:
        current = task_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not re-read task file before append: {exc}") from exc

    # Ensure file ends with a newline before appending.
    if current and not current.endswith("\n"):
        current += "\n"
    current += new_line

    try:
        task_path.write_text(current, encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write task file: {exc}") from exc

    logger.info(
        "Task created: id=%s  title=%r  status=%r  file=%s",
        new_task_id, title, status, rel_path,
    )

    new_task = {
        "id":       new_task_id,
        "title":    title,
        "status":   status,
        "area":     area,
        "priority": priority,
        "due":      due,
        "source":   source,
        "raw":      raw_repr,
    }

    return {
        "ok":        True,
        "task":      new_task,
        "path":      rel_path,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ── resume pipeline parsing + write ───────────────────────────────────────────

_RESUME_FILE      = "ops/resume-pipeline.md"
_RESUME_BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups" / "resume"
_PARSE_CHARS_RP   = 50_000

ALLOWED_RESUME_STATUSES: frozenset = frozenset({
    "new", "tailoring", "applied", "interview", "offer", "rejected", "archived"
})

ALLOWED_RESUME_PRIORITIES: frozenset = frozenset({"high", "medium", "low"})

_RESUME_STARTER_CONTENT = (
    "# Resume Pipeline\n\n"
    "| Target | Company | Role | Status | Priority | Deadline | Link | Notes |\n"
    "|---|---|---|---|---|---|---|---|\n"
)

_RESUME_COL_ALIASES: dict = {
    # target
    "target": "target", "name": "target", "title": "target", "job": "target",
    # company
    "company": "company", "org": "company", "employer": "company",
    # role
    "role": "role", "position": "role",
    # status
    "status": "status", "state": "status", "stage": "status",
    # priority
    "priority": "priority", "value": "priority", "importance": "priority",
    # deadline
    "deadline": "deadline", "due": "deadline", "date": "deadline",
    # link
    "link": "link", "url": "link", "source": "link",
    # notes
    "notes": "notes", "summary": "notes", "description": "notes",
}

_PUBLIC_RESUME_FIELDS = frozenset({
    "id", "target", "company", "role", "status", "priority",
    "deadline", "link", "notes", "raw"
})


def _norm_rp_col(name: str) -> str:
    return _RESUME_COL_ALIASES.get(name.strip().lower(), name.strip().lower())


def _parse_table_resume(lines: list) -> list:
    """
    Parse a Markdown pipe table for resume-pipeline items.
    Returns list of item dicts including internal _lineNum, _statusColIdx,
    _targetColIdx, and _colMap. Internal _* keys are stripped before the public
    API returns.
    """
    header_idx = None
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            header_idx = i
            break
    if header_idx is None:
        return []

    raw_cols        = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    col_map         = [_norm_rp_col(c) for c in raw_cols]
    status_col_idx  = col_map.index("status") if "status" in col_map else -1
    target_col_idx  = col_map.index("target") if "target" in col_map else -1
    items: list     = []

    for row_idx, line in enumerate(lines[header_idx + 2:]):
        if not _ROW_RE.match(line):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        while len(cells) < len(col_map):
            cells.append("")

        rpi: dict = {
            "id":       f"r{len(items) + 1}",
            "target":   "",
            "company":  None,
            "role":     None,
            "status":   "new",
            "priority": None,
            "deadline": None,
            "link":     None,
            "notes":    None,
            "raw":      line.strip(),
            "_lineNum":       header_idx + 2 + row_idx,
            "_statusColIdx":  status_col_idx,
            "_targetColIdx":  target_col_idx,
            "_colMap":        list(col_map),
        }

        for i, col in enumerate(col_map):
            val = cells[i] if i < len(cells) else ""
            if col == "target":
                rpi["target"] = val
            elif col in ("company", "role", "status", "priority", "deadline", "link", "notes"):
                rpi[col] = val or None

        # Fallback: use first non-empty cell as target name.
        if not rpi["target"]:
            for cell in cells:
                if cell:
                    rpi["target"] = cell
                    break

        if rpi["target"]:
            items.append(rpi)

    return items


def _strip_rp_internal(items: list) -> list:
    """Return items with only public fields; internal _* keys removed."""
    return [{k: v for k, v in it.items() if k in _PUBLIC_RESUME_FIELDS} for it in items]


def get_resume_pipeline(vault_path: str) -> dict:
    """
    Read and parse ops/resume-pipeline.md from the vault.

    Parses Markdown tables; falls back to preview-only or missing.

    Safety: read-only, path validated, preview capped, no writes.
    Internal location metadata is stripped before returning.
    """
    root: Path = Path(vault_path)
    rp_path: Optional[Path] = _safe_subpath(root, _RESUME_FILE)

    if rp_path is None or not rp_path.is_file():
        return {
            "path": _RESUME_FILE, "exists": False,
            "lastModified": None, "preview": None,
            "items": [], "parseMode": "missing",
        }

    content = _preview(rp_path, max_chars=_PARSE_CHARS_RP)
    preview = content[:_PREVIEW_CHARS] if content else None

    if not content:
        return {
            "path": _RESUME_FILE, "exists": True,
            "lastModified": _last_modified_iso(rp_path),
            "preview": None, "items": [], "parseMode": "preview-only",
        }

    lines = content[:_PARSE_CHARS_RP].splitlines()
    items = _parse_table_resume(lines)

    return {
        "path":         _RESUME_FILE,
        "exists":       True,
        "lastModified": _last_modified_iso(rp_path),
        "preview":      preview,
        "items":        _strip_rp_internal(items),
        "parseMode":    "markdown-table" if (items or _has_rp_table_header(lines)) else "preview-only",
    }


def _backup_resume_file(rp_path: Path) -> Path:
    """
    Create a timestamped backup under backend/data/backups/resume/.
    Never overwrites an existing backup. Raises on I/O failure.
    """
    _RESUME_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stem     = rp_path.stem
    ts       = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix   = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    bak_name = f"{stem}_{ts}_{suffix}.md"
    bak_path = _RESUME_BACKUP_DIR / bak_name
    if bak_path.exists():
        suffix   = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        bak_path = _RESUME_BACKUP_DIR / f"{stem}_{ts}_{suffix}.md"
    shutil.copy2(rp_path, bak_path)
    logger.info("Resume pipeline backup created: %s", bak_path)
    return bak_path


def update_resume_pipeline_status(vault_path: str, item_id: str, new_status: str) -> dict:
    """
    Update a single resume-pipeline item's status.

    Safety contract:
    - Only writes to ops/resume-pipeline.md.
    - Only ALLOWED_RESUME_STATUSES accepted.
    - Item ID must match r<positive-integer> pattern.
    - File re-read and re-parsed on every call (no stale state).
    - Target field verified before write (conflict detection).
    - Backup created before every write; aborted if backup fails.
    - Only the status cell is modified; all other cells preserved.
    - No other vault files are touched.

    Raises ValueError with a descriptive message on any safety check failure.
    Returns {"ok": True, "item": {...}, "path": str, "updatedAt": str}.
    """
    # ── validate inputs ───────────────────────────────────────────────────────
    if new_status not in ALLOWED_RESUME_STATUSES:
        raise ValueError(
            f"Invalid status {new_status!r}. "
            f"Allowed: {sorted(ALLOWED_RESUME_STATUSES)}"
        )
    if not (item_id.startswith("r") and item_id[1:].isdigit() and len(item_id) > 1):
        raise ValueError(
            f"Invalid item id {item_id!r}. Expected format: r<number> (e.g. r1)."
        )
    item_index = int(item_id[1:]) - 1
    if item_index < 0:
        raise ValueError(f"Invalid item id {item_id!r}.")

    # ── locate file ───────────────────────────────────────────────────────────
    root: Path = Path(vault_path)
    rp_path: Optional[Path] = _safe_subpath(root, _RESUME_FILE)
    if rp_path is None or not rp_path.is_file():
        raise ValueError("ops/resume-pipeline.md not found in vault.")

    # ── read full file ────────────────────────────────────────────────────────
    try:
        full_content = rp_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read resume-pipeline file: {exc}") from exc

    # ── parse ─────────────────────────────────────────────────────────────────
    lines = full_content[:_PARSE_CHARS_RP].splitlines()
    items = _parse_table_resume(lines)
    if not items:
        raise ValueError(
            "Resume pipeline file format is preview-only — "
            "status editing requires a Markdown table."
        )
    if item_index >= len(items):
        raise ValueError(
            f"Item '{item_id}' not found. File has {len(items)} item(s). "
            "Refresh and try again."
        )

    item           = items[item_index]
    status_col_idx = item["_statusColIdx"]
    target_col_idx = item["_targetColIdx"]
    col_map        = item["_colMap"]

    if status_col_idx < 0:
        raise ValueError("No status column found in the resume-pipeline table.")

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

    # Conflict detection: verify target still matches.
    if target_col_idx >= 0 and target_col_idx < len(cells):
        if cells[target_col_idx] != item["target"]:
            raise ValueError(
                "Target name mismatch — file has changed since last load. "
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
        _backup_resume_file(rp_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines[line_num] = new_line
    try:
        rp_path.write_text(''.join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write resume-pipeline file: {exc}") from exc

    logger.info(
        "Resume pipeline status updated: id=%s  target=%r  %r->%r  file=%s",
        item_id, item["target"], item.get("status"), new_status, _RESUME_FILE,
    )

    updated_item = {
        "id":       item_id,
        "target":   item["target"],
        "company":  item["company"],
        "role":     item["role"],
        "status":   new_status,
        "priority": item["priority"],
        "deadline": item["deadline"],
        "link":     item["link"],
        "notes":    item["notes"],
        "raw":      new_row,
    }
    return {
        "ok":        True,
        "item":      updated_item,
        "path":      _RESUME_FILE,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ── resume pipeline creation + field edit ─────────────────────────────────────

def _has_rp_table_header(lines: list) -> bool:
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            return True
    return False


def _read_rp_col_map(lines: list) -> list:
    """Return the normalized column order from the resume-pipeline Markdown table header."""
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            raw_cols = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            return [_norm_rp_col(c) for c in raw_cols]
    return ["target", "company", "role", "status", "priority", "deadline", "link", "notes"]


def create_resume_pipeline_file(vault_path: str) -> dict:
    """
    Create ops/resume-pipeline.md with a starter Markdown table if it is missing.

    Does not overwrite an existing file.

    Safety contract:
    - Only writes to ops/resume-pipeline.md.
    - Never overwrites an existing file.
    - Creates ops/ directory only if needed.
    - No shell commands. No AI calls. No browser automation.

    Returns the same shape as get_resume_pipeline().
    Raises ValueError on any I/O failure.
    """
    root    = Path(vault_path)
    rp_path = _safe_subpath(root, _RESUME_FILE)
    if rp_path is None:
        raise ValueError("Invalid resume-pipeline file path.")

    if rp_path.exists():
        return get_resume_pipeline(vault_path)

    ops_dir = _safe_subpath(root, "ops")
    if ops_dir is None:
        raise ValueError("Invalid vault ops path.")

    try:
        ops_dir.mkdir(parents=True, exist_ok=True)
        rp_path.write_text(_RESUME_STARTER_CONTENT, encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not create resume-pipeline file: {exc}") from exc

    logger.info("Resume pipeline starter file created: %s", rp_path)
    return get_resume_pipeline(vault_path)


def create_resume_pipeline_item(
    vault_path: str,
    target:     str,
    company:    Optional[str] = None,
    role:       Optional[str] = None,
    status:     Optional[str] = None,
    priority:   Optional[str] = None,
    deadline:   Optional[str] = None,
    link:       Optional[str] = None,
    notes:      Optional[str] = None,
) -> dict:
    """
    Append one resume-pipeline item row to ops/resume-pipeline.md.

    Safety contract:
    - Only writes to ops/resume-pipeline.md.
    - File must already exist and contain a Markdown table header.
    - target must be non-empty.
    - Rejects raw newlines in all fields.
    - Sanitizes pipe characters in all table cells.
    - status defaults to 'new'; enum fields validated against allowlists.
    - Backup created before writing; aborted if backup fails.
    - Only appends; never rewrites existing rows.
    - No AI calls. No browser automation. No application submission.

    Raises ValueError on any validation or I/O failure.
    Returns {"ok": True, "item": {...}, "path": str, "updatedAt": str}.
    """
    # ── validate inputs ───────────────────────────────────────────────────────
    target = (target or "").strip()
    if not target:
        raise ValueError("target is required and cannot be empty.")
    if "\n" in target or "\r" in target:
        raise ValueError("Field 'target' must not contain newlines.")

    for field_name, field_val in (
        ("company", company), ("role", role),
        ("deadline", deadline), ("link", link), ("notes", notes),
    ):
        if field_val and ("\n" in str(field_val) or "\r" in str(field_val)):
            raise ValueError(f"Field '{field_name}' must not contain newlines.")

    status = (status or "new").strip().lower()
    if status not in ALLOWED_RESUME_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. Allowed: {sorted(ALLOWED_RESUME_STATUSES)}"
        )

    if priority is not None:
        priority = (priority or "").strip().lower()
        if priority and priority not in ALLOWED_RESUME_PRIORITIES:
            raise ValueError(
                f"Invalid priority {priority!r}. Allowed: {sorted(ALLOWED_RESUME_PRIORITIES)}"
            )
        if not priority:
            priority = None

    # ── locate file ───────────────────────────────────────────────────────────
    root_path: Path = Path(vault_path)
    rp_path = _safe_subpath(root_path, _RESUME_FILE)
    if rp_path is None:
        raise ValueError("Invalid resume-pipeline file path.")

    if not rp_path.is_file():
        raise ValueError("Resume pipeline file does not exist. Create it first.")

    # ── read + parse ──────────────────────────────────────────────────────────
    try:
        full_content = rp_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read resume-pipeline file: {exc}") from exc

    lines = full_content[:_PARSE_CHARS_RP].splitlines()
    if not _has_rp_table_header(lines):
        raise ValueError(
            "Resume pipeline file does not contain a Markdown table — cannot append. "
            "The file may be malformed."
        )

    existing = _parse_table_resume(lines)
    col_map  = _read_rp_col_map(lines)
    new_id   = f"r{len(existing) + 1}"

    # ── build new row ─────────────────────────────────────────────────────────
    cell_values: dict = {
        "target":   _sanitize_table_cell(target),
        "company":  _sanitize_table_cell(company  or ""),
        "role":     _sanitize_table_cell(role      or ""),
        "status":   _sanitize_table_cell(status),
        "priority": _sanitize_table_cell(priority  or ""),
        "deadline": _sanitize_table_cell(deadline  or ""),
        "link":     _sanitize_table_cell(link      or ""),
        "notes":    _sanitize_table_cell(notes     or ""),
    }
    cells   = [cell_values.get(col, "") for col in col_map]
    new_row = '| ' + ' | '.join(cells) + ' |'

    # ── backup then append ────────────────────────────────────────────────────
    try:
        _backup_resume_file(rp_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    append_content = full_content
    if append_content and not append_content.endswith('\n'):
        append_content += '\n'

    try:
        rp_path.write_text(append_content + new_row + '\n', encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write resume-pipeline file: {exc}") from exc

    logger.info(
        "Resume pipeline item appended: id=%s  target=%r  status=%r",
        new_id, target, status,
    )

    new_item = {
        "id":       new_id,
        "target":   target,
        "company":  company,
        "role":     role,
        "status":   status,
        "priority": priority,
        "deadline": deadline,
        "link":     link,
        "notes":    notes,
        "raw":      new_row,
    }
    return {
        "ok":        True,
        "item":      new_item,
        "path":      _RESUME_FILE,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def update_resume_pipeline_item(
    vault_path: str,
    item_id:    str,
    target:     str,
    company:    Optional[str] = None,
    role:       Optional[str] = None,
    priority:   Optional[str] = None,
    deadline:   Optional[str] = None,
    link:       Optional[str] = None,
    notes:      Optional[str] = None,
) -> dict:
    """
    Update the non-status fields of a single resume-pipeline item.

    Editable fields: target, company, role, priority, deadline, link, notes.
    Preserved fields: status, unknown columns.

    Safety contract:
    - Only writes to ops/resume-pipeline.md.
    - target must be non-empty.
    - Enum fields validated against allowlists.
    - Rejects raw newlines in all fields.
    - Sanitizes pipe characters in all table cells.
    - File re-read and re-parsed on every call (no stale state).
    - Target field verified before write (conflict detection).
    - Backup created before every write; aborted if backup fails.
    - Reject if file is missing or malformed.
    - No AI calls. No browser automation. No application submission.

    Raises ValueError with a descriptive message on any safety check failure.
    Returns {"ok": True, "item": {...}, "path": str, "updatedAt": str}.
    """
    # ── validate item_id ─────────────────────────────────────────────────────
    if not (item_id.startswith("r") and item_id[1:].isdigit() and len(item_id) > 1):
        raise ValueError(
            f"Invalid item id {item_id!r}. Expected format: r<number> (e.g. r1)."
        )
    item_index = int(item_id[1:]) - 1
    if item_index < 0:
        raise ValueError(f"Invalid item id {item_id!r}.")

    # ── validate target ───────────────────────────────────────────────────────
    target = (target or "").strip()
    if not target:
        raise ValueError("target is required and cannot be empty.")
    if "\n" in target or "\r" in target:
        raise ValueError("Field 'target' must not contain newlines.")

    # ── validate priority ─────────────────────────────────────────────────────
    if priority is not None:
        priority = (priority or "").strip().lower()
        if priority and priority not in ALLOWED_RESUME_PRIORITIES:
            raise ValueError(
                f"Invalid priority {priority!r}. Allowed: {sorted(ALLOWED_RESUME_PRIORITIES)}"
            )
        if not priority:
            priority = None

    # ── validate optional text fields ────────────────────────────────────────
    for field_name, field_val in (
        ("company", company), ("role", role),
        ("deadline", deadline), ("link", link), ("notes", notes),
    ):
        if field_val and ("\n" in str(field_val) or "\r" in str(field_val)):
            raise ValueError(f"Field '{field_name}' must not contain newlines.")

    # ── locate file ───────────────────────────────────────────────────────────
    root_path: Path = Path(vault_path)
    rp_path = _safe_subpath(root_path, _RESUME_FILE)
    if rp_path is None:
        raise ValueError("Invalid resume-pipeline file path.")
    if not rp_path.is_file():
        raise ValueError("Resume pipeline file does not exist. Create it first.")

    # ── read full file ────────────────────────────────────────────────────────
    try:
        full_content = rp_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read resume-pipeline file: {exc}") from exc

    # ── parse ─────────────────────────────────────────────────────────────────
    lines = full_content[:_PARSE_CHARS_RP].splitlines()
    items = _parse_table_resume(lines)
    if not items:
        raise ValueError(
            "Resume pipeline file does not contain a Markdown table — cannot edit. "
            "The file may be malformed."
        )
    if item_index >= len(items):
        raise ValueError(
            f"Item '{item_id}' not found. File has {len(items)} item(s). "
            "Refresh and try again."
        )

    target_item    = items[item_index]
    target_col_idx = target_item["_targetColIdx"]
    col_map        = target_item["_colMap"]

    # ── locate and verify the line ────────────────────────────────────────────
    all_lines = full_content.splitlines(keepends=True)
    line_num: int = target_item["_lineNum"]
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

    # Conflict detection: verify target name still matches.
    if target_col_idx >= 0 and target_col_idx < len(orig_cells):
        if orig_cells[target_col_idx] != target_item["target"]:
            raise ValueError(
                "Target name mismatch — file has changed since last load. "
                "Refresh and try again."
            )

    # ── build updated cells ───────────────────────────────────────────────────
    new_cell_values: dict = {
        "target":   _sanitize_table_cell(target),
        "company":  _sanitize_table_cell(company  or ""),
        "role":     _sanitize_table_cell(role      or ""),
        "priority": _sanitize_table_cell(priority  or ""),
        "deadline": _sanitize_table_cell(deadline  or ""),
        "link":     _sanitize_table_cell(link      or ""),
        "notes":    _sanitize_table_cell(notes     or ""),
    }

    new_cells: list = []
    for i, col in enumerate(col_map):
        orig_val = orig_cells[i] if i < len(orig_cells) else ""
        if col == "status":
            new_cells.append(orig_val)               # always preserve status
        elif col in new_cell_values:
            new_cells.append(new_cell_values[col])   # update editable field
        else:
            new_cells.append(orig_val)               # preserve unknown column

    new_row  = '| ' + ' | '.join(new_cells) + ' |'
    line_end = _line_ending(orig_line)
    new_line = new_row + line_end

    # ── backup then write ─────────────────────────────────────────────────────
    try:
        _backup_resume_file(rp_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines[line_num] = new_line
    try:
        rp_path.write_text(''.join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write resume-pipeline file: {exc}") from exc

    logger.info(
        "Resume pipeline item edited: id=%s  target=%r  file=%s",
        item_id, target, _RESUME_FILE,
    )

    # Preserve status from original cells.
    status_col_idx = target_item["_statusColIdx"]
    current_status = (
        orig_cells[status_col_idx].strip()
        if status_col_idx >= 0 and status_col_idx < len(orig_cells)
        else target_item.get("status") or "new"
    )

    updated_item = {
        "id":       item_id,
        "target":   target,
        "company":  company,
        "role":     role,
        "status":   current_status,
        "priority": priority,
        "deadline": deadline,
        "link":     link,
        "notes":    notes,
        "raw":      new_row,
    }
    return {
        "ok":        True,
        "item":      updated_item,
        "path":      _RESUME_FILE,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
