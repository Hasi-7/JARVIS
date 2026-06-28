# Session Summary: Review in Tool Connections — agent → manual-execution handoff

Date: 2026-06-24
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Let an evaluated Local Agent tool request be reviewed and **manually** executed on the Tool Connections page, completing the safe flow without giving chat any execution power:

```text
agent proposes tool request → backend evaluates/logs → user clicks "Review in Tool Connections"
→ form prefilled → user manually runs the safe-local tool → gateway logs execution
```

Frontend-only — the evaluation response already carries `executionEnabled` / `allowed` / `tool`.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/store/useAppStore.ts` | New `ToolReviewTarget` type + `toolReviewTarget` state + `setToolReviewTarget` (mirrors `proposalTarget` / `agentConvTarget`). |
| `src/pages/AgentPage.tsx` | `SAFE_LOCAL_TOOLS` + `isReviewable(tool, ev)` helper. **Review in Tool Connections** button in `ChatStructuredPanel` (per request) and the right-rail Agent Tool Requests list — only when reviewable; otherwise *Evaluation only — not executable in this build*. Click sets `toolReviewTarget` and `navigate('tools')`; never executes. |
| `src/pages/ToolConnectionsPage.tsx` | `PermissionGatewaySection` consumes `toolReviewTarget` once on mount: prefills tool + reason, sets `args` to `{}` (never reconstructs raw args from the sanitized summary), shows the review notice, clears the target. No auto-evaluate / auto-execute. |

## Backend files changed

None. No new endpoints, no new execution capabilities, no new tools, no vault writes.

---

## Handoff mechanism

A Zustand app-state field `toolReviewTarget = { tool, argsSummary?, reason?, requestedBy?, source: 'agent-chat'|'agent-tool-request'|'manual', relatedId? }`. The Agent page sets it and navigates; Tool Connections consumes + clears it on mount. This mirrors the existing `proposalTarget`/`agentConvTarget` handoffs (the app has no URL router).

## Agent page behavior

The **Review in Tool Connections** button renders **only** when `evaluation.executionEnabled === true` **and** `evaluation.allowed === true` **and** the tool ∈ {`brain.status`, `brain.raw_status`, `brain.vault_path`}. For every other request (not_wired / disabled / denied / requires_approval, or any non-safe-local tool) it shows *Evaluation only — not executable in this build* and offers no handoff. Clicking never executes — it only stores the target and navigates.

## Tool Connections behavior

On mount, if a target is present: prefill the evaluator with the tool and reason, set the args textarea to `{}`, show *"Opened from Local Agent. Review before running."* plus *"This request came from the Local Agent. It has not been executed. Only low-risk local brain status tools can run here."*, and clear the target. The form does not auto-evaluate or auto-execute; the user must click **Run safe-local tool** (the existing Safe-local Execution v0 path, which logs a `gateway_execution` entry).

---

## What remains manual / disabled

- Execution is still **manual** and only from Tool Connections, only for the three safe-local brain status tools.
- No execution from chat, no auto-run, no approve-and-execute.
- Still not wired: OpenClaw/NemoClaw/OpenShell, MCP, Gmail, browser/computer-use, Google Calendar/GitHub/Drive, arbitrary brain, shell, vault writes, Proposal Queue apply.

---

## Safety constraints (this sprint)

- Nothing executes during navigation or on page load; the handoff is prefill-only.
- Raw args are never reconstructed from the sanitized summary (args prefilled as `{}`).
- The handoff button is gated on the gateway's own `executionEnabled && allowed` plus the safe-local allowlist — it can never appear for privileged tools.
- No backend mutation, no new endpoints, no new tool capabilities.

---

## Tests run

- `python -m pytest backend/tests` → **353 passed** (unchanged — no backend changes).
- `npm run build` → clean, **85 modules**.

---

## Recommended next sprint

1. **Highlight the prefilled tool on arrival** — briefly highlight/scroll the evaluator on Tool Connections when opened from the agent (mirrors the Proposal Queue highlight UX), still no auto-run.
2. **Surface `confidence` / `needs_user_decision`** from the structured block on the chat panel and carry a short rationale into the review notice (still evaluate-only / manual execution).
