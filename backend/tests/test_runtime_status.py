"""
test_runtime_status.py — OpenClaw / NemoClaw Runtime Status v0 (read-only readiness).

The endpoint reports honest config/readiness for the five privileged runtimes. It
makes NO network call, launches NO runtime, runs NO shell/`brain`, and reads NO
credentials. No runtime is reported `available` (no verified check exists), so
browser/computer-use stay blocked while NemoClaw/OpenShell is unavailable.
"""

from unittest.mock import patch

from app.runtime_status import list_runtime_status
from app.main import runtime_status

REQUIRED_IDS = ["openclaw", "nemoclaw_openshell", "browser_harness", "computer_use", "mcp_gateway"]


def _by_id(items):
    return {i["id"]: i for i in items}


# ── required items + shape ──────────────────────────────────────────────────────

def test_returns_required_items():
    items = list_runtime_status(env={})
    assert [i["id"] for i in items] == REQUIRED_IDS


def test_endpoint_returns_required_items():
    res = runtime_status()
    assert [i.id for i in res.items] == REQUIRED_IDS


def test_item_shape():
    item = _by_id(list_runtime_status(env={}))["openclaw"]
    for key in ("id", "name", "status", "available", "enabled", "requiredFor",
                "dependsOn", "blocks", "configured", "notes"):
        assert key in item


# ── default statuses (no env) ───────────────────────────────────────────────────

def test_default_statuses():
    by = _by_id(list_runtime_status(env={}))
    assert by["openclaw"]["status"] == "not_configured"
    assert by["nemoclaw_openshell"]["status"] == "not_configured"
    assert by["browser_harness"]["status"] == "disabled"
    assert by["computer_use"]["status"] == "disabled"
    assert by["mcp_gateway"]["status"] == "not_configured"


def test_nothing_available_or_enabled_by_default():
    for item in list_runtime_status(env={}):
        assert item["available"] is False
        assert item["enabled"] is False


def test_no_status_is_available():
    # Honesty: no runtime is ever reported available in this build (no verified check).
    for item in list_runtime_status(env={}):
        assert item["status"] != "available"


# ── dependency blocking ─────────────────────────────────────────────────────────

def test_browser_blocked_without_nemoclaw():
    by = _by_id(list_runtime_status(env={}))
    br = by["browser_harness"]
    assert br["status"] == "disabled"
    assert br["available"] is False
    assert "nemoclaw_openshell" in br["dependsOn"]
    assert any("NemoClaw/OpenShell" in b for b in br["blocks"])


def test_computer_use_blocked_without_nemoclaw():
    by = _by_id(list_runtime_status(env={}))
    cu = by["computer_use"]
    assert cu["status"] == "disabled"
    assert cu["available"] is False
    assert "nemoclaw_openshell" in cu["dependsOn"]
    assert any("NemoClaw/OpenShell" in b for b in cu["blocks"])


def test_browser_blocked_even_when_flag_enabled_but_nemo_unavailable():
    # Enabling the browser flag must NOT unblock it while the guardrail is unavailable.
    env = {"ENABLE_BROWSER_HARNESS": "true", "ENABLE_COMPUTER_USE": "true"}
    by = _by_id(list_runtime_status(env=env))
    assert by["browser_harness"]["status"] == "disabled"
    assert by["browser_harness"]["available"] is False
    assert by["computer_use"]["status"] == "disabled"
    assert by["computer_use"]["available"] is False
    assert any("NemoClaw/OpenShell" in b for b in by["browser_harness"]["blocks"])


def test_nemoclaw_never_available_even_when_configured():
    # Fully configured, but no verified health check exists → never available in v0.
    env = {"NEMOCLAW_ENABLED": "true", "NEMOCLAW_RUNTIME_URL": "http://localhost:9999"}
    by = _by_id(list_runtime_status(env=env))
    nc = by["nemoclaw_openshell"]
    assert nc["available"] is False
    assert nc["status"] == "unavailable"           # configured but unverified
    assert nc["configured"]["enabledFlag"] is True
    assert nc["configured"]["runtimeUrl"] is True
    # And dependents stay blocked.
    assert by["browser_harness"]["available"] is False
    assert by["computer_use"]["available"] is False


# ── config / env flag behavior ──────────────────────────────────────────────────

def test_openclaw_config_detection():
    by = _by_id(list_runtime_status(env={"OPENCLAW_ENABLED": "true", "OPENCLAW_BASE_URL": "http://x"}))
    oc = by["openclaw"]
    assert oc["configured"]["enabledFlag"] is True
    assert oc["configured"]["baseUrl"] is True
    assert oc["status"] == "unavailable"           # configured but not verified
    assert oc["available"] is False                # never claimed available


def test_explicit_disable():
    by = _by_id(list_runtime_status(env={
        "OPENCLAW_ENABLED": "false",
        "NEMOCLAW_ENABLED": "false",
        "ENABLE_MCP_GATEWAY": "false",
    }))
    assert by["openclaw"]["status"] == "disabled"
    assert by["nemoclaw_openshell"]["status"] == "disabled"
    assert by["mcp_gateway"]["status"] == "disabled"


def test_partial_config_is_not_configured():
    # enabled flag set but URL missing → still not_configured (incomplete).
    by = _by_id(list_runtime_status(env={"OPENCLAW_ENABLED": "true"}))
    assert by["openclaw"]["status"] == "not_configured"
    assert by["openclaw"]["configured"]["enabledFlag"] is True
    assert by["openclaw"]["configured"]["baseUrl"] is False


def test_unrecognized_flag_treated_as_unset():
    by = _by_id(list_runtime_status(env={"OPENCLAW_ENABLED": "maybe"}))
    assert by["openclaw"]["configured"]["enabledFlag"] is False
    assert by["openclaw"]["status"] == "not_configured"


# ── safety: no execution path ───────────────────────────────────────────────────

def test_no_shell_brain_or_subprocess_called():
    with patch("app.brain.run_brain_command") as mbrain, patch("subprocess.run") as msub:
        list_runtime_status(env={})
        list_runtime_status(env={"NEMOCLAW_ENABLED": "true", "NEMOCLAW_RUNTIME_URL": "http://x"})
        runtime_status()
    mbrain.assert_not_called()
    msub.assert_not_called()


def test_returns_fresh_copies():
    a = list_runtime_status(env={})
    a[0]["status"] = "mutated"
    b = list_runtime_status(env={})
    assert b[0]["status"] != "mutated"
