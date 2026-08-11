"""Durable, Assist-only approval queue for four narrow local tools."""

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.agent_modes import ASSIST, normalize_mode
from app.permission_gateway import (
    evaluate_tool_request,
    get_log_entry_internal,
    is_approval_required_tool,
    log_approval_transition,
    log_approved_execution,
    privileged_execution_enabled,
)
from app.write_lock import approval_state_lock

logger = logging.getLogger(__name__)

APPROVALS_DIR = Path(__file__).parent.parent / "data" / "tool-approvals"
APPROVALS_FILE = APPROVALS_DIR / "approvals.json"
APPROVAL_TOKEN_ENV = "BRAIN_UI_APPROVAL_TOKEN"
_MAX_STORED = 200
_MAX_LIVE_APPROVALS = 100
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200
_AUDIT_PERSISTENCE_WARNING = (
    "Tool executed, but audit persistence failed; inspect backend logs."
)
_lock = approval_state_lock
_dispatch_lock = threading.Lock()


class ApprovalError(ValueError):
    pass


class ApprovalNotFound(ApprovalError):
    pass


class ApprovalConflict(ApprovalError):
    pass


class ApprovalDisabled(ApprovalError):
    pass


class ApprovalAuthNotConfigured(ApprovalError):
    pass


class ApprovalUnauthorized(ApprovalError):
    pass


class ApprovalForbidden(ApprovalError):
    pass


class ApprovalAuditError(ApprovalError):
    pass


class ApprovalCapacityError(ApprovalError):
    pass


class _NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _TaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(max_length=300)
    status: Literal["todo", "in progress", "blocked", "done"]
    area: Optional[str] = Field(default=None, max_length=500)
    priority: Optional[Literal["low", "medium", "high"]] = None
    due: Optional[str] = Field(default=None, max_length=10)
    source: Optional[str] = Field(default=None, max_length=500)

    @field_validator("title", "status", "area", "priority", "due", "source", mode="before")
    @classmethod
    def _clean(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string or null")
        if "\n" in value or "\r" in value:
            raise ValueError("must not contain newlines")
        return value.strip()

    @field_validator("status", "priority", mode="before")
    @classmethod
    def _lower(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("due")
    @classmethod
    def _valid_due(cls, value):
        return _validate_iso_date(value, "due")

    @model_validator(mode="after")
    def _title_required(self):
        if not self.title:
            raise ValueError("title is required and cannot be empty")
        return self


class _CalendarArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str = Field(max_length=10)
    time: Optional[str] = Field(default=None, max_length=5)
    duration: Optional[str] = Field(default=None, max_length=50)
    title: str = Field(max_length=300)
    reason: Optional[str] = Field(default=None, max_length=500)
    source: Optional[str] = Field(default=None, max_length=500)

    @field_validator("date", "time", "duration", "title", "reason", "source", mode="before")
    @classmethod
    def _clean(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string or null")
        if "\n" in value or "\r" in value:
            raise ValueError("must not contain newlines")
        return value.strip()

    @field_validator("date")
    @classmethod
    def _valid_date(cls, value):
        return _validate_iso_date(value, "date")

    @field_validator("time")
    @classmethod
    def _valid_time(cls, value):
        if value is not None and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("time must use HH:MM (24-hour) format")
        return value

    @field_validator("duration")
    @classmethod
    def _valid_duration(cls, value):
        if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .:+-]{0,49}", value):
            raise ValueError("duration contains unsupported characters")
        return value

    @model_validator(mode="after")
    def _required_fields(self):
        if not self.title:
            raise ValueError("title is required and cannot be empty")
        if not self.date:
            raise ValueError("date is required and cannot be empty")
        return self


_ARG_MODELS = {
    "brain.today": _NoArgs,
    "brain.sync_raw": _NoArgs,
    "vault.create_task": _TaskArgs,
    "calendar.create_candidate": _CalendarArgs,
}


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def _validate_iso_date(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{field_name} must use YYYY-MM-DD format")
    try:
        date_type.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid calendar date") from exc
    return value


def authorize_approval_token(provided_token: Optional[str]) -> None:
    """Authorize an approval mutation without storing, returning, or logging tokens."""
    if not isinstance(provided_token, str) or provided_token == "":
        raise ApprovalUnauthorized("Approval authorization token is required.")
    expected = os.environ.get(APPROVAL_TOKEN_ENV)
    if expected is None or not expected.strip():
        raise ApprovalAuthNotConfigured("Approval authorization is not configured.")
    if not hmac.compare_digest(provided_token, expected):
        raise ApprovalForbidden("Approval authorization token is invalid.")


def _canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _integrity(*, approval_id: str, tool: str, mode: str, policy: dict, args: dict, request_id: str,
               args_summary: str, reason: Optional[str], requested_by: str,
               evaluation_log_id: str) -> str:
    bound = {
        "approvalId": approval_id,
        "tool": tool,
        "mode": mode,
        "policy": policy,
        "args": args,
        "requestId": request_id,
        "argsSummary": args_summary,
        "reason": reason,
        "requestedBy": requested_by,
        "evaluationLogId": evaluation_log_id,
    }
    return hashlib.sha256(_canonical_json(bound).encode("utf-8")).hexdigest()


def _clean_text(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).replace("\r", " ").replace("\n", " ").strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _approval_args_summary(tool: str, args: dict) -> str:
    """Describe an approval without echoing canonical-equivalent argument values."""
    if tool.startswith("brain."):
        return "(no args)"
    present = sorted(key for key, value in args.items() if value not in (None, ""))
    if tool == "vault.create_task":
        return f"Task creation request ({len(present)} field(s) configured)"
    if tool == "calendar.create_candidate":
        return f"Calendar candidate request ({len(present)} field(s) configured)"
    return "Approval-required arguments withheld"


def validate_canonical_args(tool: str, args: Optional[dict]) -> dict:
    model = _ARG_MODELS.get(tool)
    if model is None:
        raise ApprovalError("Tool is not eligible for privileged approval execution.")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ApprovalError("Tool arguments must be an object.")
    try:
        return model.model_validate(args).model_dump()
    except ValidationError as exc:
        raise ApprovalError(f"Invalid arguments for '{tool}': {exc}") from exc


def _ensure_dir() -> None:
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)


def _read() -> list[dict]:
    if not APPROVALS_FILE.exists():
        return []
    try:
        data = json.loads(APPROVALS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ApprovalError("Approval store root must be a list.")
        return data
    except Exception as exc:
        logger.error("Could not read approval store safely: %s", exc)
        raise ApprovalError("Approval store is unreadable; refusing to overwrite it.") from exc


def _write(entries: list[dict]) -> None:
    _ensure_dir()
    entries = _retain_approvals(entries)
    tmp = APPROVALS_FILE.with_name(f"{APPROVALS_FILE.name}.{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(entries, indent=2, ensure_ascii=False))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, APPROVALS_FILE)


def _retain_approvals(entries: list[dict]) -> list[dict]:
    live_statuses = {"pending_approval", "approved", "executing"}
    live = [record for record in entries if record.get("status") in live_statuses]
    live_ids = {id(record) for record in live}
    terminal = [record for record in entries if id(record) not in live_ids][-_MAX_STORED:]
    keep_ids = {id(record) for record in live + terminal}
    return [record for record in entries if id(record) in keep_ids]


def _public(record: dict) -> dict:
    return {
        "id": record["id"],
        "requestId": record["requestId"],
        "status": record["status"],
        "tool": record["tool"],
        "mode": record["mode"],
        "risk": record["riskLevel"],
        "argsSummary": record["argsSummary"],
        "reviewFields": _review_fields(record),
        "reason": record.get("reason"),
        "requestedBy": record["requestedBy"],
        "approvedBy": record.get("approvedBy"),
        "rejectedBy": record.get("rejectedBy"),
        "createdAt": record["createdAt"],
        "approvedAt": record.get("approvedAt"),
        "rejectedAt": record.get("rejectedAt"),
        "executionStartedAt": record.get("executionStartedAt"),
        "executedAt": record.get("executedAt"),
        "failedAt": record.get("failedAt"),
        "evaluationLogId": record.get("evaluationLogId"),
        "executionLogId": record.get("executionLogId"),
        "transitionLogId": record.get("transitionLogId"),
        "result": record.get("result"),
        "error": record.get("error"),
        "auditWarning": record.get("auditWarning"),
    }


def _review_fields(record: dict) -> dict:
    """Return only source-specific validated canonical fields for authenticated review."""
    tool = record.get("tool")
    args = record.get("canonicalArgs") or {}
    if tool in {"brain.today", "brain.sync_raw"}:
        return {}
    if tool == "vault.create_task":
        return {
            "title": args.get("title"),
            "status": args.get("status"),
            "area": args.get("area"),
            "priority": args.get("priority"),
            "due": args.get("due"),
            "source": args.get("source"),
        }
    if tool == "calendar.create_candidate":
        return {
            "date": args.get("date"),
            "time": args.get("time"),
            "duration": args.get("duration"),
            "title": args.get("title"),
            "reason": args.get("reason"),
            "source": args.get("source"),
            "approved": "No",
        }
    return {}


def _find(entries: list[dict], identifier: str) -> tuple[int, dict]:
    for index, record in enumerate(entries):
        if record.get("id") == identifier or record.get("requestId") == identifier:
            return index, record
    raise ApprovalNotFound(f"Approval/request '{identifier}' was not found.")


def _validate_request_link(record: dict) -> None:
    from app.agent_tool_requests import get_request_internal

    request = get_request_internal(record.get("requestId", ""))
    if request is None:
        raise ApprovalConflict("Approval source request is missing; execution is blocked.")
    record_status = record.get("status")
    expected_source_statuses = {
        "pending_approval": {"pending_approval"},
        "approved": {"approved"},
        "executing": {"approved", "executing"},
    }.get(record_status, {request.get("approvalStatus")})
    if (
        request.get("approvalId") != record.get("id")
        or request.get("approvalStatus") not in expected_source_statuses
        or request.get("status") != request.get("approvalStatus")
        or request.get("mode") != ASSIST
        or request.get("tool") != record.get("tool")
    ):
        raise ApprovalConflict("Approval source request linkage is invalid; execution is blocked.")


def _validate_approved_transition(record: dict) -> None:
    transition_log_id = record.get("transitionLogId")
    if not transition_log_id:
        raise ApprovalConflict("Approved transition evidence is missing; execution is blocked.")
    entry = get_log_entry_internal(transition_log_id)
    if not entry or (
        entry.get("source") != "approval_transition"
        or entry.get("decision") != "approved"
        or entry.get("approvalId") != record.get("id")
        or entry.get("requestId") != record.get("requestId")
        or entry.get("approvedBy") != record.get("approvedBy")
        or entry.get("approvedAt") != record.get("approvedAt")
    ):
        raise ApprovalConflict("Approved transition evidence is invalid; execution is blocked.")


def _mirror_request_status(record: dict, status: str) -> None:
    from app.agent_tool_requests import update_approval_status_internal

    try:
        update_approval_status_internal(record["requestId"], record["id"], status)
    except Exception as exc:  # retention errs toward keeping the linked request
        logger.error("Could not mirror approval status to agent request: %s", exc)


def delete_unbound_approval(approval_id: str, request_id: str) -> None:
    """Internal rollback only; never deletes an approved or executing record."""
    with _lock:
        entries = _read()
        index, record = _find(entries, approval_id)
        if record.get("requestId") != request_id or record.get("status") != "pending_approval":
            raise ApprovalConflict("Only the matching unbound pending approval can be rolled back.")
        del entries[index]
        _write(entries)


def create_approval(*, request_id: str, tool: str, args: Optional[dict], mode: str,
                    reason: Optional[str], requested_by: str, evaluation_log_id: str) -> dict:
    canonical_mode = normalize_mode(mode)
    if canonical_mode != ASSIST:
        raise ApprovalError("Only canonical Assist mode requests are approval eligible.")
    if not is_approval_required_tool(tool):
        raise ApprovalError("Tool is not eligible for privileged approval execution.")
    canonical_args = validate_canonical_args(tool, args)
    evaluation = evaluate_tool_request(tool, canonical_args, reason, requested_by)
    if evaluation["decision"] != "requires_approval" or not evaluation["requiresApproval"]:
        raise ApprovalError("Current tool policy does not permit approval queueing.")
    policy = {
        "decision": evaluation["decision"],
        "riskLevel": evaluation["riskLevel"],
        "requiresApproval": True,
        "policyNotes": evaluation.get("policyNotes"),
    }
    reason = _clean_text(reason, 300)
    requested_by = _clean_text(requested_by, 80) or "local-agent"
    args_summary = _approval_args_summary(tool, canonical_args)
    approval_id = str(uuid.uuid4())
    record = {
        "id": approval_id,
        "requestId": request_id,
        "status": "pending_approval",
        "tool": tool,
        "mode": canonical_mode,
        "riskLevel": evaluation["riskLevel"],
        "canonicalArgs": canonical_args,
        "argsSummary": args_summary,
        "reason": reason,
        "requestedBy": requested_by,
        "policyBinding": policy,
        "integrity": _integrity(
            approval_id=approval_id,
            tool=tool,
            mode=canonical_mode,
            policy=policy,
            args=canonical_args,
            request_id=request_id,
            args_summary=args_summary,
            reason=reason,
            requested_by=requested_by,
            evaluation_log_id=evaluation_log_id,
        ),
        "evaluationLogId": evaluation_log_id,
        "executionLogId": None,
        "transitionLogId": None,
        "createdAt": _now(),
        "approvedAt": None,
        "rejectedAt": None,
        "executionStartedAt": None,
        "executedAt": None,
        "failedAt": None,
        "approvedBy": None,
        "rejectedBy": None,
        "result": None,
        "error": None,
        "auditWarning": None,
    }
    with _lock:
        entries = _read()
        if any(r.get("requestId") == request_id for r in entries):
            raise ApprovalConflict("An approval already exists for this request.")
        live_count = sum(
            1 for item in entries
            if item.get("status") in {"pending_approval", "approved", "executing"}
        )
        if live_count >= _MAX_LIVE_APPROVALS:
            raise ApprovalCapacityError(
                f"Live approval capacity ({_MAX_LIVE_APPROVALS}) has been reached."
            )
        entries.append(record)
        _write(entries)
    return _public(record)


def list_approvals(limit: int = _DEFAULT_LIMIT) -> list[dict]:
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_LIMIT
    limit = max(1, min(limit, _MAX_LIMIT))
    with _lock:
        entries = _read()
    return [_public(r) for r in reversed(entries[-limit:])]


def protected_live_transition_log_ids() -> set[str]:
    """Return transition evidence IDs referenced by live executable approvals."""
    with _lock:
        return {
            record["transitionLogId"]
            for record in _read()
            if record.get("status") in {"approved", "executing"}
            and record.get("transitionLogId")
        }


def approve(identifier: str, actor: Optional[str] = None) -> dict:
    if not privileged_execution_enabled():
        raise ApprovalDisabled("Privileged execution is disabled by the operator kill switch.")
    with _lock:
        entries = _read()
        index, record = _find(entries, identifier)
        if record["status"] != "pending_approval":
            raise ApprovalConflict(f"Approval cannot transition from '{record['status']}' to approved.")
        _validate_request_link(record)
        original = dict(record)
        record["status"] = "approved"
        record["approvedAt"] = _now()
        record["approvedBy"] = _clean_text(actor, 80) or "local-user"
        record["transitionLogId"] = None
        entries[index] = record
        _write(entries)
        try:
            transition = log_approval_transition(record, "approved")
            record["transitionLogId"] = transition["id"]
            entries[index] = record
            _write(entries)
        except Exception as exc:
            entries[index] = original
            try:
                _write(entries)
            except Exception as rollback_exc:
                logger.critical("Approval transition rollback failed; missing evidence blocks execution: %s", rollback_exc)
            raise ApprovalAuditError("Approval transition audit failed; approval was not made executable.") from exc
    _mirror_request_status(record, "approved")
    return _public(record)


def reject(identifier: str, actor: Optional[str] = None, reason: Optional[str] = None) -> dict:
    with _lock:
        entries = _read()
        index, record = _find(entries, identifier)
        if record["status"] != "pending_approval":
            raise ApprovalConflict(f"Approval cannot transition from '{record['status']}' to rejected.")
        _validate_request_link(record)
        original = dict(record)
        record["status"] = "rejected"
        record["rejectedAt"] = _now()
        record["rejectedBy"] = _clean_text(actor, 80) or "local-user"
        record["error"] = _clean_text(reason, 300) or "Rejected by user."
        record["transitionLogId"] = None
        entries[index] = record
        _write(entries)
        try:
            transition = log_approval_transition(record, "rejected")
            record["transitionLogId"] = transition["id"]
            entries[index] = record
            _write(entries)
        except Exception as exc:
            entries[index] = original
            try:
                _write(entries)
            except Exception as rollback_exc:
                logger.critical("Rejection transition rollback failed; record remains fail-closed: %s", rollback_exc)
            raise ApprovalAuditError("Rejection transition audit failed; rejection was rolled back.") from exc
    _mirror_request_status(record, "rejected")
    return _public(record)


def _dispatch(tool: str, args: dict) -> dict:
    from app.brain import run_brain_command
    from app.calendar import create_calendar_candidate
    from app.config import get_config
    from app.vault import create_task

    if tool == "brain.today":
        return run_brain_command("today").model_dump()
    if tool == "brain.sync_raw":
        return run_brain_command("sync-raw").model_dump()
    cfg = get_config()
    if tool == "vault.create_task":
        return create_task(vault_path=cfg.vault_path, **args)
    if tool == "calendar.create_candidate":
        return create_calendar_candidate(cfg.vault_path, {**args, "approved": "No"})
    raise ApprovalError("Tool has no approval dispatcher.")


def _execution_summary(tool: str, result: Optional[dict], ok: bool) -> Optional[dict]:
    if result is None:
        return None
    if tool.startswith("brain."):
        return {
            "ok": ok,
            "resultType": "brain_command",
            "message": "Brain command completed." if ok else "Brain command failed.",
            "path": None,
            "id": None,
        }
    if tool == "vault.create_task":
        return {
            "ok": ok,
            "resultType": "task_created",
            "message": "Task created." if ok else "Task creation failed.",
            "path": _safe_result_path(result.get("path")),
            "id": _safe_result_id((result.get("task") or {}).get("id"), "t"),
        }
    if tool == "calendar.create_candidate":
        return {
            "ok": ok,
            "resultType": "calendar_candidate_created",
            "message": "Calendar candidate created." if ok else "Calendar candidate creation failed.",
            "path": _safe_result_path(result.get("path")),
            "id": _safe_result_id((result.get("candidate") or {}).get("id"), "c"),
        }
    return None


def _safe_result_path(value: object) -> Optional[str]:
    cleaned = _clean_text(value, 500) if isinstance(value, str) else None
    if not cleaned or cleaned.startswith(("/", "\\")) or ":" in cleaned:
        return None
    normalized = cleaned.replace("\\", "/")
    if ".." in normalized.split("/"):
        return None
    return normalized


def _safe_result_id(value: object, prefix: str) -> Optional[str]:
    cleaned = _clean_text(value, 100) if isinstance(value, str) else None
    if cleaned and re.fullmatch(rf"{re.escape(prefix)}[1-9]\d*", cleaned):
        return cleaned
    return None


def _restore_claim_to_approved(record: dict) -> dict:
    """Undo an executing claim only when the final switch check ran no side effect."""
    with _lock:
        entries = _read()
        index, current = _find(entries, record["id"])
        if current.get("status") != "executing":
            raise ApprovalConflict("Execution claim changed before switch-off restoration.")
        current["status"] = "approved"
        current["executionStartedAt"] = None
        entries[index] = current
        _write(entries)
    _mirror_request_status(current, "approved")
    return current


def execute(identifier: str) -> dict:
    if not privileged_execution_enabled():
        raise ApprovalDisabled("Privileged execution is disabled by the operator kill switch.")

    validation_error = None
    with _lock:
        entries = _read()
        index, record = _find(entries, identifier)
        if record["status"] != "approved":
            raise ApprovalConflict(f"Approval cannot execute from '{record['status']}'.")
        _validate_approved_transition(record)
        _validate_request_link(record)

        record["status"] = "executing"
        record["executionStartedAt"] = _now()
        try:
            _validate_request_link(record)
            if normalize_mode(record.get("mode")) != ASSIST:
                raise ApprovalError("Approval mode is no longer eligible.")
            if not is_approval_required_tool(record.get("tool", "")):
                raise ApprovalError("Approval tool is no longer eligible.")
            canonical = validate_canonical_args(record["tool"], record.get("canonicalArgs"))
            evaluation = evaluate_tool_request(
                record["tool"], canonical, record.get("reason"), record.get("requestedBy")
            )
            evaluation["sanitizedArgsSummary"] = record.get("argsSummary", "")
            policy = {
                "decision": evaluation["decision"],
                "riskLevel": evaluation["riskLevel"],
                "requiresApproval": bool(evaluation["requiresApproval"]),
                "policyNotes": evaluation.get("policyNotes"),
            }
            expected = _integrity(
                approval_id=record["id"],
                tool=record["tool"],
                mode=record["mode"],
                policy=policy,
                args=canonical,
                request_id=record["requestId"],
                args_summary=record.get("argsSummary", ""),
                reason=record.get("reason"),
                requested_by=record.get("requestedBy", ""),
                evaluation_log_id=record.get("evaluationLogId", ""),
            )
            if policy != record.get("policyBinding") or expected != record.get("integrity"):
                raise ApprovalError("Immutable approval data or bound policy failed validation.")
            if evaluation["decision"] != "requires_approval":
                raise ApprovalError("Current policy no longer permits this execution.")
        except Exception as exc:
            validation_error = str(exc)
            canonical = {}
            evaluation = {
                "tool": record.get("tool", ""), "riskLevel": record.get("riskLevel", "high"),
                "requiresApproval": True, "sanitizedArgsSummary": record.get("argsSummary", ""),
                "policyNotes": "Approval execution validation failed.",
            }
        entries[index] = record
        _write(entries)

    _mirror_request_status(record, "executing")

    started = time.monotonic()
    result = None
    error = validation_error
    ok = False
    if error is None:
        # Serialize only the final recheck + side effect across this process. The
        # approval-store lock is not held while waiting or dispatching.
        with _dispatch_lock:
            if not privileged_execution_enabled():
                _restore_claim_to_approved(record)
                raise ApprovalDisabled(
                    "Privileged execution was disabled before dispatch; approval remains approved."
                )
            else:
                try:
                    result = _dispatch(record["tool"], canonical)
                    ok = bool(result.get("ok", False))
                    if not ok:
                        error = str(result.get("stderr") or result.get("error") or "Tool execution failed.")
                except Exception as exc:
                    error = str(exc)
    duration_ms = round((time.monotonic() - started) * 1000, 1)
    log_entry = None
    try:
        log_entry = log_approved_execution(
            evaluation=evaluation,
            ok=ok,
            result=result,
            error=error,
            duration_ms=duration_ms,
            requested_by=record.get("requestedBy"),
            reason=record.get("reason"),
            approval_id=record.get("id"),
            request_id=record.get("requestId"),
            approved_by=record.get("approvedBy"),
            approved_at=record.get("approvedAt"),
        )
    except Exception as exc:  # terminal: v1 never retries an unaudited attempt
        logger.error(
            "Execution audit persistence failed for approval %s: %s",
            record.get("id"), exc,
        )
        if ok:
            record["auditWarning"] = _AUDIT_PERSISTENCE_WARNING

    with _lock:
        entries = _read()
        index, current = _find(entries, record["id"])
        if current["status"] != "executing":
            raise ApprovalConflict("Approval execution state changed unexpectedly.")
        current["status"] = "executed" if ok else "failed"
        current["executionLogId"] = log_entry["id"] if log_entry else None
        current["result"] = _execution_summary(record["tool"], result, ok)
        current["error"] = None if ok else (
            "Approval execution validation failed."
            if validation_error else "Tool execution failed."
        )
        current["auditWarning"] = record.get("auditWarning") if ok else None
        current["executedAt" if ok else "failedAt"] = _now()
        entries[index] = current
        try:
            _write(entries)
        except Exception as exc:
            # The side effect is never retried. The already-durable executing state
            # is intentionally fail-closed for operator inspection.
            logger.critical("Final approval state write failed; side effect will not be retried: %s", exc)
            raise ApprovalError(
                "Final execution state could not be persisted; record remains executing and must not be retried."
            ) from exc
    _mirror_request_status(current, current["status"])
    return _public(current)
