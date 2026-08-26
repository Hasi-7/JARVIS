import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import agent_tool_requests as atr
from app import permission_gateway as pg
from app import tool_approvals as ta
from app import write_lock as wl
from app.agent_structured_output import evaluate_structured_output
from app.agent_tool_requests import create_request
from app.main import (
    agent_tool_request_create,
    permissions_execute,
    permissions_logs,
    vault_task_create,
    tool_approval_approve,
    tool_approval_execute,
    tool_approval_reject,
    tool_approvals_list,
)
from app.models import (
    ApproveToolApprovalRequest,
    AgentChatRequest,
    BrainRunResponse,
    CreateAgentToolRequestRequest,
    ExecuteToolApprovalRequest,
    RejectToolApprovalRequest,
    ToolRequestEvaluationRequest,
    CreateVaultTaskRequest,
)

_TOKEN = "test-operator-approval-token"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(atr, "AGENT_REQUESTS_DIR", tmp_path / "agent-requests")
    monkeypatch.setattr(atr, "REQUESTS_FILE", tmp_path / "agent-requests" / "requests.json")
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", tmp_path / "tool-logs")
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", tmp_path / "tool-logs" / "evaluations.json")
    monkeypatch.setattr(ta, "APPROVALS_DIR", tmp_path / "tool-approvals")
    monkeypatch.setattr(ta, "APPROVALS_FILE", tmp_path / "tool-approvals" / "approvals.json")
    monkeypatch.setattr(wl.vault_write_lock, "path", tmp_path / "locks" / "vault-writes.lock")
    monkeypatch.setattr(wl.approval_state_lock, "path", tmp_path / "locks" / "approval-state.lock")
    monkeypatch.delenv(pg.PRIVILEGED_EXECUTION_ENV, raising=False)
    monkeypatch.setenv(ta.APPROVAL_TOKEN_ENV, _TOKEN)


def _request(tool="brain.today", args=None, mode="assist"):
    return create_request(
        tool=tool,
        args={} if args is None else args,
        reason="Needed locally",
        requested_by="local-agent",
        conversation_id="conv-1",
        mode=mode,
    )


def _enable(monkeypatch):
    monkeypatch.setenv(pg.PRIVILEGED_EXECUTION_ENV, "true")


def _brain_result(command="today", ok=True):
    return BrainRunResponse(
        command=command,
        ok=ok,
        exitCode=0 if ok else 2,
        stdout="ok" if ok else "",
        stderr="" if ok else "failed",
        durationMs=2.0,
    )


def test_assist_request_creates_pending_durable_approval_without_api_args():
    request = _request()
    assert request["mode"] == "assist"
    assert request["status"] == "pending_approval"
    assert request["approvalId"]

    public = ta.list_approvals()[0]
    assert public["requestId"] == request["id"]
    assert public["status"] == "pending_approval"
    assert public["risk"] == "low"
    assert "canonicalArgs" not in public
    assert "policyBinding" not in public
    assert "integrity" not in public
    assert "canonicalArgs" not in tool_approvals_list(50, _TOKEN).model_dump_json()


@pytest.mark.parametrize("mode", ["draft", "research", "escalation", None, "unknown"])
def test_non_assist_requests_remain_evaluate_only(mode):
    request = _request(mode=mode)
    assert request["status"] == "evaluated_only"
    assert request["approvalId"] is None
    assert request["mode"] == (mode if mode in {"draft", "research", "escalation"} else "locked")
    assert ta.list_approvals() == []


def test_manual_request_requires_explicit_assist_for_approval():
    blocked = agent_tool_request_create(CreateAgentToolRequestRequest(tool="brain.today"))
    assert blocked.status == "blocked_by_mode"
    draft = agent_tool_request_create(CreateAgentToolRequestRequest(tool="brain.today", mode="draft"))
    assert draft.status == "evaluated_only"
    with pytest.raises(HTTPException) as missing:
        agent_tool_request_create(
            CreateAgentToolRequestRequest(tool="brain.today", mode="assist"), None,
        )
    assert missing.value.status_code == 401
    assist = agent_tool_request_create(
        CreateAgentToolRequestRequest(tool="brain.today", mode="assist"), _TOKEN,
    )
    assert assist.status == "pending_approval"
    assert assist.mode == "assist"
    assert len(ta.list_approvals()) == 1


def test_kill_switch_defaults_off_and_blocks_approve_without_transition():
    request = _request()
    with pytest.raises(HTTPException) as exc:
        tool_approval_approve(request["approvalId"], ApproveToolApprovalRequest(), _TOKEN)
    assert exc.value.status_code == 503
    assert ta.list_approvals()[0]["status"] == "pending_approval"
    assert pg.privileged_execution_enabled() is False


def test_approval_auth_missing_wrong_unconfigured_and_correct(monkeypatch):
    _enable(monkeypatch)
    request = _request()

    with pytest.raises(HTTPException) as missing:
        tool_approval_approve(request["approvalId"], ApproveToolApprovalRequest(), None)
    assert missing.value.status_code == 401
    assert ta.list_approvals()[0]["status"] == "pending_approval"

    with pytest.raises(HTTPException) as wrong:
        tool_approval_approve(request["approvalId"], ApproveToolApprovalRequest(), "wrong")
    assert wrong.value.status_code == 403
    assert ta.list_approvals()[0]["status"] == "pending_approval"

    monkeypatch.delenv(ta.APPROVAL_TOKEN_ENV)
    with pytest.raises(HTTPException) as unconfigured:
        tool_approval_approve(request["approvalId"], ApproveToolApprovalRequest(), _TOKEN)
    assert unconfigured.value.status_code == 503

    monkeypatch.setenv(ta.APPROVAL_TOKEN_ENV, _TOKEN)
    approved = tool_approval_approve(
        request["approvalId"], ApproveToolApprovalRequest(approvedBy="operator"), _TOKEN,
    )
    assert approved.status == "approved"


def test_approval_list_requires_auth_and_exposes_typed_review_fields():
    brain = _request(tool="brain.today")
    task = _request(tool="vault.create_task", args={
        "title": "Review task", "status": "todo", "area": "A",
        "priority": "high", "due": "2026-08-12", "source": "agent",
    })
    calendar = _request(tool="calendar.create_candidate", args={
        "date": "2026-08-13", "time": "09:30", "duration": "30m",
        "title": "Review calendar", "reason": "Plan", "source": "agent",
    })

    with pytest.raises(HTTPException) as missing:
        tool_approvals_list(50, None)
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException) as wrong:
        tool_approvals_list(50, "wrong")
    assert wrong.value.status_code == 403

    response = tool_approvals_list(50, _TOKEN)
    by_request = {approval.requestId: approval for approval in response.approvals}
    assert by_request[brain["id"]].reviewFields.model_dump() == {}
    assert by_request[task["id"]].reviewFields.model_dump() == {
        "title": "Review task", "status": "todo", "area": "A",
        "priority": "high", "due": "2026-08-12", "source": "agent",
    }
    assert by_request[calendar["id"]].reviewFields.model_dump() == {
        "date": "2026-08-13", "time": "09:30", "duration": "30m",
        "title": "Review calendar", "reason": "Plan", "source": "agent",
        "approved": "No",
    }


def test_all_mutation_routes_require_auth(monkeypatch):
    _enable(monkeypatch)
    reject_request = _request()
    with pytest.raises(HTTPException) as reject_wrong:
        tool_approval_reject(
            reject_request["approvalId"], RejectToolApprovalRequest(), "wrong",
        )
    assert reject_wrong.value.status_code == 403
    assert ta.list_approvals()[0]["status"] == "pending_approval"

    execute_request = _request(tool="brain.sync_raw")
    ta.approve(execute_request["approvalId"])
    with patch("app.brain.run_brain_command") as run:
        with pytest.raises(HTTPException) as execute_missing:
            tool_approval_execute(
                execute_request["approvalId"], ExecuteToolApprovalRequest(), None,
            )
    assert execute_missing.value.status_code == 401
    run.assert_not_called()
    assert next(
        r for r in ta.list_approvals(10) if r["id"] == execute_request["approvalId"]
    )["status"] == "approved"


def test_assist_cannot_self_approve_without_operator_header(monkeypatch):
    _enable(monkeypatch)
    request = agent_tool_request_create(CreateAgentToolRequestRequest(
        tool="brain.today", mode="assist", requestedBy="local-agent",
    ), _TOKEN)
    with pytest.raises(HTTPException) as exc:
        tool_approval_approve(request.approvalId, ApproveToolApprovalRequest(), None)
    assert exc.value.status_code == 401
    assert ta.list_approvals()[0]["status"] == "pending_approval"


def test_auth_uses_constant_time_compare_and_token_is_never_persisted(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    with patch("app.tool_approvals.hmac.compare_digest", wraps=ta.hmac.compare_digest) as compare:
        tool_approval_approve(
            request["approvalId"], ApproveToolApprovalRequest(), _TOKEN,
        )
    compare.assert_called_once_with(_TOKEN, _TOKEN)
    stored = ta.APPROVALS_FILE.read_text(encoding="utf-8")
    logs = pg.EVALUATIONS_FILE.read_text(encoding="utf-8")
    requests = atr.REQUESTS_FILE.read_text(encoding="utf-8")
    assert _TOKEN not in stored
    assert _TOKEN not in logs
    assert _TOKEN not in requests


def test_full_lifecycle_and_replay_rejected(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    approved = tool_approval_approve(
        request["id"], ApproveToolApprovalRequest(approvedBy="owner"), _TOKEN,
    )
    assert approved.status == "approved"
    assert approved.approvedBy == "owner"
    assert approved.transitionLogId
    approved_source = atr.get_request_internal(request["id"])
    assert approved_source["status"] == "approved"
    assert approved_source["approvalStatus"] == "approved"
    with pytest.raises(HTTPException) as double:
        tool_approval_approve(request["approvalId"], ApproveToolApprovalRequest(), _TOKEN)
    assert double.value.status_code == 409

    with patch("app.brain.run_brain_command", return_value=_brain_result()) as run:
        executed = tool_approval_execute(
            request["approvalId"], ExecuteToolApprovalRequest(), _TOKEN,
        )
    run.assert_called_once_with("today")
    assert executed.status == "executed"
    assert executed.executionStartedAt
    assert executed.executedAt
    assert executed.executionLogId
    assert executed.result.resultType == "brain_command"
    assert executed.result.message == "Brain command completed."
    assert "command" not in executed.result.model_dump()
    executed_source = atr.get_request_internal(request["id"])
    assert executed_source["status"] == "executed"
    assert executed_source["approvalStatus"] == "executed"

    with patch("app.brain.run_brain_command") as replay_run:
        with pytest.raises(HTTPException) as replay:
            tool_approval_execute(request["approvalId"], ExecuteToolApprovalRequest(), _TOKEN)
    assert replay.value.status_code == 409
    replay_run.assert_not_called()


def test_initial_evaluation_log_is_correlated_to_request_id():
    request = _request()
    entry = next(e for e in pg.list_logs(100) if e["id"] == request["evaluation"]["logId"])
    assert entry["requestId"] == request["id"]
    assert entry["approvalId"] is None


def test_approve_audit_failure_rolls_back_to_pending(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    with patch("app.tool_approvals.log_approval_transition", side_effect=OSError("audit unavailable")):
        with pytest.raises(ta.ApprovalAuditError):
            ta.approve(request["approvalId"])
    record = ta.list_approvals()[0]
    assert record["status"] == "pending_approval"
    assert record["transitionLogId"] is None


def test_approve_audit_rollback_failure_still_blocks_execution(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    real_write = ta._write
    writes = {"count": 0}

    def fail_rollback(entries):
        writes["count"] += 1
        if writes["count"] == 2:
            raise OSError("rollback write failed")
        return real_write(entries)

    with patch("app.tool_approvals._write", side_effect=fail_rollback), \
         patch("app.tool_approvals.log_approval_transition", side_effect=OSError("audit unavailable")):
        with pytest.raises(ta.ApprovalAuditError):
            ta.approve(request["approvalId"])
    record = ta.list_approvals()[0]
    assert record["status"] == "approved"
    assert record["transitionLogId"] is None
    with patch("app.brain.run_brain_command") as run:
        with pytest.raises(ta.ApprovalConflict, match="evidence is missing"):
            ta.execute(request["approvalId"])
    run.assert_not_called()


def test_transition_log_binding_write_failure_rolls_back(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    real_write = ta._write
    writes = {"count": 0}

    def fail_binding(entries):
        writes["count"] += 1
        if writes["count"] == 2:
            raise OSError("transition id binding failed")
        return real_write(entries)

    with patch("app.tool_approvals._write", side_effect=fail_binding):
        with pytest.raises(ta.ApprovalAuditError):
            ta.approve(request["approvalId"])
    record = ta.list_approvals()[0]
    assert record["status"] == "pending_approval"
    assert record["transitionLogId"] is None


def test_reject_audit_failure_rolls_back_safely():
    request = _request()
    with patch("app.tool_approvals.log_approval_transition", side_effect=OSError("audit unavailable")):
        with pytest.raises(ta.ApprovalAuditError):
            ta.reject(request["approvalId"])
    record = ta.list_approvals()[0]
    assert record["status"] == "pending_approval"
    assert record["transitionLogId"] is None


def test_switch_turned_off_after_approval_blocks_execution_without_consuming(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    monkeypatch.setenv(pg.PRIVILEGED_EXECUTION_ENV, "false")
    with patch("app.brain.run_brain_command") as run:
        with pytest.raises(ta.ApprovalDisabled):
            ta.execute(request["approvalId"])
    run.assert_not_called()
    assert ta.list_approvals()[0]["status"] == "approved"


def test_switch_is_rechecked_immediately_before_dispatch(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    with patch("app.tool_approvals.privileged_execution_enabled", side_effect=[True, False]), \
         patch("app.brain.run_brain_command") as run:
        with pytest.raises(ta.ApprovalDisabled, match="remains approved"):
            ta.execute(request["approvalId"])
    run.assert_not_called()
    restored = ta.list_approvals()[0]
    assert restored["status"] == "approved"
    assert restored["executionStartedAt"] is None
    source = atr.get_request_internal(request["id"])
    assert source["status"] == "approved"
    assert source["approvalStatus"] == "approved"


def test_reject_is_terminal_and_does_not_require_switch():
    request = _request()
    rejected = tool_approval_reject(
        request["approvalId"], RejectToolApprovalRequest(
            rejectedBy="owner", reason="Not wanted",
        ), _TOKEN,
    )
    assert rejected.status == "rejected"
    assert rejected.rejectedBy == "owner"
    assert rejected.error == "Not wanted"
    rejected_source = atr.get_request_internal(request["id"])
    assert rejected_source["status"] == "rejected"
    assert rejected_source["approvalStatus"] == "rejected"
    with pytest.raises(HTTPException) as again:
        tool_approval_reject(request["approvalId"], RejectToolApprovalRequest(), _TOKEN)
    assert again.value.status_code == 409


def test_execute_route_cannot_accept_replacement_tool_or_args():
    with pytest.raises(ValidationError):
        ExecuteToolApprovalRequest(tool="brain.sync_raw")
    with pytest.raises(ValidationError):
        ExecuteToolApprovalRequest(args={"anything": True})


def test_request_persistence_failure_prevents_approval_creation():
    with patch("app.agent_tool_requests._write_requests", side_effect=OSError("disk full")), \
         patch("app.tool_approvals.create_approval") as create:
        with pytest.raises(OSError):
            _request()
    create.assert_not_called()
    assert ta.list_approvals() == []


def test_approval_creation_failure_leaves_only_evaluated_request():
    with patch("app.tool_approvals.create_approval", side_effect=OSError("approval disk full")):
        with pytest.raises(OSError):
            _request()
    requests = atr.list_requests(10)
    assert len(requests) == 1
    assert requests[0]["status"] == "evaluated_only"
    assert requests[0]["approvalId"] is None
    assert ta.list_approvals() == []


def test_binding_persistence_failure_rolls_back_approval(monkeypatch):
    real_write = atr._write_requests
    calls = {"count": 0}

    def fail_second_write(entries):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("binding write failed")
        return real_write(entries)

    monkeypatch.setattr(atr, "_write_requests", fail_second_write)
    with pytest.raises(OSError, match="binding write failed"):
        _request()
    request = atr.list_requests(10)[0]
    assert request["status"] == "evaluated_only"
    assert request["approvalId"] is None
    assert ta.list_approvals() == []


def test_failed_binding_and_failed_rollback_orphan_is_not_approvable(monkeypatch):
    _enable(monkeypatch)
    real_write = atr._write_requests
    calls = {"count": 0}

    def fail_second_write(entries):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("binding write failed")
        return real_write(entries)

    monkeypatch.setattr(atr, "_write_requests", fail_second_write)
    monkeypatch.setattr(
        ta, "delete_unbound_approval", lambda *args: (_ for _ in ()).throw(OSError("rollback failed")),
    )
    with pytest.raises(OSError, match="binding write failed"):
        _request()
    orphan = ta.list_approvals()[0]
    with pytest.raises(ta.ApprovalError, match="linkage"):
        ta.approve(orphan["id"])
    assert ta.list_approvals()[0]["status"] == "pending_approval"


def test_execution_revalidates_source_linkage(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    atr.REQUESTS_FILE.write_text("[]", encoding="utf-8")
    with patch("app.brain.run_brain_command") as run:
        with pytest.raises(ta.ApprovalConflict, match="source request"):
            ta.execute(request["approvalId"])
    run.assert_not_called()
    assert ta.list_approvals()[0]["status"] == "approved"


def test_old_execute_endpoint_cannot_bypass_approval_when_switch_on(monkeypatch):
    _enable(monkeypatch)
    policy = next(p for p in pg.list_policies() if p["tool"] == "brain.today")
    evaluation = pg.evaluate_tool_request("brain.today", {})
    assert policy["executionEnabled"] is False
    assert evaluation["executionEnabled"] is False
    with patch("app.main.run_brain_command") as run:
        response = permissions_execute(ToolRequestEvaluationRequest(tool="brain.today", args={}))
    run.assert_not_called()
    assert response.ok is False
    assert response.allowed is False
    assert response.executionEnabled is False
    assert response.executionLogId is None
    assert response.error == "Tool is not executable in this build."


@pytest.mark.parametrize("switch", ["false", "true"])
@pytest.mark.parametrize("tool,command", [
    ("brain.status", "status"),
    ("brain.raw_status", "raw-status"),
    ("brain.vault_path", "vault-path"),
])
def test_immediate_read_tools_regression_under_switch_states(monkeypatch, switch, tool, command):
    monkeypatch.setenv(pg.PRIVILEGED_EXECUTION_ENV, switch)
    with patch("app.main.run_brain_command", return_value=_brain_result(command)) as run:
        response = permissions_execute(ToolRequestEvaluationRequest(tool=tool, args={}))
    run.assert_called_once_with(command)
    assert response.ok is True
    assert response.decision == "executed"


@pytest.mark.parametrize("tool", ["shell.run", "filesystem.write_vault", "gmail.send"])
def test_arbitrary_high_risk_tools_never_enter_approval_queue(tool):
    request = _request(tool=tool, args={"cmd": "whoami"})
    assert request["status"] == "evaluated_only"
    assert request["approvalId"] is None
    assert ta.list_approvals() == []


@pytest.mark.parametrize("tool,command", [
    ("brain.today", "today"),
    ("brain.sync_raw", "sync-raw"),
])
def test_brain_dispatcher_exact_commands(monkeypatch, tool, command):
    _enable(monkeypatch)
    request = _request(tool=tool)
    ta.approve(request["approvalId"])
    with patch("app.brain.run_brain_command", return_value=_brain_result(command)) as run:
        result = ta.execute(request["approvalId"])
    run.assert_called_once_with(command)
    assert result["status"] == "executed"


def test_task_write_adapter_exact_call(monkeypatch):
    _enable(monkeypatch)
    args = {
        "title": "Ship A3", "status": "todo", "area": "JARVIS",
        "priority": "high", "due": "2026-08-11", "source": "agent",
    }
    request = _request(tool="vault.create_task", args=args)
    ta.approve(request["approvalId"])
    result = {"ok": True, "task": {"id": "t1"}, "path": "ops/task-db.md", "updatedAt": "now"}
    with patch("app.config.get_config", return_value=SimpleNamespace(vault_path="/vault")), \
         patch("app.vault.create_task", return_value=result) as create:
        executed = ta.execute(request["approvalId"])
    create.assert_called_once_with(vault_path="/vault", **args)
    assert executed["status"] == "executed"


def test_calendar_write_adapter_exact_call(monkeypatch):
    _enable(monkeypatch)
    args = {
        "date": "2026-08-12", "time": "10:00", "duration": "30m",
        "title": "Review A3", "reason": "Follow up", "source": "agent",
    }
    request = _request(tool="calendar.create_candidate", args=args)
    ta.approve(request["approvalId"])
    result = {"ok": True, "candidate": {"id": "c1"}, "path": "ops/calendar-candidates.md", "updatedAt": "now"}
    with patch("app.config.get_config", return_value=SimpleNamespace(vault_path="/vault")), \
         patch("app.calendar.create_calendar_candidate", return_value=result) as create:
        executed = ta.execute(request["approvalId"])
    create.assert_called_once_with("/vault", {**args, "approved": "No"})
    assert executed["status"] == "executed"


def test_calendar_caller_cannot_set_approved():
    with pytest.raises(ValueError):
        _request(tool="calendar.create_candidate", args={
            "date": "2026-08-12", "title": "Review", "approved": "Yes",
        })
    assert ta.list_approvals() == []


@pytest.mark.parametrize("tool,args", [
    ("vault.create_task", {"title": "x" * 301, "status": "todo"}),
    ("vault.create_task", {"title": "x", "status": "todo", "area": "a" * 501}),
    ("vault.create_task", {"title": "x", "status": "todo", "due": "08/12/2026"}),
    ("vault.create_task", {"title": "x", "status": "todo", "due": "2026-02-30"}),
    ("calendar.create_candidate", {"date": "2026/08/12", "title": "x"}),
    ("calendar.create_candidate", {"date": "2026-08-12", "title": "x", "time": "24:00"}),
    ("calendar.create_candidate", {"date": "2026-08-12", "title": "x", "time": "9:00"}),
    ("calendar.create_candidate", {"date": "2026-08-12", "title": "x", "duration": "x" * 51}),
    ("calendar.create_candidate", {"date": "2026-08-12", "title": "x", "duration": "30/60"}),
    ("calendar.create_candidate", {"date": "2026-08-12", "title": "x", "reason": "r" * 501}),
])
def test_strict_argument_bounds_and_formats(tool, args):
    with pytest.raises(ValueError):
        _request(tool=tool, args=args)
    assert ta.list_approvals() == []


def test_valid_date_time_duration_formats_are_preserved():
    request = _request(tool="calendar.create_candidate", args={
        "date": "2028-02-29", "time": "23:59", "duration": "1h 30m", "title": "Leap review",
    })
    assert request["status"] == "pending_approval"


def test_public_brain_result_and_store_do_not_expose_stdout(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    secret_output = "PRIVATE_BRAIN_OUTPUT_" + ("x" * 3000)
    brain_result = BrainRunResponse(
        command="today", ok=True, exitCode=0, stdout=secret_output,
        stderr="", durationMs=2.0,
    )
    with patch("app.brain.run_brain_command", return_value=brain_result):
        public = ta.execute(request["approvalId"])
    rendered = json.dumps(public)
    stored = ta.APPROVALS_FILE.read_text(encoding="utf-8")
    assert secret_output not in rendered
    assert secret_output not in stored
    assert "stdout" not in rendered
    assert public["result"] == {
        "ok": True, "resultType": "brain_command", "message": "Brain command completed.",
        "path": None, "id": None,
    }
    execution_log = next(e for e in pg.list_logs(100) if e["id"] == public["executionLogId"])
    assert execution_log["stdoutPreview"] is None
    assert execution_log["stderrPreview"] is None
    assert secret_output not in pg.EVALUATIONS_FILE.read_text(encoding="utf-8")
    api_log = next(e for e in permissions_logs(limit=100).logs if e.id == public["executionLogId"])
    assert api_log.stdoutPreview is None
    assert api_log.stderrPreview is None


def test_public_task_result_does_not_echo_arguments(monkeypatch):
    _enable(monkeypatch)
    title = "PRIVATE TASK TITLE"
    request = _request(tool="vault.create_task", args={
        "title": title, "status": "todo", "area": "PRIVATE AREA",
    })
    ta.approve(request["approvalId"])
    adapter_result = {
        "ok": True,
        "task": {"id": "t7", "title": title, "area": "PRIVATE AREA", "raw": title},
        "path": "ops/task-db.md",
        "updatedAt": "now",
    }
    with patch("app.config.get_config", return_value=SimpleNamespace(vault_path="/vault")), \
         patch("app.vault.create_task", return_value=adapter_result):
        public = ta.execute(request["approvalId"])
    result_rendered = json.dumps(public["result"])
    assert title not in result_rendered
    assert "PRIVATE AREA" not in result_rendered
    assert public["reviewFields"]["title"] == title
    assert public["reviewFields"]["area"] == "PRIVATE AREA"
    assert public["argsSummary"].startswith("Task creation request")
    assert public["result"] == {
        "ok": True, "resultType": "task_created", "message": "Task created.",
        "path": "ops/task-db.md", "id": "t7",
    }
    assert title not in pg.EVALUATIONS_FILE.read_text(encoding="utf-8")
    execution_log = next(e for e in pg.list_logs(100) if e["id"] == public["executionLogId"])
    assert execution_log["stdoutPreview"] is None
    assert execution_log["stderrPreview"] is None


@pytest.mark.parametrize("tool,args", [
    ("brain.today", {"command": "status"}),
    ("vault.create_task", {"title": "x", "status": "invalid"}),
    ("vault.create_task", {"title": "x\nnext", "status": "todo"}),
    ("calendar.create_candidate", {"date": "", "title": "x"}),
    ("calendar.create_candidate", {"date": "2026-08-12", "title": "x", "extra": 1}),
])
def test_canonical_argument_validation_rejects_invalid_shapes(tool, args):
    with pytest.raises(ValueError):
        _request(tool=tool, args=args)
    assert ta.list_approvals() == []


def test_persisted_argument_substitution_is_detected_and_terminal(monkeypatch):
    _enable(monkeypatch)
    request = _request(tool="vault.create_task", args={"title": "Original", "status": "todo"})
    ta.approve(request["approvalId"])
    stored = json.loads(ta.APPROVALS_FILE.read_text(encoding="utf-8"))
    stored[0]["canonicalArgs"]["title"] = "Substituted"
    ta.APPROVALS_FILE.write_text(json.dumps(stored), encoding="utf-8")

    with patch("app.vault.create_task") as create:
        failed = ta.execute(request["approvalId"])
    create.assert_not_called()
    assert failed["status"] == "failed"
    assert failed["error"] == "Approval execution validation failed."
    assert failed["executionLogId"]
    log = next(e for e in pg.list_logs(100) if e["id"] == failed["executionLogId"])
    assert log["stderrPreview"] is None
    assert log["stdoutPreview"] is None
    with pytest.raises(ta.ApprovalConflict):
        ta.execute(request["approvalId"])


def test_policy_is_re_evaluated_and_bound_at_execution(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    real_evaluate = ta.evaluate_tool_request

    def changed_policy(*args, **kwargs):
        result = real_evaluate(*args, **kwargs)
        result["riskLevel"] = "high"
        return result

    monkeypatch.setattr(ta, "evaluate_tool_request", changed_policy)
    with patch("app.brain.run_brain_command") as run:
        failed = ta.execute(request["approvalId"])
    run.assert_not_called()
    assert failed["status"] == "failed"
    assert failed["error"] == "Approval execution validation failed."


def test_dispatch_failure_is_logged_terminal_and_not_retryable(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    with patch("app.brain.run_brain_command", side_effect=RuntimeError("boom")) as run:
        failed = ta.execute(request["approvalId"])
    run.assert_called_once()
    assert failed["status"] == "failed"
    assert failed["error"] == "Tool execution failed."
    assert failed["failedAt"]
    log = next(e for e in pg.list_logs(100) if e["id"] == failed["executionLogId"])
    assert log["source"] == "gateway_execution"
    assert log["result"] == "failure"
    with pytest.raises(ta.ApprovalConflict):
        ta.execute(request["approvalId"])


def test_successful_dispatch_with_audit_failure_remains_executed(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    with patch("app.brain.run_brain_command", return_value=_brain_result()), \
         patch("app.tool_approvals.log_approved_execution", side_effect=OSError("disk full")):
        executed = tool_approval_execute(
            request["approvalId"], ExecuteToolApprovalRequest(), _TOKEN,
        )
    assert executed.status == "executed"
    assert executed.executionLogId is None
    assert executed.error is None
    assert executed.result.model_dump() == {
        "ok": True, "resultType": "brain_command", "message": "Brain command completed.",
        "path": None, "id": None,
    }
    assert executed.auditWarning == (
        "Tool executed, but audit persistence failed; inspect backend logs."
    )
    assert "disk full" not in executed.model_dump_json()
    assert ta.list_approvals()[0]["auditWarning"] == executed.auditWarning
    with pytest.raises(ta.ApprovalConflict):
        ta.execute(request["approvalId"])


def test_final_state_write_failure_stays_executing_and_never_retries_side_effect(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    real_write = ta._write
    writes = {"count": 0}

    def fail_terminal_write(entries):
        writes["count"] += 1
        if writes["count"] == 2:
            raise OSError("terminal write failed")
        return real_write(entries)

    with patch("app.tool_approvals._write", side_effect=fail_terminal_write), \
         patch("app.brain.run_brain_command", return_value=_brain_result()) as run:
        with pytest.raises(ta.ApprovalError, match="remains executing"):
            ta.execute(request["approvalId"])
    run.assert_called_once_with("today")
    assert ta.list_approvals()[0]["status"] == "executing"
    with patch("app.brain.run_brain_command") as retry_run:
        with pytest.raises(ta.ApprovalConflict):
            ta.execute(request["approvalId"])
    retry_run.assert_not_called()


def test_evaluation_and_execution_logs_are_both_present(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    with patch("app.brain.run_brain_command", return_value=_brain_result()):
        executed = ta.execute(request["approvalId"])
    logs = pg.list_logs(100)
    assert any(e["id"] == request["evaluation"]["logId"] and e["source"] == "gateway_eval" for e in logs)
    assert any(e["id"] == executed["executionLogId"] and e["source"] == "gateway_execution" for e in logs)


def test_transition_and_execution_logs_have_approval_correlation(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    approved = ta.approve(request["approvalId"], actor="operator")
    with patch("app.brain.run_brain_command", return_value=_brain_result()):
        executed = ta.execute(request["approvalId"])
    logs = pg.list_logs(100)
    transition = next(e for e in logs if e["source"] == "approval_transition")
    execution = next(e for e in logs if e["id"] == executed["executionLogId"])
    for entry in (transition, execution):
        assert entry["approvalId"] == request["approvalId"]
        assert entry["requestId"] == request["id"]
        assert entry["approvedBy"] == "operator"
        assert entry["approvedAt"] == approved["approvedAt"]


def test_structured_output_propagates_assist_mode_into_request_and_approval():
    text = '```json\n{"tool_requests":[{"tool":"brain.today","args":{},"reason":"plan"}]}\n```'
    result = evaluate_structured_output(text, "conv-1", mode="assist")
    request = result["toolRequests"][0]
    assert request["mode"] == "assist"
    assert request["status"] == "pending_approval"
    assert ta.list_approvals()[0]["requestId"] == request["id"]


def test_non_stream_chat_propagates_resolved_assist_mode(monkeypatch):
    import app.main as main

    reply = '```json\n{"tool_requests":[{"tool":"brain.today","args":{},"reason":"plan"}]}\n```'
    monkeypatch.setattr(main, "chat_with_agent", lambda **kwargs: {
        "ok": True, "provider": "ollama", "model": "test", "message": reply,
        "durationMs": 1.0,
    })
    monkeypatch.setattr(main, "get_conversation", lambda conversation_id: {"id": conversation_id})
    monkeypatch.setattr(main, "_prior_messages", lambda conversation_id: ([], 0))
    monkeypatch.setattr(main, "save_chat_turn", lambda **kwargs: None)

    response = main.agent_chat(AgentChatRequest(
        message="plan today", conversationId="conv-1", mode="Assist",
    ))
    assert response.structured.mode == "assist"
    assert response.structured.toolRequests[0].mode == "assist"
    assert response.structured.toolRequests[0].status == "pending_approval"
    assert ta.list_approvals()[0]["mode"] == "assist"


def test_stream_chat_propagates_resolved_assist_mode(monkeypatch):
    import app.main as main

    reply = '```json\n{"tool_requests":[{"tool":"brain.today","args":{},"reason":"plan"}]}\n```'
    monkeypatch.setattr(main, "stream_ollama_chat", lambda *args, **kwargs: iter([reply]))
    monkeypatch.setattr(main, "get_conversation", lambda conversation_id: {"id": conversation_id})
    monkeypatch.setattr(main, "_prior_messages", lambda conversation_id: ([], 0))
    monkeypatch.setattr(main, "save_chat_turn", lambda **kwargs: None)
    response = main.agent_chat_stream(AgentChatRequest(
        message="plan today", conversationId="conv-1", mode="assist",
    ))

    async def collect():
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = asyncio.run(collect())
    assert "event: structured" in body
    assert '"mode": "assist"' in body
    approval = ta.list_approvals()[0]
    assert approval["mode"] == "assist"
    assert approval["status"] == "pending_approval"


def test_approval_store_is_newest_first_and_capped(monkeypatch):
    monkeypatch.setattr(ta, "_MAX_STORED", 2)
    first = _request()
    second = _request(tool="brain.sync_raw")
    third = _request(tool="vault.create_task", args={"title": "x", "status": "todo"})
    listed = ta.list_approvals(100)
    assert [r["requestId"] for r in listed] == [third["id"], second["id"], first["id"]]


def test_approval_retention_keeps_all_live_and_caps_terminal(monkeypatch):
    monkeypatch.setattr(ta, "_MAX_STORED", 2)
    live = [_request(tool="brain.today") for _ in range(3)]
    terminal = []
    for _ in range(5):
        request = _request(tool="brain.sync_raw")
        ta.reject(request["approvalId"])
        terminal.append(request)
    listed = ta.list_approvals(100)
    listed_request_ids = {record["requestId"] for record in listed}
    assert {request["id"] for request in live}.issubset(listed_request_ids)
    retained_terminal = [record for record in listed if record["status"] == "rejected"]
    assert len(retained_terminal) == 2
    assert {record["requestId"] for record in retained_terminal} == {
        terminal[-1]["id"], terminal[-2]["id"],
    }


def test_live_approval_capacity_is_hard_capped(monkeypatch):
    monkeypatch.setattr(ta, "_MAX_LIVE_APPROVALS", 2)
    first = _request(tool="brain.today")
    second = _request(tool="brain.sync_raw")
    with pytest.raises(ta.ApprovalCapacityError, match="capacity"):
        _request(tool="vault.create_task", args={"title": "overflow", "status": "todo"})
    approvals = ta.list_approvals(100)
    assert {record["requestId"] for record in approvals} == {first["id"], second["id"]}
    assert len(approvals) == 2
    overflow = atr.list_requests(100)[0]
    assert overflow["status"] == "evaluated_only"
    assert overflow["approvalId"] is None


def test_manual_admission_capacity_maps_to_429(monkeypatch):
    monkeypatch.setattr(ta, "_MAX_LIVE_APPROVALS", 1)
    _request(tool="brain.today")
    with pytest.raises(HTTPException) as exc:
        agent_tool_request_create(
            CreateAgentToolRequestRequest(
                tool="brain.sync_raw", mode="assist", requestedBy="manual-ui",
            ),
            _TOKEN,
        )
    assert exc.value.status_code == 429
    assert len(ta.list_approvals(100)) == 1


def test_agent_request_retention_keeps_live_links_and_caps_terminal_unlinked(monkeypatch):
    monkeypatch.setattr(atr, "_MAX_STORED", 2)
    live = [_request(tool="brain.today") for _ in range(3)]
    terminal = _request(tool="brain.sync_raw")
    ta.reject(terminal["approvalId"])
    unlinked = [_request(tool="brain.today", mode="draft") for _ in range(3)]

    stored = atr.list_requests(100)
    stored_ids = {record["id"] for record in stored}
    assert {request["id"] for request in live}.issubset(stored_ids)
    recent_nonlive = [
        record for record in stored
        if not record.get("approvalId") or record.get("approvalStatus") == "rejected"
    ]
    assert len(recent_nonlive) == 2
    assert {record["id"] for record in recent_nonlive} == {
        unlinked[-1]["id"], unlinked[-2]["id"],
    }


def test_privileged_dispatch_lock_serializes_task_and_calendar(monkeypatch):
    _enable(monkeypatch)
    task = _request(tool="vault.create_task", args={"title": "Task", "status": "todo"})
    calendar = _request(tool="calendar.create_candidate", args={
        "date": "2026-08-12", "title": "Calendar",
    })
    ta.approve(task["approvalId"])
    ta.approve(calendar["approvalId"])

    first_entered = threading.Event()
    release_first = threading.Event()
    second_attempting = threading.Event()
    second_entered = threading.Event()
    state_lock = threading.Lock()
    state = {"active": 0, "overlap": False}
    errors = []

    def enter_dispatch(first=False):
        with state_lock:
            state["active"] += 1
            state["overlap"] = state["overlap"] or state["active"] > 1
        if first:
            first_entered.set()
            assert release_first.wait(timeout=2)
        else:
            second_entered.set()
        with state_lock:
            state["active"] -= 1

    def create_task_adapter(**kwargs):
        enter_dispatch(first=True)
        return {"ok": True, "task": {"id": "t1"}, "path": "ops/task-db.md"}

    def create_calendar_adapter(vault_path, payload):
        enter_dispatch(first=False)
        return {"ok": True, "candidate": {"id": "c1"}, "path": "ops/calendar-candidates.md"}

    def run_task():
        try:
            ta.execute(task["approvalId"])
        except Exception as exc:  # captured for assertion in the main thread
            errors.append(exc)

    def run_calendar():
        second_attempting.set()
        try:
            ta.execute(calendar["approvalId"])
        except Exception as exc:
            errors.append(exc)

    with patch("app.config.get_config", return_value=SimpleNamespace(vault_path="/vault")), \
         patch("app.vault.create_task", side_effect=create_task_adapter), \
         patch("app.calendar.create_calendar_candidate", side_effect=create_calendar_adapter):
        first_thread = threading.Thread(target=run_task)
        second_thread = threading.Thread(target=run_calendar)
        first_thread.start()
        assert first_entered.wait(timeout=2)
        second_thread.start()
        assert second_attempting.wait(timeout=2)
        assert not second_entered.wait(timeout=0.15)
        release_first.set()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert errors == []
    assert second_entered.is_set()
    assert state["overlap"] is False


def test_direct_task_create_and_approval_dispatch_share_adapter_lock(tmp_path, monkeypatch):
    _enable(monkeypatch)
    vault = tmp_path / "vault"
    task_file = vault / "ops" / "task-db.md"
    task_file.parent.mkdir(parents=True)
    task_file.write_text(
        "| Title | Status | Area | Priority | Due | Source |\n"
        "|---|---|---|---|---|---|\n"
        "| Seed | todo |  |  |  | test |\n",
        encoding="utf-8",
    )
    config = SimpleNamespace(vault_path=str(vault))
    approval = _request(tool="vault.create_task", args={
        "title": "Approval task", "status": "todo",
    })
    ta.approve(approval["approvalId"])

    first_entered = threading.Event()
    release_first = threading.Event()
    second_attempting = threading.Event()
    second_entered = threading.Event()
    calls = {"count": 0}
    calls_lock = threading.Lock()
    errors = []

    def blocking_backup(path):
        with calls_lock:
            calls["count"] += 1
            call_number = calls["count"]
        if call_number == 1:
            first_entered.set()
            assert release_first.wait(timeout=2)
        else:
            second_entered.set()
        return tmp_path / f"backup-{call_number}.md"

    def run_direct():
        try:
            vault_task_create(CreateVaultTaskRequest(title="Direct task", status="todo"))
        except Exception as exc:
            errors.append(exc)

    def run_approval():
        second_attempting.set()
        try:
            ta.execute(approval["approvalId"])
        except Exception as exc:
            errors.append(exc)

    with patch("app.main.get_config", return_value=config), \
         patch("app.config.get_config", return_value=config), \
         patch("app.vault._backup_task_file", side_effect=blocking_backup):
        direct_thread = threading.Thread(target=run_direct)
        approval_thread = threading.Thread(target=run_approval)
        direct_thread.start()
        assert first_entered.wait(timeout=2)
        approval_thread.start()
        assert second_attempting.wait(timeout=2)
        assert not second_entered.wait(timeout=0.15)
        release_first.set()
        direct_thread.join(timeout=2)
        approval_thread.join(timeout=2)

    assert not direct_thread.is_alive()
    assert not approval_thread.is_alive()
    assert errors == []
    assert second_entered.is_set()
    content = task_file.read_text(encoding="utf-8")
    assert "Direct task" in content
    assert "Approval task" in content


def test_shared_cross_process_lock_is_reentrant():
    with wl.vault_write_lock:
        with wl.vault_write_lock:
            assert wl.vault_write_lock.path.exists()


def test_approval_state_uses_distinct_cross_process_lock_and_independent_instances(tmp_path):
    assert ta._lock is wl.approval_state_lock
    assert wl.approval_state_lock.path != wl.vault_write_lock.path
    path = tmp_path / "independent-approval-state.lock"
    first_lock = wl.CrossProcessRLock(path)
    second_lock = wl.CrossProcessRLock(path)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def hold_first():
        with first_lock:
            first_entered.set()
            assert release_first.wait(timeout=2)

    def enter_second():
        with second_lock:
            second_entered.set()

    first_thread = threading.Thread(target=hold_first)
    second_thread = threading.Thread(target=enter_second)
    first_thread.start()
    assert first_entered.wait(timeout=2)
    second_thread.start()
    assert not second_entered.wait(timeout=0.15)
    release_first.set()
    first_thread.join(timeout=2)
    second_thread.join(timeout=2)
    assert second_entered.is_set()


def test_duplicate_execution_claim_sees_executing_and_rejects(monkeypatch):
    _enable(monkeypatch)
    request = _request(tool="brain.today")
    ta.approve(request["approvalId"])
    dispatch_entered = threading.Event()
    release_dispatch = threading.Event()
    first_errors = []

    def blocking_brain(command):
        dispatch_entered.set()
        assert release_dispatch.wait(timeout=2)
        return _brain_result(command)

    def first_execute():
        try:
            ta.execute(request["approvalId"])
        except Exception as exc:
            first_errors.append(exc)

    with patch("app.brain.run_brain_command", side_effect=blocking_brain) as run:
        thread = threading.Thread(target=first_execute)
        thread.start()
        assert dispatch_entered.wait(timeout=2)
        assert ta.list_approvals()[0]["status"] == "executing"
        with pytest.raises(ta.ApprovalConflict, match="executing"):
            ta.execute(request["approvalId"])
        release_dispatch.set()
        thread.join(timeout=2)

    assert not thread.is_alive()
    assert first_errors == []
    run.assert_called_once_with("today")
    assert ta.list_approvals()[0]["status"] == "executed"


def test_transition_retention_preserves_live_evidence_and_caps_unreferenced(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(pg, "_MAX_TRANSITION_LOGS", 2)
    live = []
    for _ in range(3):
        request = _request(tool="brain.today")
        live.append(ta.approve(request["approvalId"]))
    for _ in range(6):
        request = _request(tool="brain.sync_raw")
        ta.reject(request["approvalId"])

    entries = json.loads(pg.EVALUATIONS_FILE.read_text(encoding="utf-8"))
    transitions = [entry for entry in entries if entry.get("source") == "approval_transition"]
    protected = ta.protected_live_transition_log_ids()
    transition_ids = {entry["id"] for entry in transitions}
    assert protected == {record["transitionLogId"] for record in live}
    assert protected.issubset(transition_ids)
    unreferenced = [entry for entry in transitions if entry["id"] not in protected]
    assert len(unreferenced) == 2


def test_approval_dispatch_never_uses_raw_subprocess_or_shell(monkeypatch):
    _enable(monkeypatch)
    request = _request()
    ta.approve(request["approvalId"])
    with patch("app.brain.run_brain_command", return_value=_brain_result()) as brain, \
         patch("subprocess.run") as raw_run, patch("subprocess.Popen") as popen:
        ta.execute(request["approvalId"])
    brain.assert_called_once_with("today")
    raw_run.assert_not_called()
    popen.assert_not_called()


# ── approval-stack coupling guard (PRD §32) ───────────────────────────────────
# Registering a tool for approval takes SIX coordinated edits. Nothing enforced
# that, so calendar.create_event / browser.search / browser.read_page shipped in
# _APPROVAL_REQUIRED_TOOLS and _dispatch but without an _ARG_MODELS entry — which
# made them permanently unqueueable while LOOKING like a deliberate policy
# refusal, because create_approval raised the same message for both causes.
# These tests fail loudly if any of the six sites is missed again.

_NO_REVIEW_FIELDS = frozenset({"brain.today", "brain.sync_raw"})


def test_every_approval_required_tool_has_an_arg_model():
    """_ARG_MODELS is what create_approval validates against; a missing entry
    makes the tool unqueueable through the only path into the queue."""
    assert set(pg._APPROVAL_REQUIRED_TOOLS) == set(ta._ARG_MODELS), (
        "Approval-required tools and canonical arg models have diverged. "
        f"Missing arg model: {sorted(set(pg._APPROVAL_REQUIRED_TOOLS) - set(ta._ARG_MODELS))}. "
        f"Arg model with no policy: {sorted(set(ta._ARG_MODELS) - set(pg._APPROVAL_REQUIRED_TOOLS))}."
    )


@pytest.mark.parametrize("tool", sorted(pg._APPROVAL_REQUIRED_TOOLS))
def test_every_approval_required_tool_has_a_dispatch_branch(tool):
    import inspect
    source = inspect.getsource(ta._dispatch)
    assert f'"{tool}"' in source, f"{tool} has no _dispatch branch; execute would raise."


@pytest.mark.parametrize("tool", sorted(pg._APPROVAL_REQUIRED_TOOLS))
def test_every_approval_required_tool_summarizes_its_execution(tool):
    """A None summary means the operator sees no outcome for an executed action."""
    assert ta._execution_summary(tool, {}, True) is not None, (
        f"{tool} has no _execution_summary branch."
    )


@pytest.mark.parametrize("tool", sorted(pg._APPROVAL_REQUIRED_TOOLS))
def test_every_approval_required_tool_describes_its_arguments(tool):
    """The generic fallback tells the operator nothing about what they approve."""
    summary = ta._approval_args_summary(tool, {"title": "x"})
    assert summary != "Approval-required arguments withheld", (
        f"{tool} falls through to the opaque _approval_args_summary fallback."
    )


@pytest.mark.parametrize(
    "tool", sorted(pg._APPROVAL_REQUIRED_TOOLS - _NO_REVIEW_FIELDS)
)
def test_every_argument_taking_tool_exposes_review_fields(tool):
    """reviewFields is what the approval UI renders; empty means a blind approval."""
    record = {"tool": tool, "canonicalArgs": {"title": "x", "url": "https://example.com",
                                              "query": "q", "date": "2026-09-01"}}
    assert ta._review_fields(record), f"{tool} exposes no review fields for approval."


# ── the three previously-unqueueable tools, through the REAL path ─────────────
# Every pre-existing test for these called tool_approvals._dispatch(...) directly,
# which skips create_approval entirely — the exact reason the missing arg models
# went unnoticed. These go through the only path the product actually uses:
# create_request -> create_approval -> approve -> execute.


def test_calendar_event_queues_approves_and_executes(monkeypatch):
    """MVP v9's real external write, reachable end to end for the first time."""
    _enable(monkeypatch)
    request = _request(tool="calendar.create_event",
                       args={"title": "Advisor meeting", "date": "2026-09-01", "time": "14:30"})
    assert request["status"] == "pending_approval"
    assert request["approvalId"]

    tool_approval_approve(request["id"], ApproveToolApprovalRequest(approvedBy="owner"), _TOKEN)
    with patch("app.gcal_write.create_event",
               return_value={"eventId": "e12", "htmlLink": None, "summary": "Advisor meeting",
                             "start": None, "end": None, "calendarId": "primary"}) as create:
        executed = tool_approval_execute(
            request["approvalId"], ExecuteToolApprovalRequest(), _TOKEN,
        )
    create.assert_called_once()
    assert executed.status == "executed"
    assert executed.result.resultType == "calendar_event_created"
    assert executed.result.ok is True


def test_browser_search_queues_and_executes(monkeypatch):
    _enable(monkeypatch)
    request = _request(tool="browser.search",
                       args={"sessionId": "sess-1", "query": "landlock docker seccomp"})
    tool_approval_approve(request["id"], ApproveToolApprovalRequest(), _TOKEN)
    with patch("app.browser.search", return_value={"results": [], "query": "q"}) as search:
        executed = tool_approval_execute(
            request["approvalId"], ExecuteToolApprovalRequest(), _TOKEN,
        )
    search.assert_called_once_with("sess-1", "landlock docker seccomp", None)
    assert executed.status == "executed"
    assert executed.result.resultType == "sandboxed_search"


def test_page_read_goes_through_open_page_so_the_allowlist_still_applies(monkeypatch):
    """Regression guard: dispatching straight to fetch_page_in_sandbox skipped
    validate_url, the session domain allowlist, and the SSRF checks."""
    _enable(monkeypatch)
    request = _request(tool="browser.read_page",
                       args={"sessionId": "sess-1", "url": "https://example.com/a"})
    tool_approval_approve(request["id"], ApproveToolApprovalRequest(), _TOKEN)
    with patch("app.browser.open_page",
               return_value={"url": "https://example.com/a", "title": "A", "timestamp": "t",
                             "snippet": "s", "textChars": 1, "httpStatus": 200}) as open_page:
        with patch("app.openshell_exec.fetch_page_in_sandbox") as raw_fetch:
            executed = tool_approval_execute(
                request["approvalId"], ExecuteToolApprovalRequest(), _TOKEN,
            )
    open_page.assert_called_once_with("sess-1", "https://example.com/a")
    raw_fetch.assert_not_called()
    assert executed.status == "executed"
    assert executed.result.resultType == "sandboxed_page_read"


def test_session_scoped_browser_tools_reject_a_missing_session():
    """Without sessionId there is no allowlist to check the URL against, so the
    request must not be queueable at all."""
    for tool, args in (
        ("browser.search", {"query": "q"}),
        ("browser.read_page", {"url": "https://example.com"}),
    ):
        with pytest.raises(Exception) as exc:
            ta.validate_canonical_args(tool, args)
        assert "sessionId" in str(exc.value) or "Field required" in str(exc.value)


def test_page_read_rejects_a_non_http_url():
    with pytest.raises(Exception) as exc:
        ta.validate_canonical_args("browser.read_page",
                                   {"sessionId": "s", "url": "file:///etc/passwd"})
    assert "http(s)" in str(exc.value)


def test_missing_arg_model_is_distinguishable_from_a_policy_refusal():
    """These two refusals once read identically, which is how the gap survived."""
    with pytest.raises(ta.ApprovalError) as registration_gap:
        ta.validate_canonical_args("some.unregistered_tool", {})
    assert "tool-registration gap" in str(registration_gap.value)


# The registration surface turned out to be EIGHT sites, not six: the API response
# models are load-bearing too. _execution_summary emitted three resultTypes that
# the response Literal did not list, so those executions would have 500'd at
# serialization even after becoming queueable. These two guards close that.

def test_every_execution_summary_result_type_is_serializable():
    """resultType is a Literal on the response model; an unlisted value 500s."""
    from app.models import ToolApprovalExecutionSummary
    allowed = set(ToolApprovalExecutionSummary.model_fields["resultType"].annotation.__args__)
    emitted = {
        ta._execution_summary(tool, {}, True)["resultType"]
        for tool in pg._APPROVAL_REQUIRED_TOOLS
    }
    assert emitted <= allowed, (
        f"_execution_summary emits resultType(s) the response model rejects: "
        f"{sorted(emitted - allowed)}"
    )


@pytest.mark.parametrize("tool", sorted(pg._APPROVAL_REQUIRED_TOOLS))
def test_every_review_field_shape_is_serializable(tool):
    """reviewFields is a closed Union of extra='forbid' models; a shape with no
    member cannot be returned to the approval UI at all."""
    from pydantic import TypeAdapter
    from app.models import ToolApprovalResponse

    sample = {"title": "x", "date": "2026-09-01", "time": "09:30", "duration": "30m",
              "status": "todo", "area": "a", "priority": "high", "due": "2026-09-01",
              "source": "agent", "reason": "r", "location": "l", "timeZone": "UTC",
              "sessionId": "s", "query": "q", "limit": 5, "url": "https://example.com",
              "task": "Tidy the download folder", "allowedWindows": ["Explorer"],
              "budgetSeconds": 120,
              "entityType": "project", "wikiPath": "wiki/projects/X.md",
              "repoPath": "D:/dev/x", "githubUrl": "https://github.com/a/b",
              "demoUrl": "https://demo.example.com"}
    fields = ta._review_fields({"tool": tool, "canonicalArgs": sample})
    adapter = TypeAdapter(ToolApprovalResponse.model_fields["reviewFields"].annotation)
    adapter.validate_python(fields)  # raises if no Union member accepts this shape
