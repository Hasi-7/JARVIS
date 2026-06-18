"""
Generalized Proposal Queue aggregation (v1).

A thin, READ-ONLY layer that normalizes existing proposal-like items into a single
shape so the UI can review them in one place. It aggregates Raw Inbox
classification proposals, Chat/AI Consolidation drafts, and Research drafts.

This module mutates nothing: it does not approve, route, write vault files, write
intake metadata, run brain, or call Ollama. It only reads existing state and
reshapes it.

Future sources (Research, Gmail, MCP, OpenClaw tool requests) should plug into
list_normalized_proposals() by appending to the same normalized shape.
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.intake import list_proposals, list_staged

logger = logging.getLogger(__name__)

# Raw Inbox intake status  →  generalized proposal status.
#   proposed / edited → pending     (awaiting review)
#   approved          → approved    (approved, file not yet routed)
#   routed            → applied     (file copied into the vault)
#   skipped           → skipped
#   archived          → applied     (routed, staged original archived — terminal/done)
_STATUS_MAP: Dict[str, str] = {
    "proposed": "pending",
    "edited":   "pending",
    "approved": "approved",
    "routed":   "applied",
    "skipped":  "skipped",
    "archived": "applied",
}

# file_route is a medium-risk action per PRD §18 / §35.4.
_RAW_INBOX_RISK = "medium"


def _map_status(raw_status: str) -> str:
    return _STATUS_MAP.get(raw_status, "pending")


def _normalize_confidence(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip()
    return v or None


def _raw_inbox_proposals() -> List[dict]:
    """Map Raw Inbox classification proposals into the generalized shape."""
    proposals = list_proposals()
    # Build a file_id -> original filename lookup from staged entries.
    staged_by_id = {e.id: e for e in list_staged()}

    items: List[dict] = []
    for p in proposals:
        staged = staged_by_id.get(p.file_id)
        title = (
            (staged.original_name if staged else None)
            or p.routed_name
            or p.archived_name
            or p.file_id
        )
        status = _map_status(p.status)
        target_path = p.routed_path if p.status in ("routed", "archived") else p.proposed_destination
        created_at = staged.uploaded_at if staged else None
        updated_at = p.archived_at or p.routed_at or p.ai_classified_at or None

        items.append({
            "id":         f"raw-inbox:{p.file_id}",
            "source":     "raw-inbox",
            "type":       "file_route",
            "riskLevel":  _RAW_INBOX_RISK,
            "title":      title,
            "summary":    f"Route into {p.proposed_destination}",
            "status":     status,
            "confidence": _normalize_confidence(p.confidence),
            "targetPath": target_path,
            "createdAt":  created_at,
            "updatedAt":  updated_at,
            "relatedId":  p.file_id,
            "actions":    ["open_raw_inbox"],
            "details": {
                "filename":   title,
                "domain":     p.domain,
                "entity":     p.entity,
                "sourceType": p.source_type,
                "reason":     p.reason,
            },
        })
    return items


def list_normalized_proposals() -> Tuple[List[dict], List[dict]]:
    """
    Return (items, errors). Read-only. Never raises for a single failing source —
    a failing source contributes an error entry and an empty contribution so the
    rest of the queue still loads.
    """
    items: List[dict] = []
    errors: List[dict] = []

    try:
        items.extend(_raw_inbox_proposals())
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load Raw Inbox proposals for queue: %s", exc)
        errors.append({"source": "raw-inbox", "message": str(exc)})

    try:
        from app.consolidation import normalized_proposals as _consolidation_proposals
        items.extend(_consolidation_proposals())
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load consolidation drafts for queue: %s", exc)
        errors.append({"source": "chat-consolidation", "message": str(exc)})

    try:
        from app.research import normalized_proposals as _research_proposals
        items.extend(_research_proposals())
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load research drafts for queue: %s", exc)
        errors.append({"source": "research", "message": str(exc)})

    return items, errors
