"""
Research v1 — manual capture only.

A user pastes research notes, links, source snippets, and findings into the UI. The
backend stores a *draft* (structured metadata + raw notes). Nothing is written to the
vault until the user explicitly saves a draft, which writes ONE Markdown research note
under `raw/research/<topic-or-title>/`.

Safety model (this module never relaxes it):
- No browser automation, computer-use, MCP, URL fetching, web search, or external tool.
- No AI call of any kind.
- Pasted notes and source snippets are UNTRUSTED external content: they are only stored
  and embedded (raw notes inside a fenced code block). They are never executed, never
  fetched, never sent to an LLM, and never interpreted as instructions.
- Save writes exactly one file under raw/research/, never overwrites, never escapes the
  vault root, and never touches tasks/calendar/resume.
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

RESEARCH_DIR: Path = Path(__file__).parent.parent / "data" / "research"
DRAFTS_FILE:  Path = RESEARCH_DIR / "drafts.json"

_lock = threading.Lock()

SUPPORTED_DOMAINS: Tuple[str, ...] = (
    "project", "course", "business", "personal",
    "technical", "market", "general", "unknown",
)

# Fields a PATCH may change. id/createdAt/updatedAt/status/savedPath are locked.
EDITABLE_FIELDS: Tuple[str, ...] = (
    "title", "topic", "domain", "entity", "research_question", "summary",
    "key_findings", "sources", "open_questions", "recommended_next_actions", "raw_notes",
)

_FALLBACK_SUMMARY = "Manual research capture (no summary provided)."


# ══════════════════════════════════════════════════════════════════════════════
# Draft model
# ══════════════════════════════════════════════════════════════════════════════

class ResearchDraft:
    __slots__ = (
        "id", "title", "topic", "domain", "entity", "research_question", "summary",
        "key_findings", "sources", "open_questions", "recommended_next_actions",
        "raw_notes", "status", "proposed_destination", "saved_path",
        "created_at", "updated_at",
    )

    def __init__(
        self, *,
        id: str,
        title: str,
        topic: Optional[str],
        domain: str,
        entity: Optional[str],
        research_question: Optional[str],
        summary: str,
        key_findings: List[str],
        sources: List[dict],
        open_questions: List[str],
        recommended_next_actions: List[str],
        raw_notes: str,
        status: str,
        proposed_destination: str,
        saved_path: Optional[str],
        created_at: str,
        updated_at: str,
    ) -> None:
        self.id                       = id
        self.title                    = title
        self.topic                    = topic
        self.domain                   = domain
        self.entity                   = entity
        self.research_question        = research_question
        self.summary                  = summary
        self.key_findings             = key_findings
        self.sources                  = sources
        self.open_questions           = open_questions
        self.recommended_next_actions = recommended_next_actions
        self.raw_notes                = raw_notes
        self.status                   = status
        self.proposed_destination     = proposed_destination
        self.saved_path               = saved_path
        self.created_at               = created_at
        self.updated_at               = updated_at

    def to_dict(self) -> dict:
        return {
            "id":                     self.id,
            "title":                  self.title,
            "topic":                  self.topic,
            "domain":                 self.domain,
            "entity":                 self.entity,
            "researchQuestion":       self.research_question,
            "summary":                self.summary,
            "keyFindings":            self.key_findings,
            "sources":                self.sources,
            "openQuestions":          self.open_questions,
            "recommendedNextActions": self.recommended_next_actions,
            "rawNotes":               self.raw_notes,
            "status":                 self.status,
            "proposedDestination":    self.proposed_destination,
            "savedPath":              self.saved_path,
            "createdAt":              self.created_at,
            "updatedAt":              self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchDraft":
        return cls(
            id                       = d["id"],
            title                    = d["title"],
            topic                    = d.get("topic"),
            domain                   = d.get("domain", "unknown"),
            entity                   = d.get("entity"),
            research_question        = d.get("researchQuestion"),
            summary                  = d.get("summary", ""),
            key_findings             = list(d.get("keyFindings") or []),
            sources                  = list(d.get("sources") or []),
            open_questions           = list(d.get("openQuestions") or []),
            recommended_next_actions = list(d.get("recommendedNextActions") or []),
            raw_notes                = d.get("rawNotes", ""),
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
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)


def _read_drafts() -> List[ResearchDraft]:
    _ensure_dir()
    if not DRAFTS_FILE.exists():
        return []
    try:
        data = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
        return [ResearchDraft.from_dict(d) for d in data]
    except Exception as exc:
        raise RuntimeError(f"Corrupted research drafts file: {exc}") from exc


def _write_drafts(drafts: List[ResearchDraft]) -> None:
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
    """Lowercase, ASCII-ish, hyphen-separated slug safe for a path segment."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII)   # drop punctuation/unicode/slashes
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    if len(text) > 80:
        text = text[:80].rstrip("-")
    return text or "untitled"


def _reject_traversal(value: Optional[str], field: str) -> None:
    """Reject obvious path-traversal markers in free-text identity fields."""
    if not value:
        return
    if "\x00" in value or ".." in value:
        raise ValueError(f"{field} contains an illegal path sequence.")


def _clean_lines(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    return [v.strip() for v in values if isinstance(v, str) and v.strip()]


def _clean_sources(values: Optional[List[dict]]) -> List[dict]:
    """Keep only sources that carry at least one of title/url/notes; trim strings."""
    cleaned: List[dict] = []
    for s in values or []:
        if not isinstance(s, dict):
            continue
        title = (s.get("title") or "").strip() or None
        url   = (s.get("url") or "").strip() or None
        notes = (s.get("notes") or "").strip() or None
        if title or url or notes:
            cleaned.append({"title": title, "url": url, "notes": notes})
    return cleaned


def _proposed_destination(title: str, topic: Optional[str], created_at: str) -> str:
    """raw/research/<slug(topic|title)>/<YYYY-MM-DD>-<slug(title)>.md (relative, posix)."""
    folder = slugify(topic or title)
    date = created_at[:10]
    return f"raw/research/{folder}/{date}-{slugify(title)}.md"


def _fence_for(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def render_markdown(draft: ResearchDraft) -> str:
    captured = draft.created_at[:16].replace("T", " ")  # YYYY-MM-DD HH:MM

    lines: List[str] = []
    lines.append(f"# {draft.title}")
    lines.append("")
    lines.append(f"- Captured at: {captured}")
    lines.append(f"- Domain: {draft.domain}")
    lines.append(f"- Entity: {draft.entity or '—'}")
    lines.append(f"- Topic: {draft.topic or '—'}")
    lines.append("- Status: Saved from Brain UI manual research capture")
    lines.append("")
    lines.append("## Research Question")
    lines.append("")
    lines.append((draft.research_question or "—").strip() or "—")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(draft.summary.strip() or "—")
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    lines.extend([f"- {f}" for f in draft.key_findings] or ["- —"])
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    if draft.sources:
        for s in draft.sources:
            title = s.get("title") or s.get("url") or "Source"
            url   = s.get("url")
            notes = s.get("notes")
            label = f"[{title}]({url})" if url else title
            lines.append(f"- {label}" + (f" — {notes}" if notes else ""))
    else:
        lines.append("- —")
    lines.append("")
    lines.append("## Open Questions")
    lines.append("")
    lines.extend([f"- {q}" for q in draft.open_questions] or ["- —"])
    lines.append("")
    lines.append("## Recommended Next Actions")
    lines.append("")
    lines.extend([f"- {a}" for a in draft.recommended_next_actions] or ["- —"])
    lines.append("")
    lines.append("## Raw Notes")
    lines.append("")
    fence = _fence_for(draft.raw_notes)
    lines.append(f"{fence}text")
    lines.append(draft.raw_notes.rstrip("\n"))
    lines.append(fence)
    lines.append("")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def create_draft(
    *,
    title: str,
    topic: Optional[str],
    domain: str,
    entity: Optional[str],
    research_question: Optional[str],
    summary: Optional[str],
    key_findings: Optional[List[str]],
    sources: Optional[List[dict]],
    open_questions: Optional[List[str]],
    recommended_next_actions: Optional[List[str]],
    raw_notes: str,
) -> ResearchDraft:
    """
    Validate and store a research draft. Writes nothing to the vault. No AI, no fetch.
    Raises ValueError (user-facing) on invalid input.
    """
    title = (title or "").strip()
    if not title:
        raise ValueError("title is required.")

    topic_clean  = (topic or "").strip() or None
    entity_clean = (entity or "").strip() or None
    _reject_traversal(title, "title")
    _reject_traversal(topic_clean, "topic")
    _reject_traversal(entity_clean, "entity")

    domain = (domain or "").strip().lower()
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(
            f"Unsupported domain '{domain}'. Allowed: {', '.join(SUPPORTED_DOMAINS)}."
        )

    findings = _clean_lines(key_findings)
    raw_notes = raw_notes or ""
    summary_clean = (summary or "").strip()
    if not raw_notes.strip() and not summary_clean and not findings:
        raise ValueError(
            "A research draft needs at least raw notes, a summary, or one key finding."
        )

    now = _now()
    draft = ResearchDraft(
        id                       = str(uuid.uuid4()),
        title                    = title,
        topic                    = topic_clean,
        domain                   = domain,
        entity                   = entity_clean,
        research_question        = (research_question or "").strip() or None,
        summary                  = summary_clean,
        key_findings             = findings,
        sources                  = _clean_sources(sources),
        open_questions           = _clean_lines(open_questions),
        recommended_next_actions = _clean_lines(recommended_next_actions),
        raw_notes                = raw_notes,
        status                   = "draft",
        proposed_destination     = _proposed_destination(title, topic_clean, now),
        saved_path               = None,
        created_at               = now,
        updated_at               = now,
    )

    with _lock:
        drafts = _read_drafts()
        drafts.append(draft)
        _write_drafts(drafts)

    logger.info(
        "Research draft created: id=%s domain=%s title=%r (no vault write, no fetch, no AI)",
        draft.id, domain, title,
    )
    return draft


def list_drafts() -> List[ResearchDraft]:
    """All drafts, newest first."""
    with _lock:
        drafts = _read_drafts()
    return sorted(drafts, key=lambda d: d.created_at, reverse=True)


def get_draft(draft_id: str) -> Optional[ResearchDraft]:
    with _lock:
        return next((d for d in _read_drafts() if d.id == draft_id), None)


def update_draft(draft_id: str, updates: Dict[str, object]) -> Optional[ResearchDraft]:
    """
    Update editable fields only (snake_case keys in EDITABLE_FIELDS). Locked fields
    (id/createdAt/updatedAt/status/savedPath) are never changed here. Re-derives
    proposedDestination if title/topic changed and the draft is unsaved.
    Raises ValueError on invalid domain / illegal identity fields.
    """
    if "domain" in updates:
        dom = str(updates["domain"]).strip().lower()
        if dom not in SUPPORTED_DOMAINS:
            raise ValueError(
                f"Unsupported domain '{dom}'. Allowed: {', '.join(SUPPORTED_DOMAINS)}."
            )
        updates = {**updates, "domain": dom}

    if "title" in updates:
        title = str(updates["title"]).strip()
        if not title:
            raise ValueError("title cannot be empty.")
        _reject_traversal(title, "title")
        updates = {**updates, "title": title}
    if "topic" in updates and updates["topic"]:
        _reject_traversal(str(updates["topic"]), "topic")
    if "entity" in updates and updates["entity"]:
        _reject_traversal(str(updates["entity"]), "entity")

    with _lock:
        drafts = _read_drafts()
        target = next((d for d in drafts if d.id == draft_id), None)
        if target is None:
            return None

        for attr, value in updates.items():
            if attr not in EDITABLE_FIELDS:
                continue
            if attr in ("topic", "entity", "research_question"):
                value = (str(value).strip() or None) if value is not None else None
            elif attr in ("key_findings", "open_questions", "recommended_next_actions"):
                value = _clean_lines(value if isinstance(value, list) else None)
            elif attr == "sources":
                value = _clean_sources(value if isinstance(value, list) else None)
            elif attr == "raw_notes":
                value = value or ""
            setattr(target, attr, value)

        if target.status == "draft":
            target.proposed_destination = _proposed_destination(
                target.title, target.topic, target.created_at
            )
        target.updated_at = _now()
        _write_drafts(drafts)
        return target


def save_draft(draft_id: str, vault_path: str) -> Tuple[ResearchDraft, dict]:
    """
    Write ONE Markdown research note for the draft under vaultPath/raw/research/<…>/.

    - Draft must exist and not already be saved.
    - Never overwrites: a UUID suffix is appended on filename collision.
    - Destination must stay under raw/research/ and inside the vault root (traversal rejected).
    - Does not run brain, call AI, fetch URLs, or modify tasks/calendar/resume.
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
            raise ValueError(f"Research draft '{draft_id}' not found.")
        if draft.status == "saved":
            raise ValueError("Draft is already saved.")

        # The destination is a relative path under raw/research/, computed from
        # slugified fields. Re-validate it strictly (defense against tampered storage).
        rel = (draft.proposed_destination or "").replace("\\", "/").strip()
        parts = rel.split("/")
        if not rel.startswith("raw/research/") or ".." in parts or rel.startswith("/"):
            logger.error("Path traversal blocked (rel): %s", rel)
            raise ValueError("Research destination must be a safe path under raw/research/. Save blocked.")

        dest_file = (vault_root / rel).resolve()
        vault_prefix = str(vault_root.resolve())
        if not (str(dest_file).startswith(vault_prefix + "/") or
                str(dest_file).startswith(vault_prefix + "\\")):
            logger.error("Path traversal blocked (resolved): %s", dest_file)
            raise ValueError("Resolved destination escapes the configured vault path. Save blocked.")

        dest_file.parent.mkdir(parents=True, exist_ok=True)

        if dest_file.exists():
            stem, suffix = dest_file.stem, dest_file.suffix
            dest_file = dest_file.parent / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
            rel = f"{Path(rel).parent.as_posix()}/{dest_file.name}"

        dest_file.write_text(render_markdown(draft), encoding="utf-8")

        draft.status     = "saved"
        draft.saved_path = rel
        draft.updated_at = _now()
        _write_drafts(drafts)

        logger.info(
            "Research draft saved: id=%s → %s (one markdown note; no brain, no AI, no fetch)",
            draft.id, dest_file,
        )
        return draft, {
            "relativePath": rel,
            "absolutePath": str(dest_file),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Proposal Queue integration (read-only)
# ══════════════════════════════════════════════════════════════════════════════

_DRAFT_STATUS_MAP = {"draft": "pending", "saved": "applied"}


def normalized_proposals() -> List[dict]:
    """
    Map research drafts into the generalized Proposal Queue shape. Read-only.
    Called by app.proposals.list_normalized_proposals().
    """
    items: List[dict] = []
    for d in list_drafts():
        if d.summary.strip():
            summary = d.summary.strip().split("\n", 1)[0][:240]
        elif d.key_findings:
            summary = d.key_findings[0][:240]
        else:
            summary = "Manual research capture"
        items.append({
            "id":         f"research:{d.id}",
            "source":     "research",
            "type":       "research_note",
            "riskLevel":  "medium",
            "title":      d.title,
            "summary":    summary,
            "status":     _DRAFT_STATUS_MAP.get(d.status, "pending"),
            "confidence": None,
            "targetPath": d.saved_path or d.proposed_destination,
            "createdAt":  d.created_at,
            "updatedAt":  d.updated_at,
            "relatedId":  d.id,
            "actions":    ["open_research"],
            "details": {
                "filename":   Path(d.proposed_destination).name,
                "domain":     d.domain,
                "entity":     d.entity,
                "sourceType": d.topic,
                "reason":     None,
            },
        })
    return items
