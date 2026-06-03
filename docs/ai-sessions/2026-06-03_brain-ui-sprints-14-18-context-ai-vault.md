# Session Summary: Brain UI — Context Window, AI Classification, Vault Pages (Sprints 14–18)

Date: 2026-06-03
Tool: Claude Code (claude-sonnet-4-6)
Project: JARVIS / Brain UI (`D:\Hasnain\Personal\dev\JARVIS`)

---

## Goal

Implement five backend + frontend sprints building on the completed streaming local agent:

- **Sprint 14:** Bounded conversation context window — send last N user/assistant messages to Ollama
- **Sprint 15:** Local AI classification for Raw Inbox staged files — single-row AI classify button
- **Sprint 16:** Batch AI classification — select multiple proposals, AI classify selected
- **Sprint 17:** Read-only vault backfill — Projects, Courses, Hackathons, Business, Resume, Backfill pages wired to real vault data
- **Sprint 18:** Tasks page — read `ops/task-db.md` or `ops/tasks.md`, parse Markdown tables and checklists, client-side filters

---

## Context

- Continuing from `2026-06-02_brain-ui-sprints-10-13-local-agent-streaming.md`, which completed streaming SSE responses.
- All sprint work is **working tree changes only** — no new commits made. All changes remain unstaged.
- The backend (`backend/`) and `src/lib/api.ts` remain untracked (no commits since initial session).
- Stack unchanged: React 18 + Vite 5 + TypeScript + Zustand (frontend); FastAPI + Pydantic v2 + Uvicorn (backend); Ollama for local LLM.

---

## Files Changed

### New backend files

| File | Sprint | What changed |
|---|---|---|
| `backend/app/classify_ai.py` | 15 | New: Ollama-based file classifier; strict JSON validation; `ai_classify_file()`; `temperature=0.05`; allowlists for domain/sourceType/confidence/destination |
| `backend/app/vault.py` | 17–18 | New: Read-only vault scanner; `get_vault_summary`, `get_projects`, `get_courses`, `get_hackathons`, `get_business`, `get_ops_file`, `get_tasks`; Markdown table + checklist parser; path safety via `is_relative_to()` |

### Modified backend files

| File | Sprints | What changed |
|---|---|---|
| `backend/app/agent.py` | 14 | `CONTEXT_WINDOW_MESSAGES` env var; `stream_ollama_chat(prior_messages=None)`; `chat_with_agent(prior_messages=None)` — builds `[system] + prior + [user]` message list |
| `backend/app/intake.py` | 15–16 | `Proposal` gains `classified_by`, `ai_model`, `ai_classified_at` slots; `ai_classify_proposal()` (two-phase locking); `batch_ai_classify_proposals()` (three-phase locking — releases lock before Ollama calls) |
| `backend/app/models.py` | 14–18 | `AgentChatResponse` + context metadata fields; `ClassificationProposalResponse` + AI fields; `BatchAiClassifyRequest/Response`; all vault models (`VaultSummaryResponse`, `VaultProjectItem`, `VaultTask`, `VaultTasksResponse`, etc.) |
| `backend/app/main.py` | 14–18 | `_prior_messages()` helper; context metadata in agent endpoints; `ai_classify_proposal` + `batch_ai_classify_proposals` imports/endpoints; 7 vault endpoints (summary, projects, courses, hackathons, business, ops/{kind}, tasks) |

### Modified frontend files

| File | Sprints | What changed |
|---|---|---|
| `src/lib/api.ts` | 14–18 | `AgentChatResponse` + context fields; `StreamMeta` + context fields; `ClassificationProposal` + AI fields; `BatchAiClassifyRequest/Response/SkippedItem`; all vault types; `api.getVaultTasks()`, `api.getVaultProjects()`, etc. |
| `src/pages/AgentPage.tsx` | 14 | `contextInfo` state; `onMeta` captures context window counts; right-rail shows "Context used: X / N msgs"; safety notice updated |
| `src/pages/InboxPage.tsx` | 15–16 | `aiClassifyingId` state + `handleAiClassify`; `ConfirmAiBatchModal`; `showAiBatchConfirm` + `batchAiClassifying` state; `handleBatchAiClassify`; AI button per row; "AI classify selected" in batch action bar; `classifiedBy: local-ai` indicator |
| `src/pages/ProjectsPage.tsx` | 17 | Full rewrite: card grid from `wiki/projects/` + `raw/projects/`; loading/error/empty states; last modified; preview snippet; disabled "Open" placeholder |
| `src/pages/CoursesPage.tsx` | 17 | Same pattern for `wiki/courses/` + `raw/courses/` |
| `src/pages/HackathonsPage.tsx` | 17 | Same pattern for `wiki/projects/hackathons/` + `raw/hackathons/` |
| `src/pages/BusinessPage.tsx` | 17 | Card grid for `wiki/business/` + `raw/business/` |
| `src/pages/ResumePage.tsx` | 17 | Ops file preview panel for `ops/resume-pipeline.md` |
| `src/pages/BackfillPage.tsx` | 17 | Ops file preview panel for `ops/backfill.md` |
| `src/pages/TasksPage.tsx` | 18 | Full rewrite: loads `/api/vault/tasks`; Markdown table + checklist display; status/priority/area/search filters (client-side); parse mode badge; preview fallback |
| `README.md` | 14–18 | Context window section; AI classification section; vault inspection section; tasks section |

---

## Commands Run

```powershell
# Build verification (run after each sprint)
npm run build
# Result all sprints: 85 modules, 0 TypeScript errors

# Python syntax checks (run after each sprint's backend changes)
python -m py_compile backend/app/agent.py backend/app/conversations.py backend/app/models.py backend/app/main.py
python -m py_compile backend/app/classify_ai.py backend/app/intake.py backend/app/models.py backend/app/main.py
python -m py_compile backend/app/vault.py backend/app/models.py backend/app/main.py
# All passed
```

---

## Decisions Made

| Decision | Sprint | Reason |
|---|---|---|
| Context window releases lock before Ollama call | 14 | Ollama can take up to 60s; holding lock would block all staging operations |
| `BRAIN_UI_CONTEXT_WINDOW_MESSAGES` env var, default 10 | 14 | Bounded, configurable, safe fallback on invalid value |
| `classify_ai.py` separate from `classify.py` | 15 | Heuristic classifier is pure/deterministic; AI classifier has external I/O — keep them separate |
| Batch AI classify: three-phase locking | 16 | Read metadata under lock → release → call Ollama N times → re-acquire → single write; minimizes lock contention |
| Approved proposals not eligible for batch AI classify | 16 | Approved items should not be silently changed; require explicit undo/reopen first |
| `batch_ai_classify_proposals` returns HTTP 200 even on partial failures | 16 | Batch operations should be tolerant; skipped items reported in response body |
| `/api/vault/tasks` separate from `/api/vault/ops/{kind}` | 18 | Richer response shape (tasks array, parseMode) can't fit generic ops response model |
| Table parsing tries before checklist | 18 | Tables have more metadata; checklists are fallback for simpler files |
| Parser content capped at 50KB, preview at 2000 chars | 18 | Defense in depth; task files are unlikely to be huge but guard anyway |
| Wiki + raw merge by normalized lowercase name | 17 | Files from `wiki/projects/` and dirs from `raw/projects/` with same stem combined into one card |

---

## Bugs Fixed

**TS2345 — AgentPage functional state updater (carried from Sprint 13, fixed in Sprint 14)**
- Already resolved via `firstTokenRef = useRef(true)` before this session; confirmed in context window sprint build.

No new bugs encountered in this session. All sprints passed build and syntax checks on first attempt.

---

## Tests / Validation

- `npm run build` — 85 modules, 0 TypeScript errors (verified after every sprint).
- Python `py_compile` on all modified backend files — no syntax errors (verified after every sprint).
- No automated test suite exists; functional tests are manual.
- UI was not live-tested in this session (backend server not started during session). Needs manual confirmation.
- Vault parsing logic (`_parse_table_tasks`, `_parse_checklist_tasks`) not unit-tested — `Needs manual confirmation`.

---

## Open Issues

- All changes remain **unstaged and uncommitted** (no commits made since initial session).
- UI not live-tested against a running backend + Ollama + vault.
- Task parser has no unit tests — behavior with edge-case Markdown (frontmatter, nested headers, multi-line cells) is `Needs manual confirmation`.
- `is_relative_to()` requires Python 3.9+; confirmed compatible since codebase already uses 3.9+ syntax.
- "Open in Obsidian" buttons on vault pages are disabled placeholders — deep-link URI not yet wired.
- Batch AI classify calls Ollama sequentially (not concurrently) — could be slow for large batches.

---

## Next Actions

1. **Commit working tree** — all Sprints 9–18 changes are uncommitted.
2. **Live test** — start backend, Ollama (llama3.2), and frontend; verify:
   - Agent context window: ask "my codename is Atlas" then "what codename?" → should recall
   - AI classify (single row): upload a file, click AI → proposal updates
   - Batch AI classify: select multiple rows → AI classify selected
   - Projects/Courses/Hackathons pages load from vault
   - Tasks page parses ops/task-db.md or ops/tasks.md
3. **Sprint 19 options:**
   - A) Vault deep-links — `obsidian://open?vault=...&file=...` URI buttons
   - B) Task editing — safe check/uncheck + status update writes to task-db.md
   - C) File text extraction — send extracted plain text to AI classifier

---

## What Should Go to Obsidian raw/

```
raw/dev/brain-ui/sessions/2026-06-03_brain-ui-sprints-14-18.md
```

Drop this session file into Raw Inbox and route via the standard intake flow.

---

## What Should Go to Obsidian wiki/

None. Architecture and implementation are captured in the code and README.

---

## What Should Go to Obsidian ops/

Consider updating `ops/projects.md` or a Brain UI project note with the current sprint count and status (Sprint 18 complete, 9 sprint types remaining in backlog).

---

## What Should Not Be Saved

- Per-sprint TypeScript/Python error messages (transient, already fixed).
- Full diffs of large files (InboxPage, AgentPage, vault.py) — code is the source of truth.
- Intermediate build outputs.
- Any `.env` values, vault path, or local file system paths beyond what's in README.

---

## Next brain / ingest command

Once you've reviewed this file, ingest it via Raw Inbox or run:

```powershell
# Option A — Raw Inbox UI (recommended)
# Drag docs/ai-sessions/2026-06-03_brain-ui-sprints-14-18-context-ai-vault.md
# into Brain UI Raw Inbox → approve → route → brain sync-raw

# Option B — direct sync (if vault already has it staged)
brain sync-raw
```

`Needs manual confirmation` — exact ingest path depends on your vault's raw folder structure for dev sessions.
