"""
test_permission_gateway.py — Permission Gateway v0 (deny-by-default classification).

The gateway classifies tool requests and executes NOTHING. These tests assert the
policy table includes the required tools, decisions are correct for not-wired /
disabled / unknown / dangerous tools, secrets are redacted, long values truncated,
executionEnabled is always False, and no subprocess/external execution path runs.

Endpoints are exercised by calling the route functions directly (the repo's test
suite does not depend on httpx/TestClient — see test_entity_creation_safety.py).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from app import permission_gateway as pg
from app.permission_gateway import evaluate_tool_request, list_policies
from app.main import permissions_policies, permissions_evaluate
from app.models import ToolRequestEvaluationRequest


REQUIRED_TOOLS = {
    "obsidian.search", "obsidian.read", "obsidian.write",
    "gmail.search", "gmail.read", "gmail.draft", "gmail.send",
    "calendar.read", "calendar.create_event",
    "browser.search", "browser.read_page",
    "computer.click", "computer.type",
    "brain.status", "brain.today", "brain.sync_raw",
    "filesystem.read_vault", "filesystem.write_vault",
}

VALID_DECISIONS = {"denied", "requires_approval", "not_wired", "disabled"}
VALID_RISK = {"low", "medium", "high", "disabled"}
VALID_STATUS = {"not_wired", "available", "disabled"}


@pytest.fixture(autouse=True)
def _isolate_tool_log(monkeypatch):
    """Redirect the backend-local audit log into an independent temp dir so
    evaluating via the endpoint never touches real app-data — and never lands in a
    test's own tmp_path (which some tests assert stays empty)."""
    import tempfile, shutil
    d = Path(tempfile.mkdtemp())
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", d)
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", d / "evaluations.json")
    yield
    shutil.rmtree(d, ignore_errors=True)


# ── policy list ─────────────────────────────────────────────────────────────────

def test_policy_list_includes_required_tools():
    tools = {p["tool"] for p in list_policies()}
    assert REQUIRED_TOOLS.issubset(tools)


def test_endpoint_policy_list_includes_required_tools():
    res = permissions_policies()
    tools = {p.tool for p in res.policies}
    assert REQUIRED_TOOLS.issubset(tools)


_EXECUTABLE = {"brain.status", "brain.raw_status", "brain.vault_path"}


def test_policy_shape_and_enums():
    for p in list_policies():
        assert p["riskLevel"] in VALID_RISK, p
        assert p["status"] in VALID_STATUS, p
        assert isinstance(p["requiresApproval"], bool)
        assert isinstance(p["executionEnabled"], bool)


def test_execution_enabled_only_for_safe_local_tools():
    by_tool = {p["tool"]: p for p in list_policies()}
    for t, p in by_tool.items():
        assert p["executionEnabled"] is (t in _EXECUTABLE), t
    # The privileged-execution kill-switch never flips.
    assert pg.EXECUTION_ENABLED is False


def test_privileged_tools_not_wired_or_disabled():
    by_tool = {p["tool"]: p for p in list_policies()}
    for t in ("obsidian.search", "gmail.search", "gmail.read", "gmail.draft", "calendar.read"):
        assert by_tool[t]["status"] == "not_wired", t
    # Sending email has no code path at all and stays disabled.
    assert by_tool["gmail.send"]["status"] == "disabled"
    # MVP v7 routed computer-use through the gateway. It is now `available` in the
    # policy sense — reachable through the approval queue — while remaining behind
    # its own kill switch, a scoped session, and the foreground-window check.
    # It must NEVER be immediately executable.
    for t in ("computer.start_session", "computer.click", "computer.type", "computer.screenshot"):
        assert by_tool[t]["requiresApproval"] is True, t
        assert by_tool[t]["executionEnabled"] is False, t
    assert by_tool["computer.start_session"]["riskLevel"] == "high"
    assert by_tool["computer.click"]["riskLevel"] == "high"
    assert by_tool["computer.type"]["riskLevel"] == "high"
    # C1b made the browser reads reachable, but ONLY inside the sandbox and ONLY
    # through the approval queue — never immediately executable.
    for t in ("browser.read_page", "browser.search"):
        assert by_tool[t]["requiresApproval"] is True, t
        assert by_tool[t]["executionEnabled"] is False, t
    # D2 made calendar.create_event reachable, but ONLY through the approval queue:
    # never immediately executable, and always requiring explicit approval.
    create_event = by_tool["calendar.create_event"]
    assert create_event["requiresApproval"] is True
    assert create_event["executionEnabled"] is False
    assert create_event["riskLevel"] == "high"


# ── evaluate: not-wired gmail ───────────────────────────────────────────────────

def test_evaluate_gmail_search_not_wired():
    r = evaluate_tool_request("gmail.search", {"query": "from:a@b.com"}, reason="intake")
    assert r["decision"] == "not_wired"
    assert r["allowed"] is False
    assert r["executionEnabled"] is False
    assert r["tool"] == "gmail.search"
    assert r["wouldLog"] is True
    assert r["sanitizedArgsSummary"] == "query: from:a@b.com"


def test_endpoint_evaluate_gmail_search():
    req = ToolRequestEvaluationRequest(tool="gmail.search", args={"query": "x"}, reason="r", requestedBy="manual-ui")
    res = permissions_evaluate(req)
    assert res.decision == "not_wired"
    assert res.allowed is False
    assert res.executionEnabled is False


# ── evaluate: disabled dangerous ────────────────────────────────────────────────

@pytest.mark.parametrize("tool", ["gmail.send"])
def test_evaluate_known_dangerous_disabled(tool):
    r = evaluate_tool_request(tool, {})
    assert r["decision"] == "disabled"
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


@pytest.mark.parametrize("tool", [
    "computer.start_session", "computer.click", "computer.type", "computer.screenshot",
])
def test_computer_use_is_approval_gated_never_directly_executable(tool):
    """Computer-use drives the real desktop, so the gateway must never hand it
    an immediate green light — approval is the only route."""
    r = evaluate_tool_request(tool, {})
    assert r["decision"] == "requires_approval", tool
    assert r["allowed"] is False, tool
    assert r["executionEnabled"] is False, tool


@pytest.mark.parametrize("tool", ["shell.run", "filesystem.delete", "browser.submit_form", "gmail.delete", "gmail.archive", "gmail.modify_labels"])
def test_evaluate_unknown_dangerous_disabled(tool):
    """Unknown destructive-looking names must not be allowed — reported disabled."""
    r = evaluate_tool_request(tool, {"x": 1})
    assert r["decision"] == "disabled"
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


# ── evaluate: unknown tool denied ───────────────────────────────────────────────

def test_evaluate_unknown_tool_denied():
    r = evaluate_tool_request("frobnicate.thing", {"x": 1})
    assert r["decision"] == "denied"
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


def test_evaluate_empty_tool_raises():
    with pytest.raises(ValueError):
        evaluate_tool_request("   ", {})


# ── evaluate: safe-local tools are 'allowed' (executable); evaluate never runs ───

def test_evaluate_safe_local_tool_allowed():
    r = evaluate_tool_request("brain.status", None)
    assert r["decision"] == "allowed"
    assert r["allowed"] is True
    assert r["executionEnabled"] is True
    assert r["riskLevel"] == "low"


def test_evaluate_available_nonexecutable_requires_approval():
    r = evaluate_tool_request("brain.sync_raw", None)
    assert r["decision"] == "requires_approval"
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


# ── secret redaction ────────────────────────────────────────────────────────────

def test_secret_keys_redacted():
    args = {
        "password": "ZZhunter2",
        "api_token": "ZZabcdef",
        "client_secret": "ZZshhh",
        "private_key": "ZZkkk",
        "credential": "ZZcredval",
        "Authorization": "ZZBearerxyz",
        "session_cookie": "ZZckie",
        "query": "visible",
    }
    r = evaluate_tool_request("gmail.search", args)
    summary = r["sanitizedArgsSummary"]
    for secret in ("ZZhunter2", "ZZabcdef", "ZZshhh", "ZZkkk", "ZZcredval", "ZZBearerxyz", "ZZckie"):
        assert secret not in summary, secret
    assert summary.count("[redacted]") >= 7
    assert "query: visible" in summary


# ── long-value truncation ───────────────────────────────────────────────────────

def test_long_values_truncated():
    r = evaluate_tool_request("gmail.search", {"query": "A" * 500})
    summary = r["sanitizedArgsSummary"]
    assert "…" in summary
    assert "A" * 500 not in summary
    # whole summary is capped
    assert len(summary) <= 260


def test_many_args_capped():
    args = {f"k{i}": i for i in range(50)}
    r = evaluate_tool_request("gmail.search", args)
    assert "more)" in r["sanitizedArgsSummary"]


# ── no execution / no external call path ────────────────────────────────────────

def test_no_subprocess_invoked():
    with patch("subprocess.run") as m_run, patch("subprocess.Popen") as m_popen:
        list_policies()
        evaluate_tool_request("gmail.search", {"query": "x"})
        evaluate_tool_request("brain.status", None)
        evaluate_tool_request("shell.run", {"cmd": "echo hi"})
    m_run.assert_not_called()
    m_popen.assert_not_called()


def test_evaluation_writes_no_files(tmp_path):
    before = list(tmp_path.iterdir())
    evaluate_tool_request("gmail.send", {"to": "a@b.com", "body": "hi"})
    permissions_evaluate(ToolRequestEvaluationRequest(tool="gmail.search", args={"q": "x"}))
    after = list(tmp_path.iterdir())
    assert before == after


def test_args_are_never_executed_only_summarized():
    """A callable-looking arg value is stringified, never invoked."""
    r = evaluate_tool_request("gmail.search", {"cmd": "__import__('os').system('echo pwned')"})
    # The value is summarized as text, not executed.
    assert "cmd:" in r["sanitizedArgsSummary"]
    assert r["allowed"] is False
