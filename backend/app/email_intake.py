"""
Email Intake v1 — manual paste/import only.

A user pastes raw email content into the UI. The backend stores a *draft*
(structured fields + raw email + user-provided or deterministic-fallback summary).
Nothing is written to the vault until the user explicitly saves a draft, which
writes ONE Markdown summary file under an allowed raw email path.

This is the PRD's manual fallback for Gmail/email intake (§33) while Gmail stays
disconnected.

Safety model (this module never relaxes it):
- No Gmail API, Gmail MCP, Gmail auth, or any Gmail mutation (send/delete/archive/labels).
- No email search/read. No browser/computer-use. No MCP. No AI call.
- Email content is treated as UNTRUSTED external content: it is only ever stored
  and embedded inside a fenced code block. It is never executed, never sent to an
  LLM, and never interpreted as instructions.
- Save writes exactly one file under an allowlisted raw email directory, never
  overwrites, never escapes the vault root, and never creates tasks/calendar rows
  or runs brain.
"""

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

EMAIL_INTAKE_DIR: Path = Path(__file__).parent.parent / "data" / "email-intake"
DRAFTS_FILE:      Path = EMAIL_INTAKE_DIR / "drafts.json"

_lock = threading.Lock()

SUPPORTED_DOMAINS: Tuple[str, ...] = ("course", "business", "personal", "unknown")
SUPPORTED_CONFIDENCE: Tuple[str, ...] = ("High", "Medium", "Low")

# Fields a PATCH may change. id/createdAt/updatedAt/status/savedPath/rawEmail are locked.
EDITABLE_FIELDS: Tuple[str, ...] = (
    "subject", "sender", "received_at", "domain", "entity",
    "summary", "action_required", "due_date", "confidence",
    "proposed_task_rows", "proposed_calendar_rows",
)

_FALLBACK_PREVIEW_CHARS = 600


# ══════════════════════════════════════════════════════════════════════════════
# Draft model
# ══════════════════════════════════════════════════════════════════════════════

class EmailIntakeDraft:
    __slots__ = (
        "id", "subject", "sender", "received_at", "domain", "entity",
        "summary", "action_required", "due_date", "confidence", "raw_email",
        "proposed_task_rows", "proposed_calendar_rows",
        "status", "proposed_destination", "saved_path",
        "created_at", "updated_at",
    )

    def __init__(
        self, *,
        id: str,
        subject: str,
        sender: Optional[str],
        received_at: Optional[str],
        domain: str,
        entity: Optional[str],
        summary: str,
        action_required: Optional[str],
        due_date: Optional[str],
        confidence: Optional[str],
        raw_email: str,
        proposed_task_rows: List[str],
        proposed_calendar_rows: List[str],
        status: str,
        proposed_destination: str,
        saved_path: Optional[str],
        created_at: str,
        updated_at: str,
    ) -> None:
        self.id                     = id
        self.subject                = subject
        self.sender                 = sender
        self.received_at            = received_at
        self.domain                 = domain
        self.entity                 = entity
        self.summary                = summary
        self.action_required        = action_required
        self.due_date               = due_date
        self.confidence             = confidence
        self.raw_email              = raw_email
        self.proposed_task_rows     = proposed_task_rows
        self.proposed_calendar_rows = proposed_calendar_rows
        self.status                 = status
        self.proposed_destination   = proposed_destination
        self.saved_path             = saved_path
        self.created_at             = created_at
        self.updated_at             = updated_at

    def to_dict(self) -> dict:
        return {
            "id":                   self.id,
            "subject":              self.subject,
            "sender":               self.sender,
            "receivedAt":           self.received_at,
            "domain":               self.domain,
            "entity":               self.entity,
            "summary":              self.summary,
            "actionRequired":       self.action_required,
            "dueDate":              self.due_date,
            "confidence":           self.confidence,
            "rawEmail":             self.raw_email,
            "proposedTaskRows":     self.proposed_task_rows,
            "proposedCalendarRows": self.proposed_calendar_rows,
            "status":               self.status,
            "proposedDestination":  self.proposed_destination,
            "savedPath":            self.saved_path,
            "createdAt":            self.created_at,
            "updatedAt":            self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EmailIntakeDraft":
        return cls(
            id                     = d["id"],
            subject                = d["subject"],
            sender                 = d.get("sender"),
            received_at            = d.get("receivedAt"),
            domain                 = d.get("domain", "unknown"),
            entity                 = d.get("entity"),
            summary                = d.get("summary", ""),
            action_required        = d.get("actionRequired"),
            due_date               = d.get("dueDate"),
            confidence             = d.get("confidence"),
            raw_email              = d.get("rawEmail", ""),
            proposed_task_rows     = list(d.get("proposedTaskRows") or []),
            proposed_calendar_rows = list(d.get("proposedCalendarRows") or []),
            status                 = d.get("status", "draft"),
            proposed_destination   = d.get("proposedDestination", ""),
            saved_path             = d.get("savedPath"),
            created_at             = d["createdAt"],
            updated_at             = d.get("updatedAt", d["createdAt"]),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Storage
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_dir() -> None:
    EMAIL_INTAKE_DIR.mkdir(parents=True, exist_ok=True)


def _read_drafts() -> List[EmailIntakeDraft]:
    _ensure_dir()
    if not DRAFTS_FILE.exists():
        return []
    try:
        data = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
        return [EmailIntakeDraft.from_dict(d) for d in data]
    except Exception as exc:
        raise RuntimeError(f"Corrupted email-intake drafts file: {exc}") from exc


def _write_drafts(drafts: List[EmailIntakeDraft]) -> None:
    _ensure_dir()
    DRAFTS_FILE.write_text(
        json.dumps([d.to_dict() for d in drafts], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def slugify(text: str) -> str:
    """Lowercase, ASCII-ish, hyphen-separated slug safe for a filename/dir."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII)   # drop punctuation/unicode
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    if len(text) > 80:
        text = text[:80].rstrip("-")
    return text or "untitled"


def _fallback_summary(subject: str, raw_email: str) -> str:
    """
    Deterministic, conservative summary derived from subject + a raw-email preview.
    No AI call. Email is untrusted, so this only previews it verbatim.
    """
    preview = " ".join((raw_email or "").split())  # collapse whitespace/newlines
    if len(preview) > _FALLBACK_PREVIEW_CHARS:
        preview = preview[:_FALLBACK_PREVIEW_CHARS].rstrip() + "…"
    return (
        f"No summary was provided. Subject: {subject}. Auto-generated preview of the "
        f"email body (first {_FALLBACK_PREVIEW_CHARS} characters, no AI used):\n\n{preview}"
    )


def _clean_lines(values: Optional[List[str]]) -> List[str]:
    """Drop empty/whitespace-only entries; keep order."""
    if not values:
        return []
    return [v.strip() for v in values if isinstance(v, str) and v.strip()]


def _dir_parts(domain: str, entity: Optional[str]) -> List[str]:
    """
    Allowlisted raw email directory, as path parts (after the vault root).
    The only variable component (business entity) is slugified, so no caller
    input can introduce traversal.
    """
    if domain == "course":
        return ["raw", "quercus", "emails"]
    if domain == "business":
        slug = slugify(entity) if (entity and entity.strip()) else "unknown"
        return ["raw", "business", slug, "emails"]
    if domain == "personal":
        return ["raw", "personal", "email"]
    # unknown (and any unexpected value, defensively)
    return ["raw", "inbox", "email"]


def _dir_rel(domain: str, entity: Optional[str]) -> str:
    return "/".join(_dir_parts(domain, entity)) + "/"


def _proposed_destination(domain: str, entity: Optional[str], subject: str, created_at: str) -> str:
    """<dir>/<YYYY-MM-DD>-<slug-subject>.md (relative, posix)."""
    date = created_at[:10]  # YYYY-MM-DD from ISO timestamp
    return f"{_dir_rel(domain, entity)}{date}-{slugify(subject)}.md"


def _fence_for(text: str) -> str:
    """Pick a backtick fence longer than any run of backticks in the (untrusted) text."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def render_markdown(draft: EmailIntakeDraft) -> str:
    captured = draft.created_at[:16].replace("T", " ")  # YYYY-MM-DD HH:MM
    fence = _fence_for(draft.raw_email)

    lines: List[str] = []
    lines.append(f"# {draft.subject}")
    lines.append("")
    lines.append(f"- Sender: {draft.sender or '—'}")
    lines.append(f"- Received at: {draft.received_at or '—'}")
    lines.append(f"- Captured at: {captured}")
    lines.append(f"- Domain: {draft.domain}")
    lines.append(f"- Entity: {draft.entity or '—'}")
    if draft.confidence:
        lines.append(f"- Confidence: {draft.confidence}")
    lines.append("- Status: Saved from Brain UI manual email intake")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(draft.summary.strip() or "—")
    lines.append("")
    lines.append("## Action Required")
    lines.append("")
    lines.append((draft.action_required or "").strip() or "—")
    lines.append("")
    lines.append("## Due Date")
    lines.append("")
    lines.append((draft.due_date or "").strip() or "—")
    lines.append("")
    lines.append("## Proposed Task Rows")
    lines.append("")
    lines.extend([f"- {t}" for t in draft.proposed_task_rows] or ["- —"])
    lines.append("")
    lines.append("## Proposed Calendar Rows")
    lines.append("")
    lines.extend([f"- {c}" for c in draft.proposed_calendar_rows] or ["- —"])
    lines.append("")
    lines.append("## Original Email")
    lines.append("")
    lines.append(f"{fence}text")
    lines.append(draft.raw_email.rstrip("\n"))
    lines.append(fence)
    lines.append("")
    return "\n".join(lines)


def _validate_confidence(confidence: Optional[str]) -> Optional[str]:
    if confidence is None:
        return None
    c = confidence.strip()
    if not c:
        return None
    if c not in SUPPORTED_CONFIDENCE:
        raise ValueError(
            f"Unsupported confidence '{c}'. Allowed: {', '.join(SUPPORTED_CONFIDENCE)}."
        )
    return c


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def create_draft(
    *,
    subject: str,
    sender: Optional[str],
    received_at: Optional[str],
    domain: str,
    entity: Optional[str],
    summary: Optional[str],
    action_required: Optional[str],
    due_date: Optional[str],
    confidence: Optional[str],
    raw_email: str,
    proposed_task_rows: Optional[List[str]],
    proposed_calendar_rows: Optional[List[str]],
) -> EmailIntakeDraft:
    """
    Validate and store an email intake draft. Writes nothing to the vault.
    Raises ValueError (user-facing) on invalid input.
    """
    subject = (subject or "").strip()
    if not subject:
        raise ValueError("subject is required.")

    if not (raw_email or "").strip():
        raise ValueError("rawEmail is required.")

    domain = (domain or "").strip().lower()
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(
            f"Unsupported domain '{domain}'. Allowed: {', '.join(SUPPORTED_DOMAINS)}."
        )

    confidence_clean = _validate_confidence(confidence)

    entity_clean = (entity or "").strip() or None
    sender_clean = (sender or "").strip() or None
    received_clean = (received_at or "").strip() or None
    action_clean = (action_required or "").strip() or None
    due_clean = (due_date or "").strip() or None

    summary_clean = (summary or "").strip()
    if not summary_clean:
        summary_clean = _fallback_summary(subject, raw_email)

    now = _now()
    draft = EmailIntakeDraft(
        id                     = str(uuid.uuid4()),
        subject                = subject,
        sender                 = sender_clean,
        received_at            = received_clean,
        domain                 = domain,
        entity                 = entity_clean,
        summary                = summary_clean,
        action_required        = action_clean,
        due_date               = due_clean,
        confidence             = confidence_clean,
        raw_email              = raw_email,
        proposed_task_rows     = _clean_lines(proposed_task_rows),
        proposed_calendar_rows = _clean_lines(proposed_calendar_rows),
        status                 = "draft",
        proposed_destination   = _proposed_destination(domain, entity_clean, subject, now),
        saved_path             = None,
        created_at             = now,
        updated_at             = now,
    )

    with _lock:
        drafts = _read_drafts()
        drafts.append(draft)
        _write_drafts(drafts)

    logger.info(
        "Email intake draft created: id=%s domain=%s subject=%r (no vault write, no Gmail)",
        draft.id, domain, subject,
    )
    return draft


def list_drafts() -> List[EmailIntakeDraft]:
    """All drafts, newest first."""
    with _lock:
        drafts = _read_drafts()
    return sorted(drafts, key=lambda d: d.created_at, reverse=True)


def get_draft(draft_id: str) -> Optional[EmailIntakeDraft]:
    with _lock:
        return next((d for d in _read_drafts() if d.id == draft_id), None)


def update_draft(draft_id: str, updates: Dict[str, object]) -> Optional[EmailIntakeDraft]:
    """
    Update editable fields only (snake_case keys in EDITABLE_FIELDS). Locked fields
    (id/createdAt/updatedAt/status/savedPath/rawEmail) are never changed here.
    Re-derives proposedDestination if domain/entity/subject changed and the draft
    is unsaved. Raises ValueError on invalid domain/confidence/empty subject.
    """
    if "domain" in updates:
        dom = str(updates["domain"]).strip().lower()
        if dom not in SUPPORTED_DOMAINS:
            raise ValueError(
                f"Unsupported domain '{dom}'. Allowed: {', '.join(SUPPORTED_DOMAINS)}."
            )
        updates = {**updates, "domain": dom}

    if "subject" in updates:
        subj = str(updates["subject"]).strip()
        if not subj:
            raise ValueError("subject cannot be empty.")
        updates = {**updates, "subject": subj}

    if "confidence" in updates:
        updates = {**updates, "confidence": _validate_confidence(
            updates["confidence"] if updates["confidence"] is None else str(updates["confidence"])
        )}

    with _lock:
        drafts = _read_drafts()
        target = next((d for d in drafts if d.id == draft_id), None)
        if target is None:
            return None

        for attr, value in updates.items():
            if attr not in EDITABLE_FIELDS:
                continue
            if attr in ("sender", "received_at", "entity", "action_required", "due_date"):
                value = (str(value).strip() or None) if value is not None else None
            elif attr in ("proposed_task_rows", "proposed_calendar_rows"):
                value = _clean_lines(value if isinstance(value, list) else None)
            setattr(target, attr, value)

        # Keep the proposed destination in sync until the draft is saved.
        if target.status == "draft":
            target.proposed_destination = _proposed_destination(
                target.domain, target.entity, target.subject, target.created_at
            )
        target.updated_at = _now()
        _write_drafts(drafts)
        return target


def save_draft(draft_id: str, vault_path: str) -> Tuple[EmailIntakeDraft, dict]:
    """
    Write ONE Markdown summary for the draft under an allowlisted raw email path.

    - Draft must exist and not already be saved.
    - Destination is derived from validated domain/(slugified) entity only.
    - Never overwrites: a UUID suffix is appended on filename collision.
    - Resolved destination must stay inside the vault root (traversal rejected).
    - Does not run brain, call AI, connect to Gmail, or create tasks/calendar rows.
    Returns (updated_draft, info). Raises ValueError (user-facing) on any failure.
    """
    vault_path = (vault_path or "").strip()
    if not vault_path:
        raise ValueError("Vault path is not configured. Edit it in Settings.")
    vault_root = Path(vault_path)
    if not vault_root.exists():
        raise ValueError(
            f"Configured vault path does not exist: '{vault_path}'. "
            "Edit it in Settings or create the directory."
        )

    with _lock:
        drafts = _read_drafts()
        draft = next((d for d in drafts if d.id == draft_id), None)
        if draft is None:
            raise ValueError(f"Email intake draft '{draft_id}' not found.")
        if draft.status == "saved":
            raise ValueError("Draft is already saved.")

        # Re-validate the domain (defense in depth against tampered storage).
        if draft.domain not in SUPPORTED_DOMAINS:
            raise ValueError(f"Unsupported domain '{draft.domain}'. Save blocked.")

        parts = _dir_parts(draft.domain, draft.entity)
        dest_dir = vault_root.joinpath(*parts).resolve()
        vault_resolved = vault_root.resolve()
        vault_prefix = str(vault_resolved)
        if not (str(dest_dir) == vault_prefix or
                str(dest_dir).startswith(vault_prefix + "/") or
                str(dest_dir).startswith(vault_prefix + "\\")):
            logger.error("Path traversal blocked (dir): %s", dest_dir)
            raise ValueError("Resolved destination escapes the configured vault path. Save blocked.")

        dest_dir.mkdir(parents=True, exist_ok=True)

        # Filename from the proposed destination basename; slug is already sanitized.
        filename = Path(draft.proposed_destination).name or f"{draft.created_at[:10]}-untitled.md"
        dest_file = dest_dir / filename
        if dest_file.exists():
            stem, suffix = Path(filename).stem, Path(filename).suffix
            filename = f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
            dest_file = dest_dir / filename

        # Final guard: the resolved file must also stay under the vault.
        dest_file_resolved = dest_file.resolve()
        if not (str(dest_file_resolved).startswith(vault_prefix + "/") or
                str(dest_file_resolved).startswith(vault_prefix + "\\")):
            logger.error("Path traversal blocked (file): %s", dest_file_resolved)
            raise ValueError("Resolved file path escapes the configured vault path. Save blocked.")

        dest_file.write_text(render_markdown(draft), encoding="utf-8")

        rel_path = "/".join(parts) + "/" + filename
        draft.status     = "saved"
        draft.saved_path = rel_path
        draft.updated_at = _now()
        _write_drafts(drafts)

        logger.info(
            "Email intake draft saved: id=%s → %s (one markdown file; no Gmail, no brain, no AI)",
            draft.id, dest_file,
        )
        return draft, {
            "relativePath": rel_path,
            "absolutePath": str(dest_file),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Proposal Queue integration (read-only)
# ══════════════════════════════════════════════════════════════════════════════

# draft → pending, saved → applied
_DRAFT_STATUS_MAP = {"draft": "pending", "saved": "applied"}


def normalized_proposals() -> List[dict]:
    """
    Map email intake drafts into the generalized Proposal Queue shape. Read-only.
    Called by app.proposals.list_normalized_proposals().
    """
    items: List[dict] = []
    for d in list_drafts():
        summary = (d.summary or "").strip() or (d.action_required or "").strip() or d.subject
        items.append({
            "id":         f"email-intake:{d.id}",
            "source":     "email-intake",
            "type":       "email_summary",
            "riskLevel":  "medium",
            "title":      d.subject,
            "summary":    summary.split("\n", 1)[0][:240],
            "status":     _DRAFT_STATUS_MAP.get(d.status, "pending"),
            "confidence": d.confidence,
            "targetPath": d.saved_path or d.proposed_destination,
            "createdAt":  d.created_at,
            "updatedAt":  d.updated_at,
            "relatedId":  d.id,
            "actions":    ["open_email_intake"],
            "details": {
                "filename":   Path(d.proposed_destination).name,
                "domain":     d.domain,
                "entity":     d.entity,
                "sourceType": "Email",
                "reason":     d.action_required,
            },
        })
    return items
