"""
Agent Tool Request v0 — evaluate-only bridge between the agent surface and the
Permission Gateway.

The Local Agent (or a manual stand-in for it) creates a structured tool-request
proposal. The backend evaluates it through the existing Permission Gateway, writes
the existing gateway evaluation log, stores a redacted record, and returns the
decision. NOTHING is executed — this endpoint NEVER calls the execute path, the
brain wrapper, or any tool.

Safety model (this module never relaxes it):
- No tool execution of any kind (no /execute, no run_brain_command, no subprocess).
- No MCP/Gmail/browser/computer-use/Google/GitHub/Drive call; no OpenClaw/NemoClaw.
- No vault writes; no tasks/calendar/resume side effects; no AI call.
- `args` and `reason` are UNTRUSTED: args are only summarized (secrets redacted,
  values truncated) and never executed or forwarded to a tool; instructions inside
  reason/args are never followed.
"""

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.permission_gateway import (
    evaluate_tool_request,
    log_evaluation,
    sanitize_args_summary,
)

logger = logging.getLogger(__name__)

AGENT_REQUESTS_DIR: Path = Path(__file__).parent.parent / "data" / "agent-tool-requests"
REQUESTS_FILE:      Path = AGENT_REQUESTS_DIR / "requests.json"

_MAX_STORED = 200
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200
_MAX_REASON_LEN = 300
_MAX_REQUESTED_BY_LEN = 80

# v0 only ever uses this status. Future (not implemented): approved | executed |
# rejected | expired.
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
        return data if isinstance(data, list) else []
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Corrupted agent-tool-requests file, starting fresh: %s", exc)
        return []


def _write_requests(entries: List[dict]) -> None:
    _ensure_dir()
    REQUESTS_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


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


# ── public API ──────────────────────────────────────────────────────────────────

def create_request(
    *,
    tool: str,
    args: Optional[dict],
    reason: Optional[str],
    requested_by: Optional[str],
    conversation_id: Optional[str],
) -> dict:
    """
    Evaluate a proposed tool request through the Permission Gateway, write the
    gateway evaluation log, store a redacted record, and return it. NEVER executes.

    Raises ValueError (user-facing) on an invalid request shape (empty tool).
    """
    # evaluate_tool_request validates the tool and raises ValueError on empty tool.
    # It is classification-only: it never executes anything.
    result = evaluate_tool_request(
        tool=tool, args=args, reason=reason, requested_by=requested_by,
    )

    # Write the existing gateway evaluation log (source=gateway_eval). No execution log.
    eval_entry = log_evaluation(result, requested_by=requested_by, reason=reason)

    requested_by_clean = _truncate(requested_by, _MAX_REQUESTED_BY_LEN) or "local-agent"
    record = {
        "id":             str(uuid.uuid4()),
        "tool":           result["tool"],
        # Store only the sanitized summary — never the raw args.
        "argsSummary":    result["sanitizedArgsSummary"],
        "reason":         _truncate(reason, _MAX_REASON_LEN),
        "requestedBy":    requested_by_clean,
        "conversationId": conversation_id,
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
        "status":         STATUS_EVALUATED_ONLY,   # never executed in v0
    }

    with _lock:
        entries = _read_requests()
        entries.append(record)
        if len(entries) > _MAX_STORED:
            entries = entries[-_MAX_STORED:]
        _write_requests(entries)

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
