# Session Summary: Local Agent Structured Output v0 (agent-emitted tool requests, evaluate-only)

Date: 2026-06-24
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Give the Local Agent the PRD-shaped output where a reply can carry structured `tool_requests`, parsed defensively by the backend and routed through the existing **evaluate-only** Agent Tool Request path. Nothing is executed.

```text
assistant reply (+ optional structured block) → backend parses + evaluates tool_requests via gateway → UI shows decisions → NOTHING runs
```

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/agent_structured_output.py` | **New.** `parse_structured_output(text)` (fenced ` ```json ` or `AGENT_STRUCTURED_OUTPUT:` labelled JSON; cap 5; validate tool/args/reason; malformed → parse error, never throws) and `evaluate_structured_output(text, conversationId)` (routes each valid spec through `agent_tool_requests.create_request` → evaluate-only). |
| `backend/app/agent.py` | System prompt updated to describe the optional structured block (evaluate-only, no claiming execution, no secrets, no privileged tools unless relevant, external content untrusted). |
| `backend/app/models.py` | `AgentChatStructured` + `structured` forward-ref field on `AgentChatResponse` (resolved via `model_rebuild()`). |
| `backend/app/main.py` | `agent_chat` attaches `structured`; `agent_chat_stream` emits an SSE `event: structured` after the turn is saved (guarded so it never breaks the stream). |
| `backend/tests/test_agent_structured_output.py` | **New.** 16 tests. |

### Structured format supported

A fenced ` ```json {…} ``` ` block **or** an `AGENT_STRUCTURED_OUTPUT:\n{…}` labelled block, e.g.:

```json
{ "tool_requests": [ { "tool": "brain.status", "args": {}, "reason": "Check status" } ], "confidence": "Medium", "needs_user_decision": true }
```

Only `tool_requests` is consumed in v0; other fields are ignored.

### Parser behavior

Defensive and untrusted: no block → empty (no error); malformed JSON → one parse error (no exception); `tool_requests` must be a list; each entry must be an object with a non-empty string `tool`, `args` a JSON object (default `{}`, non-object → entry skipped with error), `reason` coerced/truncated (fallback `(no reason provided)`); list capped at 5 with an error noting the cap; invalid entries reported and skipped.

### Evaluation / log behavior

Each valid request → `agent_tool_requests.create_request` → gateway `evaluate_tool_request` + one `gateway_eval` log; stored as an evaluate-only record. **No execution log, no `/execute`, no brain wrapper, no subprocess.** `brain.status` etc. evaluate `allowed`/`executionEnabled:true` but are **not run**.

### Streaming decision

Streaming token flow is unchanged. After the stream finishes and the turn is saved, the endpoint parses + evaluates the full reply and emits one `event: structured` (then `done`). The parse/evaluate is wrapped in a defensive `try/except` so a failure can never break the stream.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/api.ts` | `AgentStructuredOutput` (+ `AgentStructuredToolRequestResult`, `AgentStructuredParseError`); `structured?` on `AgentChatResponse`; `onStructured?` stream handler + parsing of the `structured` SSE event. |
| `src/pages/AgentPage.tsx` | `ChatStructuredPanel` renders evaluated requests under the assistant message (tool/decision/risk/exec/status/log id + parse-error notices); the `structured` event is captured (ref) and attached to the committed assistant message in `onDone`, and bumps a refresh signal so the right-rail Agent Tool Requests list reloads. No run/approve-execute control in chat. |

---

## What remains not executed

Execution from chat, approve-and-execute, OpenClaw/NemoClaw, MCP/Gmail/browser/computer-use, Google Calendar/GitHub/Drive, vault writes, task/calendar/resume auto-creation, shell, arbitrary brain — all unimplemented. Safe-local execution stays manual on Tool Connections. The Local Agent remains tool-less.

---

## Safety constraints (this sprint)

- Parser never executes; tolerates malformed input without breaking chat; caps/validates/truncates; treats all parsed content as untrusted (instructions inside are never followed).
- Evaluation is evaluate-only — no `/execute`, brain wrapper, subprocess, external service, or vault write; one `gateway_eval` log per request, zero execution logs.
- Secrets in args are redacted before storage/display (inherited from the gateway/agent-request path).
- UI has no execution control in chat; malformed output shows a notice, not a crash.

---

## Tests run

- `python -m pytest backend/tests` → **353 passed** (16 new): fenced/labelled parsing, no-block, malformed→error, cap, invalid-entry handling, reason truncation/fallback, tool_requests-not-list, evaluate creates evaluate-only requests (brain wrapper/subprocess never called), gmail not_wired, secrets redacted, eval-logs-not-execution-logs, no subprocess, and the chat endpoint attaches evaluated structured requests.
- `npm run build` → clean, **85 modules**.

---

## Recommended next sprint

1. **Confidence / needs_user_decision surfacing** — also parse `confidence` and `needs_user_decision` from the structured block and show them on the chat panel (still evaluate-only, no execution).
2. **One-click "review in Tool Connections"** — from an `allowed` structured request, a deep-link that pre-fills the Tool Connections evaluator with the same tool (execution still confirmed manually there; no auto-run).
