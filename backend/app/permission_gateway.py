"""
Permission Gateway (v0) — deny-by-default tool-request classification.

This is the backend "app-specific permission gateway" layer the PRD requires
(§4.3, §9.2, §32) — the part that decides whether a requested tool action is
allowed, needs approval, is unavailable, or is disabled. v0 implements ONLY the
classification/shape:

    manual simulated tool request
      → backend classifies it
      → backend returns denied / requires_approval / not_wired / disabled
      → UI displays result
      → NOTHING is executed

Hard guarantees — this module:
  * executes NO tool,
  * makes NO external calls (MCP, Gmail, browser, computer-use, Google, GitHub, Drive),
  * launches NO OpenClaw / NemoClaw / OpenShell runtime,
  * runs NO shell and never invokes `brain`,
  * writes NO vault files and reads NO credentials.

It only reads a static policy table and reshapes a request into a decision. Args
are treated as untrusted: never executed, summarized for display only, with
secret-bearing keys redacted and long values truncated.

Future wiring (a real runtime + approval queue + execution path) replaces the
constant `EXECUTION_ENABLED = False` and the per-tool execution adapters — not
this classification logic.
"""

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Privileged-execution kill-switch. Stays False: no privileged/external tool ever
# executes. Safe-local execution is opt-in PER TOOL via _EXECUTABLE_TOOLS below —
# it does NOT flip this flag.
EXECUTION_ENABLED = False

# Backend-local audit log of Permission Gateway evaluations + executions (NOT the
# vault). Vault ops/tool-logs/ writes remain future work.
TOOL_LOGS_DIR:    Path = Path(__file__).parent.parent / "data" / "tool-logs"
EVALUATIONS_FILE: Path = TOOL_LOGS_DIR / "evaluations.json"

_MAX_STORED_LOGS = 500     # retention cap (latest N kept)
_DEFAULT_LOG_LIMIT = 50
_MAX_LOG_LIMIT = 200
_MAX_REASON_LEN = 300
_MAX_REQUESTED_BY_LEN = 80
_MAX_OUTPUT_PREVIEW = 2000  # stdout/stderr preview truncation in execution logs

_log_lock = threading.Lock()

_log_lock = threading.Lock()

# ── policy table ────────────────────────────────────────────────────────────────
# riskLevel: low | medium | high | disabled
# status:    not_wired | available | disabled
# Keys are camelCase to match the API response models directly.
#
# Conventions for v0:
#   * MCP / Gmail / calendar tools           → not_wired (gateway/runtime absent)
#   * browser / computer-use tools           → disabled  (runtime not wired; off by default)
#   * explicitly dangerous mutations         → disabled
#   * safe brain / vault-read tools          → available (implemented elsewhere)
#                                              but executionEnabled stays False here
_POLICIES: List[dict] = [
    # Obsidian MCP
    {"tool": "obsidian.search", "category": "obsidian", "riskLevel": "low",    "status": "not_wired", "requiresApproval": False, "notes": "Obsidian MCP not wired. Vault search currently uses the filesystem adapter."},
    {"tool": "obsidian.read",   "category": "obsidian", "riskLevel": "low",    "status": "not_wired", "requiresApproval": False, "notes": "Obsidian MCP not wired. Vault reads currently use the filesystem adapter."},
    {"tool": "obsidian.write",  "category": "obsidian", "riskLevel": "medium", "status": "not_wired", "requiresApproval": True,  "notes": "Obsidian MCP not wired. Real vault writes use backup-before-write elsewhere, not this gateway."},

    # Gmail MCP
    {"tool": "gmail.search",    "category": "gmail",    "riskLevel": "medium", "status": "not_wired", "requiresApproval": True,  "notes": "Gmail MCP is not wired yet. Email search/read/intake is planned through the backend gateway."},
    {"tool": "gmail.read",      "category": "gmail",    "riskLevel": "medium", "status": "not_wired", "requiresApproval": True,  "notes": "Gmail MCP is not wired yet."},
    {"tool": "gmail.draft",     "category": "gmail",    "riskLevel": "medium", "status": "not_wired", "requiresApproval": True,  "notes": "Gmail MCP is not wired yet. Draft creation is a planned medium-risk action."},
    {"tool": "gmail.send",      "category": "gmail",    "riskLevel": "disabled","status": "disabled",  "requiresApproval": True,  "notes": "Sending email is disabled by default. Gmail mutations remain disabled."},

    # Google Calendar
    {"tool": "calendar.read",         "category": "calendar", "riskLevel": "low",     "status": "not_wired", "requiresApproval": False, "notes": "Google Calendar API is not wired. The vault stays the source of truth for candidates."},
    {"tool": "calendar.create_event", "category": "calendar", "riskLevel": "disabled","status": "disabled",  "requiresApproval": True,  "notes": "Creating real calendar events is disabled by default (high risk)."},

    # Browser harness
    {"tool": "browser.search",    "category": "browser", "riskLevel": "low",  "status": "disabled", "requiresApproval": True, "notes": "Browser harness is disabled until NemoClaw/OpenShell runtime safety is wired."},
    {"tool": "browser.read_page", "category": "browser", "riskLevel": "low",  "status": "disabled", "requiresApproval": True, "notes": "Browser harness is disabled until NemoClaw/OpenShell runtime safety is wired."},

    # Computer use
    {"tool": "computer.click", "category": "computer", "riskLevel": "high", "status": "disabled", "requiresApproval": True, "notes": "Computer-use is disabled until NemoClaw/OpenShell runtime safety is wired."},
    {"tool": "computer.type",  "category": "computer", "riskLevel": "high", "status": "disabled", "requiresApproval": True, "notes": "Computer-use is disabled until NemoClaw/OpenShell runtime safety is wired."},

    # Brain CLI — low-risk, read-only status commands are executable through the
    # gateway (via the existing safe brain wrapper). Everything else stays off.
    {"tool": "brain.status",     "category": "brain", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Safe allowlisted read-only brain command. Executable through the gateway via the safe brain wrapper."},
    {"tool": "brain.raw_status", "category": "brain", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Safe allowlisted read-only brain command (raw-status). Executable through the gateway via the safe brain wrapper."},
    {"tool": "brain.vault_path", "category": "brain", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Safe allowlisted read-only brain command (vault-path). Executable through the gateway via the safe brain wrapper."},
    {"tool": "brain.today",      "category": "brain", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Allowlisted brain command, implemented elsewhere. Not executable through the gateway in this build."},
    {"tool": "brain.sync_raw",   "category": "brain", "riskLevel": "medium", "status": "available", "requiresApproval": True,  "notes": "Allowlisted brain command (moves raw files). Implemented elsewhere; not executable through the gateway in this build."},

    # Filesystem / vault
    {"tool": "filesystem.read_vault",  "category": "filesystem", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Read-only vault access, implemented elsewhere. Permission Gateway v0 does not execute it."},
    {"tool": "filesystem.write_vault", "category": "filesystem", "riskLevel": "medium", "status": "available", "requiresApproval": True,  "notes": "Real vault writes use backup-before-write elsewhere. Permission Gateway v0 does not execute it."},
]

_POLICY_BY_TOOL: Dict[str, dict] = {p["tool"]: p for p in _POLICIES}

# ── executable tools (safe-local execution v0) ──────────────────────────────────
# ONLY these low-risk, read-only brain status tools may execute through the gateway,
# and ONLY via the existing safe brain wrapper (no new subprocess path, no shell,
# no arbitrary command names). Everything else is classification-only.
_BRAIN_TOOL_COMMANDS: Dict[str, str] = {
    "brain.status":     "status",
    "brain.raw_status": "raw-status",
    "brain.vault_path": "vault-path",
}
_EXECUTABLE_TOOLS = frozenset(_BRAIN_TOOL_COMMANDS)


def is_executable(tool: str) -> bool:
    """True only for the allowlisted safe-local tools enabled this build."""
    return tool in _EXECUTABLE_TOOLS


def brain_command_for(tool: str) -> Optional[str]:
    """Map an executable tool id to its safe brain subcommand (or None)."""
    return _BRAIN_TOOL_COMMANDS.get(tool)


# ── argument sanitization ───────────────────────────────────────────────────────

# If any of these substrings appears in an arg key (case-insensitive), the value
# is redacted so secrets are never echoed back or logged.
_SECRET_KEY_SUBSTRINGS = (
    "password",
    "token",
    "secret",
    "key",
    "credential",
    "authorization",
    "cookie",
)

_REDACTED = "[redacted]"
_MAX_VALUE_LEN = 60       # per-value truncation
_MAX_SUMMARY_LEN = 240    # overall summary cap
_MAX_PAIRS = 12           # cap number of key/value pairs shown


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(sub in k for sub in _SECRET_KEY_SUBSTRINGS)


def _truncate(value: str, limit: int = _MAX_VALUE_LEN) -> str:
    value = value.replace("\n", " ").replace("\r", " ").strip()
    if len(value) > limit:
        return value[:limit] + "…"
    return value


def sanitize_args_summary(args: Optional[dict]) -> str:
    """
    Build a short, display-safe summary of request args. Args are never executed
    and never trusted. Secret-bearing keys are redacted; long values truncated.
    """
    if args is None:
        return "(no args)"
    if not isinstance(args, dict):
        # Defensive — request validation should already enforce an object.
        return _truncate(str(args))
    if not args:
        return "(no args)"

    parts: List[str] = []
    for i, (k, v) in enumerate(args.items()):
        if i >= _MAX_PAIRS:
            parts.append(f"… (+{len(args) - _MAX_PAIRS} more)")
            break
        key = str(k)
        if _is_secret_key(key):
            parts.append(f"{key}: {_REDACTED}")
            continue
        if isinstance(v, (dict, list)):
            shown = _truncate(f"<{type(v).__name__}:{len(v)}>")
        else:
            shown = _truncate(str(v))
        parts.append(f"{key}: {shown}")

    summary = ", ".join(parts)
    if len(summary) > _MAX_SUMMARY_LEN:
        summary = summary[:_MAX_SUMMARY_LEN] + "…"
    return summary


# ── unknown-tool danger heuristic ───────────────────────────────────────────────
# Unknown tools are denied by default. Unknown names that look destructive/mutating
# are reported as `disabled` (off by default) rather than merely denied.
_DANGEROUS_SUBSTRINGS = (
    "send", "delete", "archive", "label", "create_event", "create-event",
    "type", "click", "submit", "shell", "run", "exec", "rm", "drop",
    "truncate", "format", "install", "purchase", "pay", "transfer",
    "remove", "move", "write", "post", "put", "patch", "upload", "download",
)


def _looks_dangerous(tool: str) -> bool:
    name = tool.lower()
    tail = name.split(".", 1)[1] if "." in name else name
    return any(sub in tail for sub in _DANGEROUS_SUBSTRINGS)


# ── public API ──────────────────────────────────────────────────────────────────

def list_policies() -> List[dict]:
    """Return read-only copies of the policy table. executionEnabled reflects the
    global v0 kill-switch (False) for every entry — the gateway executes nothing."""
    out: List[dict] = []
    for p in _POLICIES:
        item = dict(p)
        # Only the allowlisted safe-local tools are executable; all others False.
        item["executionEnabled"] = p["tool"] in _EXECUTABLE_TOOLS
        out.append(item)
    return out


def evaluate_tool_request(
    tool: str,
    args: Optional[dict] = None,
    reason: Optional[str] = None,
    requested_by: Optional[str] = None,
) -> dict:
    """
    Classify a tool request. Deny-by-default. This function NEVER executes anything
    — it only classifies. (Execution happens in the /execute endpoint, and only for
    is_executable() tools, via the safe brain wrapper.)

    Returns a dict with camelCase keys matching ToolRequestEvaluationResponse.
    Raises ValueError on an invalid request shape (empty tool name).
    """
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("`tool` must be a non-empty string.")
    tool = tool.strip()

    sanitized = sanitize_args_summary(args)
    policy = _POLICY_BY_TOOL.get(tool)

    if policy is None:
        # Unknown tool → denied by default; destructive-looking names → disabled.
        if _looks_dangerous(tool):
            decision, risk = "disabled", "disabled"
            msg = f"'{tool}' is not a known tool and looks destructive. Disabled by default."
        else:
            decision, risk = "denied", "high"
            msg = f"'{tool}' is not a known tool. Denied by default."
        return {
            "allowed": False,
            "decision": decision,
            "riskLevel": risk,
            "tool": tool,
            "requiresApproval": True,
            "executionEnabled": False,
            "reason": msg,
            "policyNotes": "Unknown tool — not in the permission policy table.",
            "sanitizedArgsSummary": sanitized,
            "wouldLog": True,
        }

    status = policy["status"]
    risk = policy["riskLevel"]
    requires_approval = policy["requiresApproval"]
    executable = tool in _EXECUTABLE_TOOLS

    if status == "disabled":
        decision = "disabled"
        allowed = False
        msg = f"'{tool}' is disabled by default and cannot run."
    elif status == "not_wired":
        decision = "not_wired"
        allowed = False
        msg = f"'{tool}' is not wired yet. No connection or runtime exists for it."
    elif executable:
        # Allowlisted safe-local tool — permitted to execute through the gateway.
        decision = "allowed"
        allowed = True
        msg = f"'{tool}' is a low-risk local tool and may execute through the gateway."
    else:  # available but not executable in this build
        decision = "requires_approval"
        allowed = False
        if requires_approval:
            msg = f"'{tool}' would require approval. It is not executable through the gateway in this build."
        else:
            msg = (
                f"'{tool}' is a safe tool implemented elsewhere, but it is not executable "
                f"through the gateway in this build."
            )

    return {
        "allowed": allowed,
        "decision": decision,
        "riskLevel": risk,
        "tool": tool,
        "requiresApproval": requires_approval,
        "executionEnabled": executable,   # True only for allowlisted safe-local tools
        "reason": msg,
        "policyNotes": policy["notes"],
        "sanitizedArgsSummary": sanitized,
        "wouldLog": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool Log v0 — backend-local audit of Permission Gateway evaluations
# ══════════════════════════════════════════════════════════════════════════════
# Records ONLY classification evaluations (no tool ever runs). Stored in backend
# app-data, never the vault. Only the already-sanitized args summary is stored —
# raw args and secret values are never persisted.

def _ensure_log_dir() -> None:
    TOOL_LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _read_log_entries() -> List[dict]:
    _ensure_log_dir()
    if not EVALUATIONS_FILE.exists():
        return []
    try:
        data = json.loads(EVALUATIONS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Corrupted tool-log file, starting fresh: %s", exc)
        return []


def _write_log_entries(entries: List[dict]) -> None:
    _ensure_log_dir()
    EVALUATIONS_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _truncate_plain(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    v = str(value).replace("\n", " ").replace("\r", " ").strip()
    if not v:
        return None
    return v[:limit] + "…" if len(v) > limit else v


def _truncate_output(value: Optional[str]) -> str:
    """Truncate a command's stdout/stderr to a stored preview (keeps newlines)."""
    if not value:
        return ""
    v = str(value)
    return v[:_MAX_OUTPUT_PREVIEW] + "\n…[truncated]" if len(v) > _MAX_OUTPUT_PREVIEW else v


def log_evaluation(
    evaluation: dict,
    requested_by: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    """
    Append one redacted audit entry for a Permission Gateway evaluation.

    `evaluation` is the dict returned by evaluate_tool_request — it already holds
    the sanitized (redacted/truncated) args summary; raw args are never passed in
    or stored. Returns the stored entry (including its generated id).
    Caps stored entries to the latest _MAX_STORED_LOGS.
    """
    entry = {
        "id":                   str(uuid.uuid4()),
        "timestamp":            datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
        "source":               "gateway_eval",
        "tool":                 evaluation.get("tool", ""),
        "requestedBy":          _truncate_plain(requested_by, _MAX_REQUESTED_BY_LEN),
        "reason":               _truncate_plain(reason, _MAX_REASON_LEN),
        "decision":             evaluation.get("decision", ""),
        "riskLevel":            evaluation.get("riskLevel", ""),
        "allowed":              bool(evaluation.get("allowed", False)),
        "requiresApproval":     bool(evaluation.get("requiresApproval", False)),
        "executionEnabled":     bool(evaluation.get("executionEnabled", False)),
        "sanitizedArgsSummary": evaluation.get("sanitizedArgsSummary", ""),
        "policyNotes":          evaluation.get("policyNotes"),
        "result":               "evaluated_only",   # classification only — nothing executed
        "exitCode":             None,
        "stdoutPreview":        None,
        "stderrPreview":        None,
        "durationMs":           None,
    }
    _append_log_entry(entry)
    logger.info(
        "Permission evaluation logged: id=%s tool=%s decision=%s (evaluated_only)",
        entry["id"], entry["tool"], entry["decision"],
    )
    return entry


def log_execution(
    evaluation: dict,
    brain_result,
    requested_by: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    """
    Append one audit entry for an executed safe-local tool. `brain_result` is the
    BrainRunResponse from the existing safe brain wrapper. stdout/stderr are stored
    only as truncated previews; raw args are never stored (only the sanitized
    summary carried from the evaluation).
    """
    ok = bool(getattr(brain_result, "ok", False))
    entry = {
        "id":                   str(uuid.uuid4()),
        "timestamp":            datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
        "source":               "gateway_execution",
        "tool":                 evaluation.get("tool", ""),
        "requestedBy":          _truncate_plain(requested_by, _MAX_REQUESTED_BY_LEN),
        "reason":               _truncate_plain(reason, _MAX_REASON_LEN),
        "decision":             "executed",
        "riskLevel":            evaluation.get("riskLevel", ""),
        "allowed":              True,
        "requiresApproval":     bool(evaluation.get("requiresApproval", False)),
        "executionEnabled":     True,
        "sanitizedArgsSummary": evaluation.get("sanitizedArgsSummary", ""),
        "policyNotes":          evaluation.get("policyNotes"),
        "result":               "success" if ok else "failure",
        "exitCode":             getattr(brain_result, "exitCode", None),
        "stdoutPreview":        _truncate_output(getattr(brain_result, "stdout", "")),
        "stderrPreview":        _truncate_output(getattr(brain_result, "stderr", "")),
        "durationMs":           getattr(brain_result, "durationMs", None),
    }
    _append_log_entry(entry)
    logger.info(
        "Permission execution logged: id=%s tool=%s result=%s exit=%s",
        entry["id"], entry["tool"], entry["result"], entry["exitCode"],
    )
    return entry


def _append_log_entry(entry: dict) -> None:
    with _log_lock:
        entries = _read_log_entries()
        entries.append(entry)
        if len(entries) > _MAX_STORED_LOGS:
            entries = entries[-_MAX_STORED_LOGS:]
        _write_log_entries(entries)


def list_logs(
    limit: int = _DEFAULT_LOG_LIMIT,
    tool: Optional[str] = None,
    decision: Optional[str] = None,
) -> List[dict]:
    """
    Return evaluation log entries, newest first. Read-only.
    limit is clamped to [1, _MAX_LOG_LIMIT]; optional exact-match tool/decision filters.
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_LOG_LIMIT
    limit = max(1, min(limit, _MAX_LOG_LIMIT))

    with _log_lock:
        entries = _read_log_entries()

    tool = (tool or "").strip() or None
    decision = (decision or "").strip() or None
    if tool:
        entries = [e for e in entries if e.get("tool") == tool]
    if decision:
        entries = [e for e in entries if e.get("decision") == decision]

    # Stored append-order is oldest→newest; newest first for display.
    entries = list(reversed(entries))
    return entries[:limit]
