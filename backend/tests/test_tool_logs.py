"""
test_tool_logs.py — Tool Log v0 (backend-local audit of Permission Gateway evals).

Every Permission Gateway evaluation writes one redacted, backend-local audit entry
(never the vault, never raw args/secrets). These tests isolate the storage path into
tmp_path and exercise both the module functions and the route functions directly
(the repo's test suite does not depend on httpx/TestClient).
"""

import json
from unittest.mock import patch

import pytest

from app import permission_gateway as pg
from app.permission_gateway import evaluate_tool_request, log_evaluation, list_logs
from app.main import permissions_evaluate, permissions_logs
from app.models import ToolRequestEvaluationRequest


@pytest.fixture(autouse=True)
def _isolate_log(tmp_path, monkeypatch):
    d = tmp_path / "tool-logs"
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", d)
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", d / "evaluations.json")
    yield


def _evaluate(tool, args=None, reason=None, requested_by="manual-ui"):
    return permissions_evaluate(ToolRequestEvaluationRequest(
        tool=tool, args=args, reason=reason, requestedBy=requested_by,
    ))


# ── evaluate writes a log + returns logId ───────────────────────────────────────

def test_evaluate_writes_log_and_returns_logid():
    res = _evaluate("gmail.search", {"query": "from:a@b.com"}, reason="intake")
    assert res.logId
    logs = list_logs()
    assert len(logs) == 1
    assert logs[0]["id"] == res.logId
    assert logs[0]["tool"] == "gmail.search"
    assert logs[0]["decision"] == "not_wired"
    assert logs[0]["result"] == "evaluated_only"
    assert logs[0]["requestedBy"] == "manual-ui"
    assert logs[0]["reason"] == "intake"


def test_log_entry_has_required_fields():
    _evaluate("gmail.send", {})
    e = list_logs()[0]
    for field in ("id", "timestamp", "tool", "requestedBy", "reason", "decision",
                  "riskLevel", "allowed", "requiresApproval", "executionEnabled",
                  "sanitizedArgsSummary", "policyNotes", "result"):
        assert field in e, field
    assert e["allowed"] is False
    assert e["executionEnabled"] is False


# ── newest first ────────────────────────────────────────────────────────────────

def test_logs_newest_first():
    _evaluate("gmail.search")
    _evaluate("gmail.send")
    _evaluate("shell.run")
    tools = [e["tool"] for e in list_logs()]
    assert tools[0] == "shell.run"
    assert tools[-1] == "gmail.search"


# ── limit enforcement ───────────────────────────────────────────────────────────

def test_limit_default_and_clamp():
    for _ in range(10):
        _evaluate("brain.status")
    assert len(list_logs(limit=3)) == 3
    assert len(list_logs(limit=9999)) <= 200      # clamped to max
    assert len(list_logs(limit=0)) == 1           # clamped to min 1
    # default
    for _ in range(60):
        _evaluate("brain.today")
    assert len(list_logs()) == 50                 # default limit


def test_endpoint_logs_clamped():
    for _ in range(5):
        _evaluate("gmail.search")
    res = permissions_logs(limit=2)
    assert len(res.logs) == 2


# ── filters ─────────────────────────────────────────────────────────────────────

def test_filter_by_tool_and_decision():
    _evaluate("gmail.search")
    _evaluate("gmail.send")
    _evaluate("shell.run")
    assert {e["tool"] for e in list_logs(tool="gmail.search")} == {"gmail.search"}
    disabled = list_logs(decision="disabled")
    assert {e["tool"] for e in disabled} == {"gmail.send", "shell.run"}
    assert list_logs(tool="does.not.exist") == []


def test_endpoint_filter():
    _evaluate("gmail.send")
    _evaluate("gmail.search")
    res = permissions_logs(decision="disabled")
    assert all(e.decision == "disabled" for e in res.logs)


# ── redaction: secrets never stored, raw args never stored ───────────────────────

def test_secrets_redacted_in_stored_log():
    _evaluate("gmail.search", {
        "password": "ZZhunter2", "api_token": "ZZtok", "session_cookie": "ZZckie",
        "query": "visible",
    })
    raw_file = pg.EVALUATIONS_FILE.read_text(encoding="utf-8")
    for secret in ("ZZhunter2", "ZZtok", "ZZckie"):
        assert secret not in raw_file, secret
    assert "[redacted]" in raw_file
    assert "query: visible" in list_logs()[0]["sanitizedArgsSummary"]


def test_raw_args_not_stored():
    _evaluate("gmail.search", {"query": "needle_in_haystack_value"})
    e = list_logs()[0]
    # only the sanitized summary is present; there is no raw args field
    assert "args" not in e
    assert "rawArgs" not in e
    assert e["sanitizedArgsSummary"] == "query: needle_in_haystack_value"


# ── retention cap ────────────────────────────────────────────────────────────────

def test_cap_latest_500(monkeypatch):
    monkeypatch.setattr(pg, "_MAX_STORED_LOGS", 5)
    for _ in range(12):
        _evaluate("brain.status")
    stored = json.loads(pg.EVALUATIONS_FILE.read_text(encoding="utf-8"))
    assert len(stored) == 5


# ── no execution / no external call path ────────────────────────────────────────

def test_no_subprocess_invoked():
    with patch("subprocess.run") as m_run, patch("subprocess.Popen") as m_popen:
        _evaluate("gmail.send", {"to": "x@y.com"})
        list_logs()
        permissions_logs(limit=10)
    m_run.assert_not_called()
    m_popen.assert_not_called()


def test_log_evaluation_is_evaluated_only():
    e = log_evaluation(evaluate_tool_request("gmail.send", {}))
    assert e["result"] == "evaluated_only"
    assert e["allowed"] is False
    assert e["executionEnabled"] is False
