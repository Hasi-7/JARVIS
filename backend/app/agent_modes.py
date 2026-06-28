"""
Agent Mode Enforcement v0 — central, backend-enforced agent mode policy.

Agent modes are no longer purely frontend labels. This module is the single source
of truth for what the Local Agent surface may do in each mode:

  - whether structured tool requests may be EVALUATED (never executed) from a mode,
  - whether a "Review in Tool Connections" handoff may be offered from a mode,
  - whether a mode is available at all in this build.

The flow this protects:

    chat / manual tool request (+ mode)
      → backend resolves the mode and enforces policy
      → Locked / Observe / Computer-Use: tool requests are BLOCKED (not evaluated, not stored)
      → Draft / Assist / Research / Escalation: tool requests are EVALUATED ONLY
      → NOTHING executes from any mode

Hard guarantees (this module enforces policy; it NEVER executes anything):
  * No tool ever executes from any mode — evaluation only, always.
  * `computer_use` is recognized but unavailable/blocked (browser/computer-use stay off).
  * Unknown / missing / malformed modes fall back to the SAFEST mode (`locked`).
  * Where a rule could be ambiguous, the safer (more restrictive) choice is taken.
"""

from typing import List, Optional

# ── canonical modes ──────────────────────────────────────────────────────────────

LOCKED = "locked"
OBSERVE = "observe"
DRAFT = "draft"
ASSIST = "assist"
RESEARCH = "research"
ESCALATION = "escalation"
COMPUTER_USE = "computer_use"

# Unknown / missing modes resolve here — the safest mode.
DEFAULT_MODE = LOCKED

# Policy table. `evaluate` = may structured tool requests be EVALUATED (never run).
# `review` = may a Review-in-Tool-Connections handoff be offered. `available` =
# is the mode usable in this build at all.
#
#   locked       → evaluate=false, review=false, available=true
#   observe      → evaluate=false, review=false, available=true
#   draft        → evaluate=true,  review=false, available=true
#   assist       → evaluate=true,  review=true,  available=true
#   research     → evaluate=true,  review=false, available=true
#   escalation   → evaluate=true,  review=false, available=true
#   computer_use → evaluate=false, review=false, available=false (recognized, blocked)
_MODE_POLICY = {
    LOCKED: {
        "label": "Locked", "available": True, "evaluate": False, "review": False,
        "notes": "Agent tools disabled. Manual UI pages still work. No tool requests are accepted from chat.",
    },
    OBSERVE: {
        "label": "Observe", "available": True, "evaluate": False, "review": False,
        "notes": "Chat only. Structured tool requests are blocked.",
    },
    DRAFT: {
        "label": "Draft", "available": True, "evaluate": True, "review": False,
        "notes": "Tool requests may be evaluated, but nothing executes and no review handoff is offered.",
    },
    ASSIST: {
        "label": "Assist", "available": True, "evaluate": True, "review": True,
        "notes": "Safe-local requests may be reviewed in Tool Connections. Execution remains manual.",
    },
    RESEARCH: {
        "label": "Research", "available": True, "evaluate": True, "review": False,
        "notes": "Structured tool requests are evaluated only. Browser/computer-use remains blocked.",
    },
    ESCALATION: {
        "label": "Escalation", "available": True, "evaluate": True, "review": False,
        "notes": "Handoff/escalation discussion. Tool requests are evaluated only.",
    },
    COMPUTER_USE: {
        "label": "Computer-Use", "available": False, "evaluate": False, "review": False,
        "notes": "Not wired. Browser/computer-use remains disabled in this build.",
    },
}

# Listing order for the read-only modes endpoint.
_MODE_ORDER = [LOCKED, OBSERVE, DRAFT, ASSIST, RESEARCH, ESCALATION, COMPUTER_USE]

# Aliases map non-canonical / frontend ids → a canonical mode. Anything not found
# here or in the policy table normalizes to DEFAULT_MODE (safest).
_ALIASES = {
    "computer": COMPUTER_USE,
    # "Manual" means "you drive / agent off" — treat as locked (no tool requests).
    "manual": LOCKED,
}


# ── normalization ────────────────────────────────────────────────────────────────

def normalize_mode(mode: Optional[str]) -> str:
    """
    Resolve any incoming mode string to a canonical mode id, falling back to the
    SAFEST mode (`locked`) for missing / unknown / malformed input. Never raises.
    """
    if not isinstance(mode, str):
        return DEFAULT_MODE
    m = mode.strip().lower().replace(" ", "_").replace("-", "_")
    if m in _MODE_POLICY:
        return m
    if m in _ALIASES:
        return _ALIASES[m]
    return DEFAULT_MODE


def _policy(mode: Optional[str]) -> dict:
    return _MODE_POLICY[normalize_mode(mode)]


# ── policy helpers ───────────────────────────────────────────────────────────────

def is_mode_available(mode: Optional[str]) -> bool:
    """True if the (normalized) mode is usable in this build."""
    return bool(_policy(mode)["available"])


def can_evaluate_tool_requests(mode: Optional[str]) -> bool:
    """
    True if structured tool requests may be EVALUATED (never executed) in this mode.
    An unavailable mode can never evaluate (belt-and-suspenders with `available`).
    """
    p = _policy(mode)
    return bool(p["available"] and p["evaluate"])


def can_offer_review_handoff(mode: Optional[str]) -> bool:
    """
    True if a Review-in-Tool-Connections handoff may be offered in this mode.
    Only Assist offers it in v0. Execution still happens manually on Tool Connections.
    """
    p = _policy(mode)
    return bool(p["available"] and p["review"])


def mode_label(mode: Optional[str]) -> str:
    """Human-readable label for the (normalized) mode."""
    return _policy(mode)["label"]


def blocked_message(mode: Optional[str]) -> str:
    """A clear, user-facing reason a tool request was blocked in this mode."""
    canonical = normalize_mode(mode)
    p = _MODE_POLICY[canonical]
    if not p["available"]:
        return f"{p['label']} mode is not available in this build. Tool requests are blocked."
    return f"Tool requests are blocked in {p['label']} mode."


def list_modes() -> List[dict]:
    """Read-only list of all modes with availability + permissions, for the UI."""
    out: List[dict] = []
    for mid in _MODE_ORDER:
        p = _MODE_POLICY[mid]
        out.append({
            "id": mid,
            "label": p["label"],
            "available": bool(p["available"]),
            "canEvaluateToolRequests": bool(p["available"] and p["evaluate"]),
            "canOfferReviewHandoff": bool(p["available"] and p["review"]),
            "notes": p["notes"],
        })
    return out
