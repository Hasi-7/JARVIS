"""
Chat/AI Consolidation v1 — manual paste/import only.

A user pastes a transcript from ChatGPT / Claude / Claude Code / OpenCode (or other)
into the UI. The backend stores a *draft* (metadata + transcript + user-provided or
deterministic-fallback summary). Nothing is written to the vault until the user
explicitly saves a draft, which writes ONE Markdown summary file under
`raw/chats/<sourceTool>/`.

Safety model (this module never relaxes it):
- No browser automation, computer-use, MCP, or external tool launch.
- No AI call. If no summary is provided, a conservative deterministic fallback is
  derived from a transcript preview.
- Transcript text is treated as UNTRUSTED external content: it is only ever stored
  and embedded inside a fenced code block. It is never executed, never sent to an
  LLM, and never interpreted as instructions.
- Save writes exactly one file under raw/chats/<sourceTool>/, never overwrites,
  never escapes the vault root, and never touches tasks/calendar/resume.
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

CONSOLIDATION_DIR: Path = Path(__file__).parent.parent / "data" / "consolidation"
DRAFTS_FILE:       Path = CONSOLIDATION_DIR / "drafts.json"

_lock = threading.Lock()

# Supported source tools → vault sub-directory + display name.
_TOOLS: Dict[str, Dict[str, str]] = {
    "chatgpt":     {"dir": "raw/chats/chatgpt/",     "label": "ChatGPT"},
    "claude":      {"dir": "raw/chats/claude/",      "label": "Claude"},
    "claude-code": {"dir": "raw/chats/claude-code/", "label": "Claude Code"},
    "opencode":    {"dir": "raw/chats/opencode/",    "label": "OpenCode"},
    "other":       {"dir": "raw/chats/other/",       "label": "Other"},
}

SUPPORTED_TOOLS:   Tuple[str, ...] = tuple(_TOOLS.keys())
SUPPORTED_DOMAINS: Tuple[str, ...] = (
    "project", "course", "business", "research", "personal", "unknown",
)

# Fields a PATCH may change. id/createdAt/sourceTool/transcript/status/savedPath are locked.
EDITABLE_FIELDS: Tuple[str, ...] = (
    "conversation_title", "domain", "entity",
    "summary", "decisions", "action_items", "code_or_files_referenced",
)

_FALLBACK_PREVIEW_CHARS = 600


# ══════════════════════════════════════════════════════════════════════════════
# Draft model
# ══════════════════════════════════════════════════════════════════════════════

class ConsolidationDraft:
    __slots__ = (
        "id", "source_tool", "conversation_title", "domain", "entity",
        "transcript", "summary", "decisions", "action_items",
        "code_or_files_referenced", "status",
        "proposed_destination", "saved_path",
        "created_at", "updated_at",
    )

    def __init__(
        self, *,
        id: str,
        source_tool: str,
        conversation_title: str,
        domain: str,
        entity: Optional[str],
        transcript: str,
        summary: str,
        decisions: List[str],
        action_items: List[str],
        code_or_files_referenced: List[str],
        status: str,
        proposed_destination: str,
        saved_path: Optional[str],
        created_at: str,
        updated_at: str,
    ) -> None:
        self.id                       = id
        self.source_tool              = source_tool
        self.conversation_title       = conversation_title
        self.domain                   = domain
        self.entity                   = entity
        self.transcript               = transcript
        self.summary                  = summary
        self.decisions                = decisions
        self.action_items             = action_items
        self.code_or_files_referenced = code_or_files_referenced
        self.status                   = status
        self.proposed_destination     = proposed_destination
        self.saved_path               = saved_path
        self.created_at               = created_at
        self.updated_at               = updated_at

    def to_dict(self) -> dict:
        return {
            "id":                     self.id,
            "sourceTool":             self.source_tool,
            "conversationTitle":      self.conversation_title,
            "domain":                 self.domain,
            "entity":                 self.entity,
            "transcript":             self.transcript,
            "summary":                self.summary,
            "decisions":              self.decisions,
            "actionItems":            self.action_items,
            "codeOrFilesReferenced":  self.code_or_files_referenced,
            "status":                 self.status,
            "proposedDestination":    self.proposed_destination,
            "savedPath":              self.saved_path,
            "createdAt":              self.created_at,
            "updatedAt":              self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConsolidationDraft":
        return cls(
            id                       = d["id"],
            source_tool              = d["sourceTool"],
            conversation_title       = d["conversationTitle"],
            domain                   = d.get("domain", "unknown"),
            entity                   = d.get("entity"),
            transcript               = d.get("transcript", ""),
            summary                  = d.get("summary", ""),
            decisions                = list(d.get("decisions") or []),
            action_items             = list(d.get("actionItems") or []),
            code_or_files_referenced = list(d.get("codeOrFilesReferenced") or []),
            status                   = d.get("status", "draft"),
            proposed_destination     = d.get("proposedDestination", ""),
            saved_path               = d.get("savedPath"),
            created_at               = d["createdAt"],
            updated_at               = d.get("updatedAt", d["createdAt"]),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Storage
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_dir() -> None:
    CONSOLIDATION_DIR.mkdir(parents=True, exist_ok=True)


def _read_drafts() -> List[ConsolidationDraft]:
    _ensure_dir()
    if not DRAFTS_FILE.exists():
        return []
    try:
        data = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
        return [ConsolidationDraft.from_dict(d) for d in data]
    except Exception as exc:
        raise RuntimeError(f"Corrupted consolidation drafts file: {exc}") from exc


def _write_drafts(drafts: List[ConsolidationDraft]) -> None:
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
    """Lowercase, ASCII-ish, hyphen-separated slug safe for a filename."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII)   # drop punctuation/unicode
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    if len(text) > 80:
        text = text[:80].rstrip("-")
    return text or "untitled"


def _fallback_summary(transcript: str) -> str:
    """
    Deterministic, conservative summary derived from a transcript preview.
    No AI call. Transcript is untrusted, so this only previews it verbatim.
    """
    preview = " ".join(transcript.split())  # collapse whitespace/newlines
    if len(preview) > _FALLBACK_PREVIEW_CHARS:
        preview = preview[:_FALLBACK_PREVIEW_CHARS].rstrip() + "…"
    return (
        "No summary was provided. Auto-generated preview of the transcript "
        f"(first {_FALLBACK_PREVIEW_CHARS} characters, no AI used):\n\n{preview}"
    )


def _clean_lines(values: Optional[List[str]]) -> List[str]:
    """Drop empty/whitespace-only entries; keep order."""
    if not values:
        return []
    return [v.strip() for v in values if isinstance(v, str) and v.strip()]


def _proposed_destination(source_tool: str, conversation_title: str, created_at: str) -> str:
    """raw/chats/<tool>/<YYYY-MM-DD>-<slug>.md (relative, posix)."""
    sub = _TOOLS[source_tool]["dir"]
    date = created_at[:10]  # YYYY-MM-DD from ISO timestamp
    return f"{sub}{date}-{slugify(conversation_title)}.md"


def _fence_for(text: str) -> str:
    """Pick a backtick fence longer than any run of backticks in the (untrusted) text."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def render_markdown(draft: ConsolidationDraft) -> str:
    label = _TOOLS.get(draft.source_tool, {}).get("label", draft.source_tool)
    captured = draft.created_at[:16].replace("T", " ")  # YYYY-MM-DD HH:MM
    fence = _fence_for(draft.transcript)

    lines: List[str] = []
    lines.append(f"# {draft.conversation_title}")
    lines.append("")
    lines.append(f"- Source tool: {label}")
    lines.append(f"- Captured at: {captured}")
    lines.append(f"- Domain: {draft.domain}")
    lines.append(f"- Entity: {draft.entity or '—'}")
    lines.append("- Status: Saved from Brain UI manual consolidation")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(draft.summary.strip() or "—")
    lines.append("")
    lines.append("## Decisions")
    lines.append("")
    lines.extend([f"- {d}" for d in draft.decisions] or ["- —"])
    lines.append("")
    lines.append("## Action Items")
    lines.append("")
    lines.extend([f"- {a}" for a in draft.action_items] or ["- —"])
    lines.append("")
    lines.append("## Code or Files Referenced")
    lines.append("")
    lines.extend([f"- {c}" for c in draft.code_or_files_referenced] or ["- —"])
    lines.append("")
    lines.append("## Original Transcript")
    lines.append("")
    lines.append(f"{fence}text")
    lines.append(draft.transcript.rstrip("\n"))
    lines.append(fence)
    lines.append("")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def create_draft(
    *,
    source_tool: str,
    conversation_title: str,
    domain: str,
    entity: Optional[str],
    transcript: str,
    summary: Optional[str],
    decisions: Optional[List[str]],
    action_items: Optional[List[str]],
    code_or_files_referenced: Optional[List[str]],
) -> ConsolidationDraft:
    """
    Validate and store a consolidation draft. Writes nothing to the vault.
    Raises ValueError (user-facing) on invalid input.
    """
    source_tool = (source_tool or "").strip().lower()
    if source_tool not in _TOOLS:
        raise ValueError(
            f"Unsupported sourceTool '{source_tool}'. "
            f"Allowed: {', '.join(SUPPORTED_TOOLS)}."
        )

    domain = (domain or "").strip().lower()
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(
            f"Unsupported domain '{domain}'. Allowed: {', '.join(SUPPORTED_DOMAINS)}."
        )

    conversation_title = (conversation_title or "").strip()
    if not conversation_title:
        raise ValueError("conversationTitle is required.")

    if not (transcript or "").strip():
        raise ValueError("transcript is required.")

    entity_clean = (entity or "").strip() or None
    summary_clean = (summary or "").strip()
    if not summary_clean:
        summary_clean = _fallback_summary(transcript)

    now = _now()
    draft = ConsolidationDraft(
        id                       = str(uuid.uuid4()),
        source_tool              = source_tool,
        conversation_title       = conversation_title,
        domain                   = domain,
        entity                   = entity_clean,
        transcript               = transcript,
        summary                  = summary_clean,
        decisions                = _clean_lines(decisions),
        action_items             = _clean_lines(action_items),
        code_or_files_referenced = _clean_lines(code_or_files_referenced),
        status                   = "draft",
        proposed_destination     = _proposed_destination(source_tool, conversation_title, now),
        saved_path               = None,
        created_at               = now,
        updated_at               = now,
    )

    with _lock:
        drafts = _read_drafts()
        drafts.append(draft)
        _write_drafts(drafts)

    logger.info(
        "Consolidation draft created: id=%s tool=%s domain=%s title=%r (no vault write)",
        draft.id, source_tool, domain, conversation_title,
    )
    return draft


def list_drafts() -> List[ConsolidationDraft]:
    """All drafts, newest first."""
    with _lock:
        drafts = _read_drafts()
    return sorted(drafts, key=lambda d: d.created_at, reverse=True)


def get_draft(draft_id: str) -> Optional[ConsolidationDraft]:
    with _lock:
        return next((d for d in _read_drafts() if d.id == draft_id), None)


def update_draft(draft_id: str, updates: Dict[str, object]) -> Optional[ConsolidationDraft]:
    """
    Update editable fields only (snake_case keys in EDITABLE_FIELDS). Locked fields
    (id/createdAt/sourceTool/transcript/status/savedPath) are never changed here.
    Re-derives proposedDestination if the title changed and the draft is unsaved.
    Raises ValueError on invalid domain.
    """
    if "domain" in updates:
        dom = str(updates["domain"]).strip().lower()
        if dom not in SUPPORTED_DOMAINS:
            raise ValueError(
                f"Unsupported domain '{dom}'. Allowed: {', '.join(SUPPORTED_DOMAINS)}."
            )
        updates = {**updates, "domain": dom}

    if "conversation_title" in updates:
        title = str(updates["conversation_title"]).strip()
        if not title:
            raise ValueError("conversationTitle cannot be empty.")
        updates = {**updates, "conversation_title": title}

    with _lock:
        drafts = _read_drafts()
        target = next((d for d in drafts if d.id == draft_id), None)
        if target is None:
            return None

        for attr, value in updates.items():
            if attr not in EDITABLE_FIELDS:
                continue
            if attr == "entity":
                value = (str(value).strip() or None) if value is not None else None
            elif attr in ("decisions", "action_items", "code_or_files_referenced"):
                value = _clean_lines(value if isinstance(value, list) else None)
            setattr(target, attr, value)

        # Keep the proposed filename in sync with the title until the draft is saved.
        if target.status == "draft":
            target.proposed_destination = _proposed_destination(
                target.source_tool, target.conversation_title, target.created_at
            )
        target.updated_at = _now()
        _write_drafts(drafts)
        return target


def save_draft(draft_id: str, vault_path: str) -> Tuple[ConsolidationDraft, dict]:
    """
    Write ONE Markdown summary for the draft under vaultPath/raw/chats/<sourceTool>/.

    - Draft must exist and not already be saved.
    - Never overwrites: a UUID suffix is appended on filename collision.
    - Resolved destination must stay inside the vault root (traversal rejected).
    - Does not run brain, call AI, or modify tasks/calendar/resume.
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
            raise ValueError(f"Consolidation draft '{draft_id}' not found.")
        if draft.status == "saved":
            raise ValueError("Draft is already saved.")

        # Re-validate the source tool (defense in depth against tampered storage).
        if draft.source_tool not in _TOOLS:
            raise ValueError(f"Unsupported source tool '{draft.source_tool}'. Save blocked.")

        # Destination directory is derived from the validated source tool only.
        dest_dir = (vault_root / "raw" / "chats" / draft.source_tool).resolve()
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

        rel_path = f"raw/chats/{draft.source_tool}/{filename}"
        draft.status     = "saved"
        draft.saved_path = rel_path
        draft.updated_at = _now()
        _write_drafts(drafts)

        logger.info(
            "Consolidation draft saved: id=%s → %s (one markdown file; no brain, no AI)",
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
    Map consolidation drafts into the generalized Proposal Queue shape. Read-only.
    Called by app.proposals.list_normalized_proposals().
    """
    items: List[dict] = []
    for d in list_drafts():
        label = _TOOLS.get(d.source_tool, {}).get("label", d.source_tool)
        items.append({
            "id":         f"consolidation:{d.id}",
            "source":     "chat-consolidation",
            "type":       "chat_consolidation",
            "riskLevel":  "medium",
            "title":      d.conversation_title,
            "summary":    (d.summary or "").split("\n", 1)[0][:240],
            "status":     _DRAFT_STATUS_MAP.get(d.status, "pending"),
            "confidence": None,
            "targetPath": d.saved_path or d.proposed_destination,
            "createdAt":  d.created_at,
            "updatedAt":  d.updated_at,
            "relatedId":  d.id,
            "actions":    ["open_consolidation"],
            "details": {
                "filename":   Path(d.proposed_destination).name,
                "domain":     d.domain,
                "entity":     d.entity,
                "sourceType": label,
                "reason":     None,
            },
        })
    return items
