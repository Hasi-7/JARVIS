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


# ── apply / reject dispatch (A1) ──────────────────────────────────────────────
#
# The apply spine does NOT introduce a new write primitive. It dispatches a
# normalized proposal id to the SAME save/route function the source page already
# uses manually, so every safety guarantee (never-overwrite, stay-in-vault,
# path-traversal rejection, no brain/AI side effects) is inherited unchanged.
#
# Generalized statuses that are eligible to be applied.
_APPLYABLE_STATUSES = {"pending", "approved"}

# Normalized-id prefixes → source label, for messages.
_KNOWN_PREFIXES = {
    "raw-inbox", "consolidation", "research", "email-intake",
    # MVP v8: an Email Intake draft's proposed rows applied into the vault.
    "email-task", "email-calendar",
}


def _split_proposal_id(proposal_id: str) -> Tuple[str, str]:
    """Split "<prefix>:<relatedId>" — relatedId is a UUID/file_id (no colon)."""
    prefix, sep, related = (proposal_id or "").partition(":")
    if not sep or not prefix or not related:
        raise ValueError(f"Malformed proposal id: {proposal_id!r}")
    if prefix not in _KNOWN_PREFIXES:
        raise ValueError(f"Unknown proposal source '{prefix}'.")
    return prefix, related


def _apply_raw_inbox(file_id: str, vault_path: str) -> dict:
    from app.intake import approve_proposal, list_proposals, route_proposal

    proposal = next((p for p in list_proposals() if p.file_id == file_id), None)
    if proposal is None:
        raise ValueError(f"Raw Inbox proposal '{file_id}' not found.")
    if proposal.status in ("routed", "archived"):
        return {"ok": True, "status": "applied", "alreadyApplied": True,
                "message": "Already routed into the vault.",
                "targetPath": proposal.routed_path}
    if proposal.status == "skipped":
        raise ValueError("Skipped proposal cannot be applied. Re-open it in Raw Inbox.")
    approve_proposal(file_id)
    routed, info = route_proposal(file_id, vault_path)
    return {"ok": True, "status": "applied", "alreadyApplied": False,
            "message": f"Routed into {info['relativePath']}",
            "targetPath": info["relativePath"]}


def _apply_draft(prefix: str, related: str, vault_path: str) -> dict:
    if prefix == "consolidation":
        from app.consolidation import save_draft as _save
    elif prefix == "research":
        from app.research import save_draft as _save
    else:  # email-intake
        from app.email_intake import save_draft as _save
    draft, info = _save(related, vault_path)
    return {"ok": True, "status": "applied", "alreadyApplied": False,
            "message": f"Saved to {info['relativePath']}",
            "targetPath": info["relativePath"]}


def apply_proposal(proposal_id: str, vault_path: str) -> dict:
    """
    Apply one normalized proposal by dispatching to its source save/route path.
    Returns a result dict; raises ValueError (user-facing) on failure.
    """
    prefix, related = _split_proposal_id(proposal_id)
    if prefix == "raw-inbox":
        result = _apply_raw_inbox(related, vault_path)
    elif prefix == "email-task":
        result = apply_email_task_rows(related, vault_path)
    elif prefix == "email-calendar":
        result = apply_email_calendar_rows(related, vault_path)
    else:
        result = _apply_draft(prefix, related, vault_path)
    result["id"] = proposal_id
    return result


def apply_batch(ids: List[str], vault_path: str) -> List[dict]:
    """Apply many; never raise for one failure — collect per-item results."""
    results: List[dict] = []
    for pid in ids:
        try:
            results.append(apply_proposal(pid, vault_path))
        except ValueError as exc:
            results.append({"id": pid, "ok": False, "status": "error",
                            "alreadyApplied": False, "message": str(exc),
                            "targetPath": None})
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("apply_batch failed for %s: %s", pid, exc)
            results.append({"id": pid, "ok": False, "status": "error",
                            "alreadyApplied": False,
                            "message": "Unexpected error while applying.",
                            "targetPath": None})
    return results


def reject_proposal(proposal_id: str) -> dict:
    """
    Reject a proposal. Supported for Raw Inbox (marks it skipped). Draft sources
    have no reject state in v1 — edit or leave the draft unsaved instead.
    """
    prefix, related = _split_proposal_id(proposal_id)
    if prefix == "raw-inbox":
        from app.intake import skip_proposal
        updated = skip_proposal(related)
        if updated is None:
            raise ValueError(f"Raw Inbox proposal '{related}' not found.")
        return {"id": proposal_id, "ok": True, "status": "skipped",
                "alreadyApplied": False, "message": "Marked skipped.",
                "targetPath": None}
    raise ValueError(
        "Rejecting is not supported for this source yet. "
        "Edit or leave the draft unsaved in its source page."
    )


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

    try:
        from app.email_intake import normalized_proposals as _email_proposals
        items.extend(_email_proposals())
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load email intake drafts for queue: %s", exc)
        errors.append({"source": "email-intake", "message": str(exc)})

    return items, errors


# ══════════════════════════════════════════════════════════════════════════════
# Email Intake proposed rows → vault (MVP v8)
# ══════════════════════════════════════════════════════════════════════════════
# Email Intake records proposed task and calendar rows as free text. This turns
# them into real vault rows through the SAME adapters the A3 approval queue uses
# (`vault.create_task`, `calendar.create_calendar_candidate`), so backup-before-
# write, conflict re-check, pipe sanitisation and traversal rejection are all
# inherited unchanged — no new write primitive is introduced here.
#
# Parsing is deliberately conservative. A calendar candidate REQUIRES a date, and
# this never invents one: a row with no recognisable date is reported as skipped
# rather than being placed on an arbitrary day.

import re as _re

_MAX_ROWS_PER_APPLY = 25
_MAX_TITLE_CHARS = 200

# ISO first (unambiguous), then common written forms. Deliberately no bare
# numeric D/M vs M/D form — that is ambiguous and guessing would be worse than
# skipping the row.
_DATE_PATTERNS = (
    (_re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), "%Y-%m-%d"),
    (_re.compile(r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b", _re.I), "%d %b %Y"),
    (_re.compile(r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b", _re.I), "%b %d %Y"),
)
_TIME_RE = _re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", _re.I)
_DURATION_RE = _re.compile(r"\b(\d+(?:\.\d+)?\s*(?:h|hr|hrs|hour|hours|m|min|mins|minutes))\b", _re.I)


def _clean_row(text: str) -> str:
    """Collapse whitespace and strip list markers. Newlines would break a table."""
    cleaned = " ".join(str(text or "").split())
    return _re.sub(r"^[-*\u2022]\s*", "", cleaned).strip()


def parse_task_row(text: str) -> Optional[dict]:
    """Parse a proposed task row into a `vault.create_task` payload, or None."""
    row = _clean_row(text)
    if not row:
        return None

    due = ""
    for pattern, fmt in _DATE_PATTERNS:
        match = pattern.search(row)
        if match:
            from datetime import datetime as _dt
            raw = match.group(1).replace(",", "")
            try:
                due = _dt.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                due = ""
            break

    return {"title": row[:_MAX_TITLE_CHARS], "due": due}


def parse_calendar_row(text: str) -> Optional[dict]:
    """Parse a proposed calendar row, or None when it carries no usable date.

    Returning None is the correct outcome for a dateless row: a calendar
    candidate without a date cannot be scheduled, and inventing one would put a
    fabricated commitment in the user's calendar file.
    """
    row = _clean_row(text)
    if not row:
        return None

    date = ""
    for pattern, fmt in _DATE_PATTERNS:
        match = pattern.search(row)
        if match:
            from datetime import datetime as _dt
            raw = match.group(1).replace(",", "")
            try:
                date = _dt.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                date = ""
            break
    if not date:
        return None

    time_match = _TIME_RE.search(row)
    time_value = ""
    if time_match:
        hour, minute, meridiem = int(time_match.group(1)), time_match.group(2), time_match.group(3)
        if meridiem:
            meridiem = meridiem.lower()
            if meridiem == "pm" and hour != 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
        if 0 <= hour <= 23:
            time_value = f"{hour:02d}:{minute}"

    duration_match = _DURATION_RE.search(row)
    return {
        "title": row[:_MAX_TITLE_CHARS],
        "date": date,
        "time": time_value,
        "duration": duration_match.group(1).replace(" ", "") if duration_match else "",
        "source": "email-intake",
        # Never pre-approved: an emailed suggestion is a proposal, not a decision.
        "approved": "No",
    }


def _load_email_draft(draft_id: str):
    from app.email_intake import get_draft
    draft = get_draft(draft_id)
    if draft is None:
        raise ValueError(f"Email intake draft '{draft_id}' not found.")
    return draft


def apply_email_task_rows(draft_id: str, vault_path: str) -> dict:
    """Create one vault task per parseable proposed task row."""
    from app.vault import create_task

    draft = _load_email_draft(draft_id)
    rows = list(draft.proposed_task_rows or [])[:_MAX_ROWS_PER_APPLY]
    if not rows:
        raise ValueError("This email draft has no proposed task rows.")

    created: List[str] = []
    skipped: List[str] = []
    for row in rows:
        payload = parse_task_row(row)
        if payload is None:
            skipped.append(_clean_row(row) or "(blank row)")
            continue
        try:
            create_task(
                vault_path=vault_path,
                title=payload["title"],
                status="todo",
                source="email-intake",
                due=payload["due"] or None,
            )
            created.append(payload["title"])
        except ValueError as exc:
            skipped.append(f"{payload['title']} — {exc}")

    if not created:
        raise ValueError(
            "No task rows could be applied. " + ("; ".join(skipped) if skipped else "")
        )

    message = f"Created {len(created)} task(s)."
    if skipped:
        message += f" Skipped {len(skipped)}: " + "; ".join(skipped[:3])
    return {
        "ok": True, "status": "applied", "alreadyApplied": False,
        "message": message, "targetPath": "ops/task-db.md",
        "created": created, "skipped": skipped,
    }


def apply_email_calendar_rows(draft_id: str, vault_path: str) -> dict:
    """Create one calendar candidate per proposed row that carries a date."""
    from app.calendar import create_calendar_candidate

    draft = _load_email_draft(draft_id)
    rows = list(draft.proposed_calendar_rows or [])[:_MAX_ROWS_PER_APPLY]
    if not rows:
        raise ValueError("This email draft has no proposed calendar rows.")

    created: List[str] = []
    skipped: List[str] = []
    for row in rows:
        payload = parse_calendar_row(row)
        if payload is None:
            skipped.append(f"{_clean_row(row) or '(blank row)'} — no date found")
            continue
        try:
            create_calendar_candidate(vault_path, payload)
            created.append(payload["title"])
        except ValueError as exc:
            skipped.append(f"{payload['title']} — {exc}")

    if not created:
        raise ValueError(
            "No calendar rows could be applied. " + ("; ".join(skipped) if skipped else "")
        )

    message = f"Created {len(created)} calendar candidate(s), all Approved=No."
    if skipped:
        message += f" Skipped {len(skipped)}: " + "; ".join(skipped[:3])
    return {
        "ok": True, "status": "applied", "alreadyApplied": False,
        "message": message, "targetPath": "ops/calendar-candidates.md",
        "created": created, "skipped": skipped,
    }
