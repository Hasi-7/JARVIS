# Session Summary: Permission Gateway v0 (deny-by-default classification)

Date: 2026-06-24
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Implement the backend **permission-gateway shape** the PRD requires before any privileged tool is wired (§4.3, §9.2, §32) — the layer that decides whether a requested tool action is allowed, needs approval, is unavailable, or is disabled. v0 is **deny-by-default classification only**:

```text
manual simulated tool request → backend classifies it → returns denied / requires_approval / not_wired / disabled → UI displays result → NOTHING runs
```

This is the safety spine before future tools. No tool execution, no MCP/Gmail/browser/computer-use, no real agent tool use.

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/permission_gateway.py` | **New.** `list_policies()` (18-tool static policy table) + `evaluate_tool_request()` (deny-by-default classifier). Module constant `EXECUTION_ENABLED = False`. No execution, no external calls, no shell, no `brain`, no vault writes, no credential reads. |
| `backend/app/models.py` | **New models** `PermissionPolicy`, `PermissionPolicyResponse`, `ToolRequestEvaluationRequest` (`extra="forbid"`), `ToolRequestEvaluationResponse`. Added `Any`, `Dict` to typing import. |
| `backend/app/main.py` | **New endpoints** `GET /api/permissions/policies`, `POST /api/permissions/evaluate`. |
| `backend/tests/test_permission_gateway.py` | **New.** 26 tests. |

### Policy list behavior

18 tools across `obsidian.*`, `gmail.*`, `calendar.*`, `browser.*`, `computer.*`, `brain.*`, `filesystem.*`. `executionEnabled` is `false` for every entry. MCP/Gmail/calendar-read → `not_wired`; browser/computer-use + `gmail.send` + `calendar.create_event` → `disabled`; safe brain/vault-read → `available` (but never executed by the gateway).

### Evaluator behavior

- `not_wired` for MCP/Gmail/calendar-read tools.
- `disabled` for browser/computer-use, `gmail.send`, `calendar.create_event`, and unknown destructive-looking names (`shell.run`, `filesystem.delete`, `browser.submit_form`, `gmail.delete/archive/modify_labels`, …).
- `denied` for unknown non-dangerous tools.
- `requires_approval` for safe `available` tools — still **not executed** (v0 has no execution path).
- `allowed` and `executionEnabled` are **always `false`**; `wouldLog` is `true` but no log is written.
- Empty tool name → `ValueError` → HTTP 400.

### Redaction behavior

Args are untrusted — never executed, only summarized. Keys containing `password`, `token`, `secret`, `key`, `credential`, `authorization`, `cookie` → value `[redacted]`. Long values truncated (~60 chars), summary capped (~240 chars), pair count capped (12, with "+N more"). A callable-looking arg string is stringified, never invoked.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/api.ts` | Types `PermissionPolicy`, `PermissionPolicyResponse`, `ToolRequestEvaluationRequest`, `ToolRequestEvaluationResponse`, `ToolDecision`, `PermissionRisk`, `PermissionStatus`; functions `getPermissionPolicies()`, `evaluateToolRequest()`. |
| `src/pages/ToolConnectionsPage.tsx` | Added a **Permission Gateway section**: required-copy banner, policy table (tool/category/risk/status/approval/execution/notes), and a manual evaluator (tool datalist + reason + JSON-args textarea → result panel). Invalid JSON → clear validation error. No Run / Approve-and-execute button. |

---

## What remains disabled / not wired

Actual tool execution, MCP/Gmail/browser/computer-use/Google Calendar/GitHub/Drive integration, OpenClaw/NemoClaw/OpenShell bridges, agent tool requests, vault tool logs, shell execution, `brain` execution through the gateway, approval-queue execution, and credentials — **all remain not implemented**. Local Agent is still tool-less; Tool Connections remains a read-only status inventory.

---

## Docs updated

`README.md` (new "Permission Gateway (v0)" section), `context/current-task.md` (latest entry + Real Workflows row), this session summary, and memory.

---

## Tests run

- `python -m pytest backend/tests` → **257 passed** (26 new): policy list includes required tools, valid enums, executionEnabled false everywhere, not-wired Gmail, disabled dangerous (known + unknown), unknown denied, secret redaction, long-value truncation + pair cap, safe-tool-not-executed, empty-tool raises, no subprocess invoked, no files written, args-never-executed.
- `npm run build` → clean, **84 modules**.

---

## Safety constraints (this sprint)

- Deny-by-default: `allowed` and `executionEnabled` are always `false`.
- Gateway executes nothing — no tool, no MCP/Gmail/browser/computer-use/Google/GitHub/Drive call, no shell, no `brain`, no vault write, no credential read.
- Args untrusted: never executed; secrets redacted; long values truncated.
- UI is read-only classification — no Run / Approve-and-execute control.

---

## Recommended next sprint

1. **Wire the evaluator output into the Proposal Queue / Local Agent as a *simulated* tool-request card** — a tool request becomes a `pending` proposal carrying the gateway decision (still no execution), so the propose→approve spine and the gateway classification meet in one place.
2. **Approval record shape (still no execution)** — add a backend-local (app-data JSON) approval/decision audit record + `GET` history so the `wouldLog` path becomes a real, inspectable preview log, without touching the vault or running any tool.
