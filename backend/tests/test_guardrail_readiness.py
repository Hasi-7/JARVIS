"""
test_guardrail_readiness.py — Guardrail Readiness v0.

Readiness is a read-only correlation of runtime status + the cached LAST NemoClaw/
OpenShell probe + policy inspection + agent mode policy. It never enforces policy,
runs a fresh probe, makes a network call, runs shell/`brain`/a subprocess, writes the
vault, or unlocks any capability.

The data-source callables are injected so these tests build deterministic states with
no real network/process/vault side effects.
"""

import pytest

from app import guardrail_readiness as gr
from app.guardrail_readiness import get_guardrail_readiness


# ── fake data-source builders ────────────────────────────────────────────────────

def _runtime(*, url=False, browser_enabled=False):
    """Minimal runtime inventory with the NemoClaw guardrail row (+ dependents)."""
    return [
        {"id": "nemoclaw_openshell", "status": "unavailable" if url else "not_configured",
         "available": False, "enabled": False, "configured": {"runtimeUrl": url}},
        {"id": "browser_harness", "status": "disabled",
         "available": browser_enabled, "enabled": browser_enabled, "configured": {}},
        {"id": "computer_use", "status": "disabled",
         "available": False, "enabled": False, "configured": {}},
    ]


def _probe_reachable():
    return {"status": "reachable", "reachable": True, "checkedAt": "t", "durationMs": 3}


def _probe_unreachable():
    return {"status": "unavailable", "reachable": False, "checkedAt": "t", "durationMs": 3}


def _policy_loaded():
    return {"status": "loaded", "valid": True, "pathConfigured": True}


def _policy_missing():
    return {"status": "not_configured", "valid": False, "pathConfigured": False}


def _modes():
    return [{"id": "locked"}, {"id": "assist"}]


def _readiness(*, runtime=None, probe=None, policy=None, modes=None):
    return get_guardrail_readiness(
        list_runtime=lambda: runtime if runtime is not None else _runtime(url=True),
        read_probe=lambda: probe,
        inspect_policy=lambda: policy if policy is not None else _policy_missing(),
        list_agent_modes=lambda: modes if modes is not None else _modes(),
    )


# ── correlation matrix ───────────────────────────────────────────────────────────

def test_no_probe_no_policy_is_not_ready():
    r = _readiness(runtime=_runtime(url=False), probe=None, policy=_policy_missing())
    assert r["status"] == "not_ready"
    assert r["ready"] is False
    assert r["components"]["lastProbe"] == "not_run"
    assert "NemoClaw/OpenShell runtime is not reachable." in r["blockers"]
    assert "No valid NemoClaw/OpenShell policy is loaded." in r["blockers"]


def test_reachable_probe_no_policy_is_partially_ready():
    r = _readiness(probe=_probe_reachable(), policy=_policy_missing())
    assert r["status"] == "partially_ready"
    assert r["ready"] is False
    assert "No valid NemoClaw/OpenShell policy is loaded." in r["blockers"]
    assert "NemoClaw/OpenShell runtime is not reachable." not in r["blockers"]


def test_loaded_policy_no_reachable_probe_is_partially_ready():
    r = _readiness(probe=_probe_unreachable(), policy=_policy_loaded())
    assert r["status"] == "partially_ready"
    assert r["ready"] is False
    assert "NemoClaw/OpenShell runtime is not reachable." in r["blockers"]
    assert "No valid NemoClaw/OpenShell policy is loaded." not in r["blockers"]


def test_loaded_policy_no_probe_at_all_is_partially_ready():
    r = _readiness(probe=None, policy=_policy_loaded())
    assert r["status"] == "partially_ready"
    assert r["components"]["lastProbe"] == "not_run"


def test_reachable_probe_and_loaded_policy_is_ready_for_bridge_design():
    r = _readiness(probe=_probe_reachable(), policy=_policy_loaded())
    assert r["status"] == "ready_for_bridge_design"
    assert r["ready"] is True
    assert r["blockers"] == []
    assert r["components"]["lastProbe"] == "reachable"
    assert r["components"]["policy"] == "loaded"


# ── capabilities stay false in every state ───────────────────────────────────────

@pytest.mark.parametrize("probe,policy", [
    (None, _policy_missing()),
    (_probe_reachable(), _policy_missing()),
    (_probe_unreachable(), _policy_loaded()),
    (_probe_reachable(), _policy_loaded()),
])
def test_capabilities_remain_false_in_all_states(probe, policy):
    r = _readiness(probe=probe, policy=policy)
    caps = r["capabilityUnlocks"]
    assert caps == {
        "openclawBridge": False, "browserHarness": False, "computerUse": False,
        "mcpGateway": False, "gmail": False,
    }
    assert all(v is False for v in caps.values())


def test_ready_for_bridge_design_never_means_execution_ready():
    r = _readiness(probe=_probe_reachable(), policy=_policy_loaded())
    assert r["ready"] is True
    # capabilities still all false, and the standing warning is present
    assert all(v is False for v in r["capabilityUnlocks"].values())
    assert "Ready for bridge design does not mean ready for execution." in r["warnings"]


def test_standing_warnings_always_present():
    for probe, policy in [(None, _policy_missing()), (_probe_reachable(), _policy_loaded())]:
        r = _readiness(probe=probe, policy=policy)
        for w in [
            "This does not enable browser or computer-use.",
            "This does not enable OpenClaw execution.",
            "This does not enforce NemoClaw/OpenShell policy.",
            "This does not execute tools.",
        ]:
            assert w in r["warnings"]


# ── safety guard: a dependent falsely reporting enabled is caught ────────────────

def test_falsely_enabled_dependent_blocks_ready():
    r = _readiness(
        runtime=_runtime(url=True, browser_enabled=True),
        probe=_probe_reachable(), policy=_policy_loaded(),
    )
    # even with reachable probe + loaded policy, a falsely-enabled dependent prevents ready
    assert r["status"] != "ready_for_bridge_design"
    assert r["ready"] is False


def test_mode_policy_unavailable_blocks_ready():
    r = _readiness(probe=_probe_reachable(), policy=_policy_loaded(), modes=[])
    assert r["status"] != "ready_for_bridge_design"
    assert r["components"]["modePolicy"] == "unavailable"
    assert "Agent mode policy is unavailable." in r["blockers"]


# ── next steps reflect what still needs doing ────────────────────────────────────

def test_next_steps_when_nothing_configured():
    r = _readiness(runtime=_runtime(url=False), probe=None, policy=_policy_missing())
    joined = " ".join(r["nextSteps"])
    assert "NEMOCLAW_RUNTIME_URL" in joined
    assert "NEMOCLAW_POLICY_PATH" in joined


def test_next_steps_when_ready_points_at_bridge_design():
    r = _readiness(probe=_probe_reachable(), policy=_policy_loaded())
    assert any("bridge contract" in s for s in r["nextSteps"])


# ── never runs a fresh probe / network / process ─────────────────────────────────

def test_uses_cached_last_probe_never_a_fresh_one():
    """
    Guard: readiness reads the cached last probe (read_last_probe) and must never call
    the fresh, network-hitting probe_nemoclaw. Verified at the source level so the
    guarantee can't silently regress.
    """
    import inspect as _inspect
    src = _inspect.getsource(gr)
    assert "read_last_probe" in src
    assert "probe_nemoclaw" not in src


def test_default_probe_source_is_read_last_probe():
    """The default `read_probe` argument is exactly runtime_probe.read_last_probe."""
    import inspect as _inspect
    from app.runtime_probe import read_last_probe as real_read
    default = _inspect.signature(get_guardrail_readiness).parameters["read_probe"].default
    assert default is real_read


def test_no_subprocess_or_socket(monkeypatch):
    import socket
    import subprocess

    def _boom(*a, **k):
        raise AssertionError("guardrail readiness must not spawn a process / open a socket")

    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(socket, "socket", _boom)
    r = _readiness(probe=_probe_reachable(), policy=_policy_loaded())
    assert r["status"] == "ready_for_bridge_design"


def test_never_raises_on_bad_inputs():
    r = get_guardrail_readiness(
        list_runtime=lambda: None,
        read_probe=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        inspect_policy=lambda: {},
        list_agent_modes=lambda: [],
    )
    assert r["status"] == "error"
    assert all(v is False for v in r["capabilityUnlocks"].values())


def test_does_not_write_vault(tmp_path, monkeypatch):
    """Readiness writes nothing to the (temp) working area."""
    before = set(p.name for p in tmp_path.iterdir())
    monkeypatch.chdir(tmp_path)
    _readiness(probe=_probe_reachable(), policy=_policy_loaded())
    after = set(p.name for p in tmp_path.iterdir())
    assert before == after


# ── endpoint smoke (read-only) ───────────────────────────────────────────────────

def test_endpoint_returns_readiness(monkeypatch):
    from app.main import runtime_guardrail_readiness
    monkeypatch.delenv("NEMOCLAW_RUNTIME_URL", raising=False)
    monkeypatch.delenv("NEMOCLAW_POLICY_PATH", raising=False)
    res = runtime_guardrail_readiness()
    assert res.id == "nemoclaw_openshell_guardrail"
    assert res.status in ("not_ready", "partially_ready", "ready_for_bridge_design", "error")
    assert res.capabilityUnlocks.openclawBridge is False
    assert res.capabilityUnlocks.browserHarness is False
