"""
Guardrail Readiness v0 — read-only correlation of the runtime guardrail surfaces.

The PRD gates privileged actions behind a chain:

    OpenClaw → NemoClaw/OpenShell runtime → Brain UI permission gateway → approved tools

Runtime Status v0, the NemoClaw/OpenShell Health Probe v0, and Policy Inspection v0
each report ONE facet of that guardrail. This module correlates them (plus the agent
mode policy) into a single honest answer to: "is the guardrail ready for a bridge to be
*designed*?" — the last readiness view before an actual bridge CONTRACT is written.

It correlates ONLY. It does NOT:
  * enforce policy,
  * run a fresh health probe (it reads the cached LAST probe only — loading it is not
    a probe), make a network call, start OpenClaw / NemoClaw/OpenShell, or launch any
    runtime,
  * unlock browser / computer-use / MCP / OpenClaw / Gmail,
  * execute any tool, run shell / `brain`, read credentials, or write the vault.

Honesty rule (load-bearing):
  * `ready_for_bridge_design` / `ready: true` means only "ready for a bridge to be
    designed", NEVER "ready to execute". Copy makes this explicit everywhere.
  * `capabilityUnlocks.*` is False in EVERY state — readiness enables nothing.
"""

import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional

from app.runtime_status import list_runtime_status
from app.runtime_probe import read_last_probe
from app.runtime_policy import inspect_nemoclaw_policy
from app.agent_modes import list_modes

logger = logging.getLogger(__name__)

READINESS_ID = "nemoclaw_openshell_guardrail"

# Status vocabulary (explicit; mirrors the spec).
STATUS_NOT_READY = "not_ready"
STATUS_PARTIALLY_READY = "partially_ready"
STATUS_READY_FOR_BRIDGE_DESIGN = "ready_for_bridge_design"
STATUS_ERROR = "error"

# Component-state vocabulary (informational; describes each correlated input).
COMP_NOT_CONFIGURED = "not_configured"
COMP_NOT_RUN = "not_run"
COMP_AVAILABLE = "available"
COMP_UNAVAILABLE = "unavailable"

# Standing truths — always surfaced so readiness is never mistaken for capability.
_STANDING_WARNINGS = [
    "Ready for bridge design does not mean ready for execution.",
    "This does not enable browser or computer-use.",
    "This does not enable OpenClaw execution.",
    "This does not enforce NemoClaw/OpenShell policy.",
    "This does not execute tools.",
    "Browser and computer-use remain disabled until a separate bridge is implemented.",
]

_NOTES = (
    "Readiness is informational only. No capabilities are enabled by this endpoint."
)


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def _capability_unlocks() -> dict:
    """Every unlock is False in every state — readiness enables nothing."""
    return {
        "openclawBridge": False,
        "browserHarness": False,
        "computerUse": False,
        "mcpGateway": False,
        "gmail": False,
    }


def get_guardrail_readiness(
    list_runtime: Callable[[], list] = list_runtime_status,
    read_probe: Callable[[], Optional[dict]] = read_last_probe,
    inspect_policy: Callable[[], dict] = inspect_nemoclaw_policy,
    list_agent_modes: Callable[[], list] = list_modes,
    env: Optional[dict] = None,
) -> dict:
    """
    Correlate runtime status + last probe + policy inspection + mode policy into a
    single read-only readiness view. Never raises. Makes NO network call and runs NO
    fresh probe — `read_probe` reads the cached last probe only.

    The data-source callables are injectable so this stays pure and testable; the
    defaults read the existing cached/inspection data only.
    """
    try:
        return _build(list_runtime, read_probe, inspect_policy, list_agent_modes)
    except Exception as exc:  # pragma: no cover - defensive; must never raise
        logger.warning("Guardrail readiness correlation failed: %s", exc)
        return {
            "id": READINESS_ID,
            "status": STATUS_ERROR,
            "ready": False,
            "checkedAt": _now(),
            "summary": "Guardrail readiness could not be determined.",
            "components": {
                "runtimeStatus": COMP_NOT_CONFIGURED,
                "lastProbe": COMP_NOT_RUN,
                "policy": COMP_NOT_CONFIGURED,
                "modePolicy": COMP_UNAVAILABLE,
            },
            "blockers": ["Guardrail readiness inputs could not be read."],
            "warnings": list(_STANDING_WARNINGS),
            "nextSteps": [],
            "capabilityUnlocks": _capability_unlocks(),
            "notes": _NOTES,
        }


def _build(list_runtime, read_probe, inspect_policy, list_agent_modes) -> dict:
    # ── runtime status: locate the NemoClaw/OpenShell guardrail row ──────────────
    runtime_items = list_runtime() or []
    nemo = next((it for it in runtime_items if it.get("id") == "nemoclaw_openshell"), None)
    runtime_status_value = nemo["status"] if nemo else COMP_NOT_CONFIGURED
    url_configured = bool(nemo and nemo.get("configured", {}).get("runtimeUrl"))

    # Safety guard: readiness must never depend on a runtime that falsely reports
    # browser / computer-use as enabled. In v0 this is impossible, but we check anyway.
    runtime_falsely_enabled = any(
        it.get("id") in ("browser_harness", "computer_use")
        and (it.get("available") or it.get("enabled"))
        for it in runtime_items
    )

    # ── last probe: cached only (loading it is NOT a probe) ──────────────────────
    last = read_probe()
    if last is None:
        probe_component = COMP_NOT_RUN
        probe_reachable = False
    else:
        probe_component = str(last.get("status") or COMP_NOT_RUN)
        probe_reachable = bool(last.get("reachable")) and probe_component == "reachable"

    # ── policy inspection: read-only ─────────────────────────────────────────────
    policy = inspect_policy() or {}
    policy_component = str(policy.get("status") or COMP_NOT_CONFIGURED)
    policy_loaded = policy_component == "loaded" and bool(policy.get("valid"))
    policy_path_configured = bool(policy.get("pathConfigured"))
    policy_errored = policy_component == "error"

    # ── mode policy: present when the enforced modes list resolves ───────────────
    modes = list_agent_modes() or []
    mode_available = len(modes) > 0
    mode_component = COMP_AVAILABLE if mode_available else COMP_UNAVAILABLE

    # ── correlate ────────────────────────────────────────────────────────────────
    if probe_reachable and policy_loaded and mode_available and not runtime_falsely_enabled:
        status = STATUS_READY_FOR_BRIDGE_DESIGN
        ready = True
    elif probe_reachable or policy_loaded:
        status = STATUS_PARTIALLY_READY
        ready = False
    else:
        status = STATUS_NOT_READY
        ready = False

    # ── blockers ─────────────────────────────────────────────────────────────────
    blockers: List[str] = []
    if not probe_reachable:
        blockers.append("NemoClaw/OpenShell runtime is not reachable.")
    if not policy_loaded:
        blockers.append("No valid NemoClaw/OpenShell policy is loaded.")
    if not mode_available:
        blockers.append("Agent mode policy is unavailable.")
    if runtime_falsely_enabled:
        blockers.append(
            "A dependent runtime is reporting browser/computer-use as enabled without a bridge."
        )

    # ── next steps (only what actually still needs doing) ────────────────────────
    next_steps: List[str] = []
    if not url_configured:
        next_steps.append("Configure NEMOCLAW_RUNTIME_URL (and NEMOCLAW_ENABLED=true).")
    if not probe_reachable:
        next_steps.append("Run the explicit NemoClaw/OpenShell health probe.")
    if not policy_path_configured:
        next_steps.append("Configure NEMOCLAW_POLICY_PATH.")
    elif not policy_loaded:
        next_steps.append("Provide a valid NemoClaw/OpenShell policy file.")
    if status == STATUS_READY_FOR_BRIDGE_DESIGN:
        next_steps.append(
            "Design the NemoClaw/OpenShell bridge contract — no execution is enabled yet."
        )

    # ── summary copy (makes the ready-for-design vs ready-for-execution split explicit) ──
    if status == STATUS_READY_FOR_BRIDGE_DESIGN:
        summary = (
            "Runtime guardrail is ready for bridge design: NemoClaw/OpenShell is reachable "
            "(per the last probe) and a valid policy is loaded. This does NOT mean the system "
            "can execute tools — no bridge is implemented and no capability is unlocked."
        )
    elif status == STATUS_PARTIALLY_READY:
        have = "the runtime is reachable" if probe_reachable else "a valid policy is loaded"
        missing = "no valid policy is loaded" if probe_reachable else "the runtime is not reachable"
        summary = (
            f"Runtime guardrail is partially ready: {have}, but {missing}. It is not yet ready "
            "for bridge design, and nothing is enabled."
        )
    else:
        summary = (
            "Runtime guardrail is not ready. NemoClaw/OpenShell is not reachable and no valid "
            "policy is loaded. Nothing is enabled."
        )

    warnings = list(_STANDING_WARNINGS)
    if policy_errored:
        warnings.append("Policy inspection reported an error; treat policy state as unknown.")

    return {
        "id": READINESS_ID,
        "status": status,
        "ready": ready,
        "checkedAt": _now(),
        "summary": summary,
        "components": {
            "runtimeStatus": runtime_status_value,
            "lastProbe": probe_component,
            "policy": policy_component,
            "modePolicy": mode_component,
        },
        "blockers": blockers,
        "warnings": warnings,
        "nextSteps": next_steps,
        "capabilityUnlocks": _capability_unlocks(),
        "notes": _NOTES,
    }
