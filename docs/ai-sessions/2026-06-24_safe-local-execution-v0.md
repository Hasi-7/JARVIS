# Session Summary: Safe-local Tool Execution v0 (Permission Gateway)

Date: 2026-06-24
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Prove the Permission Gateway can safely **evaluate → execute → log** for a tiny allowlist of low-risk local actions, without enabling any privileged tool. Only three read-only `brain` status tools may execute, routed through the existing safe brain wrapper.

```text
request → evaluate + log → if safe-local tool: run via safe brain wrapper + log → return output
```

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/permission_gateway.py` | Added `_EXECUTABLE_TOOLS` + `_BRAIN_TOOL_COMMANDS`, `is_executable()`, `brain_command_for()`. `list_policies()` now sets `executionEnabled` true only for the 3 safe tools. `evaluate_tool_request()` returns `decision="allowed"` (allowed/executionEnabled true) for them, `requires_approval` for other available tools. Added `log_execution()` + `source` field on log entries + `_truncate_output()` for stdout/stderr previews. `EXECUTION_ENABLED` kept `False` (privileged kill-switch, no longer used as a per-policy override). |
| `backend/app/models.py` | `ToolExecutionResponse`; extended `PermissionEvaluationLog` with `source`, `exitCode`, `stdoutPreview`, `stderrPreview`, `durationMs`. |
| `backend/app/main.py` | New `POST /api/permissions/execute` (evaluate+log → execute safe-local via `run_brain_command` → log → return; safe non-execution response otherwise). |
| `backend/tests/test_tool_execution.py` | **New.** 18 tests (mocked wrapper). |
| `backend/tests/test_permission_gateway.py` | Updated 3 tests for the new `executionEnabled`/`decision` semantics. |

### Exact tools enabled

| Tool | brain command | policy |
|---|---|---|
| `brain.status` | `brain status` | available / low / no-approval / executable |
| `brain.raw_status` | `brain raw-status` | available / low / no-approval / executable |
| `brain.vault_path` | `brain vault-path` | available / low / no-approval / executable |

`brain.today`, `brain.weekly`, `brain.sync_raw`, `brain.calendar_*`, and all privileged tools remain **not executable**.

### Execution flow

`POST /api/permissions/execute` always evaluates and writes a `gateway_eval` log. If `is_executable(tool)`, it maps the tool to its allowlisted brain subcommand and calls the **existing** `run_brain_command` (`shell=False`, allowlisted, **no args forwarded to brain**), then writes a `gateway_execution` log and returns stdout/stderr/exit/duration. For any other tool it returns a safe response (`allowed:false`, `executionLogId:null`, `error:"Tool is not executable in this build."`) and **never** calls the wrapper — no 500.

### Logging behavior

Every request → one `gateway_eval` entry. Each actual execution → one `gateway_execution` entry with `result` (success/failure), `exitCode`, truncated `stdoutPreview`/`stderrPreview` (2000 chars), `durationMs`. Only the sanitized args summary is stored; raw args and secrets are never persisted. Cap stays 500.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/api.ts` | `ToolExecutionRequest`, `ToolExecutionResponse`, `executePermissionTool()`; `ToolLogSource`; extended `PermissionEvaluationLog` with `source`/`exitCode`/`stdoutPreview`/`stderrPreview`/`durationMs`. |
| `src/pages/ToolConnectionsPage.tsx` | *Run safe-local tool* button (enabled only for the 3 tools; otherwise disabled + "Execution disabled in this build."); `ExecResultPanel` (status/exit/duration/stdout/stderr/log ids); logs panel now shows eval vs execution badges + execution fields/previews; auto-refresh after evaluate/execute. |

---

## What remains disabled / not wired

Gmail/MCP/Obsidian-MCP/browser/computer-use/Google Calendar/GitHub/Drive execution, OpenClaw/NemoClaw/OpenShell, agent tool requests, vault `ops/tool-logs/` writes, arbitrary `brain` commands, shell execution, task/calendar/resume auto-creation, AI calls — all remain unimplemented. Local Agent stays tool-less.

---

## Safety constraints (this sprint)

- Executes only the three low-risk read-only brain status tools, only via the existing safe brain wrapper (`shell=False`, allowlisted, no args to brain, no new subprocess path).
- `EXECUTION_ENABLED` privileged kill-switch stays `False`; execution is opt-in per tool via a small allowlist.
- No MCP/Gmail/browser/computer-use/Google/GitHub/Drive call; no OpenClaw/NemoClaw; no arbitrary brain/shell; no vault write; no credentials; no tasks/calendar; no AI.
- Args untrusted (redacted/truncated, never forwarded to brain); stdout/stderr stored only as truncated previews.
- UI Run button is disabled for every non-safe-local tool; no approve-and-execute/replay action.

---

## Tests run

- `python -m pytest backend/tests` → **318 passed** (18 new execution tests; 3 gateway tests updated): execute the 3 safe tools (mapped command asserted, mocked wrapper), non-executable tools never call the wrapper, empty-tool 400, eval log for every request, execution log only for executed tools, failure logged as failure, stdout/stderr previews truncated, secret args redacted in stored log, no raw subprocess used, no vault writes.
- `npm run build` → clean, **85 modules**.

---

## Recommended next sprint

1. **Wire `filesystem.read_vault` as the next safe-local executable** (read-only vault summary/lookups through the gateway), reusing the same evaluate→execute→log path — still read-only, no writes.
2. **Manual export of the evaluation/execution log to the vault** — opt-in "export today's tool log to `ops/tool-logs/YYYY-MM-DD-tool-log.md`" (backup-before-write, never overwrite), so the durable PRD log location exists while privileged execution stays disabled.
