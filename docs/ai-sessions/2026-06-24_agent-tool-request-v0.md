# Session Summary: Agent Tool Request v0 (evaluate-only agent → gateway bridge)

Date: 2026-06-24
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Connect the Local Agent surface to the Permission Gateway **for evaluation only**, without giving the agent any execution power. The agent (or a manual stand-in) creates a structured tool-request proposal; the backend evaluates it through the gateway, logs the evaluation, and shows the decision. Nothing runs.

```text
agent proposes tool request → backend evaluates via gateway + writes gateway eval log → UI shows decision → NOTHING runs
```

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/agent_tool_requests.py` | **New.** `create_request()` evaluates via `evaluate_tool_request`, writes the existing `log_evaluation` (`gateway_eval`) log, stores a redacted record (`backend/data/agent-tool-requests/requests.json`, cap 200), returns it. `list_requests()` newest-first. Never executes / calls the brain wrapper / subprocess. |
| `backend/app/models.py` | `CreateAgentToolRequestRequest` (`extra="forbid"`), `AgentToolRequestEvaluation`, `AgentToolRequestResponse`, `AgentToolRequestListResponse`. |
| `backend/app/main.py` | `POST /api/agent/tool-request`, `GET /api/agent/tool-requests`. |
| `backend/tests/test_agent_tool_requests.py` | **New.** 19 tests. |

### Request lifecycle

`POST /api/agent/tool-request` → validate shape → `evaluate_tool_request` (classification only) → `log_evaluation` (one `gateway_eval` entry) → build a redacted record (only the sanitized args summary, truncated reason/requestedBy) → store (cap 200) → return `{ id, tool, argsSummary, reason, requestedBy, conversationId, evaluation{…, logId}, createdAt, status }`. `status` is always `evaluated_only`. `GET /api/agent/tool-requests?limit=` returns newest-first (clamped [1, 200]).

### Permission evaluation behavior

The proposed tool is classified exactly as the gateway classifies any request: `brain.status`/`brain.raw_status`/`brain.vault_path` → `allowed` (executionEnabled true), MCP/Gmail/calendar-read → `not_wired`, browser/computer-use/`gmail.send`/dangerous-unknown → `disabled`, unknown → `denied`, other available → `requires_approval`.

### Log linkage

Each request writes exactly one `gateway_eval` entry via the existing Tool Log path and stores its id as `evaluation.logId`. **No execution log is ever created** by this endpoint.

### What is deliberately NOT executed

Even for the safe-local tools, the agent request path **never** calls `/api/permissions/execute`, `run_brain_command`, any subprocess, or any external tool — a `brain.status` request returns `allowed`/`executionEnabled:true` but is not run. Safe-local execution remains manual on the Tool Connections page.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/api.ts` | `AgentToolRequestEvaluation`, `AgentToolRequestResponse`, `AgentToolRequest` (alias), `CreateAgentToolRequestRequest`, `AgentToolRequestListResponse`; functions `createAgentToolRequest()`, `listAgentToolRequests()`. |
| `src/pages/AgentPage.tsx` | New `AgentToolRequestsPanel` in the right rail (replaces the old "Tool requests — stub"): manual/simulated request form (tool dropdown + reason + JSON args, invalid JSON → clear error) and a recent-requests list (tool, decision, risk, execution-enabled, status, log id). Passes the active `convId`. **No run / approve-and-execute / auto-run** control; states requests are evaluated only. |

---

## Safety constraints (this sprint)

- Evaluate-only: never executes a tool, never calls `/execute`, the brain wrapper, a subprocess, MCP/Gmail/browser/computer-use/Google/GitHub/Drive, OpenClaw/NemoClaw, or the vault; no tasks/calendar; no AI.
- `args`/`reason` untrusted — only the sanitized args summary is stored (secrets redacted, values truncated); instructions inside them are never followed.
- The UI has no execution control on the Local Agent page; execution stays on Tool Connections (safe-local manual only).

---

## Tests run

- `python -m pytest backend/tests` → **337 passed** (19 new): create evaluates + logs (one `gateway_eval`, no execution log), safe-local allowed-but-not-executed (brain wrapper/subprocess never called), gmail not_wired, dangerous/unknown/other not executed, empty-tool 400, secrets redacted + raw args not stored, list newest-first + limit clamp, no subprocess, no vault write.
- `npm run build` → clean, **85 modules**.

---

## Recommended next sprint

1. **Structured-output bridge from the local model** — let the Local Agent chat optionally emit a tool-request JSON block that is parsed (defensively, untrusted) into the same `POST /api/agent/tool-request` evaluation, still evaluate-only and no execution.
2. **Manual "promote to execution" handoff** — for an `allowed` agent tool request, a one-click deep-link to the Tool Connections evaluator pre-filled with the same tool (execution still confirmed manually there) — no auto-run, just a smoother review path.
