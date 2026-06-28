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

It only returns the readiness inventory. Nothing here is marked `available`
because nothing performs a real check yet. Privileged systems are reported as
`not_configured`, `planned`, or `disabled` per the PRD permission model.

Future wiring (real MCP/Gmail/browser gateways) should replace individual static
entries with backend-derived status — and only then may a system report
`available`, after a genuine check.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

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
        "name": "Gmail MCP",
        "category": "mcp",
        "status": "not_configured",
        "enabled": False,
        "riskLevel": "high",
        "capabilities": ["search_email_planned", "read_email_planned", "intake_to_vault_planned"],
        "allowedNow": [],
        "blockedNow": ["search", "read", "draft", "send", "delete", "archive", "modify_labels"],
        "requires": ["Gmail auth via backend gateway", "NemoClaw/OpenShell runtime", "approval rules"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "Gmail is not connected. Email search/read/intake is planned through the "
            "backend gateway. Gmail mutations remain disabled."
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
        "requires": ["NemoClaw/OpenShell runtime", "browser harness controller", "approval rules"],
        "lastCheckedAt": None,
        "lastError": None,
        "notes": (
            "Browser and computer-use actions are disabled until NemoClaw/OpenShell or "
            "equivalent runtime safety is wired."
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
    """
    return [dict(item) for item in _TOOL_SYSTEMS]
