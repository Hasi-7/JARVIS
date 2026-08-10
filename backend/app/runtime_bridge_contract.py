"""
NemoClaw/OpenShell Bridge Contract v0 — dry-run validator for FUTURE bridge requests.

The PRD gates privileged actions behind a chain:

    OpenClaw → NemoClaw/OpenShell runtime → Brain UI permission gateway → approved tools

Runtime Status, the Health Probe, Policy Inspection, and Guardrail Readiness each report
whether that guardrail *could* exist. This module defines the **request/response
contract** for the future bridge and a **dry-run validator** that answers, for a
proposed bridge request: would it be blocked, would it require approval, and is its shape
structurally acceptable for a future bridge to be *designed*?

It validates ONLY. It does NOT:
  * call NemoClaw/OpenShell or OpenClaw, or start any runtime,
  * execute browser / computer-use / MCP / Gmail / Calendar / vault / brain actions,
  * run a fresh health probe (readiness reads the cached last probe only),
  * run shell / `brain`, read credentials, write the vault, or unlock any capability.

The dry-run pipeline (all read-only, no execution):

    proposed bridge request
      → schema validation
      → mode policy check          (agent_modes)
      → guardrail readiness check  (guardrail_readiness — cached, no probe)
      → permission-gateway dry-run decision (permission_gateway.evaluate_tool_request)
      → sanitized audit log entry  (source: runtime_bridge_validation)
      → clear blocked / validated dry-run response

Honesty rule (load-bearing):
  * `allowed` and `executionEnabled` are False in EVERY response — a valid bridge
    request is never an approval to run it, and nothing executes here.
  * `runtimeBridgeImplemented` is always False — the bridge is not implemented.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, List, Optional

from app.agent_modes import (
    normalize_mode,
    is_mode_available,
    can_evaluate_tool_requests,
    can_offer_review_handoff,
    blocked_message as mode_blocked_message,
)
from app.guardrail_readiness import get_guardrail_readiness
from app.permission_gateway import (
    evaluate_tool_request,
    sanitize_args_summary,
    log_bridge_validation,
)

logger = logging.getLogger(__name__)

# ── status vocabulary ────────────────────────────────────────────────────────────
STATUS_BLOCKED_BY_MODE = "blocked_by_mode"
STATUS_BLOCKED = "blocked"
STATUS_VALIDATED = "validated"   # shape acceptable for future bridge design (still no execution)
STATUS_ERROR = "error"

# ── action-kind registry ─────────────────────────────────────────────────────────
# Each recognized future action kind maps to a conservative risk, a category, and a
# representative existing Permission Gateway policy tool used for the DRY-RUN decision.
# Risk levels follow the spec's conservative mapping (never the gateway's own risk).
UNKNOWN_KIND = "unknown"

_ACTION_KINDS = {
    "browser.open":        {"risk": "medium", "category": "browser",  "gatewayTool": "browser.read_page"},
    "browser.search":      {"risk": "medium", "category": "browser",  "gatewayTool": "browser.search"},
    "browser.read_page":   {"risk": "medium", "category": "browser",  "gatewayTool": "browser.read_page"},
    "computer.click":      {"risk": "high",   "category": "computer", "gatewayTool": "computer.click"},
    "computer.type":       {"risk": "high",   "category": "computer", "gatewayTool": "computer.type"},
    "computer.screenshot": {"risk": "high",   "category": "computer", "gatewayTool": "computer.click"},
    "mcp.call":            {"risk": "medium", "category": "mcp",      "gatewayTool": "obsidian.search"},
    "gmail.search":        {"risk": "medium", "category": "gmail",    "gatewayTool": "gmail.search"},
    "gmail.read":          {"risk": "medium", "category": "gmail",    "gatewayTool": "gmail.read"},
    "calendar.read":       {"risk": "medium", "category": "calendar", "gatewayTool": "calendar.read"},
    "vault.read":          {"risk": "low",    "category": "vault",    "gatewayTool": "filesystem.read_vault"},
    "vault.write":         {"risk": "high",   "category": "vault",    "gatewayTool": "filesystem.write_vault"},
    "brain.status":        {"risk": "low",    "category": "brain",    "gatewayTool": "brain.status"},
    "brain.raw_status":    {"risk": "low",    "category": "brain",    "gatewayTool": "brain.raw_status"},
    "brain.vault_path":    {"risk": "low",    "category": "brain",    "gatewayTool": "brain.vault_path"},
    UNKNOWN_KIND:          {"risk": "high",   "category": "unknown",  "gatewayTool": None},
}

# Safe-local action kinds — low-risk, read-only. Even these NEVER execute from this
# endpoint (manual safe-local execution remains only in Tool Connections).
_SAFE_LOCAL_KINDS = frozenset({"brain.status", "brain.raw_status", "brain.vault_path", "vault.read"})

# Human-readable category labels for messages/blockers.
_CATEGORY_LABEL = {
    "browser":  "Browser",
    "computer": "Computer-use",
    "mcp":      "MCP",
    "gmail":    "Gmail",
    "calendar": "Google Calendar",
    "vault":    "Vault",
    "brain":    "Brain",
    "unknown":  "Unknown",
}

READY_STATUS = "ready_for_bridge_design"


def list_action_kinds() -> List[str]:
    """Recognized future action kinds (for the UI dropdown). Read-only."""
    return list(_ACTION_KINDS.keys())


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def _normalize_kind(kind: Optional[str]) -> str:
    """Resolve an incoming action kind to a recognized kind, else `unknown`."""
    if not isinstance(kind, str):
        return UNKNOWN_KIND
    k = kind.strip()
    return k if k in _ACTION_KINDS else UNKNOWN_KIND


def validate_bridge_request(
    *,
    source: Optional[str] = "openclaw",
    mode: Optional[str] = None,
    action_kind: Optional[str] = None,
    target: Optional[str] = None,
    args: Optional[dict] = None,
    reason: Optional[str] = None,
    conversation_id: Optional[str] = None,
    readiness_fn: Callable[[], dict] = get_guardrail_readiness,
    log_fn: Callable[..., dict] = log_bridge_validation,
) -> dict:
    """
    Dry-run validate a proposed future bridge request. Never raises. Executes nothing,
    calls no runtime, and unlocks nothing. `readiness_fn`/`log_fn` are injectable so
    tests can verify no probe/side effects.
    """
    try:
        return _validate(
            source=source, mode=mode, action_kind=action_kind, target=target,
            args=args, reason=reason, conversation_id=conversation_id,
            readiness_fn=readiness_fn, log_fn=log_fn,
        )
    except Exception as exc:  # pragma: no cover - defensive; must never raise
        logger.warning("Bridge validation failed: %s", exc)
        return {
            "id": str(uuid.uuid4()),
            "status": STATUS_ERROR,
            "allowed": False,
            "requiresApproval": False,
            "executionEnabled": False,
            "mode": normalize_mode(mode),
            "source": _short(source) or "openclaw",
            "actionKind": UNKNOWN_KIND,
            "riskLevel": "high",
            "decision": "error",
            "message": "Bridge validation could not be completed. Nothing was executed.",
            "checks": {
                "schemaValid": False,
                "modeAllowsEvaluation": False,
                "guardrailReadyForBridgeDesign": False,
                "runtimeBridgeImplemented": False,
                "permissionGatewayDecision": "n/a",
            },
            "blockers": ["Bridge validation error.", "This endpoint does not execute actions."],
            "warnings": ["Dry-run validation only.", "No capabilities are unlocked."],
            "logId": None,
            "createdAt": _now(),
        }


def _short(v: Optional[str], limit: int = 80) -> Optional[str]:
    if not isinstance(v, str):
        return None
    s = v.strip().replace("\n", " ").replace("\r", " ")
    if not s:
        return None
    return s[:limit] + "…" if len(s) > limit else s


def _validate(*, source, mode, action_kind, target, args, reason, conversation_id,
              readiness_fn, log_fn) -> dict:
    src = _short(source) or "openclaw"

    # ── 1. schema + action-kind normalization ───────────────────────────────────
    raw_kind = action_kind.strip() if isinstance(action_kind, str) else ""
    kind = _normalize_kind(raw_kind)
    schema_valid = bool(raw_kind)   # a blank/missing kind is a malformed request shape
    spec = _ACTION_KINDS[kind]
    category = spec["category"]
    risk = spec["risk"]
    gateway_tool = spec["gatewayTool"]

    # Args are UNTRUSTED — summarized for display/logging only, never executed/stored raw.
    sanitized = sanitize_args_summary(args if isinstance(args, dict) else None)

    # ── 2. mode policy ───────────────────────────────────────────────────────────
    mode_norm = normalize_mode(mode)
    mode_available = is_mode_available(mode_norm)
    mode_can_eval = can_evaluate_tool_requests(mode_norm)
    mode_allows_eval = bool(mode_available and mode_can_eval)

    # ── 3. guardrail readiness (cached; NEVER triggers a probe) ──────────────────
    readiness = readiness_fn() or {}
    guardrail_ready = readiness.get("status") == READY_STATUS

    # ── 4. permission-gateway dry-run decision (classification only) ─────────────
    if mode_allows_eval and gateway_tool:
        gw = evaluate_tool_request(gateway_tool, args if isinstance(args, dict) else None,
                                   reason=reason, requested_by=src)
        gateway_decision = gw["decision"]
        requires_approval = bool(gw["requiresApproval"])
    else:
        gateway_decision = "n/a"
        requires_approval = kind != UNKNOWN_KIND  # unknown is denied; others would need approval

    # ── 5. compose outcome ───────────────────────────────────────────────────────
    cat_label = _CATEGORY_LABEL.get(category, "This")

    if not mode_allows_eval:
        status = STATUS_BLOCKED_BY_MODE
        decision = "blocked_by_mode"
        message = f"{mode_blocked_message(mode_norm)} Bridge validation is dry-run only and executes nothing."
    elif not schema_valid or kind == UNKNOWN_KIND:
        status = STATUS_BLOCKED
        decision = "denied"
        message = (
            "Unrecognized action kind — denied by default (conservative high risk). "
            "Bridge validation is dry-run only and executes nothing."
        )
    elif kind in _SAFE_LOCAL_KINDS:
        if guardrail_ready:
            status = STATUS_VALIDATED
            decision = "schema_acceptable_for_bridge_design"
            message = (
                "Request shape is acceptable for future bridge design. It is NOT approved to run — "
                "bridge validation is dry-run only and executes nothing."
            )
        else:
            status = STATUS_BLOCKED
            decision = "runtime_guardrail_not_ready"
            message = (
                "Runtime guardrail is not ready for bridge design. Bridge validation is dry-run only "
                "and executes nothing."
            )
    else:
        # Recognized privileged action (browser/computer/mcp/gmail/calendar/vault.write).
        status = STATUS_BLOCKED
        decision = "runtime_bridge_not_implemented"
        message = f"Runtime bridge validation is dry-run only. {cat_label} actions are not wired."

    # ── 6. blockers ──────────────────────────────────────────────────────────────
    blockers: List[str] = []
    if not mode_allows_eval:
        blockers.append(mode_blocked_message(mode_norm))
    blockers.append("Runtime bridge is not implemented.")
    if category == "browser":
        blockers.append("Browser harness is disabled.")
    elif category == "computer":
        blockers.append("Computer-use is disabled.")
    elif category == "mcp":
        blockers.append("MCP gateway is not wired.")
    elif category == "gmail":
        blockers.append("Gmail is not wired.")
    elif category == "calendar":
        blockers.append("Google Calendar is not wired.")
    elif kind == "vault.write":
        blockers.append("Vault writes are not performed by the bridge validator.")
    if kind == UNKNOWN_KIND or not schema_valid:
        blockers.append("Unknown action kind is denied by default.")
    if not guardrail_ready:
        blockers.append("Runtime guardrail is not ready for bridge design.")
    blockers.append("This endpoint does not execute actions.")

    # ── 7. warnings ──────────────────────────────────────────────────────────────
    warnings: List[str] = ["Dry-run validation only.", "No capabilities are unlocked."]
    if mode_allows_eval and kind in _SAFE_LOCAL_KINDS and can_offer_review_handoff(mode_norm):
        warnings.append(
            "In Assist mode, a safe-local action may later be routed to manual review in "
            "Tool Connections — but never executed by this endpoint."
        )

    # ── 8. sanitized audit log (never executes; secrets already redacted) ────────
    log_id: Optional[str] = None
    try:
        entry = log_fn(
            action_kind=kind,
            decision=decision,
            risk_level=risk,
            requires_approval=requires_approval,
            sanitized_args_summary=sanitized,
            source=src,
            reason=reason,
            message=message,
        )
        log_id = entry.get("id")
    except Exception as exc:  # pragma: no cover - logging is best-effort, never fatal
        logger.warning("Could not log bridge validation: %s", exc)

    return {
        "id": str(uuid.uuid4()),
        "status": status,
        "allowed": False,            # never an approval to run
        "requiresApproval": requires_approval,
        "executionEnabled": False,   # nothing executes here
        "mode": mode_norm,
        "source": src,
        "actionKind": kind,
        "riskLevel": risk,
        "decision": decision,
        "message": message,
        "checks": {
            "schemaValid": schema_valid,
            "modeAllowsEvaluation": mode_allows_eval,
            "guardrailReadyForBridgeDesign": guardrail_ready,
            "runtimeBridgeImplemented": False,
            "permissionGatewayDecision": gateway_decision,
        },
        "blockers": blockers,
        "warnings": warnings,
        "logId": log_id,
        "createdAt": _now(),
    }
