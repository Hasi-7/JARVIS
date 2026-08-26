"""
test_runtime_bridge_contract.py — NemoClaw/OpenShell Bridge Contract v0 (dry-run).

The validator is dry-run only: it validates a proposed FUTURE bridge request against
mode policy, guardrail readiness, and a Permission Gateway dry-run classification, then
logs a sanitized audit entry. It NEVER calls a runtime, executes any action (not even
safe-local brain.status), runs a fresh probe, spawns a process, or writes the vault.

Guardrail readiness is injected so tests are deterministic; the log dir is isolated so
no real app-data is touched.
"""

import pytest

from app import permission_gateway as pg
from app import runtime_bridge_contract as rbc
from app.runtime_bridge_contract import validate_bridge_request


@pytest.fixture(autouse=True)
def _isolate_log(tmp_path, monkeypatch):
    d = tmp_path / "tool-logs"
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", d)
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", d / "evaluations.json")
    yield


def _ready():
    return {"status": "ready_for_bridge_design", "ready": True}


def _not_ready():
    return {"status": "not_ready", "ready": False}


def _validate(**kw):
    kw.setdefault("readiness_fn", _not_ready)
    return validate_bridge_request(**kw)


# ── every response is non-executing ──────────────────────────────────────────────

@pytest.mark.parametrize("kind,mode", [
    ("browser.open", "assist"), ("brain.status", "assist"), ("computer.type", "draft"),
    ("unknown", "assist"), ("gmail.read", "research"), ("vault.write", "escalation"),
])
def test_never_allows_or_executes(kind, mode):
    r = _validate(mode=mode, action_kind=kind, readiness_fn=_ready)
    assert r["allowed"] is False
    assert r["executionEnabled"] is False
    assert r["checks"]["runtimeBridgeImplemented"] is False


# ── mode rules ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["locked", "observe"])
def test_locked_observe_blocked_by_mode(mode):
    r = _validate(mode=mode, action_kind="brain.status", readiness_fn=_ready)
    assert r["status"] == "blocked_by_mode"
    assert r["decision"] == "blocked_by_mode"
    assert r["checks"]["modeAllowsEvaluation"] is False
    assert r["checks"]["permissionGatewayDecision"] == "n/a"


def test_computer_use_mode_blocked_unavailable():
    r = _validate(mode="computer_use", action_kind="brain.status", readiness_fn=_ready)
    assert r["status"] == "blocked_by_mode"
    assert r["checks"]["modeAllowsEvaluation"] is False


@pytest.mark.parametrize("mode", ["draft", "assist", "research", "escalation"])
def test_evaluating_modes_validate_only(mode):
    r = _validate(mode=mode, action_kind="brain.status", readiness_fn=_ready)
    assert r["checks"]["modeAllowsEvaluation"] is True
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


def test_missing_mode_normalizes_to_locked_and_blocks():
    r = _validate(mode=None, action_kind="brain.status", readiness_fn=_ready)
    assert r["mode"] == "locked"
    assert r["status"] == "blocked_by_mode"


# ── action kind → risk / decision ────────────────────────────────────────────────

def test_browser_action_bridge_not_implemented():
    r = _validate(mode="assist", action_kind="browser.open", target="https://example.com",
                  args={"url": "https://example.com"}, readiness_fn=_ready)
    assert r["status"] == "blocked"
    assert r["decision"] == "runtime_bridge_not_implemented"
    assert r["riskLevel"] == "medium"
    assert "Runtime bridge is not implemented." in r["blockers"]
    assert "Browser harness is disabled." in r["blockers"]
    # C1b made page reads reachable through the APPROVAL QUEUE, not through this
    # bridge — so the gateway now classifies them requires_approval, while the
    # bridge itself remains unimplemented and the request stays blocked.
    assert r["checks"]["permissionGatewayDecision"] in ("disabled", "requires_approval")
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


def test_computer_action_high_risk_blocked():
    r = _validate(mode="assist", action_kind="computer.click", readiness_fn=_ready)
    assert r["status"] == "blocked"
    assert r["riskLevel"] == "high"
    assert "Computer-use is disabled." in r["blockers"]


def test_unknown_action_conservative_high_risk_blocked():
    r = _validate(mode="assist", action_kind="totally.made_up", readiness_fn=_ready)
    assert r["actionKind"] == "unknown"
    assert r["riskLevel"] == "high"
    assert r["status"] == "blocked"
    assert r["decision"] == "denied"
    assert "Unknown action kind is denied by default." in r["blockers"]


def test_blank_kind_is_schema_invalid_and_unknown():
    r = _validate(mode="assist", action_kind="   ", readiness_fn=_ready)
    assert r["checks"]["schemaValid"] is False
    assert r["actionKind"] == "unknown"
    assert r["status"] == "blocked"


def test_mcp_gmail_calendar_are_not_wired_blockers():
    for kind, blocker in [
        ("mcp.call", "MCP gateway is not wired."),
        ("gmail.search", "Gmail is not wired."),
        ("calendar.read", "Google Calendar is not wired."),
    ]:
        r = _validate(mode="assist", action_kind=kind, readiness_fn=_ready)
        assert r["status"] == "blocked"
        assert blocker in r["blockers"]


def test_vault_write_high_risk_blocked():
    r = _validate(mode="assist", action_kind="vault.write", readiness_fn=_ready)
    assert r["riskLevel"] == "high"
    assert r["status"] == "blocked"
    assert "Vault writes are not performed by the bridge validator." in r["blockers"]


# ── safe-local: validates only, never executes ───────────────────────────────────

def test_safe_local_brain_status_validates_only_when_ready():
    r = _validate(mode="assist", action_kind="brain.status", readiness_fn=_ready)
    assert r["status"] == "validated"
    assert r["decision"] == "schema_acceptable_for_bridge_design"
    assert r["riskLevel"] == "low"
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


def test_safe_local_vault_read_validates_only_when_ready():
    r = _validate(mode="assist", action_kind="vault.read", readiness_fn=_ready)
    assert r["status"] == "validated"
    assert r["riskLevel"] == "low"
    assert r["executionEnabled"] is False


def test_assist_safe_local_mentions_review_handoff_possible_later():
    r = _validate(mode="assist", action_kind="brain.status", readiness_fn=_ready)
    assert any("review" in w.lower() for w in r["warnings"])


def test_draft_safe_local_has_no_review_handoff_note():
    r = _validate(mode="draft", action_kind="brain.status", readiness_fn=_ready)
    assert not any("review" in w.lower() for w in r["warnings"])


# ── guardrail readiness rules ────────────────────────────────────────────────────

def test_guardrail_not_ready_is_a_blocker_for_safe_local():
    r = _validate(mode="assist", action_kind="brain.status", readiness_fn=_not_ready)
    assert r["status"] == "blocked"
    assert r["decision"] == "runtime_guardrail_not_ready"
    assert r["checks"]["guardrailReadyForBridgeDesign"] is False
    assert "Runtime guardrail is not ready for bridge design." in r["blockers"]


def test_guardrail_ready_still_does_not_execute():
    r = _validate(mode="assist", action_kind="brain.status", readiness_fn=_ready)
    assert r["checks"]["guardrailReadyForBridgeDesign"] is True
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


# ── logging: sanitized, secrets redacted ─────────────────────────────────────────

def test_validation_is_logged_with_bridge_source():
    r = _validate(mode="assist", action_kind="brain.status", readiness_fn=_ready)
    assert r["logId"]
    logs = pg.list_logs(limit=10)
    entry = next(e for e in logs if e["id"] == r["logId"])
    assert entry["source"] == "runtime_bridge_validation"
    assert entry["result"] == "validated_only"
    assert entry["allowed"] is False
    assert entry["executionEnabled"] is False


def test_secrets_redacted_in_log_and_response():
    r = _validate(
        mode="assist", action_kind="mcp.call",
        args={"password": "hunter2", "token": "abc123", "url": "https://x"},
        readiness_fn=_ready,
    )
    logs = pg.list_logs(limit=10)
    entry = next(e for e in logs if e["id"] == r["logId"])
    blob = entry["sanitizedArgsSummary"]
    assert "hunter2" not in blob
    assert "abc123" not in blob
    assert "[redacted]" in blob


def test_log_stores_no_raw_page_content_or_full_args():
    # A big "page content" arg must be truncated, never stored whole.
    big = "SECRET_BODY " * 500
    r = _validate(mode="assist", action_kind="browser.read_page",
                  args={"content": big}, readiness_fn=_ready)
    logs = pg.list_logs(limit=10)
    entry = next(e for e in logs if e["id"] == r["logId"])
    assert len(entry["sanitizedArgsSummary"]) < len(big)


# ── safety: no probe / no subprocess / no socket / no vault write ────────────────

def test_reads_readiness_but_never_runs_a_fresh_probe():
    import inspect as _inspect
    src = _inspect.getsource(rbc)
    # module must never import or call the network-hitting probe
    assert "probe_nemoclaw" not in src
    assert "get_guardrail_readiness" in src


def test_no_subprocess_socket_or_brain(monkeypatch):
    import socket
    import subprocess
    import app.brain as brain

    def _boom(*a, **k):
        raise AssertionError("bridge validation must not spawn a process / open a socket / run brain")

    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(brain, "run_brain_command", _boom)

    r = _validate(mode="assist", action_kind="brain.status", readiness_fn=_ready)
    assert r["status"] == "validated"


def test_does_not_write_vault(tmp_path):
    # A dedicated "vault" dir the validator must never touch (the audit log lives
    # elsewhere, under the isolated tool-logs dir).
    vault = tmp_path / "vault"
    vault.mkdir()
    before = set(p.name for p in vault.iterdir())
    _validate(mode="assist", action_kind="vault.write", args={"path": "x.md"}, readiness_fn=_ready)
    after = set(p.name for p in vault.iterdir())
    assert before == after == set()


def test_never_raises_on_bad_inputs():
    r = validate_bridge_request(
        mode=123, action_kind=None,
        readiness_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert r["status"] == "error"
    assert r["allowed"] is False
    assert r["executionEnabled"] is False


# ── endpoint smoke (read-only, dry-run) ──────────────────────────────────────────

def test_endpoint_dry_run_blocked(monkeypatch):
    from app.main import runtime_bridge_validate
    from app.models import RuntimeBridgeValidationRequest, RuntimeBridgeAction
    monkeypatch.delenv("NEMOCLAW_RUNTIME_URL", raising=False)
    monkeypatch.delenv("NEMOCLAW_POLICY_PATH", raising=False)
    req = RuntimeBridgeValidationRequest(
        source="openclaw", mode="assist",
        requestedAction=RuntimeBridgeAction(kind="browser.open", target="https://example.com",
                                            args={"url": "https://example.com"}),
        reason="Research this page",
    )
    res = runtime_bridge_validate(req)
    assert res.allowed is False
    assert res.executionEnabled is False
    assert res.status in ("blocked", "blocked_by_mode", "validated")
    assert res.checks.runtimeBridgeImplemented is False
