"""
OpenClaw / NemoClaw Runtime Status (v0) — read-only readiness surface.

The PRD requires OpenClaw as the resident local assistant and NemoClaw/OpenShell as
the required runtime guardrail for privileged actions:

    OpenClaw → NemoClaw/OpenShell runtime → Brain UI permission gateway → approved tools

This module reports, HONESTLY and READ-ONLY, what is configured / missing / disabled /
blocked for the five runtimes — so the UI can show readiness without pretending
anything is wired.

For v0 it implements ONLY: configuration/readiness detection → honest status. It does
NOT launch a runtime, make a network/health call, read credentials, run shell/`brain`,
write the vault, or execute any tool.

Honesty rule (load-bearing): NO runtime is reported `available`. v0 performs no
verified health check (and must not), so even fully-configured runtimes stay
`unavailable` (configured but unverified), and dependents (browser / computer-use)
stay blocked while NemoClaw/OpenShell is unavailable.

Config is read from environment variables only (no network, no credential reads):
    OPENCLAW_ENABLED, OPENCLAW_BASE_URL,
    NEMOCLAW_ENABLED, NEMOCLAW_RUNTIME_URL, NEMOCLAW_POLICY_PATH,
    ENABLE_BROWSER_HARNESS, ENABLE_COMPUTER_USE, ENABLE_MCP_GATEWAY
These config knobs do not exist elsewhere in the app yet; when unset, the runtime is
reported `not_configured`.
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── status vocabulary (mirrors app/tools.py) ────────────────────────────────────
STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_DISABLED = "disabled"
STATUS_PLANNED = "planned"
STATUS_ERROR = "error"

# v0 performs NO health check / network call, so no runtime can be verified as
# reachable. Until a genuine verified check exists, `available` stays False for every
# runtime and dependents (browser/computer-use) stay blocked. Flipping this is a
# FUTURE sprint that adds a real (sandboxed) check — not this one.
RUNTIME_VERIFICATION_WIRED = False

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _flag(env: dict, name: str) -> Optional[bool]:
    """Return True/False for an env enable flag, or None when unset/unrecognized."""
    raw = env.get(name)
    if raw is None:
        return None
    v = str(raw).strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    return None


def _present(env: dict, name: str) -> bool:
    """True if an env value is present and non-empty (value itself is never stored)."""
    return bool(str(env.get(name, "")).strip())


def _nemoclaw_available(nemo_enabled: bool, nemo_url_present: bool) -> bool:
    """
    Whether the NemoClaw/OpenShell guardrail can be relied on for dependents.

    Requires config AND a verified runtime check. The verified check is intentionally
    NOT wired in this build, so this is always False — we never claim availability
    without verification, and we never make the network call needed to verify it.
    """
    return bool(RUNTIME_VERIFICATION_WIRED and nemo_enabled and nemo_url_present)


def list_runtime_status(env: Optional[dict] = None) -> List[dict]:
    """
    Return the read-only runtime readiness inventory (fresh dicts; safe to mutate).

    Pure: reads environment variables only. No network call, no process launch, no
    shell/`brain`, no credential read, no vault write, no tool execution.
    """
    env = os.environ if env is None else env

    oc_flag = _flag(env, "OPENCLAW_ENABLED")
    oc_url = _present(env, "OPENCLAW_BASE_URL")
    nc_flag = _flag(env, "NEMOCLAW_ENABLED")
    nc_url = _present(env, "NEMOCLAW_RUNTIME_URL")
    nc_pol = _present(env, "NEMOCLAW_POLICY_PATH")
    br_flag = _flag(env, "ENABLE_BROWSER_HARNESS")
    cu_flag = _flag(env, "ENABLE_COMPUTER_USE")
    mcp_flag = _flag(env, "ENABLE_MCP_GATEWAY")

    # The hard dependency gate for browser / computer-use (always False in v0).
    nemo_available = _nemoclaw_available(nc_flag is True, nc_url)

    items: List[dict] = []

    # ── OpenClaw ────────────────────────────────────────────────────────────────
    if oc_flag is False:
        oc_status = STATUS_DISABLED
    elif oc_flag is True and oc_url:
        oc_status = STATUS_UNAVAILABLE          # configured but not verified
    else:
        oc_status = STATUS_NOT_CONFIGURED
    oc_blocks: List[str] = []
    if oc_status == STATUS_DISABLED:
        oc_blocks.append("OpenClaw explicitly disabled (OPENCLAW_ENABLED)")
    elif oc_status == STATUS_NOT_CONFIGURED:
        oc_blocks.append("OpenClaw bridge not wired in this build")
    else:
        oc_blocks.append("OpenClaw runtime not verified (no health check in this build)")
    if not nemo_available:
        oc_blocks.append("NemoClaw/OpenShell unavailable — privileged OpenClaw actions blocked")
    items.append({
        "id": "openclaw",
        "name": "OpenClaw",
        "status": oc_status,
        "available": False,
        "enabled": False,
        "requiredFor": ["Resident local agent", "Agent tool requests (later)"],
        "dependsOn": ["nemoclaw_openshell"],
        "blocks": oc_blocks,
        "configured": {"enabledFlag": oc_flag is True, "baseUrl": oc_url},
        "notes": (
            "OpenClaw bridge is planned but not wired in this build. The Local Agent is "
            "local chat with evaluate-only tool requests; privileged OpenClaw actions "
            "require NemoClaw/OpenShell."
        ),
    })

    # ── NemoClaw / OpenShell ────────────────────────────────────────────────────
    if nc_flag is False:
        nc_status = STATUS_DISABLED
    elif nc_flag is True and nc_url:
        nc_status = STATUS_UNAVAILABLE          # configured but not verified
    else:
        nc_status = STATUS_NOT_CONFIGURED
    nc_blocks: List[str] = []
    if nc_status == STATUS_DISABLED:
        nc_blocks.append("NemoClaw/OpenShell explicitly disabled (NEMOCLAW_ENABLED)")
    elif nc_status == STATUS_NOT_CONFIGURED:
        nc_blocks.append("NemoClaw/OpenShell runtime not configured")
    else:
        nc_blocks.append("NemoClaw/OpenShell not verified (no health check in this build)")
    items.append({
        "id": "nemoclaw_openshell",
        "name": "NemoClaw / OpenShell",
        "status": nc_status,
        "available": nemo_available,            # False in v0
        "enabled": False,
        "requiredFor": [
            "Browser harness", "Computer-use",
            "OpenClaw privileged actions", "MCP privileged actions",
        ],
        "dependsOn": [],
        "blocks": nc_blocks,
        "configured": {
            "enabledFlag": nc_flag is True,
            "runtimeUrl": nc_url,
            "policyPath": nc_pol,
        },
        "notes": (
            "NemoClaw/OpenShell is the required runtime guardrail for privileged agent "
            "actions. It is not wired in this build; no sandbox/policy runtime is reachable."
        ),
    })

    # ── Browser harness (depends on NemoClaw/OpenShell) ─────────────────────────
    br_blocks = ["NemoClaw/OpenShell runtime unavailable"]
    if br_flag is not True:
        br_blocks.append("Browser harness not enabled (ENABLE_BROWSER_HARNESS)")
    items.append({
        "id": "browser_harness",
        "name": "Browser Harness",
        # Blocked while the guardrail is unavailable — disabled regardless of its flag.
        "status": STATUS_DISABLED,
        "available": False,
        "enabled": False,
        "requiredFor": ["Time-boxed research", "Source capture (later)"],
        "dependsOn": ["nemoclaw_openshell"],
        "blocks": br_blocks,
        "configured": {"enabledFlag": br_flag is True},
        "notes": (
            "Browser harness stays blocked until NemoClaw/OpenShell is available. No "
            "browser is opened, navigated, or read in this build."
        ),
    })

    # ── Computer-use (depends on NemoClaw/OpenShell) ────────────────────────────
    cu_blocks = ["NemoClaw/OpenShell runtime unavailable"]
    if cu_flag is not True:
        cu_blocks.append("Computer-use not enabled (ENABLE_COMPUTER_USE)")
    items.append({
        "id": "computer_use",
        "name": "Computer Use",
        "status": STATUS_DISABLED,
        "available": False,
        "enabled": False,
        "requiredFor": ["Supervised UI operation (later)"],
        "dependsOn": ["nemoclaw_openshell"],
        "blocks": cu_blocks,
        "configured": {"enabledFlag": cu_flag is True},
        "notes": (
            "Computer-use stays blocked until NemoClaw/OpenShell is available. No screen "
            "is observed and no click/type/copy occurs in this build."
        ),
    })

    # ── MCP gateway ─────────────────────────────────────────────────────────────
    if mcp_flag is False:
        mcp_status = STATUS_DISABLED
    else:
        mcp_status = STATUS_NOT_CONFIGURED
    mcp_blocks = ["Runtime guardrail (NemoClaw/OpenShell) unavailable for privileged actions"]
    if mcp_flag is not True:
        mcp_blocks.append("MCP gateway not enabled (ENABLE_MCP_GATEWAY)")
    items.append({
        "id": "mcp_gateway",
        "name": "MCP Gateway",
        "status": mcp_status,
        "available": False,
        "enabled": False,
        "requiredFor": ["Obsidian MCP", "Gmail MCP", "Calendar / Drive tools (later)"],
        "dependsOn": ["nemoclaw_openshell"],
        "blocks": mcp_blocks,
        "configured": {"enabledFlag": mcp_flag is True},
        "notes": (
            "MCP gateway is not wired. Privileged MCP actions require the Permission "
            "Gateway plus the runtime guardrail; nothing is connected or executed."
        ),
    })

    return items
