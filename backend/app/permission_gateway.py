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
  * reads NO credentials,
  * writes to the vault ONLY the append-only tool-log mirror below (PRD §32).

It only reads a static policy table and reshapes a request into a decision. Args
are treated as untrusted: never executed, summarized for display only, with
secret-bearing keys redacted and long values truncated.

Future wiring (a real runtime + approval queue + execution path) replaces the
constant `EXECUTION_ENABLED = False` and the per-tool execution adapters — not
this classification logic.
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ToolLogError(RuntimeError):
    pass

# Backward-compatible default value. The real privileged kill switch is read from
# the environment by privileged_execution_enabled() on every privileged transition.
EXECUTION_ENABLED = False
PRIVILEGED_EXECUTION_ENV = "BRAIN_UI_PRIVILEGED_EXECUTION_ENABLED"

# Backend-local audit log of Permission Gateway evaluations + executions. This is
# the queryable source of truth; a human-readable copy is mirrored into the vault
# at ops/tool-logs/ (see _mirror_entry_to_vault).
TOOL_LOGS_DIR:    Path = Path(__file__).parent.parent / "data" / "tool-logs"
EVALUATIONS_FILE: Path = TOOL_LOGS_DIR / "evaluations.json"

_MAX_STORED_LOGS = 500     # retention cap (latest N kept)
_MAX_TRANSITION_LOGS = 500 # recent terminal/unreferenced transitions
_DEFAULT_LOG_LIMIT = 50
_MAX_LOG_LIMIT = 200
_MAX_REASON_LEN = 300
_MAX_REQUESTED_BY_LEN = 80
_MAX_OUTPUT_PREVIEW = 2000  # stdout/stderr preview truncation in execution logs

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
    {"tool": "gmail.search",    "category": "gmail",    "riskLevel": "medium", "status": "available", "requiresApproval": False, "notes": "Read-only Gmail thread search via the local OAuth client (gmail.readonly). Runs through the Gmail read endpoint, not this gateway's execute path. Results are untrusted content."},
    {"tool": "gmail.read",      "category": "gmail",    "riskLevel": "medium", "status": "available", "requiresApproval": False, "notes": "Read-only Gmail message fetch via the local OAuth client (gmail.readonly). Body and headers are untrusted content. No mutation method is reachable."},
    {"tool": "gmail.draft",     "category": "gmail",    "riskLevel": "medium", "status": "not_wired", "requiresApproval": True,  "notes": "Gmail MCP is not wired yet. Draft creation is a planned medium-risk action."},
    {"tool": "gmail.send",      "category": "gmail",    "riskLevel": "disabled","status": "disabled",  "requiresApproval": True,  "notes": "Sending email is disabled by default. Gmail mutations remain disabled."},

    # Google Calendar
    {"tool": "calendar.read",         "category": "calendar", "riskLevel": "low",     "status": "available", "requiresApproval": False, "notes": "Read-only Google Calendar event list via the local OAuth client (calendar.readonly). Used to reconcile vault candidates against real events. Creates/moves/deletes nothing."},
    {"tool": "calendar.create_event", "category": "calendar", "riskLevel": "high", "status": "available", "requiresApproval": True, "notes": "Creates ONE real Google Calendar event through the Assist-mode approval queue. Requires the calendar.events scope, the operator token, and the privileged kill switch. Never updates, moves, or deletes an event, and never notifies attendees."},

    # Browser harness
    {"tool": "browser.search",    "category": "browser", "riskLevel": "medium", "status": "available", "requiresApproval": True, "notes": "Queries ONE fixed privacy-respecting provider from INSIDE the OpenShell sandbox, through the Assist-mode approval queue. Results are untrusted and are only openable if their host is in the session allowlist."},
    {"tool": "browser.read_page", "category": "browser", "riskLevel": "medium", "status": "available", "requiresApproval": True, "notes": "Reads one page from INSIDE the OpenShell sandbox, through the Assist-mode approval queue. Refuses if the sandbox policy fails open (best_effort Landlock). Page content is untrusted."},

    # Computer use
    {"tool": "computer.click", "category": "computer", "riskLevel": "high", "status": "disabled", "requiresApproval": True, "notes": "Computer-use is disabled until NemoClaw/OpenShell runtime safety is wired."},
    {"tool": "computer.type",  "category": "computer", "riskLevel": "high", "status": "disabled", "requiresApproval": True, "notes": "Computer-use is disabled until NemoClaw/OpenShell runtime safety is wired."},

    # Brain CLI — low-risk, read-only status commands are executable through the
    # gateway (via the existing safe brain wrapper). Everything else stays off.
    {"tool": "brain.status",     "category": "brain", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Safe allowlisted read-only brain command. Executable through the gateway via the safe brain wrapper."},
    {"tool": "brain.raw_status", "category": "brain", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Safe allowlisted read-only brain command (raw-status). Executable through the gateway via the safe brain wrapper."},
    {"tool": "brain.vault_path", "category": "brain", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Safe allowlisted read-only brain command (vault-path). Executable through the gateway via the safe brain wrapper."},
    {"tool": "brain.today",      "category": "brain", "riskLevel": "low",    "status": "available", "requiresApproval": True,  "notes": "Allowlisted local brain command. Runs only through the Assist-mode approval queue when privileged execution is enabled."},
    {"tool": "brain.sync_raw",   "category": "brain", "riskLevel": "medium", "status": "available", "requiresApproval": True,  "notes": "Allowlisted brain command (moves raw files). Runs only through the Assist-mode approval queue when privileged execution is enabled."},

    # External read-only integrations (D3)
    {"tool": "github.read", "category": "external", "riskLevel": "low", "status": "available", "requiresApproval": False, "notes": "Read-only GitHub repo/commit/issue reads via a local token. GET only; no write, merge, or comment path exists. Content is untrusted."},
    {"tool": "drive.read",  "category": "external", "riskLevel": "medium", "status": "available", "requiresApproval": False, "notes": "Read-only Google Drive listing and text export (drive.readonly). No create/update/delete/share path exists. Document content is untrusted."},

    # Filesystem / vault
    {"tool": "filesystem.read_vault",  "category": "filesystem", "riskLevel": "low",    "status": "available", "requiresApproval": False, "notes": "Read-only vault access, implemented elsewhere. Permission Gateway v0 does not execute it."},
    {"tool": "filesystem.write_vault", "category": "filesystem", "riskLevel": "medium", "status": "available", "requiresApproval": True,  "notes": "Real vault writes use backup-before-write elsewhere. Permission Gateway v0 does not execute it."},
    {"tool": "vault.create_task",       "category": "filesystem", "riskLevel": "medium", "status": "available", "requiresApproval": True,  "notes": "Creates one task through the existing validated, backup-before-write vault adapter. Assist approval required."},
    {"tool": "calendar.create_candidate", "category": "calendar", "riskLevel": "medium", "status": "available", "requiresApproval": True, "notes": "Creates one vault calendar candidate only; never writes Google Calendar. Assist approval required."},
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

# Deliberately separate from _EXECUTABLE_TOOLS. These tools can only be reached
# through tool_approvals' state machine and narrow dispatcher.
_APPROVAL_REQUIRED_TOOLS = frozenset({
    "brain.today",
    "brain.sync_raw",
    "vault.create_task",
    "calendar.create_candidate",
    # D2: the ONLY external write. Approval-gated exactly like the local tools,
    # and additionally refused unless the calendar.events scope was granted.
    "calendar.create_event",
    # C1b: page reads and searches execute inside the OpenShell sandbox, so they
    # are privileged.
    "browser.read_page",
    "browser.search",
})


# External READ-ONLY tools. These never run through /permissions/execute (that path
# is brain-only); they run through their own dedicated read endpoints, which must
# classify + log here first. They mutate nothing, so they need no approval queue —
# but they are only `allowed` once their credentials actually exist on disk.
_EXTERNAL_READ_TOOLS = frozenset({
    "gmail.search",
    "gmail.read",
    "calendar.read",
    "drive.read",
})

# GitHub uses its own token rather than the Google credential, so it has a
# separate readiness check.
_GITHUB_READ_TOOLS = frozenset({"github.read"})


def _github_ready() -> bool:
    try:
        from app.github import github_configured
        return github_configured()
    except Exception:
        return False


github_read_ready_fn: "Callable[[], bool]" = _github_ready


def _google_reads_ready() -> bool:
    """Configuration-only readiness check; never raises, reads no token contents.

    Gmail and Calendar reads share one OAuth client and token file, so a single
    check covers both.
    """
    try:
        from app.gmail import gmail_configured
        return gmail_configured()
    except Exception:
        return False


# Rebound by tests so the gateway never touches the real filesystem/credentials.
external_read_ready_fn: "Callable[[], bool]" = _google_reads_ready


def is_external_read_tool(tool: str) -> bool:
    """True for allowlisted read-only external lookups (Gmail reads)."""
    return tool in _EXTERNAL_READ_TOOLS


def is_executable(tool: str) -> bool:
    """True only for the allowlisted safe-local tools enabled this build."""
    return tool in _EXECUTABLE_TOOLS


def brain_command_for(tool: str) -> Optional[str]:
    """Map an executable tool id to its safe brain subcommand (or None)."""
    return _BRAIN_TOOL_COMMANDS.get(tool)


def privileged_execution_enabled(env=None) -> bool:
    """Return the operator-controlled privileged execution kill-switch state."""
    source = os.environ if env is None else env
    value = str(source.get(PRIVILEGED_EXECUTION_ENV, "false")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def is_approval_required_tool(tool: str) -> bool:
    """True only for tools owned by the gated approval dispatcher."""
    return tool in _APPROVAL_REQUIRED_TOOLS


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
    "send", "delete", "trash", "archive", "label", "create_event", "create-event",
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
    external_ready: Optional[bool] = None
    for p in _POLICIES:
        item = dict(p)
        # This field means immediately executable through /permissions/execute.
        # Approval-only tools remain false even when their separate kill switch is on.
        item["executionEnabled"] = p["tool"] in _EXECUTABLE_TOOLS
        if p["tool"] in _GITHUB_READ_TOOLS and not github_read_ready_fn():
            item["status"] = "not_wired"
            item["notes"] = (
                "Read-only GitHub support is implemented but no token is configured. "
                "Set BRAIN_UI_GITHUB_TOKEN to enable it."
            )
        if p["tool"] in _EXTERNAL_READ_TOOLS:
            # Report `available` only when the credentials actually exist — the
            # repo's standing honesty rule against claiming unwired capability.
            if external_ready is None:
                external_ready = external_read_ready_fn()
            if not external_ready:
                item["status"] = "not_wired"
                item["notes"] = (
                    "Read-only Gmail access is implemented but not authorized on this "
                    "machine. Run the local Google authorize command to enable it."
                )
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
    elif tool in _GITHUB_READ_TOOLS:
        if github_read_ready_fn():
            decision, allowed = "allowed", True
            msg = f"'{tool}' is a read-only GitHub lookup and may run through its read endpoint."
        else:
            decision, allowed = "not_wired", False
            msg = f"'{tool}' requires a local GitHub token. Set BRAIN_UI_GITHUB_TOKEN, then retry."
    elif tool in _EXTERNAL_READ_TOOLS:
        # Read-only external lookup. Allowed once credentials exist, but never
        # executable through /permissions/execute — it runs on its own read
        # endpoint, which classifies and logs here first.
        if external_read_ready_fn():
            decision = "allowed"
            allowed = True
            msg = (
                f"'{tool}' is a read-only external lookup and may run through its "
                f"dedicated read endpoint. It cannot mutate anything."
            )
        else:
            decision = "not_wired"
            allowed = False
            msg = (
                f"'{tool}' requires local Google authorization first. Run the "
                f"authorize command, then retry."
            )
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
        "executionEnabled": executable,
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
        if not isinstance(data, list):
            raise ToolLogError("Tool-log root must be a list.")
        return data
    except Exception as exc:
        logger.error("Could not read tool-log history safely: %s", exc)
        raise ToolLogError("Tool-log history is unreadable; refusing to overwrite it.") from exc


def _write_log_entries(entries: List[dict]) -> None:
    _ensure_log_dir()
    tmp = EVALUATIONS_FILE.with_name(f"{EVALUATIONS_FILE.name}.{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(entries, indent=2, ensure_ascii=False))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, EVALUATIONS_FILE)


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
    request_id: Optional[str] = None,
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
        "approvalId":           None,
        "requestId":            request_id,
        "approvedBy":           None,
        "approvedAt":           None,
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


def log_approved_execution(
    *,
    evaluation: dict,
    ok: bool,
    result: Optional[dict] = None,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
    requested_by: Optional[str] = None,
    reason: Optional[str] = None,
    approval_id: Optional[str] = None,
    request_id: Optional[str] = None,
    approved_by: Optional[str] = None,
    approved_at: Optional[str] = None,
) -> dict:
    """Audit one approval-dispatch execution without storing canonical arguments."""
    exit_code = result.get("exitCode") if isinstance(result, dict) else None
    entry = {
        "id":                   str(uuid.uuid4()),
        "timestamp":            datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
        "source":               "gateway_execution",
        "tool":                 evaluation.get("tool", ""),
        "requestedBy":          _truncate_plain(requested_by, _MAX_REQUESTED_BY_LEN),
        "reason":               _truncate_plain(reason, _MAX_REASON_LEN),
        "decision":             "executed" if ok else "failed",
        "riskLevel":            evaluation.get("riskLevel", ""),
        "allowed":              bool(ok),
        "requiresApproval":     True,
        "executionEnabled":     True,
        "sanitizedArgsSummary": evaluation.get("sanitizedArgsSummary", ""),
        "policyNotes":          evaluation.get("policyNotes"),
        "result":               "success" if ok else "failure",
        "exitCode":             exit_code,
        # Approval-backed execution logs are metadata-only. Raw/canonical tool
        # results and brain output never enter this audit path.
        "stdoutPreview":        None,
        "stderrPreview":        None,
        "durationMs":           duration_ms,
        "approvalId":           approval_id,
        "requestId":            request_id,
        "approvedBy":           _truncate_plain(approved_by, _MAX_REQUESTED_BY_LEN),
        "approvedAt":           approved_at,
    }
    _append_log_entry(entry)
    logger.info(
        "Approved tool execution logged: id=%s tool=%s result=%s",
        entry["id"], entry["tool"], entry["result"],
    )
    return entry


def log_approval_transition(record: dict, transition: str) -> dict:
    """Audit an approved/rejected transition using display-safe request fields."""
    if transition not in {"approved", "rejected"}:
        raise ValueError("Unsupported approval transition.")
    entry = {
        "id":                   str(uuid.uuid4()),
        "timestamp":            datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
        "source":               "approval_transition",
        "tool":                 record.get("tool", ""),
        "requestedBy":          _truncate_plain(record.get("requestedBy"), _MAX_REQUESTED_BY_LEN),
        "reason":               _truncate_plain(record.get("reason"), _MAX_REASON_LEN),
        "decision":             transition,
        "riskLevel":            record.get("riskLevel", ""),
        "allowed":              transition == "approved",
        "requiresApproval":     True,
        "executionEnabled":     False,
        "sanitizedArgsSummary": record.get("argsSummary", ""),
        "policyNotes":          "Operator-authorized approval state transition.",
        "result":               transition,
        "exitCode":             None,
        "stdoutPreview":        None,
        "stderrPreview":        None,
        "durationMs":           None,
        "approvalId":           record.get("id"),
        "requestId":            record.get("requestId"),
        "approvedBy":           _truncate_plain(record.get("approvedBy"), _MAX_REQUESTED_BY_LEN),
        "approvedAt":           record.get("approvedAt"),
    }
    _append_log_entry(entry)
    logger.info(
        "Approval transition logged: id=%s approval=%s transition=%s",
        entry["id"], entry["approvalId"], transition,
    )
    return entry


def log_bridge_validation(
    *,
    action_kind: str,
    decision: str,
    risk_level: str,
    requires_approval: bool,
    sanitized_args_summary: str,
    source: Optional[str] = None,
    reason: Optional[str] = None,
    message: Optional[str] = None,
) -> dict:
    """
    Append one redacted audit entry for a runtime-bridge DRY-RUN validation.

    Nothing is executed by bridge validation — this only records that a proposed
    future bridge request was validated. `sanitized_args_summary` must already be the
    redacted/truncated summary (raw args and secret values are never passed in or
    stored). Returns the stored entry (including its generated id).
    """
    entry = {
        "id":                   str(uuid.uuid4()),
        "timestamp":            datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
        "source":               "runtime_bridge_validation",
        "tool":                 action_kind,
        "requestedBy":          _truncate_plain(source, _MAX_REQUESTED_BY_LEN),
        "reason":               _truncate_plain(reason, _MAX_REASON_LEN),
        "decision":             decision,
        "riskLevel":            risk_level,
        "allowed":              False,   # bridge validation never approves execution
        "requiresApproval":     bool(requires_approval),
        "executionEnabled":     False,   # bridge validation never executes
        "sanitizedArgsSummary": sanitized_args_summary,
        "policyNotes":          _truncate_plain(message, _MAX_REASON_LEN),
        "result":               "validated_only",   # dry-run — nothing executed
        "exitCode":             None,
        "stdoutPreview":        None,
        "stderrPreview":        None,
        "durationMs":           None,
    }
    _append_log_entry(entry)
    logger.info(
        "Runtime bridge validation logged: id=%s kind=%s decision=%s (validated_only)",
        entry["id"], entry["tool"], entry["decision"],
    )
    return entry


def _append_log_entry(entry: dict) -> None:
    # Resolve protected IDs before taking the log lock. Approval code may call
    # logging while holding its process RLock; this ordering avoids log->approval
    # lock inversion while the helper's RLock permits same-thread nesting.
    from app.tool_approvals import protected_live_transition_log_ids
    protected_transition_ids = protected_live_transition_log_ids()

    with _log_lock:
        entries = _read_log_entries()
        entries.append(entry)
        # Preserve evidence referenced by approved/executing records, then retain
        # only the newest capped terminal/unreferenced transition history.
        transition_indexes = [
            index for index, item in enumerate(entries)
            if item.get("source") == "approval_transition"
            and item.get("id") not in protected_transition_ids
        ]
        transition_excess = len(transition_indexes) - _MAX_TRANSITION_LOGS
        remove = set(transition_indexes[:max(0, transition_excess)])

        ordinary_indexes = [
            index for index, item in enumerate(entries)
            if item.get("source") != "approval_transition"
        ]
        excess = len(ordinary_indexes) - _MAX_STORED_LOGS
        if excess > 0:
            remove.update(ordinary_indexes[:excess])
        if remove:
            entries = [item for index, item in enumerate(entries) if index not in remove]
        _write_log_entries(entries)

    # PRD §32 wants a durable, human-readable log in the vault so the record stays
    # readable from Obsidian alone. The JSON above remains the queryable source;
    # this is a mirror, and it must NEVER fail the action it is recording.
    _mirror_entry_to_vault(entry)


def get_log_entry_internal(log_id: str) -> Optional[dict]:
    """Internal exact-id lookup used to validate durable transition evidence."""
    with _log_lock:
        for entry in _read_log_entries():
            if entry.get("id") == log_id:
                return dict(entry)
    return None


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


# ══════════════════════════════════════════════════════════════════════════════
# Vault tool-log mirror (PRD §32) — durable, human-readable, best-effort
# ══════════════════════════════════════════════════════════════════════════════
# The JSON log above is the queryable source of truth. This mirror exists so the
# record survives outside the app and stays readable in Obsidian on its own, which
# is one of the PRD's stated principles ("no critical data trapped in a
# proprietary app database"). It is deliberately best-effort: a mirror failure is
# logged and swallowed, because losing the audit copy must never break, or appear
# to break, the action being audited.

VAULT_TOOL_LOG_DIR = ("ops", "tool-logs")
VAULT_LOG_MIRROR_ENV = "BRAIN_UI_VAULT_TOOL_LOG"

_MIRROR_HEADER = (
    "| Time | Agent/Model | Tool | Args summary | Risk | Approval req. | "
    "Approval result | Affected | Result |"
)
_MIRROR_SEPARATOR = "|---|---|---|---|---|---|---|---|---|"


def vault_log_mirror_enabled(env=None) -> bool:
    """Mirror is on by default; set the env var to a falsey value to disable."""
    source = os.environ if env is None else env
    return str(source.get(VAULT_LOG_MIRROR_ENV, "true")).strip().lower() not in {
        "0", "false", "no", "off",
    }


def _mirror_cell(value) -> str:
    """Render one Markdown table cell. Pipes and newlines would break the table."""
    text = "" if value is None else str(value)
    text = text.replace("|", r"\|").replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    return _truncate_plain(text, 200) or "—"


def format_mirror_row(entry: dict) -> str:
    """One PRD §32 table row for a log entry."""
    approval_result = entry.get("result") or ""
    if entry.get("approvedBy"):
        approval_result = f"{approval_result} by {entry.get('approvedBy')}"

    affected = entry.get("affectedPath") or entry.get("approvalId") or entry.get("requestId")
    exit_code = entry.get("exitCode")
    if entry.get("source") == "gateway_eval":
        outcome = "evaluated"
    elif exit_code is None:
        outcome = "success" if entry.get("allowed") else "n/a"
    else:
        outcome = "success" if exit_code == 0 else f"failure (exit {exit_code})"

    cells = [
        entry.get("timestamp"),
        entry.get("requestedBy"),
        entry.get("tool"),
        entry.get("sanitizedArgsSummary"),
        entry.get("riskLevel"),
        "yes" if entry.get("requiresApproval") else "no",
        approval_result,
        affected,
        outcome,
    ]
    return "| " + " | ".join(_mirror_cell(c) for c in cells) + " |"


def _mirror_entry_to_vault(entry: dict, vault_path: Optional[str] = None) -> Optional[str]:
    """Append one row to ops/tool-logs/<date>-tool-log.md. Never raises."""
    try:
        if not vault_log_mirror_enabled():
            return None

        root = vault_path
        if root is None:
            from app.config import get_config
            root = get_config().vault_path
        if not (root or "").strip():
            return None

        from app.vault import _safe_subpath

        timestamp = str(entry.get("timestamp") or "")
        date = timestamp[:10] or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        target = _safe_subpath(Path(root), *VAULT_TOOL_LOG_DIR, f"{date}-tool-log.md")
        if target is None:
            return None       # traversal rejected by the shared helper

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            # Append-only: never rewrite prior rows, so there is nothing to back up
            # and no way for this mirror to destroy existing evidence.
            with target.open("a", encoding="utf-8") as handle:
                handle.write(format_mirror_row(entry) + "\n")
        else:
            target.write_text(
                f"# Tool Log — {date}\n\n"
                f"Actions evaluated or executed by Brain UI. Written append-only; "
                f"the queryable source is backend tool-log JSON.\n\n"
                f"{_MIRROR_HEADER}\n{_MIRROR_SEPARATOR}\n"
                f"{format_mirror_row(entry)}\n",
                encoding="utf-8",
            )
        return str(target)
    except Exception as exc:  # pragma: no cover - mirror must never break the action
        logger.warning("Vault tool-log mirror failed (non-fatal): %s", exc)
        return None
