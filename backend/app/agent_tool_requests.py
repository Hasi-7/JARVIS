"""
Agent Tool Request — evaluation and Assist-only approval handoff.

The Local Agent (or a manual stand-in for it) creates a structured tool-request
proposal. The backend evaluates it through the Permission Gateway and first stores
a redacted, non-executable record. Eligible canonical Assist requests may then be
linked to the separate approval queue. Creation never executes a tool.

Safety model (this module never relaxes it):
- No tool execution during request creation (no run_brain_command or subprocess).
- No MCP/Gmail/browser/computer-use/Google/GitHub/Drive call; no OpenClaw/NemoClaw.
- No vault/tool side effects and no AI call during request creation.
- Raw args are never stored in the agent-request record. Approval-eligible args are
  separately validated and persisted only in the backend-local approval service.
- An approval cannot execute unless it is linked back to this stored request.
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.agent_modes import ASSIST, normalize_mode

from app.permission_gateway import (
    evaluate_tool_request,
    log_evaluation,
)

logger = logging.getLogger(__name__)

AGENT_REQUESTS_DIR: Path = Path(__file__).parent.parent / "data" / "agent-tool-requests"
REQUESTS_FILE:      Path = AGENT_REQUESTS_DIR / "requests.json"

_MAX_STORED = 200
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200
_MAX_REASON_LEN = 300
_MAX_REQUESTED_BY_LEN = 80

# Every request starts evaluate-only. Eligible Assist requests may then be linked
# to a separate pending approval; this store itself never executes a tool.
STATUS_EVALUATED_ONLY = "evaluated_only"

_lock = threading.Lock()


# ── storage ─────────────────────────────────────────────────────────────────────

def _ensure_dir() -> None:
    AGENT_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)


def _read_requests() -> List[dict]:
    _ensure_dir()
    if not REQUESTS_FILE.exists():
        return []
    try:
        data = json.loads(REQUESTS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Agent request store root must be a list.")
        return data
    except Exception as exc:
        logger.error("Could not read agent request store safely: %s", exc)
        raise ValueError("Agent request store is unreadable; refusing to overwrite it.") from exc


def _write_requests(entries: List[dict]) -> None:
    _ensure_dir()
    tmp = REQUESTS_FILE.with_name(f"{REQUESTS_FILE.name}.{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(entries, indent=2, ensure_ascii=False))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, REQUESTS_FILE)


# ── helpers ─────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def _truncate(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    v = str(value).replace("\n", " ").replace("\r", " ").strip()
    if not v:
        return None
    return v[:limit] + "…" if len(v) > limit else v


def _persist_new_request(record: dict) -> None:
    with _lock:
        entries = _read_requests()
        entries.append(record)
        _write_requests(_retain_requests(entries))


def _retain_requests(entries: List[dict]) -> List[dict]:
    live_statuses = {"pending_approval", "approved", "executing"}
    live = [
        record for record in entries
        if record.get("approvalId") and record.get("approvalStatus") in live_statuses
    ]
    live_ids = {id(record) for record in live}
    recent = [record for record in entries if id(record) not in live_ids][-_MAX_STORED:]
    keep_ids = {id(record) for record in live + recent}
    return [record for record in entries if id(record) in keep_ids]


def _bind_approval(request_id: str, approval_id: str, args_summary: str) -> None:
    with _lock:
        entries = _read_requests()
        for index, record in enumerate(entries):
            if record.get("id") != request_id:
                continue
            if record.get("status") != STATUS_EVALUATED_ONLY or record.get("approvalId"):
                raise ValueError("Agent request is not eligible for approval binding.")
            record["approvalId"] = approval_id
            record["status"] = "pending_approval"
            record["approvalStatus"] = "pending_approval"
            record["argsSummary"] = args_summary
            entries[index] = record
            _write_requests(entries)
            return
    raise ValueError("Agent request disappeared before approval binding.")


def update_approval_status_internal(request_id: str, approval_id: str, status: str) -> None:
    """Mirror approval state for retention; linkage identity cannot be changed here."""
    with _lock:
        entries = _read_requests()
        for index, record in enumerate(entries):
            if record.get("id") != request_id:
                continue
            if record.get("approvalId") != approval_id:
                raise ValueError("Agent request approval linkage does not match.")
            record["approvalStatus"] = status
            record["status"] = status
            entries[index] = record
            _write_requests(_retain_requests(entries))
            return
    raise ValueError("Agent request was not found for approval status update.")


def get_request_internal(request_id: str) -> Optional[dict]:
    """Internal linkage lookup. Agent records contain no canonical/raw arguments."""
    with _lock:
        for record in _read_requests():
            if record.get("id") == request_id:
                return dict(record)
    return None


# ── public API ──────────────────────────────────────────────────────────────────

def create_request(
    *,
    tool: str,
    args: Optional[dict],
    reason: Optional[str],
    requested_by: Optional[str],
    conversation_id: Optional[str],
    mode: Optional[str] = None,
) -> dict:
    """
    Evaluate a proposed tool request through the Permission Gateway, write the
    gateway evaluation log, store a redacted record, and return it. NEVER executes.

    Raises ValueError (user-facing) on an invalid request shape (empty tool).
    """
    canonical_mode = normalize_mode(mode)
    request_id = str(uuid.uuid4())

    # evaluate_tool_request validates the tool and raises ValueError on empty tool.
    # It is classification-only: it never executes anything.
    result = evaluate_tool_request(
        tool=tool, args=args, reason=reason, requested_by=requested_by,
    )

    from app.permission_gateway import is_approval_required_tool
    approval_eligible = canonical_mode == ASSIST and is_approval_required_tool(result["tool"])
    if approval_eligible:
        # Do not put canonical-equivalent short task/calendar values in the public
        # evaluation log while canonical validation/linkage is still pending.
        result["sanitizedArgsSummary"] = "Approval-required arguments withheld pending validation."

    # Write the existing gateway evaluation log (source=gateway_eval). No execution log.
    eval_entry = log_evaluation(
        result, requested_by=requested_by, reason=reason, request_id=request_id,
    )

    requested_by_clean = _truncate(requested_by, _MAX_REQUESTED_BY_LEN) or "local-agent"
    record = {
        "id":             request_id,
        "tool":           result["tool"],
        # Store only the sanitized summary — never the raw args.
        "argsSummary":    (
            "Approval-required arguments withheld pending validation."
            if approval_eligible else result["sanitizedArgsSummary"]
        ),
        "reason":         _truncate(reason, _MAX_REASON_LEN),
        "requestedBy":    requested_by_clean,
        "conversationId": conversation_id,
        "mode":           canonical_mode,
        "approvalId":     None,
        "approvalStatus": None,
        "evaluation": {
            "allowed":          bool(result["allowed"]),
            "decision":         result["decision"],
            "riskLevel":        result["riskLevel"],
            "requiresApproval": bool(result["requiresApproval"]),
            "executionEnabled": bool(result["executionEnabled"]),
            "reason":           result["reason"],
            "policyNotes":      result["policyNotes"],
            "logId":            eval_entry["id"],
        },
        "createdAt":      _now(),
        "status":         STATUS_EVALUATED_ONLY,   # persisted before any approval link
    }

    # Persist the non-executable evaluation before creating any approval. This
    # guarantees approval creation cannot precede its source request.
    _persist_new_request(record)

    # Only an explicitly resolved canonical Assist request can enter the durable
    # approval queue. Other modes retain the already-persisted evaluate-only record.
    if approval_eligible:
        from app.tool_approvals import create_approval
        approval = create_approval(
            request_id=request_id,
            tool=result["tool"],
            args=args,
            mode=canonical_mode,
            reason=_truncate(reason, _MAX_REASON_LEN),
            requested_by=requested_by_clean,
            evaluation_log_id=eval_entry["id"],
        )
        try:
            _bind_approval(request_id, approval["id"], approval["argsSummary"])
        except Exception:
            # Roll back the pending approval if possible. If rollback storage
            # also fails, execution still rejects it because linkage is absent.
            from app.tool_approvals import delete_unbound_approval
            try:
                delete_unbound_approval(approval["id"], request_id)
            except Exception as rollback_exc:  # pragma: no cover - defensive
                logger.error("Approval rollback failed; linkage remains fail-closed: %s", rollback_exc)
            raise
        record["approvalId"] = approval["id"]
        record["status"] = "pending_approval"
        record["approvalStatus"] = "pending_approval"
        record["argsSummary"] = approval["argsSummary"]

    logger.info(
        "Agent tool request evaluated (NOT executed): id=%s tool=%s decision=%s by=%s",
        record["id"], record["tool"], record["evaluation"]["decision"], requested_by_clean,
    )
    return record


def list_requests(limit: int = _DEFAULT_LIMIT) -> List[dict]:
    """Return stored agent tool requests, newest first. Read-only."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_LIMIT
    limit = max(1, min(limit, _MAX_LIMIT))

    with _lock:
        entries = _read_requests()
    return list(reversed(entries))[:limit]
