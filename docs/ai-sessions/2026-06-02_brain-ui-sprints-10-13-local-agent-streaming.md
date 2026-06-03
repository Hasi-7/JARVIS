# Session Summary: Brain UI — Local Agent + Streaming (Sprints 10–13)

Date: 2026-06-02
Tool: Claude Code (claude-sonnet-4-6)
Project: JARVIS / Brain UI (`D:\Hasnain\Personal\dev\JARVIS`)

---

## Goal

Implement four backend + frontend sprints on top of the existing intake pipeline:

- **Sprint 10:** Backend config file persistence (`backend/data/brain-ui-config.json`)
- **Sprint 11:** Local agent chat via Ollama — `GET /api/agent/status`, `POST /api/agent/chat`
- **Sprint 12:** Local conversation history — `backend/data/conversations/` with full CRUD + left-rail UI
- **Sprint 13:** Streaming responses via SSE — `POST /api/agent/chat/stream`, token-by-token UI, AgentSphere state transitions

---

## Context

- Continuing from `2026-06-01_brain-ui-sprints-1-9-intake-pipeline.md`, which left Sprint 9 (archive) partially complete.
- Sprint 9 was confirmed **already fully implemented** at session start (reading the files showed `archive` endpoint and UI code fully in place). No additional work needed.
- All sprints in this session are **working tree changes only** — no new commits were made. All changes remain unstaged.
- Stack unchanged: React 18 + Vite 5 + TypeScript + Zustand (frontend); FastAPI + Pydantic v2 + Uvicorn (backend).
- Ollama: local LLM provider via stdlib `urllib.request` — no new Python dependencies added.

---

## Files Changed

### New backend files

| File | What changed |
|---|---|
| `backend/app/config.py` | Full rewrite — load order: env → file → defaults; `_load_startup_config()`, `_write_config_file()`, `update_config()` now writes `brain-ui-config.json`; `RuntimeConfig` dataclass with `.source`, `.persisted`, `.warning`; corrupt file logged + left untouched |
| `backend/app/agent.py` | New — `get_agent_status()` probes Ollama `/api/version` + `/api/tags`; `chat_with_agent()` non-streaming POST to Ollama `/api/chat`; `stream_ollama_chat()` generator reads Ollama with `stream:true` via `urllib readline()`; hard-coded `_SYSTEM_PROMPT` (no tools, no vault, no shell); raises `ValueError` on HTTP/network failure |
| `backend/app/conversations.py` | New — `CONVERSATIONS_DIR`; `_safe_path(id)` rejects `/`, `\`, `..`, validates resolved path; `create_conversation()`, `list_conversations()`, `get_conversation()`, `delete_conversation()`, `save_chat_turn()`; thread-safe via `threading.Lock`; system prompt never stored |
| `backend/app/models.py` | Added `ConfigResponse` fields (`configSource`, `configPersisted`, `configWarning`); `AgentStatusResponse`, `AgentChatContext`, `AgentChatRequest`, `AgentChatResponse`; `AgentChatRequest.conversationId`; `ConversationSummary`, `ConversationMessage`, `ConversationDetail`, `ConversationListResponse`, `CreateConversationRequest`, `DeleteConversationResponse` |
| `backend/app/main.py` | Added Sprint 10 config source/persisted/warning in `_config_response()`; Sprint 11 `GET /api/agent/status`, `POST /api/agent/chat`; Sprint 12 conversation CRUD routes; Sprint 13 `import json`, `import time`, `StreamingResponse`, `_sse()` helper, `POST /api/agent/chat/stream` endpoint with generate() closure |

### Modified frontend files

| File | What changed |
|---|---|
| `src/lib/api.ts` | Sprint 10: `BackendConfig` gains `configSource`, `configPersisted`, `configWarning`; Sprint 11: `AgentStatus`, `AgentChatRequest`, `AgentChatResponse`, `getAgentStatus()`, `sendAgentMessage()`; Sprint 12: conversation types + CRUD functions; Sprint 13: `StreamMeta`, `StreamDone`, `StreamError`, `StreamHandlers`; standalone `streamAgentMessage()` export using fetch+ReadableStream+TextDecoder+double-newline SSE parsing |
| `src/store/useAppStore.ts` | Added `agentStatus: AgentStatus | null`, `agentPrefill: string`; `checkAgentStatus()`, `setAgentPrefill()` actions; `checkBackend()` now probes Ollama when backend is up |
| `src/pages/AgentPage.tsx` | Full rewrite across sprints 11→13; final state: left rail (conversation list with inline delete confirm, mode selector, model status, safety notice); center (cockpit head, transcript, live streaming bubble with blinking cursor, error strip, composer); `streamingMsg: string|null` state; `streamContentRef` + `firstTokenRef` + `resolvedConvIdRef` refs; `handleSend` calls `streamAgentMessage()`; AgentSphere: thinking→speaking on first token→idle 3s after done; send + textarea disabled while `isGenerating` |
| `src/pages/DashboardPage.tsx` | Added `agentStatus` from store; Ollama shown as third row in runtime status panel; Ask form calls `setAgentPrefill()` before navigating to agent page |
| `src/pages/SettingsPage.tsx` | Shows `configSource` and `configWarning` from backend |
| `README.md` | Added Local Agent section (Ollama setup, env vars, streaming SSE event format, conversation history, safety rules); updated "What is real" table for Sprints 10–13 |

---

## Commands Run

```powershell
# Build verification (run after each sprint)
npm run build
# Result: 85 modules, 0 TypeScript errors

# Python syntax check (run after backend changes)
python -m py_compile backend/app/agent.py
python -m py_compile backend/app/conversations.py
python -m py_compile backend/app/main.py
# All passed
```

---

## Decisions Made

| Decision | Reason |
|---|---|
| `urllib.request` for Ollama calls (not httpx/requests) | No new Python dependencies; stdlib is sufficient for local HTTP |
| `fetch + ReadableStream` for SSE (not EventSource) | EventSource does not support POST requests |
| Double-newline (`\n\n`) SSE event delimiter | Standard SSE spec; clean boundary detection without regex |
| `stream:true` + `readline()` for Ollama streaming | Ollama returns NDJSON — one JSON object per line |
| Conversation saved **only** after full stream success | Partial responses from failed streams must not be persisted |
| System prompt never stored as a message | Prevents leaking internal instructions; conversation export would show it otherwise |
| `_safe_path()` rejects `/`, `\`, `..` in conversation IDs | Path traversal prevention; UUIDs are the only valid IDs |
| `firstTokenRef` instead of functional `setAgentState` updater | `setAgentState` is typed to only accept `AgentStateKey`, not a functional updater — avoids TS2345 |
| `threading.Lock` in conversations.py | Multiple concurrent requests could corrupt the JSON file otherwise |
| Conversation title = first 50 chars of first user message | No extra title input required; auto-title is good enough for local history |

---

## Bugs Fixed

**TS2345 / TS7006 — AgentPage functional state updater**

- Symptom: `setAgentState((prev) => prev === 'thinking' ? 'speaking' : prev)` failed type check — `setAgentState` only accepts `AgentStateKey`, not a function.
- Fix: Added `firstTokenRef = useRef(true)`; in `onToken` callback: `if (firstTokenRef.current) { firstTokenRef.current = false; setAgentState('speaking'); }` — fires the transition exactly once on first token.
- Build passed after fix.

---

## Tests / Validation

- `npm run build` — 85 modules, 0 TypeScript errors (verified after each sprint).
- Python `py_compile` on all modified backend files — no syntax errors.
- No automated test suite exists; functional tests are manual.
- UI was not live-tested in this session (backend server not started during session). Needs manual confirmation.

---

## Open Issues

- Old conversation messages are **not sent to the model as context** — only the latest user message is sent each turn. Multi-turn coherence requires Sprint 14 (context window).
- No automated tests for backend routes (conversations, agent, streaming).
- `npm run build` does not verify streaming correctness — only type safety.
- Archive restore is manual only (files are in `backend/data/archive/`, no restore endpoint).
- Bulk archive not implemented.
- All changes remain **unstaged and uncommitted**.

---

## Next Actions

1. **Commit current working tree** — all Sprints 9–13 changes are uncommitted.
2. **Sprint 14 (context window)** — send last N (e.g. 10) user+assistant messages as context to the model. Required for coherent multi-turn conversations. Change: `GET /api/conversations/{id}` already returns message history; `stream_ollama_chat()` needs a `messages` parameter; `AgentChatRequest` gains `includeHistory: bool`; AgentPage passes loaded conversation messages.
3. **Sprint B (vault backfill)** — wire Projects/Courses/Hackathons stub pages to real vault data via `brain` CLI.
4. **Sprint C (research page)** — web search + summarize flow using the local model.
5. Start Ollama + backend and do a live end-to-end test of the streaming path.

---

## What Should Go to Obsidian raw/

```
raw/dev/brain-ui/sessions/2026-06-02_brain-ui-sprints-10-13.md
```

This session summary. Route via Raw Inbox intake flow.

---

## What Should Go to Obsidian wiki/

None. No new architectural concepts that aren't already captured in README.md or the codebase.

---

## What Should Go to Obsidian ops/

Consider adding a note to `ops/projects/brain-ui-status.md` (or equivalent):

> Local agent chat is now live with streaming SSE (Sprints 11–13). Conversation history persists in `backend/data/conversations/`. Next: context window (Sprint 14).

---

## What Should Not Be Saved

- Intermediate TypeScript error messages (transient, already fixed).
- The full AgentPage.tsx diff (too large, code is the source of truth).
- Ollama model weights or local data files.
- Any `.env` values or vault path contents.

---

## Next brain / ingest command

Once you've reviewed this file, drop it into Raw Inbox or run:

```powershell
# Option A — ingest via Raw Inbox UI (recommended)
# Drag docs/ai-sessions/2026-06-02_brain-ui-sprints-10-13-local-agent-streaming.md
# into the Brain UI Raw Inbox, approve the proposal, route + sync.

# Option B — direct brain ingest (if brain CLI supports it)
brain sync-raw
```

`Needs manual confirmation` — exact brain ingest command depends on your vault's raw intake flow.
