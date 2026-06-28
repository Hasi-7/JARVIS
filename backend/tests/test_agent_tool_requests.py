"""
test_agent_tool_requests.py — Agent Tool Request v0 (evaluate-only).

The Local Agent (or a manual stand-in) proposes a structured tool request; the
backend evaluates it through the Permission Gateway and logs the evaluation, but
NEVER executes anything. These tests isolate the request store and the gateway log
path, and assert the brain wrapper / subprocess are never touched and no vault file
is written.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app import agent_tool_requests as atr
from app import permission_gateway as pg
from app.agent_tool_requests import create_request, list_requests
from app.main import agent_tool_request_create, agent_tool_requests_list
from app.models import CreateAgentToolRequestRequest


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    import tempfile, shutil
    d = Path(tempfile.mkdtemp())
    monkeypatch.setattr(atr, "AGENT_REQUESTS_DIR", d / "atr")
    monkeypatch.setattr(atr, "REQUESTS_FILE", d / "atr" / "requests.json")
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", d / "logs")
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", d / "logs" / "evaluations.json")
    yield
    shutil.rmtree(d, ignore_errors=True)


def _create(tool, args=None, reason="because", requested_by="local-agent", conv="c1"):
    return create_request(tool=tool, args=args, reason=reason, requested_by=requested_by, conversation_id=conv)


# ── create evaluates + logs ─────────────────────────────────────────────────────

def test_create_evaluates_and_logs():
    r = _create("brain.status", {})
    assert r["status"] == "evaluated_only"
    assert r["tool"] == "brain.status"
    assert r["requestedBy"] == "local-agent"
    assert r["conversationId"] == "c1"
    ev = r["evaluation"]
    assert ev["logId"]
    # one gateway_eval log written, no execution log
    logs = pg.list_logs(limit=100)
    assert any(l["id"] == ev["logId"] and l["source"] == "gateway_eval" for l in logs)
    assert all(l["source"] != "gateway_execution" for l in logs)


def test_safe_local_tool_allowed_but_not_executed():
    with patch("app.brain.run_brain_command") as mbrain, patch("subprocess.run") as msub:
        r = _create("brain.status", {})
    ev = r["evaluation"]
    assert ev["decision"] == "allowed"
    assert ev["allowed"] is True
    assert ev["executionEnabled"] is True
    assert r["status"] == "evaluated_only"      # evaluated, never executed
    mbrain.assert_not_called()
    msub.assert_not_called()


@pytest.mark.parametrize("tool,cmd", [
    ("brain.status", "status"), ("brain.raw_status", "raw-status"), ("brain.vault_path", "vault-path"),
])
def test_executable_tools_still_not_run(tool, cmd):
    with patch("app.brain.run_brain_command") as mbrain:
        r = _create(tool)
    assert r["evaluation"]["executionEnabled"] is True
    mbrain.assert_not_called()


# ── non-allowed tools ───────────────────────────────────────────────────────────

def test_gmail_request_not_wired_not_executed():
    with patch("app.brain.run_brain_command") as mbrain:
        r = _create("gmail.search", {"query": "x"})
    ev = r["evaluation"]
    assert ev["decision"] == "not_wired"
    assert ev["allowed"] is False
    assert ev["executionEnabled"] is False
    mbrain.assert_not_called()


@pytest.mark.parametrize("tool,expected", [
    ("gmail.send", "disabled"),
    ("shell.run", "disabled"),
    ("filesystem.delete", "disabled"),
    ("frobnicate.thing", "denied"),
    ("brain.sync_raw", "requires_approval"),
])
def test_dangerous_unknown_other_not_executed(tool, expected):
    with patch("app.brain.run_brain_command") as mbrain:
        r = _create(tool, {"x": 1})
    assert r["evaluation"]["decision"] == expected
    assert r["evaluation"]["allowed"] is False
    mbrain.assert_not_called()


def test_empty_tool_raises():
    with pytest.raises(ValueError):
        _create("   ")


def test_endpoint_empty_tool_400():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        agent_tool_request_create(CreateAgentToolRequestRequest(tool="  "))
    assert ei.value.status_code == 400


# ── redaction: secrets never stored ─────────────────────────────────────────────

def test_secrets_redacted_in_stored_request():
    _create("gmail.search", {"password": "ZZpw", "api_token": "ZZtok", "query": "visible"})
    raw = atr.REQUESTS_FILE.read_text(encoding="utf-8")
    assert "ZZpw" not in raw
    assert "ZZtok" not in raw
    assert "[redacted]" in raw
    assert "query: visible" in raw


def test_raw_args_not_stored():
    r = _create("gmail.search", {"query": "needle_value"})
    assert "args" not in r            # only argsSummary is kept
    assert r["argsSummary"] == "query: needle_value"
    raw = json.loads(atr.REQUESTS_FILE.read_text(encoding="utf-8"))
    assert all("args" not in entry for entry in raw)


# ── list newest first + limit ───────────────────────────────────────────────────

def test_list_newest_first_and_limit():
    _create("brain.status")
    _create("gmail.search")
    _create("shell.run")
    reqs = list_requests(limit=2)
    assert len(reqs) == 2
    assert reqs[0]["tool"] == "shell.run"        # newest first
    # clamp
    assert len(list_requests(limit=0)) == 1
    assert len(list_requests(limit=9999)) == 3


def test_endpoint_list():
    _create("brain.status")
    res = agent_tool_requests_list(limit=10)
    assert len(res.requests) == 1
    assert res.requests[0].evaluation.logId


# ── no execution / no vault write ───────────────────────────────────────────────

def test_no_subprocess_and_no_execute_path():
    with patch("app.brain.run_brain_command") as mbrain, \
         patch("subprocess.run") as msub, patch("subprocess.Popen") as mpop:
        _create("brain.status")
        _create("gmail.send", {"to": "a@b.com"})
    mbrain.assert_not_called()
    msub.assert_not_called()
    mpop.assert_not_called()


def test_no_vault_write(tmp_path):
    before = list(tmp_path.iterdir())
    _create("brain.status")
    _create("gmail.search", {"q": "x"})
    assert list(tmp_path.iterdir()) == before
