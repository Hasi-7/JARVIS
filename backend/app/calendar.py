"""
calendar.py — Read and safe write for ops/calendar-candidates.md.

Read operation:
- get_calendar_candidates(): parses Markdown table; falls back to preview-only.

Write operations:
- create_calendar_candidates_file(): creates the starter table when missing.
- create_calendar_candidate(): appends one candidate row.
- update_calendar_candidate(): rewrites a single row's cells.
- approve_calendar_candidate(): sets Approved = Yes on one row.

Safety rules:
- Only reads/writes ops/calendar-candidates.md.
- Path traversal blocked via Path.is_relative_to().
- Backup created under backend/data/backups/calendar/ before every write.
- Backup aborts the write if it fails.
- Re-reads and re-parses on every write call (no stale state).
- Rejects fields containing raw newlines.
- Sanitizes pipe characters in cell values.
- Never deletes the file.
- Never touches unrelated vault files.
- Never writes to Google Calendar.
- Encoding errors handled via errors='replace'.
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

logger = logging.getLogger(__name__)

_PARSE_CHARS   = 50_000
_PREVIEW_CHARS = 2_000

_CALENDAR_FILE = "ops/calendar-candidates.md"
_BACKUP_DIR    = Path(__file__).parent.parent / "data" / "backups" / "calendar"
_STARTER_CONTENT = """# Calendar Candidates

| Date | Time | Duration | Title | Reason | Source | Approved |
|---|---|---|---|---|---|---|
"""

_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
_SEP_RE = re.compile(r"^\s*\|[-| :]+\|\s*$")

# Column normalisation: maps common header variants to canonical field names.
_COL_ALIASES: dict = {
    "date":     "date",
    "time":     "time",     "start":    "time",
    "duration": "duration", "length":   "duration",
    "title":    "title",    "name":     "title",    "event": "title",
    "reason":   "reason",   "why":      "reason",
    "source":   "source",   "from":     "source",
    "approved": "approved", "approve":  "approved",
}

_PUBLIC_CAND_FIELDS = frozenset({
    "id", "date", "time", "duration", "title",
    "reason", "source", "approved", "raw",
})


# ── helpers ───────────────────────────────────────────────────────────────────

def _norm_col(name: str) -> str:
    return _COL_ALIASES.get(name.strip().lower(), name.strip().lower())


def _safe_subpath(vault_root: Path, *parts: str) -> Optional[Path]:
    """Resolve and verify the result stays inside vault_root. Returns None on traversal."""
    try:
        resolved_root  = vault_root.resolve()
        resolved_child = vault_root.joinpath(*parts).resolve()
        if resolved_child.is_relative_to(resolved_root):
            return resolved_child
    except Exception:
        pass
    logger.warning("Path traversal rejected: %s / %s", vault_root, parts)
    return None


def _last_modified_iso(path: Path) -> Optional[str]:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


def _read_preview(path: Path, max_chars: int = _PREVIEW_CHARS) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception as exc:
        logger.debug("Could not preview %s: %s", path, exc)
        return None


def _backup_calendar_file(file_path: Path) -> Path:
    """
    Create a timestamped backup under backend/data/backups/calendar/.
    Raises on any I/O failure so callers can abort the write.
    """
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stem    = file_path.stem
    ts      = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix  = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    bak     = _BACKUP_DIR / f"{stem}_{ts}_{suffix}.md"
    if bak.exists():
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        bak    = _BACKUP_DIR / f"{stem}_{ts}_{suffix}.md"
    shutil.copy2(file_path, bak)
    logger.info("Calendar backup created: %s", bak)
    return bak


def _sanitize_cell(value: str) -> str:
    """Replace pipe chars and collapse newlines for safe Markdown table cell insertion."""
    return (
        value
        .replace("|", "∣")
        .replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        .strip()
    )


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"): return "\r\n"
    if line.endswith("\r"):   return "\r"
    if line.endswith("\n"):   return "\n"
    return ""


# ── parsing ───────────────────────────────────────────────────────────────────

def _parse_table_candidates(lines: list) -> list:
    """
    Parse a Markdown pipe table into candidate dicts.
    Returns list with internal _lineNum and _colMap fields (stripped before API).
    Stops at the first non-table line after the data rows.
    """
    header_idx = None
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            header_idx = i
            break
    if header_idx is None:
        return []

    raw_cols = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    col_map  = [_norm_col(c) for c in raw_cols]
    candidates: list = []

    for row_idx, line in enumerate(lines[header_idx + 2:]):
        if not _ROW_RE.match(line):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        while len(cells) < len(col_map):
            cells.append("")

        cand: dict = {
            "id":       f"c{len(candidates) + 1}",
            "date":     "",
            "time":     None,
            "duration": None,
            "title":    "",
            "reason":   None,
            "source":   None,
            "approved": "No",
            "raw":      line.strip(),
            # Internal location metadata — stripped before API response.
            "_lineNum": header_idx + 2 + row_idx,
            "_colMap":  list(col_map),
        }

        title_set = False
        for i, col in enumerate(col_map):
            val = cells[i] if i < len(cells) else ""
            if   col == "date":     cand["date"]     = val
            elif col == "time":     cand["time"]     = val or None
            elif col == "duration": cand["duration"] = val or None
            elif col == "title":    cand["title"] = val; title_set = True
            elif col == "reason":   cand["reason"]   = val or None
            elif col == "source":   cand["source"]   = val or None
            elif col == "approved": cand["approved"] = val if val else "No"

        if not title_set or not cand["title"]:
            for cell in cells:
                if cell:
                    cand["title"] = cell
                    break

        if cand["title"] or cand["date"]:
            candidates.append(cand)

    return candidates


def _table_info(lines: list) -> Optional[dict]:
    """
    Return basic table structure even when there are no candidate rows.
    """
    for i in range(len(lines) - 1):
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            raw_cols = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            col_map  = [_norm_col(c) for c in raw_cols]
            end_idx = i + 2
            while end_idx < len(lines) and _ROW_RE.match(lines[end_idx].rstrip("\r\n")):
                end_idx += 1
            return {
                "header_idx": i,
                "separator_idx": i + 1,
                "insert_idx": end_idx,
                "raw_cols": raw_cols,
                "col_map": col_map,
            }
    return None


def _strip_internal(candidates: list) -> list:
    return [{k: v for k, v in c.items() if k in _PUBLIC_CAND_FIELDS} for c in candidates]


# ── public read ───────────────────────────────────────────────────────────────

def get_calendar_candidates(vault_path: str) -> dict:
    """
    Read ops/calendar-candidates.md and parse Markdown table candidates.

    Returns:
      parseMode "markdown-table"  — file exists and at least one candidate row found
      parseMode "preview-only"    — file exists but no table could be parsed
      parseMode "missing"         — file does not exist

    Read-only. No vault writes. Preview capped at 2000 chars.
    """
    root      = Path(vault_path)
    file_path = _safe_subpath(root, _CALENDAR_FILE)

    if file_path is None or not file_path.is_file():
        return {
            "path":         _CALENDAR_FILE,
            "exists":       False,
            "lastModified": None,
            "preview":      None,
            "parseMode":    "missing",
            "candidates":   [],
        }

    content = _read_preview(file_path, max_chars=_PARSE_CHARS)
    preview = content[:_PREVIEW_CHARS] if content else None

    if not content:
        return {
            "path":         _CALENDAR_FILE,
            "exists":       True,
            "lastModified": _last_modified_iso(file_path),
            "preview":      None,
            "parseMode":    "preview-only",
            "candidates":   [],
        }

    lines      = content.splitlines()
    table      = _table_info(lines)
    candidates = _parse_table_candidates(lines)

    if table is not None:
        return {
            "path":         _CALENDAR_FILE,
            "exists":       True,
            "lastModified": _last_modified_iso(file_path),
            "preview":      preview,
            "parseMode":    "markdown-table",
            "candidates":   _strip_internal(candidates),
        }

    return {
        "path":         _CALENDAR_FILE,
        "exists":       True,
        "lastModified": _last_modified_iso(file_path),
        "preview":      preview,
        "parseMode":    "preview-only",
        "candidates":   [],
    }


# ── shared write helpers ──────────────────────────────────────────────────────

def _locate_and_reparse(vault_path: str, candidate_id: str) -> tuple:
    """
    Validate candidate_id, locate the file, read and re-parse.
    Returns (file_path, full_content, all_lines, candidates, candidate, candidate_index).
    Raises ValueError on any failure.
    """
    if not (candidate_id.startswith("c") and candidate_id[1:].isdigit() and len(candidate_id) > 1):
        raise ValueError(
            f"Invalid candidate id {candidate_id!r}. Expected format: c<number> (e.g. c1)."
        )
    candidate_index = int(candidate_id[1:]) - 1
    if candidate_index < 0:
        raise ValueError(f"Invalid candidate id {candidate_id!r}.")

    root      = Path(vault_path)
    file_path = _safe_subpath(root, _CALENDAR_FILE)
    if file_path is None or not file_path.is_file():
        raise ValueError("Calendar candidates file not found in vault ops/.")

    try:
        full_content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read calendar file: {exc}") from exc

    lines      = full_content[:_PARSE_CHARS].splitlines()
    candidates = _parse_table_candidates(lines)

    if not candidates:
        raise ValueError(
            "Calendar file format is preview-only — editing requires a Markdown table."
        )

    if candidate_index >= len(candidates):
        raise ValueError(
            f"Candidate '{candidate_id}' not found. "
            f"File has {len(candidates)} candidate(s). Refresh and try again."
        )

    cand    = candidates[candidate_index]
    all_lines = full_content.splitlines(keepends=True)

    line_num: int = cand["_lineNum"]
    if line_num >= len(all_lines):
        raise ValueError(
            f"Candidate line {line_num} not found (file has {len(all_lines)} lines). "
            "File may have changed — refresh and try again."
        )

    orig_line = all_lines[line_num]
    if not _ROW_RE.match(orig_line.rstrip("\r\n")):
        raise ValueError(
            f"Line {line_num} no longer looks like a table row. "
            "File may have changed — refresh and try again."
        )

    return file_path, full_content, all_lines, candidates, cand, candidate_index


def _write_updated_line(file_path: Path, all_lines: list, line_num: int,
                        col_map: list, cells: list, orig_line: str) -> str:
    """
    Reconstruct the updated table row, backup, and write the file.
    Returns the new raw row string.
    """
    new_row  = "| " + " | ".join(cells) + " |"
    new_line = new_row + _line_ending(orig_line)

    try:
        _backup_calendar_file(file_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines[line_num] = new_line
    try:
        file_path.write_text("".join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write calendar file: {exc}") from exc

    return new_row


# ── public writes ─────────────────────────────────────────────────────────────

@serialized_vault_write
def create_calendar_candidates_file(vault_path: str) -> dict:
    """
    Create ops/calendar-candidates.md with the starter table if it is missing.

    Does not overwrite an existing file and does not create a backup because no
    existing calendar candidate file is being modified.
    """
    root      = Path(vault_path)
    file_path = _safe_subpath(root, _CALENDAR_FILE)
    if file_path is None:
        raise ValueError("Invalid calendar candidates path.")

    if file_path.exists():
        return get_calendar_candidates(vault_path)

    ops_dir = _safe_subpath(root, "ops")
    if ops_dir is None:
        raise ValueError("Invalid vault ops path.")

    try:
        ops_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_text(_STARTER_CONTENT, encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not create calendar candidates file: {exc}") from exc

    logger.info("Calendar candidates starter file created: %s", file_path)
    return get_calendar_candidates(vault_path)


def _validate_candidate_payload(payload: dict, *, require_date: bool) -> dict:
    title = (payload.get("title") or "").strip()
    date  = (payload.get("date")  or "").strip()
    if not title:
        raise ValueError("title is required and cannot be empty.")
    if require_date and not date:
        raise ValueError("date is required and cannot be empty.")

    approved = (payload.get("approved") or "No").strip()
    if approved not in ("Yes", "No"):
        raise ValueError(f"Invalid approved value {approved!r}. Must be 'Yes' or 'No'.")

    for field in ("date", "time", "duration", "title", "reason", "source", "approved"):
        v = payload.get(field)
        if v and ("\n" in str(v) or "\r" in str(v)):
            raise ValueError(f"Field '{field}' must not contain newlines.")

    return {
        "date":     date,
        "time":     (payload.get("time")     or "").strip(),
        "duration": (payload.get("duration") or "").strip(),
        "title":    title,
        "reason":   (payload.get("reason")   or "").strip(),
        "source":   (payload.get("source")   or "").strip(),
        "approved": approved,
    }


@serialized_vault_write
def create_calendar_candidate(vault_path: str, payload: dict) -> dict:
    """
    Append one candidate row to an existing parseable Markdown table.

    Creates a backup before modifying the existing file. Rejects missing or
    unparseable files; starter creation is an explicit separate action.
    """
    values = _validate_candidate_payload(payload, require_date=True)

    root      = Path(vault_path)
    file_path = _safe_subpath(root, _CALENDAR_FILE)
    if file_path is None or not file_path.is_file():
        raise ValueError("Calendar candidates file does not exist. Create it first.")

    try:
        full_content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Could not read calendar file: {exc}") from exc

    all_lines = full_content.splitlines(keepends=True)
    table = _table_info([line.rstrip("\r\n") for line in all_lines])
    if table is None:
        raise ValueError("Calendar file format is preview-only — adding requires a Markdown table.")

    col_map = table["col_map"]
    field_values = {k: _sanitize_cell(v) for k, v in values.items()}
    cells = []
    for col in col_map:
        cells.append(field_values.get(col, ""))

    new_row = "| " + " | ".join(cells) + " |"
    insert_idx = table["insert_idx"]
    newline = "\n"
    if all_lines:
        prev_idx = max(0, insert_idx - 1)
        prev_ending = _line_ending(all_lines[prev_idx])
        if prev_ending:
            newline = prev_ending
        else:
            all_lines[prev_idx] = all_lines[prev_idx] + newline

    try:
        _backup_calendar_file(file_path)
    except Exception as exc:
        raise ValueError(f"Backup failed — write aborted: {exc}") from exc

    all_lines.insert(insert_idx, new_row + newline)
    try:
        file_path.write_text("".join(all_lines), encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not write calendar file: {exc}") from exc

    candidate_id = f"c{len(_parse_table_candidates(full_content[:_PARSE_CHARS].splitlines())) + 1}"
    created_cand = {
        "id":       candidate_id,
        "date":     values["date"],
        "time":     values["time"] or None,
        "duration": values["duration"] or None,
        "title":    values["title"],
        "reason":   values["reason"] or None,
        "source":   values["source"] or None,
        "approved": values["approved"],
        "raw":      new_row,
    }

    logger.info("Calendar candidate created: id=%s  title=%r", candidate_id, values["title"])
    return {
        "ok":        True,
        "candidate": created_cand,
        "path":      _CALENDAR_FILE,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

@serialized_vault_write
def update_calendar_candidate(vault_path: str, candidate_id: str, updates: dict) -> dict:
    """
    Update all editable fields in one calendar candidate row.

    Safety:
    - Re-reads and re-parses file on every call.
    - Verifies row is still a valid table row before writing.
    - Sanitizes pipe characters; rejects raw newlines.
    - Creates backup before write; aborts if backup fails.
    - Only writes ops/calendar-candidates.md.

    Raises ValueError with a descriptive message on any failure.
    """
    # ── validate user inputs ──────────────────────────────────────────────────
    title = (updates.get("title") or "").strip()
    if not title:
        raise ValueError("title is required and cannot be empty.")

    approved = (updates.get("approved") or "No").strip()
    if approved not in ("Yes", "No"):
        raise ValueError(f"Invalid approved value {approved!r}. Must be 'Yes' or 'No'.")

    for field in ("date", "time", "duration", "title", "reason", "source", "approved"):
        v = updates.get(field)
        if v and ("\n" in str(v) or "\r" in str(v)):
            raise ValueError(f"Field '{field}' must not contain newlines.")

    # ── locate candidate ──────────────────────────────────────────────────────
    file_path, _, all_lines, _, cand, _ = _locate_and_reparse(vault_path, candidate_id)

    col_map:  list = cand["_colMap"]
    line_num: int  = cand["_lineNum"]
    orig_line: str = all_lines[line_num]

    cells = [c.strip() for c in orig_line.strip().rstrip("\r\n").strip("|").split("|")]
    while len(cells) < len(col_map):
        cells.append("")

    # ── build updated cell values ─────────────────────────────────────────────
    field_values = {
        "date":     _sanitize_cell(updates.get("date")     or ""),
        "time":     _sanitize_cell(updates.get("time")     or ""),
        "duration": _sanitize_cell(updates.get("duration") or ""),
        "title":    _sanitize_cell(title),
        "reason":   _sanitize_cell(updates.get("reason")   or ""),
        "source":   _sanitize_cell(updates.get("source")   or ""),
        "approved": _sanitize_cell(approved),
    }

    for i, col in enumerate(col_map):
        if col in field_values and i < len(cells):
            cells[i] = field_values[col]

    new_row = _write_updated_line(file_path, all_lines, line_num, col_map, cells, orig_line)

    logger.info(
        "Calendar candidate updated: id=%s  title=%r  approved=%r",
        candidate_id, title, approved,
    )

    updated_cand = {
        "id":       candidate_id,
        "date":     updates.get("date")     or "",
        "time":     updates.get("time")     or None,
        "duration": updates.get("duration") or None,
        "title":    title,
        "reason":   updates.get("reason")   or None,
        "source":   updates.get("source")   or None,
        "approved": approved,
        "raw":      new_row,
    }

    return {
        "ok":        True,
        "candidate": updated_cand,
        "path":      _CALENDAR_FILE,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@serialized_vault_write
def approve_calendar_candidate(vault_path: str, candidate_id: str) -> dict:
    """
    Set Approved = Yes for one calendar candidate.

    Safety: same contract as update_calendar_candidate.
    Only the Approved cell is modified; all other cells are preserved exactly.
    """
    file_path, _, all_lines, _, cand, _ = _locate_and_reparse(vault_path, candidate_id)

    col_map:  list = cand["_colMap"]
    line_num: int  = cand["_lineNum"]
    orig_line: str = all_lines[line_num]

    if "approved" not in col_map:
        raise ValueError("No 'Approved' column found in the calendar candidates table.")
    approved_idx = col_map.index("approved")

    cells = [c.strip() for c in orig_line.strip().rstrip("\r\n").strip("|").split("|")]
    while len(cells) < len(col_map):
        cells.append("")

    cells[approved_idx] = "Yes"

    new_row = _write_updated_line(file_path, all_lines, line_num, col_map, cells, orig_line)

    logger.info("Calendar candidate approved: id=%s  title=%r", candidate_id, cand["title"])

    updated_cand = {
        "id":       candidate_id,
        "date":     cand["date"],
        "time":     cand["time"],
        "duration": cand["duration"],
        "title":    cand["title"],
        "reason":   cand["reason"],
        "source":   cand["source"],
        "approved": "Yes",
        "raw":      new_row,
    }

    return {
        "ok":        True,
        "candidate": updated_cand,
        "path":      _CALENDAR_FILE,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
