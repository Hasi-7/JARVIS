# Session Summary: OpenClaw / NemoClaw Runtime Status v0

Date: 2026-06-28
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Add an honest, **read-only** backend runtime-status surface for the five privileged runtimes
(OpenClaw, NemoClaw/OpenShell, browser harness, computer-use, MCP gateway) and show readiness in the
Dashboard, Tool Connections, and Local Agent — without wiring any runtime. **Status/readiness only:**
no launch, no network/health call, no credentials, no execution.

```text
configuration/readiness detection → honest status response → UI display
(no runtime launch · no privileged actions · no new autonomy)
```

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/runtime_status.py` | **New.** `list_runtime_status(env=None)` returns the read-only readiness inventory for the 5 runtimes from **env config only**. Pure: no network, no process, no shell/`brain`, no creds, no vault, no tool exec. |
| `backend/app/models.py` | New `RuntimeStatusItem` (id, name, status, available, enabled, requiredFor[], dependsOn[], blocks[], configured{}, notes) + `RuntimeStatusResponse`. |
| `backend/app/main.py` | New `GET /api/runtime/status`. |
| `backend/tests/test_runtime_status.py` | **New.** 16 tests. |

---

## Runtime status model

Each item: `id`, `name`, `status` (`available | unavailable | not_configured | disabled | planned |
error`), `available` (bool), `enabled` (bool), `requiredFor[]` (what it would unlock), `dependsOn[]`
(runtime ids), `blocks[]` (human-readable blocker reasons), `configured{}` (which env knobs are
present — values never stored), `notes`.

**Honesty rule (load-bearing):** no runtime is ever reported `available`. v0 performs **no verified
health check** (and must not), so a fully-configured runtime reports `unavailable`
(configured-but-unverified) and `available`/`enabled` are always `false`.

**Config detection (env only, read-only):** `OPENCLAW_ENABLED`/`OPENCLAW_BASE_URL`,
`NEMOCLAW_ENABLED`/`NEMOCLAW_RUNTIME_URL`/`NEMOCLAW_POLICY_PATH`,
`ENABLE_BROWSER_HARNESS`/`ENABLE_COMPUTER_USE`/`ENABLE_MCP_GATEWAY`. These knobs do not exist
elsewhere yet; unset → `not_configured`. Only presence/enabled-flag is read.

---

## Dependency / blocking behavior

- Browser harness and computer-use **depend on** NemoClaw/OpenShell and are `disabled` + blocked
  while it is unavailable — **even if their own enable flag is set** (the guardrail is the hard gate).
- NemoClaw/OpenShell is never `available` (no verified check), so dependents stay blocked in v0.
- OpenClaw privileged actions and MCP privileged actions likewise list the runtime-guardrail blocker.
- Default (no env): openclaw `not_configured`, nemoclaw `not_configured`, browser `disabled`,
  computer-use `disabled`, mcp `not_configured`.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/api.ts` | `RuntimeStatusItem` / `RuntimeStatusResponse` / `RuntimeStatusState` types + `getRuntimeStatus()`. |
| `src/lib/runtimeStatus.ts` | **New.** `useRuntimeStatus()` hook (backend + static `RUNTIME_FALLBACK`, `degraded` flag), `runtimeStatusLabel`/`runtimeStatusTone`/`isBlocked`, `RUNTIME_TRUTHS`. |
| `src/components/runtime/RuntimeStatus.tsx` | **New.** `RuntimeStatusRows` (Dashboard), `RuntimeGuardrails` (Tool Connections — dependency chain, per-runtime status/requiredFor/blocks, disabled **Not wired yet** button), `RuntimeGuardrailNote` (Local Agent). |
| `src/pages/DashboardPage.tsx` | Runtime panel now shows real backend-derived rows (replaced the mock `SYSTEM` "Planned" rows) + the two required truths. |
| `src/pages/ToolConnectionsPage.tsx` | New **Runtime Guardrails** section. |
| `src/pages/AgentPage.tsx` | Small runtime guardrail note in the right rail. |

---

## Dashboard / Tool Connections / Agent UI behavior

- **Dashboard:** honest runtime rows (OpenClaw / NemoClaw / Browser / Computer-use / MCP) with status
  labels and amber/grey tones; never shown ready. Plus *Privileged agent runtimes are not wired yet.*
  / *Browser and computer-use remain blocked until NemoClaw/OpenShell is available.*
- **Tool Connections:** a Runtime Guardrails section showing the dependency chain
  (`OpenClaw → NemoClaw/OpenShell → Permission Gateway → approved tools`), each runtime's status, what
  it would unlock, and why it is blocked. The only per-runtime control is a disabled **Not wired yet**.
- **Local Agent:** a small note (NemoClaw/OpenShell + OpenClaw bridge status; "Agent remains local
  chat + evaluate-only tool requests").
- **Degraded/backend-down:** `useRuntimeStatus()` falls back to `RUNTIME_FALLBACK` and surfaces
  "backend unreachable — showing fallback"; the app never blocks.

---

## What remains not wired

OpenClaw bridge, NemoClaw/OpenShell, browser harness, computer-use, MCP gateway, Gmail, Google
Calendar/Drive, GitHub — all **not wired**. No runtime launch, no health network call, no process
start/stop, no shell, no `brain`, no execution from chat, no new agent autonomy.

---

## Tests run

```bash
python -m pytest backend/tests -q   # 407 passed (16 new runtime-status tests)
npm run build                        # 88 modules, 0 TypeScript errors
```

---

## Safety constraints

- Reads environment config only; makes no external call, starts no process, runs no shell/`brain`,
  reads no credentials, writes no vault, executes no tool.
- No runtime is reported `available` without a genuine verified check (which does not exist yet).
- Browser/computer-use are blocked whenever NemoClaw/OpenShell is unavailable.
- No connect/start/test/enable control is clickable (only a disabled **Not wired yet** button).

---

## Recommended next sprint

Add a **sandboxed, opt-in health probe** for NemoClaw/OpenShell behind an explicit feature flag: only
when a verified check passes may that runtime report `available`, which then (and only then) lets
browser/computer-use move from `blocked` to a gated `requires_approval` state — still routed through
the Permission Gateway, still no execution from chat.
