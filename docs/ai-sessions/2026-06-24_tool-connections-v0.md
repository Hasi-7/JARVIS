# Session Summary: MCP / Tool Connections v0 (read-only readiness surface)

Date: 2026-06-24
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Implement MCP / Tool Connections v0 as an **honest status/config readiness page** — a place to show what privileged tool systems exist, what is configured, what is disabled, what is planned, each system's risk level, and what is currently allowed vs blocked. The user should be able to see, before any privileged integration is built, that everything privileged is still unavailable.

Scope was deliberately read-only: prepare the UI and backend shape for future MCP/Gmail/browser work **without enabling privileged tools**. No MCP calls, no Gmail, no browser/computer-use, no external tool launches, no credentials, no tool execution.

---

## What was built

### Backend

| File | Role |
|---|---|
| `backend/app/tools.py` | New read-only module. `list_tool_connections() -> list[dict]` returns a static readiness inventory (fresh copies, so callers can't mutate module state). No external calls, no shell, no `brain`, no credentials, no execution. |
| `backend/app/models.py` | New Pydantic models `ToolConnectionStatus` and `ToolConnectionStatusResponse`. |
| `backend/app/main.py` | New endpoint `GET /api/tools/status` → `ToolConnectionStatusResponse`. |

**Endpoint:** `GET /api/tools/status` returns `{ items: ToolConnectionStatus[] }`. Each item:
`id`, `name`, `category`, `status`, `enabled`, `riskLevel`, `capabilities[]`, `allowedNow[]`, `blockedNow[]`, `requires[]`, `lastCheckedAt`, `lastError`, `notes`.

**Status values:** `available | unavailable | not_configured | disabled | planned | error`.
**Categories:** `runtime` (Agent Runtime), `mcp` (MCP), `browser` (Browser / Computer Use), `external` (External Services), `developer` (Developer Tools).

**Tool systems (10):** `obsidian-mcp`, `gmail-mcp`, `google-calendar-api`, `browser-harness`, `computer-use`, `openclaw`, `nemoclaw-openshell`, `github`, `google-drive`, `graphify`.

Nothing is reported `available` (no real check runs in this build). Privileged systems are `not_configured`, `planned`, or `disabled`, per the PRD permission model.

### Frontend

| File | Role |
|---|---|
| `src/lib/api.ts` | Types `ToolConnectionStatus`, `ToolConnectionStatusResponse`, `ToolConnectionCategory`, `ToolConnectionState`, `ToolRiskLevel`; client function `getToolConnectionStatus()`. |
| `src/pages/ToolConnectionsPage.tsx` | New page. Cards grouped by category with status badge, risk badge, enabled/disabled indicator, capabilities, allowed-now, blocked-now, requirements, notes. Loading + backend-error + empty states. |
| `src/types/index.ts` | Added `tools` to `RouteId`. |
| `src/App.tsx` | Imported + routed `ToolConnectionsPage` for route `tools`. |
| `src/data/mock.ts` | Added `Tool Connections` nav item under the Control group. |

**Actions:** only **Refresh status** and **Settings** navigation are live. There is no Connect / Enable / Authenticate / Test / Launch action — the per-card control is clearly disabled and labelled **"Not wired yet."**

**Required copy present:** Gmail not-connected + mutations disabled; Obsidian MCP filesystem-adapter/backup-before-write; browser/computer-use disabled pending NemoClaw/OpenShell; OpenClaw/NemoClaw planned runtime layers / Local Agent has no tools.

---

## What is blocked / still not implemented

- Actual MCP connection, Gmail search/read/auth/mutations, browser harness, computer-use harness, OpenClaw bridge, NemoClaw/OpenShell bridge, Google Calendar/Drive/GitHub API calls — all remain **not wired**.
- No credential storage, no tool logs, no tool execution, no approval queue, no agent tool requests, no shell execution, no new write actions.

This sprint only adds the **read-only readiness surface and the backend/UI shape** for those future systems.

---

## Tests run

- `python -m pytest backend/tests` → **231 passed** (15 new in `backend/tests/test_tools_status.py`: required systems present, valid enums, nothing falsely available/enabled, Gmail mutations blocked, browser/computer-use disabled + require NemoClaw, OpenClaw/NemoClaw planned, no subprocess invoked, no files written, fresh-copy isolation).
- `npm run build` → clean, **84 modules** (was 83; +1 page).

---

## Safety constraints (this sprint)

- `GET /api/tools/status` is read-only: no external calls, no shell, no `brain`, no credential reads, no tool execution.
- `list_tool_connections()` returns fresh copies — the static inventory can't be mutated by callers.
- Nothing is reported `available`; no privileged system is shown as connected/ready/enabled.
- Dashboard and Tool Safety continue to show honest statuses (unchanged).

---

## Recommended next sprint

1. **Wire the inventory to real local checks where safe** — e.g. surface the already-real Ollama/local-model and Brain CLI status into the Tool Connections inventory (still no privileged external calls), so the page reflects backend-derived state for the safe-local rows.
2. **MCP gateway scaffolding (still no execution)** — define the backend permission-gateway request/response shape (`tool`, `args`, `reason`, `risk`, `approval`) as types + a stub that always denies, so the propose→approve→apply spine is ready before any tool is actually wired.
