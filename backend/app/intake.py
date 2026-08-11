"""
Staging file intake + classification proposals + vault routing.

Files land in backend/data/staging/ until approved and routed into the vault.
Routing copies files into vaultPath/proposedDestination — staged originals are kept.
Proposals are heuristic-only in this run; OpenClaw classification replaces them later.
"""

import json
import logging
import re
import shutil
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.classify import classify_file

logger = logging.getLogger(__name__)

STAGING_DIR:    Path = Path(__file__).parent.parent / "data" / "staging"
ARCHIVE_DIR:    Path = Path(__file__).parent.parent / "data" / "archive"
INDEX_FILE:     Path = STAGING_DIR / "index.json"
PROPOSALS_FILE: Path = STAGING_DIR / "proposals.json"

# Single lock guards both index.json and proposals.json so uploads/deletes are atomic.
_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# Staged file entry
# ══════════════════════════════════════════════════════════════════════════════

class StagedEntry:
    __slots__ = (
        "id", "original_name", "stored_name",
        "size_bytes", "content_type", "uploaded_at", "status",
    )

    def __init__(
        self, *,
        id: str,
        original_name: str,
        stored_name: str,
        size_bytes: int,
        content_type: Optional[str],
        uploaded_at: str,
        status: str = "staged",
    ) -> None:
        self.id            = id
        self.original_name = original_name
        self.stored_name   = stored_name
        self.size_bytes    = size_bytes
        self.content_type  = content_type
        self.uploaded_at   = uploaded_at
        self.status        = status

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "originalName": self.original_name,
            "storedName":   self.stored_name,
            "sizeBytes":    self.size_bytes,
            "contentType":  self.content_type,
            "uploadedAt":   self.uploaded_at,
            "status":       self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StagedEntry":
        return cls(
            id            = d["id"],
            original_name = d["originalName"],
            stored_name   = d["storedName"],
            size_bytes    = d["sizeBytes"],
            content_type  = d.get("contentType"),
            uploaded_at   = d["uploadedAt"],
            status        = d.get("status", "staged"),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Classification proposal entry
# ══════════════════════════════════════════════════════════════════════════════

class Proposal:
    __slots__ = (
        "file_id", "domain", "entity", "source_type",
        "proposed_destination", "confidence", "needs_review",
        "reason", "status",
        # populated after routing
        "routed_at", "routed_path", "routed_name",
        # populated after archiving
        "archived_at", "archived_path", "archived_name",
        # populated after AI classification
        "classified_by", "ai_model", "ai_classified_at",
    )

    def __init__(
        self, *,
        file_id: str,
        domain: str,
        entity: str = "Unassigned",
        source_type: str,
        proposed_destination: str,
        confidence: str,
        needs_review: bool = True,
        reason: str,
        status: str = "proposed",
        routed_at: Optional[str] = None,
        routed_path: Optional[str] = None,
        routed_name: Optional[str] = None,
        archived_at: Optional[str] = None,
        archived_path: Optional[str] = None,
        archived_name: Optional[str] = None,
        classified_by: Optional[str] = None,
        ai_model: Optional[str] = None,
        ai_classified_at: Optional[str] = None,
    ) -> None:
        self.file_id              = file_id
        self.domain               = domain
        self.entity               = entity
        self.source_type          = source_type
        self.proposed_destination = proposed_destination
        self.confidence           = confidence
        self.needs_review         = needs_review
        self.reason               = reason
        self.status               = status
        self.routed_at            = routed_at
        self.routed_path          = routed_path
        self.routed_name          = routed_name
        self.archived_at          = archived_at
        self.archived_path        = archived_path
        self.archived_name        = archived_name
        self.classified_by        = classified_by
        self.ai_model             = ai_model
        self.ai_classified_at     = ai_classified_at

    def to_dict(self) -> dict:
        d: dict = {
            "fileId":              self.file_id,
            "domain":              self.domain,
            "entity":              self.entity,
            "sourceType":          self.source_type,
            "proposedDestination": self.proposed_destination,
            "confidence":          self.confidence,
            "needsReview":         self.needs_review,
            "reason":              self.reason,
            "status":              self.status,
        }
        if self.routed_at:
            d["routedAt"]   = self.routed_at
            d["routedPath"] = self.routed_path
            d["routedName"] = self.routed_name
        if self.archived_at:
            d["archivedAt"]   = self.archived_at
            d["archivePath"]  = self.archived_path
            d["archiveName"]  = self.archived_name
        if self.classified_by:
            d["classifiedBy"]    = self.classified_by
            d["aiModel"]         = self.ai_model
            d["aiClassifiedAt"]  = self.ai_classified_at
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Proposal":
        return cls(
            file_id              = d["fileId"],
            domain               = d["domain"],
            entity               = d.get("entity", "Unassigned"),
            source_type          = d["sourceType"],
            proposed_destination = d["proposedDestination"],
            confidence           = d["confidence"],
            needs_review         = d.get("needsReview", True),
            reason               = d.get("reason", ""),
            status               = d.get("status", "proposed"),
            routed_at            = d.get("routedAt"),
            routed_path          = d.get("routedPath"),
            routed_name          = d.get("routedName"),
            archived_at          = d.get("archivedAt"),
            archived_path        = d.get("archivePath"),
            archived_name        = d.get("archiveName"),
            classified_by        = d.get("classifiedBy"),
            ai_model             = d.get("aiModel"),
            ai_classified_at     = d.get("aiClassifiedAt"),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Staging directory + file helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_staging_dir() -> None:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_archive_dir() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


# ── index I/O ─────────────────────────────────────────────────────────────────

def _read_index() -> List[StagedEntry]:
    _ensure_staging_dir()
    if not INDEX_FILE.exists():
        return []
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        return [StagedEntry.from_dict(item) for item in data]
    except Exception as exc:
        raise RuntimeError(f"Corrupted staging index: {exc}") from exc


def _write_index(entries: List[StagedEntry]) -> None:
    _ensure_staging_dir()
    INDEX_FILE.write_text(
        json.dumps([e.to_dict() for e in entries], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── proposals I/O ─────────────────────────────────────────────────────────────

def _read_proposals() -> List[Proposal]:
    _ensure_staging_dir()
    if not PROPOSALS_FILE.exists():
        return []
    try:
        data = json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
        return [Proposal.from_dict(p) for p in data]
    except Exception as exc:
        raise RuntimeError(f"Corrupted proposals file: {exc}") from exc


def _write_proposals(proposals: List[Proposal]) -> None:
    _ensure_staging_dir()
    PROPOSALS_FILE.write_text(
        json.dumps([p.to_dict() for p in proposals], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── filename helpers ───────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    name = Path(name).name
    name = name.replace("\x00", "")
    name = re.sub(r"[^\w\s\-.]", "_", name)
    name = re.sub(r"\s+", "_", name)
    name = name.strip("._")
    if not name:
        name = "file"
    if len(name) > 200:
        stem   = Path(name).stem[:190]
        suffix = Path(name).suffix[:10]
        name   = stem + suffix
    return name


def _unique_stored_name(safe_name: str) -> str:
    if not (STAGING_DIR / safe_name).exists():
        return safe_name
    stem   = Path(safe_name).stem
    suffix = Path(safe_name).suffix
    short  = uuid.uuid4().hex[:8]
    return f"{stem}_{short}{suffix}"


# ── destination validation ─────────────────────────────────────────────────────

def validate_destination(dest: str) -> str:
    """
    Ensures a proposed vault destination is safe and relative.
    Raises ValueError with a user-facing message on failure.
    """
    dest = dest.strip()
    if not dest:
        raise ValueError("proposedDestination cannot be empty.")
    # No absolute paths (Unix or Windows)
    if dest.startswith("/") or (len(dest) > 1 and dest[1] == ":"):
        raise ValueError("proposedDestination must be a relative path (no leading / or drive letter).")
    # No parent traversal
    parts = dest.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError("proposedDestination cannot contain '..'.")
    # Must live under raw/
    if not dest.startswith("raw/"):
        raise ValueError("proposedDestination must start with 'raw/'.")
    return dest


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers (called under _lock)
# ══════════════════════════════════════════════════════════════════════════════

def _create_proposal_unlocked(file_id: str, original_name: str, content_type: Optional[str]) -> Proposal:
    result   = classify_file(original_name, content_type)
    proposal = Proposal(
        file_id              = file_id,
        domain               = result.domain,
        entity               = "Unassigned",
        source_type          = result.source_type,
        proposed_destination = result.proposed_destination,
        confidence           = result.confidence,
        needs_review         = True,
        reason               = result.reason,
        status               = "proposed",
    )
    proposals = _read_proposals()
    proposals.append(proposal)
    _write_proposals(proposals)
    return proposal


def _delete_proposal_unlocked(file_id: str) -> None:
    proposals = _read_proposals()
    _write_proposals([p for p in proposals if p.file_id != file_id])


# ══════════════════════════════════════════════════════════════════════════════
# Public API — staged files
# ══════════════════════════════════════════════════════════════════════════════

def list_staged() -> List[StagedEntry]:
    with _lock:
        return _read_index()


def stage_file(
    original_name: str,
    content: bytes,
    content_type: Optional[str],
) -> StagedEntry:
    with _lock:
        _ensure_staging_dir()
        safe_name   = sanitize_filename(original_name)
        stored_name = _unique_stored_name(safe_name)
        stored_path = STAGING_DIR / stored_name

        stored_path.write_bytes(content)

        entry = StagedEntry(
            id            = str(uuid.uuid4()),
            original_name = original_name,
            stored_name   = stored_name,
            size_bytes    = len(content),
            content_type  = content_type or None,
            uploaded_at   = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
            status        = "staged",
        )

        entries = _read_index()
        entries.append(entry)
        _write_index(entries)

        _create_proposal_unlocked(entry.id, original_name, content_type)

        logger.info(
            "Staged: %r → %r  (%d bytes)  domain=%s",
            original_name, stored_name, len(content),
            classify_file(original_name, content_type).domain,
        )
        return entry


def delete_staged(file_id: str) -> Optional[StagedEntry]:
    with _lock:
        entries = _read_index()
        target  = next((e for e in entries if e.id == file_id), None)
        if target is None:
            return None

        stored_path      = (STAGING_DIR / target.stored_name).resolve()
        staging_resolved = STAGING_DIR.resolve()
        sep = "\\" if "\\" in str(staging_resolved) else "/"
        if not str(stored_path).startswith(str(staging_resolved) + sep) and \
           stored_path != staging_resolved:
            logger.error("Path traversal detected: %s", stored_path)
            raise ValueError("Stored path is outside the staging directory.")

        if stored_path.exists():
            stored_path.unlink()
        else:
            logger.warning("File already missing on disk: %s", stored_path)

        _write_index([e for e in entries if e.id != file_id])
        _delete_proposal_unlocked(file_id)

        logger.info("Deleted staged file: id=%s  stored=%r", file_id, target.stored_name)
        return target


# ══════════════════════════════════════════════════════════════════════════════
# Public API — proposals
# ══════════════════════════════════════════════════════════════════════════════

def list_proposals() -> List[Proposal]:
    with _lock:
        return _read_proposals()


def update_proposal(file_id: str, updates: Dict[str, object]) -> Optional[Proposal]:
    """
    Update editable fields on a proposal.
    `updates` keys must match Proposal.__slots__ (snake_case).
    Validates `proposed_destination` if present.
    Raises ValueError on invalid destination.
    """
    if "proposed_destination" in updates:
        validate_destination(str(updates["proposed_destination"]))  # raises ValueError
    with _lock:
        proposals = _read_proposals()
        target    = next((p for p in proposals if p.file_id == file_id), None)
        if target is None:
            return None
        for attr, value in updates.items():
            if hasattr(target, attr):
                setattr(target, attr, value)
        _write_proposals(proposals)
        return target


def approve_proposal(file_id: str) -> Optional[Proposal]:
    return update_proposal(file_id, {"status": "approved"})


def skip_proposal(file_id: str) -> Optional[Proposal]:
    return update_proposal(file_id, {"status": "skipped"})


def route_proposal(
    file_id: str,
    vault_path: str,
) -> Tuple[Proposal, dict]:
    """
    Copy the staged file for file_id into vaultPath/proposedDestination/.

    - Proposal must be 'approved'.
    - Uses shutil.copy2 (Python only, no shell).
    - Staged original is kept in backend/data/staging/.
    - brain sync-raw is NOT called here.
    - Returns (updated_proposal, route_info_dict).
    - Raises ValueError with a user-facing message on any failure.
    """
    vault_path = vault_path.strip()
    if not vault_path:
        raise ValueError("Vault path is not configured. Edit it in Settings.")

    vault_root = Path(vault_path)
    if not vault_root.exists():
        raise ValueError(
            f"Configured vault path does not exist: '{vault_path}'. "
            "Edit it in Settings or create the directory."
        )

    with _lock:
        # ── load entry ────────────────────────────────────────────────────────
        entries = _read_index()
        entry   = next((e for e in entries if e.id == file_id), None)
        if entry is None:
            raise ValueError(f"Staged file '{file_id}' not found.")

        # ── load proposal ─────────────────────────────────────────────────────
        proposals = _read_proposals()
        proposal  = next((p for p in proposals if p.file_id == file_id), None)
        if proposal is None:
            raise ValueError(f"No proposal found for file '{file_id}'.")

        # ── must be approved ──────────────────────────────────────────────────
        if proposal.status != "approved":
            raise ValueError(
                f"Only approved proposals can be routed. "
                f"Current status: '{proposal.status}'."
            )

        # ── validate destination (reuses existing rules) ──────────────────────
        validate_destination(proposal.proposed_destination)

        # ── resolve destination path ──────────────────────────────────────────
        dest_rel  = proposal.proposed_destination.rstrip("/").rstrip("\\")
        dest_full = (vault_root / dest_rel).resolve()
        vault_resolved = vault_root.resolve()

        # Safety: dest_full must be under vault_resolved
        # Use str comparison (portable; resolve() normalises drive letters on Windows)
        vault_prefix = str(vault_resolved)
        dest_str     = str(dest_full)
        if not (dest_str == vault_prefix or
                dest_str.startswith(vault_prefix + "/") or
                dest_str.startswith(vault_prefix + "\\")):
            logger.error(
                "Path traversal blocked: dest=%r  vault=%r", dest_str, vault_prefix
            )
            raise ValueError(
                "Resolved destination escapes the configured vault path. Routing blocked."
            )

        # ── staged file must exist on disk ────────────────────────────────────
        staged_path = (STAGING_DIR / entry.stored_name).resolve()
        if not staged_path.exists():
            raise ValueError(
                f"Staged file is missing from disk: '{entry.stored_name}'. "
                "It may have been manually removed."
            )

        # ── create destination directory ──────────────────────────────────────
        dest_full.mkdir(parents=True, exist_ok=True)

        # ── unique destination filename (never overwrite) ─────────────────────
        dest_name = sanitize_filename(entry.original_name)
        dest_file = dest_full / dest_name
        if dest_file.exists():
            stem      = Path(dest_name).stem
            suffix    = Path(dest_name).suffix
            short     = uuid.uuid4().hex[:8]
            dest_name = f"{stem}_{short}{suffix}"
            dest_file = dest_full / dest_name

        # ── copy (not move) ───────────────────────────────────────────────────
        shutil.copy2(str(staged_path), str(dest_file))

        # ── update proposal ───────────────────────────────────────────────────
        routed_path_rel = (Path(dest_rel) / dest_name).as_posix()
        now = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")

        proposal.status      = "routed"
        proposal.routed_at   = now
        proposal.routed_path = routed_path_rel
        proposal.routed_name = dest_name

        _write_proposals(proposals)

        logger.info(
            "Routed: '%s' → '%s'  (staged original kept at '%s')",
            entry.original_name, dest_file, staged_path,
        )

        return proposal, {
            "copied":       True,
            "relativePath": routed_path_rel,
            "absolutePath": str(dest_file),
        }


def batch_approve_proposals(
    file_ids: List[str],
) -> tuple:  # (List[Proposal], List[dict])
    """
    Approve multiple proposals in a single lock acquisition.

    Returns (approved, skipped) where:
      - approved: Proposal objects whose status was set to 'approved'
      - skipped: dicts with {fileId, reason} for items that could not be approved

    Tolerant: one invalid id does not abort the whole batch.
    Does NOT move files. Does NOT write to vault.
    """
    approved: List[Proposal] = []
    skipped:  List[dict]     = []

    with _lock:
        staged_ids   = {e.id for e in _read_index()}
        proposals    = _read_proposals()
        proposal_map = {p.file_id: p for p in proposals}
        changed      = False

        for file_id in file_ids:
            if file_id not in staged_ids:
                skipped.append({"fileId": file_id, "reason": "Staged file not found."})
                continue
            proposal = proposal_map.get(file_id)
            if proposal is None:
                skipped.append({"fileId": file_id, "reason": "Proposal not found."})
                continue
            if proposal.status not in ("proposed", "edited"):
                skipped.append({
                    "fileId": file_id,
                    "reason": f"Not eligible — current status is '{proposal.status}'.",
                })
                continue
            proposal.status = "approved"
            approved.append(proposal)
            changed = True

        if changed:
            _write_proposals(proposals)
            logger.info(
                "Batch approved %d proposals, %d skipped.", len(approved), len(skipped)
            )

    return approved, skipped


# ══════════════════════════════════════════════════════════════════════════════
# Public API — archive
# ══════════════════════════════════════════════════════════════════════════════

def archive_staged_file(file_id: str) -> Tuple[Proposal, dict]:
    """
    Move the staged original for file_id from STAGING_DIR to ARCHIVE_DIR.

    - Proposal must be 'routed' — other statuses are rejected.
    - Uses shutil.move (Python only, no shell).
    - Staged original is removed from the active index.
    - Vault copy (routed_path) is never touched.
    - brain sync-raw is NOT called here.
    - Archive files are never overwritten; a UUID suffix is added if needed.
    - Returns (updated_proposal, archive_info_dict).
    - Raises ValueError with a user-facing message on any failure.
    """
    _ensure_archive_dir()

    with _lock:
        # ── load entry ────────────────────────────────────────────────────────
        entries = _read_index()
        entry   = next((e for e in entries if e.id == file_id), None)
        if entry is None:
            raise ValueError(f"Staged file '{file_id}' not found.")

        # ── load proposal ─────────────────────────────────────────────────────
        proposals = _read_proposals()
        proposal  = next((p for p in proposals if p.file_id == file_id), None)
        if proposal is None:
            raise ValueError(f"No proposal found for file '{file_id}'.")

        # ── must be routed ────────────────────────────────────────────────────
        if proposal.status != "routed":
            raise ValueError(
                f"Only routed proposals can be archived. "
                f"Current status: '{proposal.status}'."
            )

        # ── staged source must be under STAGING_DIR ───────────────────────────
        staged_path      = (STAGING_DIR / entry.stored_name).resolve()
        staging_resolved = STAGING_DIR.resolve()
        staging_prefix   = str(staging_resolved)
        staged_str       = str(staged_path)
        if not (staged_str == staging_prefix or
                staged_str.startswith(staging_prefix + "/") or
                staged_str.startswith(staging_prefix + "\\")):
            logger.error("Path traversal in archive source: %s", staged_path)
            raise ValueError("Staged path is outside the staging directory.")

        if not staged_path.exists():
            raise ValueError(
                f"Staged file is missing from disk: '{entry.stored_name}'. "
                "It may have been manually removed."
            )

        # ── unique archive filename — never overwrite ─────────────────────────
        archive_name = sanitize_filename(entry.original_name)
        archive_dest = ARCHIVE_DIR / archive_name
        if archive_dest.exists():
            stem         = Path(archive_name).stem
            suffix       = Path(archive_name).suffix
            short        = uuid.uuid4().hex[:8]
            archive_name = f"{stem}_{short}{suffix}"
            archive_dest = ARCHIVE_DIR / archive_name

        # ── archive dest must be under ARCHIVE_DIR ────────────────────────────
        archive_resolved      = ARCHIVE_DIR.resolve()
        archive_dest_resolved = archive_dest.resolve()
        archive_prefix        = str(archive_resolved)
        archive_dest_str      = str(archive_dest_resolved)
        if not (archive_dest_str == archive_prefix or
                archive_dest_str.startswith(archive_prefix + "/") or
                archive_dest_str.startswith(archive_prefix + "\\")):
            logger.error("Path traversal in archive dest: %s", archive_dest_resolved)
            raise ValueError("Archive destination is outside the archive directory.")

        # ── move file (not copy — staged original consumed) ───────────────────
        shutil.move(str(staged_path), str(archive_dest))

        # ── update proposal ───────────────────────────────────────────────────
        now = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")
        proposal.status        = "archived"
        proposal.archived_at   = now
        proposal.archived_path = str(archive_dest)
        proposal.archived_name = archive_name
        _write_proposals(proposals)

        # ── remove from active staging index ──────────────────────────────────
        _write_index([e for e in entries if e.id != file_id])

        logger.info(
            "Archived: '%s' → '%s'  (vault copy '%s' untouched)",
            entry.original_name, archive_dest, proposal.routed_path,
        )

        return proposal, {
            "archiveName": archive_name,
            "archivePath": str(archive_dest),
            "archivedAt":  now,
        }


def list_archived() -> List[Proposal]:
    """Return all proposals with status 'archived'."""
    with _lock:
        return [p for p in _read_proposals() if p.status == "archived"]


# ══════════════════════════════════════════════════════════════════════════════
# Public API — AI classification
# ══════════════════════════════════════════════════════════════════════════════

def batch_ai_classify_proposals(file_ids: List[str]) -> tuple:  # (List[Proposal], List[dict])
    """
    Use the local Ollama model to reclassify multiple staged files in one pass.

    Safety:
    - Sends metadata only per file; no file contents, vault contents, or conversation history.
    - The lock is released before any Ollama call (each can take up to 60s).
    - One failed item does not abort the rest.
    - Proposals are written in a single batch write after all Ollama calls complete.
    - Routed, archived, and approved proposals are silently skipped.
    - Invalid AI output leaves the existing proposal unchanged.

    Returns (classified, skipped) where:
      classified — List[Proposal] that were successfully updated
      skipped    — List[dict] with {"fileId": str, "reason": str} for each failure
    """
    from app.classify_ai import ai_classify_file
    from app.agent import resolve_model_tier

    everyday_model = resolve_model_tier("everyday")

    classified: List[Proposal] = []
    skipped:    List[dict]     = []

    # ── phase 1: collect eligible metadata under lock ─────────────────────────
    work_items: List[dict] = []

    with _lock:
        entries      = _read_index()
        proposals    = _read_proposals()
        entries_by_id   = {e.id: e for e in entries}
        proposals_by_id = {p.file_id: p for p in proposals}

        for file_id in file_ids:
            entry = entries_by_id.get(file_id)
            if entry is None:
                skipped.append({"fileId": file_id, "reason": "Staged file not found."})
                continue
            proposal = proposals_by_id.get(file_id)
            if proposal is None:
                skipped.append({"fileId": file_id, "reason": "Proposal not found."})
                continue
            if proposal.status in ("routed", "archived", "approved"):
                skipped.append({
                    "fileId": file_id,
                    "reason": f"Not eligible — status is '{proposal.status}'.",
                })
                continue
            work_items.append({
                "file_id":      file_id,
                "original_name": entry.original_name,
                "stored_name":  entry.stored_name,
                "content_type": entry.content_type,
                "size_bytes":   entry.size_bytes,
                "heuristic": {
                    "domain":              proposal.domain,
                    "entity":              proposal.entity,
                    "sourceType":          proposal.source_type,
                    "proposedDestination": proposal.proposed_destination,
                    "confidence":          proposal.confidence,
                    "reason":              proposal.reason,
                },
            })

    if not work_items:
        return classified, skipped

    # ── phase 2: call Ollama per item — no lock held ──────────────────────────
    ai_results: dict = {}  # file_id -> validated result dict

    for item in work_items:
        file_id = item["file_id"]
        try:
            result = ai_classify_file(
                original_name=item["original_name"],
                stored_name=item["stored_name"],
                content_type=item["content_type"],
                size_bytes=item["size_bytes"],
                heuristic=item["heuristic"],
            )
            ai_results[file_id] = result
            logger.info("Batch AI: classified %s → %s", file_id, result.get("domain"))
        except ValueError as exc:
            msg = str(exc)
            skipped.append({
                "fileId": file_id,
                "reason": f"AI classification failed: {msg[:120]}",
            })
            logger.warning("Batch AI: skipped %s — %s", file_id, msg[:120])

    if not ai_results:
        return classified, skipped

    # ── phase 3: apply all successful updates under lock — single write ───────
    with _lock:
        proposals       = _read_proposals()
        proposals_by_id = {p.file_id: p for p in proposals}
        now             = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")

        for file_id, result in ai_results.items():
            proposal = proposals_by_id.get(file_id)
            if proposal is None:
                skipped.append({
                    "fileId": file_id,
                    "reason": "Proposal disappeared before update could be applied.",
                })
                continue

            proposal.domain               = result["domain"]
            proposal.entity               = result["entity"]
            proposal.source_type          = result["sourceType"]
            proposal.proposed_destination = result["proposedDestination"]
            proposal.confidence           = result["confidence"]
            proposal.needs_review         = True
            proposal.reason               = result["reason"]
            proposal.status               = "proposed"
            proposal.classified_by        = "local-ai"
            proposal.ai_model             = everyday_model
            proposal.ai_classified_at     = now
            classified.append(proposal)

        if classified:
            _write_proposals(proposals)
            logger.info(
                "Batch AI classify: %d classified, %d skipped.",
                len(classified), len(skipped),
            )

    return classified, skipped


def ai_classify_proposal(file_id: str) -> Optional[Proposal]:
    """
    Use the local Ollama model to improve the classification proposal for a staged file.

    Safety:
    - Sends metadata only (filename, extension, size, content type, stored name).
    - Does NOT send file contents, vault contents, or conversation history.
    - All AI output is strictly validated before use.
    - Unsafe destinations are rejected.
    - The lock is released before calling Ollama (call can take up to 60s).
    - If Ollama is unavailable or AI output is invalid, ValueError is raised;
      the caller (endpoint) surfaces this as HTTP 503 without modifying the proposal.

    Returns the updated Proposal on success, or None if the file/proposal is not found.
    Raises ValueError on Ollama failure or invalid model output.
    """
    # Local imports to avoid circular dependency at module load time.
    from app.classify_ai import ai_classify_file
    from app.agent import resolve_model_tier

    everyday_model = resolve_model_tier("everyday")

    # ── phase 1: read under lock ──────────────────────────────────────────────
    with _lock:
        entries  = _read_index()
        entry    = next((e for e in entries if e.id == file_id), None)
        if entry is None:
            return None
        proposals = _read_proposals()
        proposal  = next((p for p in proposals if p.file_id == file_id), None)
        if proposal is None:
            return None
        # Build context for the AI from current proposal (no file contents).
        heuristic = {
            "domain":              proposal.domain,
            "entity":              proposal.entity,
            "sourceType":          proposal.source_type,
            "proposedDestination": proposal.proposed_destination,
            "confidence":          proposal.confidence,
            "reason":              proposal.reason,
        }
        original_name = entry.original_name
        stored_name   = entry.stored_name
        content_type  = entry.content_type
        size_bytes    = entry.size_bytes

    # ── phase 2: call Ollama (no lock held — can take up to 60s) ─────────────
    # Raises ValueError on failure; caller should surface as HTTP 503.
    result = ai_classify_file(
        original_name=original_name,
        stored_name=stored_name,
        content_type=content_type,
        size_bytes=size_bytes,
        heuristic=heuristic,
    )

    # ── phase 3: write under lock (re-read in case of concurrent changes) ─────
    with _lock:
        proposals = _read_proposals()
        proposal  = next((p for p in proposals if p.file_id == file_id), None)
        if proposal is None:
            return None

        proposal.domain               = result["domain"]
        proposal.entity               = result["entity"]
        proposal.source_type          = result["sourceType"]
        proposal.proposed_destination = result["proposedDestination"]
        proposal.confidence           = result["confidence"]
        proposal.needs_review         = True
        proposal.reason               = result["reason"]
        proposal.status               = "proposed"
        proposal.classified_by        = "local-ai"
        proposal.ai_model             = everyday_model
        proposal.ai_classified_at     = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")

        _write_proposals(proposals)
        logger.info(
            "AI classified %s → domain=%s dest=%s model=%s",
            file_id, proposal.domain, proposal.proposed_destination, everyday_model,
        )
        return proposal
