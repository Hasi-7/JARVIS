# Session Summary: Agent Mode Enforcement v0

Date: 2026-06-28
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Make agent modes **real, backend-enforced policy** instead of frontend-only labels. The selected
mode now gates whether the Local Agent may **evaluate** a structured tool request and whether a
**Review in Tool Connections** handoff may be offered. Nothing executes from any mode — execution
stays manual on Tool Connections, and no new privileged integrations are added.

```text
chat / manual tool request (+ mode)
  → backend resolves the mode and enforces policy
  → Locked / Observe / Computer-Use: tool requests BLOCKED (not evaluated, not stored, not logged)
  → Draft / Assist / Research / Escalation: tool requests EVALUATED ONLY
  → only Assist offers the Review-in-Tool-Connections handoff
  → NOTHING executes from any mode
```

---

## Mode policy (v0)

| mode | available | evaluate tool requests | review handoff |
|---|---|---|---|
| locked | true | false | false |
| observe | true | false | false |
| draft | true | **true** | false |
| assist | true | **true** | **true** |
| research | true | **true** | false |
| escalation | true | **true** | false |
| computer_use | **false** | false | false |

- `computer_use` is recognized but **unavailable/blocked** (browser/computer-use stay off).
- Unknown / missing / malformed mode → safest mode **`locked`** (blocked). Frontend aliases:
  `manual → locked`, `computer → computer_use`.

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/agent_modes.py` | **New.** Single source of truth. `normalize_mode` (alias map + unknown→locked, never raises), `is_mode_available`, `can_evaluate_tool_requests`, `can_offer_review_handoff`, `mode_label`, `blocked_message`, `list_modes`. Executes nothing — pure policy. |
| `backend/app/models.py` | New `AgentModePolicy`, `AgentModesResponse`, `AgentModeBlockedResponse`. Added optional `mode` to `CreateAgentToolRequestRequest`. Extended `AgentChatStructured` with `mode` / `blockedByMode` / `message`. |
| `backend/app/main.py` | New `GET /api/agent/modes`. `POST /api/agent/tool-request` now mode-gates (blocked modes → `blocked_by_mode`, 200, no record/log). Both chat endpoints (`/api/agent/chat`, `/api/agent/chat/stream`) only **evaluate** structured output when the mode allows; otherwise parse for visibility only and return a `blockedByMode` notice. |
| `backend/tests/test_agent_modes.py` | **New.** 38 tests. |
| `backend/tests/test_agent_tool_requests.py`, `backend/tests/test_agent_structured_output.py` | Two existing tests updated to pass an evaluating mode (mode-less now safely defaults to locked/blocked). |

### Manual request: blocked vs evaluated

`POST /api/agent/tool-request` resolves `mode = normalize_mode(req.mode)`. If
`can_evaluate_tool_requests(mode)` is False it returns `AgentModeBlockedResponse(status="blocked_by_mode",
mode, message)` **before** evaluating, storing, or logging anything. Otherwise it evaluates exactly
as before (one `gateway_eval` log, `status="evaluated_only"`, never executes).

### Chat integration

Each chat turn resolves the mode once. In an evaluating mode, structured tool requests are routed
through the existing evaluate-only path (`evaluate_structured_output`). In a blocking mode, the reply
is parsed for **visibility only** (`parse_structured_output`) and — if it proposed requests — the
response/SSE carries `blockedByMode=True` + a clear message; nothing is evaluated, stored, or logged.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/types/index.ts` | Added `escalation` to `AgentModeId`. |
| `src/data/mock.ts` | Added an `escalation` mode; updated every mode `desc` to honest policy copy (assist stays index 3 → store default unchanged). |
| `src/lib/api.ts` | `AgentModePolicy` / `AgentModesResponse` / `AgentModeBlockedResponse` types, `getAgentModes()`, `isBlockedByMode()` guard; `mode` on the create payload; `createAgentToolRequest` returns a record **or** a blocked response; `AgentStructuredOutput` extended with `mode`/`blockedByMode`/`message`. |
| `src/pages/AgentPage.tsx` | Fetches `getAgentModes()` (static fallback offline); resolves the current mode's policy; replaced the "UI-only" note with real per-mode policy copy (tool requests evaluated/blocked/unavailable, review handoff allowed/not, not-wired). The manual request form is disabled + shows blocked copy when the mode can't evaluate, sends `mode`, and handles a `blocked_by_mode` response as a clear notice. The chat **Blocked by mode** panel renders instead of a gateway failure. Review buttons are gated on `canOfferReviewHandoff` (Assist only) **and** the gateway's safe-local check. |

---

## What remains non-executing

No mode executes tools from chat. No path calls `/api/permissions/execute`, `run_brain_command`, a
subprocess, MCP, Gmail, browser/computer-use, Google Calendar, or writes the vault. Safe-local
execution stays **manual** on the Tool Connections page. Blocked modes write **no** records and
**no** logs, so no execution logs are ever created from agent-mode paths.

---

## Tests run

```bash
python -m pytest backend/tests -q   # 391 passed (38 new mode tests)
npm run build                        # 85 modules, 0 TypeScript errors
```

---

## Safety constraints

- Mode policy lives in one backend module and is enforced server-side; the frontend mirrors it for
  display but the backend is authoritative.
- Unknown/missing modes fall back to the **safest** mode (`locked`); rules were kept safer, not looser.
- `computer_use` enables nothing — recognized but unavailable.
- External/structured content stays untrusted: parsed for visibility, never executed or followed.

---

## Recommended next sprint

Wire the read-only `GET /api/agent/modes` into the global mode badge (TopCommandBar / Dashboard) so
honest mode policy is visible app-wide, and begin the OpenClaw/NemoClaw bridge **behind** this policy
(modes already gate evaluation; the bridge adds the runtime guardrail before any execution path).
