"""
test_tools_status.py — Tool / MCP Connections readiness inventory (v0).

The inventory is a static, READ-ONLY readiness surface. These tests assert it
returns every required planned tool system, never falsely reports a privileged
system as available/connected, lists Gmail mutations as blocked, keeps
browser/computer-use disabled, and triggers no external execution path.

The endpoint is exercised by calling the route function directly (the repo's test
suite does not depend on httpx/TestClient — see test_entity_creation_safety.py).
"""

from unittest.mock import patch

import pytest

from app.main import tools_status
from app.tools import list_tool_connections


REQUIRED_IDS = {
    "obsidian-mcp",
    "gmail-mcp",
    "google-calendar-api",
    "browser-harness",
    "computer-use",
    "openclaw",
    "nemoclaw-openshell",
    "github",
    "google-drive",
    "graphify",
}

VALID_STATUSES = {"available", "unavailable", "not_configured", "disabled", "planned", "error"}
VALID_CATEGORIES = {"runtime", "mcp", "browser", "external", "developer"}
VALID_RISK = {"low", "medium", "high"}


def _by_id(items):
    return {it["id"]: it for it in items}


# ── required systems ────────────────────────────────────────────────────────────

def test_returns_all_required_systems():
    items = list_tool_connections()
    ids = {it["id"] for it in items}
    assert REQUIRED_IDS.issubset(ids)


def test_endpoint_returns_all_required_systems():
    res = tools_status()
    ids = {it.id for it in res.items}
    assert REQUIRED_IDS.issubset(ids)


def test_endpoint_status_values_are_valid_enum():
    res = tools_status()
    for it in res.items:
        assert it.status in VALID_STATUSES, it.id
        assert it.category in VALID_CATEGORIES, it.id
        assert it.riskLevel in VALID_RISK, it.id


def test_shape_and_field_presence():
    for it in list_tool_connections():
        assert it["status"] in VALID_STATUSES, it
        assert it["category"] in VALID_CATEGORIES, it
        assert it["riskLevel"] in VALID_RISK, it
        assert isinstance(it["enabled"], bool)
        for key in ("capabilities", "allowedNow", "blockedNow", "requires"):
            assert isinstance(it[key], list), (it["id"], key)
        assert "lastCheckedAt" in it
        assert "lastError" in it
        assert "notes" in it


# ── nothing is falsely available / connected ────────────────────────────────────

def test_nothing_is_falsely_available():
    for it in list_tool_connections():
        assert it["status"] != "available", it["id"]
        assert it["enabled"] is False, it["id"]


def test_endpoint_reports_no_available_or_enabled():
    res = tools_status()
    for it in res.items:
        assert it.status != "available", it.id
        assert it.enabled is False, it.id


def test_privileged_systems_not_configured_or_planned_or_disabled():
    privileged = _by_id(list_tool_connections())
    for sid in REQUIRED_IDS:
        assert privileged[sid]["status"] in {"not_configured", "planned", "disabled"}, sid


# ── Gmail: mutations blocked, not connected ─────────────────────────────────────

def test_gmail_not_connected_and_mutations_blocked():
    gmail = _by_id(list_tool_connections())["gmail-mcp"]
    assert gmail["status"] == "not_configured"
    assert gmail["enabled"] is False
    for mutation in ("send", "delete", "archive", "modify_labels"):
        assert mutation in gmail["blockedNow"], mutation
    # No Gmail capability or action is allowed right now.
    assert gmail["allowedNow"] == []


# ── browser / computer-use: disabled pending runtime ────────────────────────────

@pytest.mark.parametrize("sid", ["browser-harness", "computer-use"])
def test_browser_and_computer_use_disabled(sid):
    sysinfo = _by_id(list_tool_connections())[sid]
    assert sysinfo["status"] == "disabled"
    assert sysinfo["enabled"] is False
    assert sysinfo["allowedNow"] == []


def test_browser_harness_requires_the_sandbox_runtime():
    """Browsing runs INSIDE OpenShell, so the runtime is a real prerequisite."""
    sysinfo = _by_id(list_tool_connections())["browser-harness"]
    assert any("NemoClaw" in r or "OpenShell" in r for r in sysinfo["requires"]), \
        sysinfo["requires"]


def test_computer_use_requires_the_kill_switch_not_the_sandbox():
    """Full desktop control (the chosen design) runs on the HOST, so its
    prerequisite is the operator kill switch and token — not a sandbox. Claiming
    NemoClaw gates it would misdescribe what actually protects the user."""
    sysinfo = _by_id(list_tool_connections())["computer-use"]
    joined = " ".join(sysinfo["requires"])
    assert "BRAIN_UI_COMPUTER_USE_ENABLED" in joined
    assert "BRAIN_UI_APPROVAL_TOKEN" in joined
    assert "foreground window" in joined.lower()


# ── OpenClaw / NemoClaw: planned / not wired ────────────────────────────────────

@pytest.mark.parametrize("sid", ["openclaw", "nemoclaw-openshell"])
def test_openclaw_nemoclaw_planned(sid):
    sysinfo = _by_id(list_tool_connections())[sid]
    assert sysinfo["status"] == "planned"
    assert sysinfo["enabled"] is False


# ── read-only: no external execution path is invoked ────────────────────────────

def test_no_external_execution_path_invoked():
    """
    Listing must not spawn a subprocess (no brain, no shell, no tool launch).
    We patch subprocess entry points and assert none are touched.
    """
    with patch("subprocess.run") as m_run, \
         patch("subprocess.Popen") as m_popen:
        items = list_tool_connections()
        res = tools_status()
    assert len(items) >= len(REQUIRED_IDS)
    assert len(res.items) >= len(REQUIRED_IDS)
    m_run.assert_not_called()
    m_popen.assert_not_called()


def test_listing_writes_no_files(tmp_path):
    before = list(tmp_path.iterdir())
    list_tool_connections()
    tools_status()
    after = list(tmp_path.iterdir())
    assert before == after


def test_returns_fresh_copies_not_shared_state():
    """Mutating a returned item must not affect later calls (no shared state leak)."""
    first = list_tool_connections()
    first[0]["status"] = "available"
    first[0]["enabled"] = True
    second = list_tool_connections()
    assert second[0]["status"] != "available"
    assert second[0]["enabled"] is False
