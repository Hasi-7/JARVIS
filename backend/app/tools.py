"""
Tool / MCP Connections inventory (v0).

A thin, READ-ONLY status/config readiness surface. It returns a static inventory
of the planned tool systems the PRD describes (§13, §31, §32, §33) so the UI can
honestly show what exists, what is configured, what is disabled, what is planned,
and what each system's current risk level and allowed/blocked actions are.

Honesty guarantees — this module:
  * makes NO external calls (no Gmail, MCP, browser, computer-use, Google APIs,
    GitHub, Drive),
  * runs NO shell commands and never invokes `brain`,
  * reads NO credentials,
  * launches NO OpenClaw / NemoClaw / OpenShell runtime,
  * executes NO tools and performs NO writes.

Entries are static EXCEPT where a real backend capability now exists. Gmail
read-only (B1) is the first such entry: it reports `available` only when local
OAuth credentials are actually present, and its mutations stay blocked forever.
Every other privileged system remains `not_configured`, `planned`, or `disabled`
per the PRD permission model.

Future wiring (real MCP/browser gateways) should follow the same rule — a system
may report `available` only after a genuine check.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


def _computer_use_ready() -> bool:
    """Kill-switch check only. Reads no screen and starts no session."""
    try:
        from app.computer_use import computer_use_enabled
        return computer_use_enabled()
    except Exception:
        return False


def _gmail_reads_ready() -> bool:
    """Configuration-only check. Reads no token contents and makes no API call."""
    try:
        from app.gmail import gmail_configured
        return gmail_configured()
    except Exception:
        return False

# ── category ids (display names are mapped in the frontend) ─────────────────────
#   runtime   → Agent Runtime
#   mcp       → MCP
#   browser   → Browser / Computer Use
#   external  → External Services
#   developer → Developer Tools

# A static, read-only inventory. Keys are camelCase to match the API response
# models directly (mirrors app/proposals.py). lastCheckedAt / lastError stay None
# because no real check runs in this build.
_TOOL_SYSTEMS: List[dict] = [
    {
        "id": "obsidian-mcp",
        "name": "Obsidian MCP",
        "category": "mcp",
        "status": "not_configured",
        "enabled": False,
        "riskLevel": "medium",
        "capabilities": ["search_notes", "read_note", "write_note_planned"],
        "allowedNow": ["manual_filesystem_fallback"],
        "blockedNow": ["mcp_read", "mcp_write", "delete_note", "move_note"],
        "requires": ["MCP server config", "backend gateway", "approval rules"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "Obsidian MCP is not connected. Current vault workflows use the "
            "filesystem adapter and backup-before-write protections."
        ),
    },
    {
        "id": "gmail-mcp",
        "name": "Gmail (read-only)",
        "category": "external",
        "status": "available" if _gmail_reads_ready() else "not_configured",
        "enabled": _gmail_reads_ready(),
        "riskLevel": "medium",
        "capabilities": ["search_threads", "read_message", "import_to_email_intake_draft"],
        "allowedNow": ["search", "read"] if _gmail_reads_ready() else [],
        "blockedNow": ["draft", "send", "delete", "trash", "archive", "modify_labels"],
        "requires": ["Local Google OAuth (gmail.readonly)", "Permission Gateway classification + tool log"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "Read-only Gmail via local OAuth (gmail.readonly). Search and message "
            "reads are classified and logged by the Permission Gateway, and feed "
            "Email Intake drafts (no vault write). Message bodies are untrusted "
            "content. Send/delete/trash/archive/label are permanently disabled and "
            "no code path for them exists."
            if _gmail_reads_ready() else
            "Gmail read-only support is implemented but not authorized on this "
            "machine. Run: python -m app.google_auth authorize. Gmail mutations "
            "remain permanently disabled."
        ),
    },
    {
        "id": "google-calendar-api",
        "name": "Google Calendar API",
        "category": "external",
        "status": "not_configured",
        "enabled": False,
        "riskLevel": "high",
        "capabilities": ["read_events_planned", "conflict_check_planned", "create_event_planned"],
        "allowedNow": ["manual_ics_export"],
        "blockedNow": ["api_read", "create_event", "update_event", "delete_event"],
        "requires": ["Google OAuth via backend gateway", "approval rules"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "Google Calendar API is not connected. The vault stays the source of truth "
            "for candidates; .ics export/open is the current manual path. No API reads "
            "or event writes are made."
        ),
    },
    {
        "id": "browser-harness",
        "name": "Browser Harness",
        "category": "browser",
        "status": "disabled",
        "enabled": False,
        "riskLevel": "high",
        "capabilities": ["open_page_planned", "read_page_planned", "capture_source_planned"],
        "allowedNow": [],
        "blockedNow": ["navigate", "read_page", "capture", "fill_form", "click"],
        "requires": [
            "NemoClaw/OpenShell runtime (wired)",
            "sandbox policy with landlock.compatibility: hard_requirement",
            "a created sandbox (NEMOCLAW_SANDBOX_ID)",
        ],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "Page reads and searches are implemented and run INSIDE the OpenShell "
            "sandbox through the approval queue. They stay disabled here because "
            "sandboxed execution refuses a fail-open policy: set "
            "landlock.compatibility: hard_requirement and create a sandbox. Reported "
            "disabled rather than available because this module performs no live "
            "health check."
        ),
    },
    {
        "id": "computer-use",
        "name": "Computer Use",
        "category": "browser",
        "status": "disabled",
        "enabled": False,
        "riskLevel": "high",
        "capabilities": ["observe_screen_planned", "click_type_copy_planned"],
        "allowedNow": [],
        "blockedNow": ["screenshot", "click", "type", "copy", "navigate_apps"],
        "requires": [
            "NemoClaw/OpenShell runtime",
            "computer-use controller",
            "visible session + stop control",
            "approval rules",
        ],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "Browser and computer-use actions are disabled until NemoClaw/OpenShell or "
            "equivalent runtime safety is wired."
        ),
    },
    {
        "id": "openclaw",
        "name": "OpenClaw",
        "category": "runtime",
        "status": "planned",
        "enabled": False,
        "riskLevel": "medium",
        "capabilities": ["local_agent_chat", "proposals_planned", "tool_requests_planned"],
        "allowedNow": ["manual_local_agent_chat_no_tools"],
        "blockedNow": ["tool_execution", "browser", "computer_use", "filesystem", "mcp"],
        "requires": ["OpenClaw runtime", "NemoClaw/OpenShell runtime", "backend gateway"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "OpenClaw and NemoClaw/OpenShell are planned runtime layers. Current Local "
            "Agent chat has no tools."
        ),
    },
    {
        "id": "nemoclaw-openshell",
        "name": "NemoClaw / OpenShell",
        "category": "runtime",
        "status": "planned",
        "enabled": False,
        "riskLevel": "high",
        "capabilities": ["sandbox_planned", "policy_enforcement_planned", "network_guardrails_planned"],
        "allowedNow": [],
        "blockedNow": ["sandbox", "policy_checks", "browser_mediation", "computer_use_mediation"],
        "requires": ["NemoClaw/OpenShell runtime install", "policy config", "runtime URL"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "OpenClaw and NemoClaw/OpenShell are planned runtime layers. Current Local "
            "Agent chat has no tools."
        ),
    },
    {
        "id": "github",
        "name": "GitHub",
        "category": "developer",
        "status": "not_configured",
        "enabled": False,
        "riskLevel": "medium",
        "capabilities": ["read_repo_planned", "list_issues_planned"],
        "allowedNow": ["manual_repo_paths_and_links"],
        "blockedNow": ["api_read", "create_issue", "push", "create_pr"],
        "requires": ["GitHub auth via backend gateway", "approval rules"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "GitHub API is not connected. Repo paths and links are tracked manually. "
            "No API reads or writes are made."
        ),
    },
    {
        "id": "google-drive",
        "name": "Google Drive",
        "category": "external",
        "status": "not_configured",
        "enabled": False,
        "riskLevel": "medium",
        "capabilities": ["search_files_planned", "read_file_planned"],
        "allowedNow": [],
        "blockedNow": ["search", "read", "create", "update", "delete"],
        "requires": ["Google OAuth via backend gateway", "approval rules"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": "Google Drive is not connected. No file reads or writes are made.",
    },
    {
        "id": "graphify",
        "name": "Graphify",
        "category": "developer",
        "status": "planned",
        "enabled": False,
        "riskLevel": "low",
        "capabilities": ["graph_export_planned"],
        "allowedNow": [],
        "blockedNow": ["graph_setup", "graph_export"],
        "requires": ["brain graphify-setup", "local graph tooling"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "Graphify is planned. No safe local check is wired yet, so it is reported "
            "as planned only."
        ),
    },
]


def list_tool_connections() -> List[dict]:
    """
    Return the read-only tool-connection inventory.

    Returns fresh copies so callers cannot mutate the module-level inventory.
    Performs no external calls, no shell, no `brain`, and no credential reads.

    The Gmail entry is resolved on every call (not at import time) so it reflects
    the machine's current authorization state rather than whatever was true when
    the module was first imported.
    """
    items = [dict(item) for item in _TOOL_SYSTEMS]
    ready = _gmail_reads_ready()
    cu_ready = _computer_use_ready()
    for item in items:
        if item["id"] == "computer-use":
            # MVP v7 is implemented, but it stays `disabled` until the operator
            # turns the kill switch on — reporting otherwise would overstate it.
            item["status"] = "available" if cu_ready else "disabled"
            item["enabled"] = cu_ready
            item["capabilities"] = ["observe_screen", "click", "type"]
            item["allowedNow"] = (
                ["screenshot", "click", "type"] if cu_ready else []
            )
            item["blockedNow"] = (
                ["credential_typing"] if cu_ready
                else ["screenshot", "click", "type", "copy", "navigate_apps"]
            )
            item["requires"] = [
                "BRAIN_UI_COMPUTER_USE_ENABLED=true",
                "BRAIN_UI_APPROVAL_TOKEN",
                "scoped session with a window allowlist",
                "foreground window match on every action",
            ]
            item["notes"] = (
                "Full desktop control, gated by a kill switch, the operator token, "
                "a scoped session, a wall-clock budget, and a foreground-window "
                "check that REFUSES rather than retargets. Risky actions need "
                "per-action confirmation; typing into a credential window is "
                "refused outright."
                if cu_ready else
                "Computer-use is implemented but the kill switch is off. Start the "
                "backend with BRAIN_UI_COMPUTER_USE_ENABLED=true to enable it."
            )
            continue
        if item["id"] == "google-calendar-api":
            item["status"] = "available" if ready else "not_configured"
            item["enabled"] = ready
            item["allowedNow"] = ["read_events", "reconcile_candidates"] if ready else []
            item["blockedNow"] = ["create_event", "update_event", "delete_event", "move_event"]
            item["notes"] = (
                "Read-only Google Calendar via local OAuth (calendar.readonly). "
                "Reconciles approved vault candidates against real events; writes "
                "nothing on either side. Event creation requires the calendar.events "
                "scope and explicit re-consent (Phase D2) and is not available."
                if ready else
                "Google Calendar read-only support is implemented but not authorized "
                "on this machine. Run: python -m app.google_auth authorize. Calendar "
                "writes remain unavailable."
            )
            continue
        if item["id"] != "gmail-mcp":
            continue
        item["status"] = "available" if ready else "not_configured"
        item["enabled"] = ready
        item["allowedNow"] = ["search", "read"] if ready else []
        item["notes"] = (
            "Read-only Gmail via local OAuth (gmail.readonly). Search and message "
            "reads are classified and logged by the Permission Gateway, and feed "
            "Email Intake drafts (no vault write). Message bodies are untrusted "
            "content. Send/delete/trash/archive/label are permanently disabled and "
            "no code path for them exists."
            if ready else
            "Gmail read-only support is implemented but not authorized on this "
            "machine. Run: python -m app.google_auth authorize. Gmail mutations "
            "remain permanently disabled."
        )
    return items
