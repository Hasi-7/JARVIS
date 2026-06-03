# Brain UI

Local-first personal AI command center. React + Vite + TypeScript + Tailwind CSS + FastAPI.

## Running the app

### Backend (required for real brain command execution)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Docs at `http://localhost:8000/docs`.

### Frontend

```bash
npm install
npm run dev      # dev server at http://localhost:5173
npm run build    # production build → dist/
npm run preview  # preview production build locally
```

The frontend works without the backend (falls back to mock/localStorage state).
When the backend is running, Dashboard buttons and the ⌘K palette call the real
`brain.cmd` CLI.

## Local agent (Ollama)

Brain UI supports a local chat agent via Ollama. This is **local-agent mode only** — no tools, no vault, no files, no browser, no shell. Responses are text drafts only.

### Setup

1. [Install Ollama](https://ollama.com)
2. Pull a model: `ollama pull llama3.2` (or any model you prefer)
3. Start Ollama: `ollama serve`
4. Set env var before starting the backend:
   ```
   $env:BRAIN_UI_LOCAL_MODEL = "llama3.2"
   $env:BRAIN_UI_OLLAMA_BASE_URL = "http://localhost:11434"  # default
   ```

The backend default model placeholder is `llama3.2`. Set `BRAIN_UI_LOCAL_MODEL` to any model you have installed.

### What the local agent can do

- Answer questions, help plan, draft suggestions
- It does **not** have tools in this mode
- It cannot access files, vault, email, calendar, browser, or shell
- If asked to perform an action, it will explain it can only draft/suggest

### Checking status

`GET /api/agent/status` returns whether Ollama is reachable and whether the configured model is installed.

The Dashboard runtime status panel and Local Agent page both reflect this live.

### Streaming responses

The Local Agent page uses `POST /api/agent/chat/stream` by default. Responses appear token by token as Ollama generates them.

SSE event format:

```
event: meta   data: {"conversationId":"...","provider":"ollama","model":"..."}
event: token  data: {"text":"partial text"}
event: done   data: {"ok":true,"durationMs":123}
event: error  data: {"message":"..."}
```

The non-streaming `POST /api/agent/chat` endpoint remains available as a fallback.

Conversations are saved to disk only after the stream completes successfully. Partial responses from failed streams are not saved.

### Conversation history and context window

Conversations are saved locally under `backend/data/conversations/` — one JSON file per conversation.

**This is not long-term memory.** It is only local backend chat history for the app:

- Conversations survive page refresh and backend restarts.
- Each conversation stores user and assistant messages. The system prompt is never saved as a visible message.
- The last **N** user/assistant messages from the active conversation are sent to the model as context, enabling multi-turn coherence. Default `N = 10`.
- Set `BRAIN_UI_CONTEXT_WINDOW_MESSAGES=<number>` before starting the backend to change the window size. Invalid values fall back to 10.
- **What is NOT sent:** vault contents, staged files, command logs, settings secrets, browser data, Gmail, MCP results, or any other privileged content. Only bounded recent messages from the selected conversation are included.
- Files are never written to the Obsidian vault.
- To clear history: delete files from `backend/data/conversations/` or use the delete button in the UI.

Conversation endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/conversations` | Create a new conversation |
| `GET` | `/api/conversations` | List conversation summaries |
| `GET` | `/api/conversations/{id}` | Get full conversation |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation |

---

## Vault inspection (read-only)

Brain UI can read metadata from your configured Obsidian vault to populate the Work pages.

**What is read:**

| Page | Vault locations scanned |
|---|---|
| Projects | `wiki/projects/*.md`, `raw/projects/*/` |
| Courses | `wiki/courses/*.md`, `raw/courses/*/` |
| Hackathons | `wiki/projects/hackathons/*.md`, `raw/hackathons/*/` |
| Business | `wiki/business/*.md`, `raw/business/*/` |
| Resume Pipeline | `ops/resume-pipeline.md` (preview only) |
| Backfill | `ops/backfill.md` (preview only) |

**Safety:**
- Read-only. No vault files are created, modified, moved, or deleted.
- Previews are limited to the first 2000 characters.
- Path traversal is prevented: all paths are resolved and validated to stay inside the configured vault root.
- Missing folders return empty results, not errors.

**Endpoints:**

```
GET /api/vault/summary       — vault exists + top-level folder presence
GET /api/vault/projects      — project items from wiki/projects + raw/projects
GET /api/vault/courses       — course items from wiki/courses + raw/courses
GET /api/vault/hackathons    — hackathon items
GET /api/vault/business      — business entity items
GET /api/vault/ops/{kind}    — single ops file: resume-pipeline | backfill | tasks
```

**Merge logic:** `.md` files from `wiki/` and subdirectories from `raw/` with the same lowercase name are merged into a single item. Items with wiki notes show a text preview.

**No AI generation occurs.** These pages only reflect what already exists in the vault.

### Tasks page

The Tasks page reads `ops/task-db.md` (priority) or `ops/tasks.md` from the vault and displays a parsed task list.

**Supported formats:**

| Format | Example |
|---|---|
| Markdown table | `\| Title \| Status \| Area \| Priority \| Due \|` … |
| Checklist | `- [ ] Task title` / `- [x] Done task` |
| Preview-only | File exists but cannot be parsed — raw preview shown |

**Column mapping (table format):** `title/task/name`, `status/state`, `area/project/domain`, `priority/pri`, `due/date/deadline`, `source/link` are all recognized.

**Client-side filters:** status, area, priority, text search — all filter without a server round-trip.

**Editing is not yet implemented.** Task editing and creation will be added in a later sprint.

**Endpoint:** `GET /api/vault/tasks` — returns `{path, exists, lastModified, preview, tasks[], parseMode}`.

## What is real now vs still mocked

| Feature | Status |
|---|---|
| Health / config endpoints | **Real** — FastAPI backend |
| brain command execution | **Real** — allowlisted subprocess calls |
| Dashboard "Run today" / "Weekly" | **Real** — calls backend |
| Dashboard "Sync Raw" / "Export Calendar" | **Real** — calls backend |
| ⌘K palette brain commands | **Real** — calls backend |
| Command output panel | **Real** — live output from backend |
| Runtime status: Backend row | **Real** — reflects actual connection |
| Runtime status: Brain CLI row | **Real** — reflects backend config |
| Vault path display | **Real** — from backend config (falls back to localStorage) |
| Raw Inbox — upload / stage files | **Real** — stored in `backend/data/staging/` |
| Raw Inbox — heuristic proposals | **Real** — deterministic filename + MIME classifier |
| Raw Inbox — approve / skip / edit | **Real** — persisted in `backend/data/staging/proposals.json` |
| Raw Inbox — batch approve | **Real** — single lock acquisition |
| Raw Inbox — route to vault | **Real** — `shutil.copy2` into configured vault path |
| Raw Inbox — brain sync-raw | **Real** — calls `brain sync-raw` via allowlisted subprocess |
| Raw Inbox — archive staged original | **Real** — `shutil.move` into `backend/data/archive/` |
| Local Agent — streaming chat | **Real** — SSE via `POST /api/agent/chat/stream` (no tools) |
| Local Agent — non-streaming chat | **Real** — `POST /api/agent/chat` still available as fallback |
| Local Agent / Ollama status | **Real** — `GET /api/agent/status` probes Ollama |
| Local Agent — conversation history | **Real** — persisted in `backend/data/conversations/` after successful stream |
| Dashboard runtime: Local model row | **Real** — reflects Ollama availability |
| OpenClaw | Mocked — not wired |
| NemoClaw / OpenShell | Mocked — not wired |
| Browser harness | Mocked — not wired |
| Computer use | Mocked — not wired |
| MCP gateway | Mocked — not wired |
| Approvals / Escalations / AI Consolidation | Mocked — not wired |

## Brain command allowlist

Only these `brain` subcommands may run through the backend API:

```
doctor  status  vault-path  today  weekly
raw-status  sync-raw  calendar-export  calendar-open
```

Non-allowlisted commands are rejected with HTTP 400. No arbitrary shell
execution is possible.

## Settings and config

Three config layers exist, applied in priority order:

| Layer | How to set | Survives restart? |
|---|---|---|
| Environment variables | `BRAIN_UI_VAULT_PATH`, `BRAIN_UI_BRAIN_CMD` | Yes (process env) |
| Persisted config file | `PUT /api/config` (Settings page) | Yes — written to `backend/data/brain-ui-config.json` |
| Built-in defaults | hardcoded in `config.py` | Always |

**Load order (per field):** env var → config file → default.
Env vars override the file. If the file is missing, defaults are used.
If the file is corrupt, the backend falls back to env/defaults and reports a
warning via `GET /api/config` (`configWarning` field). The corrupt file is not
auto-deleted.

**Frontend localStorage** (`brain-ui.settings`) keeps display/preferences in
sync between page loads. On startup, if localStorage has settings they are
pushed to the backend (which then persists them). If no localStorage settings
exist, the frontend seeds its display from the backend config.

**`GET /api/config`** now also returns:

```json
{
  "configSource":   "env | file | defaults | runtime",
  "configPersisted": true,
  "configWarning":  null
}
```

`configSource` shows where the active config came from. `runtime` means the
config was updated via `PUT /api/config` this session.

## What's built

**App shell**
- Sidebar with grouped nav (Operate / Intake / Work / Control), live badges
- Top command bar: screen title · ⌘K palette trigger · runtime status pills · agent mode dropdown
- `⌘K` / `Ctrl+K` command palette with fuzzy search; brain commands call the real backend

**Dashboard** (hi-fi)
- Header: date, focus line, quick actions (Run today / Weekly / Upload raw) → **real backend calls**
- Count strip: 6 clickable metric tiles
- Main column: Today's plan, Pending approvals (batch), 2-up (command output + recent AI work)
- Right rail: Agent panel (sphere + mode + ask input), Runtime status (Backend/Brain real + others mocked), Quick actions grid
- Command output panel shows **real stdout** from brain commands

**AgentSphere** — all 13 states from DESIGN.md

**Settings** — vault path and brain.cmd path editable, persisted in localStorage

**Stub pages** — all 15 routes beyond Dashboard

## Backend structure

```
backend/
  app/
    main.py       FastAPI app, CORS, all routes
    config.py     env-var overrides + defaults
    models.py     Pydantic request/response models
    brain.py      safe subprocess wrapper
    security.py   allowlist definition
  requirements.txt
  README.md
```

## Stack

| Layer | Choice |
|---|---|
| Build | Vite 5 |
| UI framework | React 18 + TypeScript |
| Styling | Tailwind CSS v3 + CSS custom properties (oklch design tokens) |
| State | Zustand |
| Backend | FastAPI + Uvicorn + Pydantic |
| Fonts | Schibsted Grotesk (UI) · JetBrains Mono (machine data) via Google Fonts |

## File structure

```
src/
  types/index.ts          shared TypeScript types
  data/mock.ts            typed mock data (approvals, plan, etc.)
  lib/
    config.ts             localStorage settings (vault path, brain.cmd)
    api.ts                backend API client (health, config, brain run)
    utils.ts              tone helpers
  store/useAppStore.ts    Zustand store (route, agentState, backend status, cmdLog)
  index.css               design tokens + keyframes
  components/
    ui/                   Icon · AgentSphere · StatusDot · Pill · RiskBadge ·
                          PanelHeader · TagChip · SourceGlyph · ModeBadge ·
                          CommandPalette · EmptyState
    dashboard/            StatusCard · PlanBlock · ApprovalRow · SystemRow
    layout/               AppShell · Sidebar · TopCommandBar
  pages/                  DashboardPage + 15 stubs
  App.tsx                 route switch
  main.tsx                entry point
```

## Raw Inbox intake flow

The complete intake pipeline (end-to-end):

```
Drop files → stage → heuristic proposal → review/edit → approve
  → route to vault → brain sync-raw → archive staged original
```

1. **Upload** — drag and drop files onto the Raw Inbox. Each file is stored in `backend/data/staging/` and a heuristic classification proposal is auto-generated.
2. **Review** — edit the proposal's domain, source type, entity, or destination path. The proposed destination must start with `raw/`.
3. **Approve** — approve individually or select multiple and batch-approve. No files move at this stage.
4. **Route** — click "Route" on an approved item. The backend copies the staged file into `<vaultPath>/<proposedDestination>/` using `shutil.copy2`. The staged original remains in `backend/data/staging/`.
5. **Sync** — click "Run brain sync-raw" in the panel that appears after routing. This calls `brain sync-raw` via the allowlisted subprocess wrapper.
6. **Archive staged original** — after routing (and optionally syncing), click "Archive" on a routed row. A confirmation modal explains what will happen. On confirm, the backend moves the staged original from `backend/data/staging/` to `backend/data/archive/`. The vault copy is untouched.

### Local AI classification

The Raw Inbox can use the local Ollama model to improve heuristic classification proposals.

**How it works:**

1. Upload a file — a heuristic proposal is generated automatically.
2. Click **AI** on any proposed/edited/skipped row.
3. The backend sends metadata only to Ollama: filename, extension, content type, size, stored name, and the existing heuristic proposal. **File contents are never sent.**
4. The model returns a JSON classification proposal.
5. The backend validates all fields strictly against an allowlist. Invalid output is rejected and an error is returned — the existing proposal is not modified.
6. If valid, the proposal is updated with the AI result and marked `classifiedBy: local-ai`.
7. Status is reset to `proposed` — **you still approve before routing.**

**Limitations:**
- Metadata only — no file content, no vault context, no OCR, no PDF parsing.
- Requires Ollama running with `BRAIN_UI_LOCAL_MODEL` set.
- If Ollama is unavailable, the endpoint returns HTTP 503 and the proposal is unchanged.

**Heuristic fallback:**
- The heuristic classifier always runs on upload.
- The AI classifier is optional and triggered manually.
- If AI classification fails, the original heuristic proposal is preserved.

**Safety:**
- No vault writes occur from AI classification.
- `brain sync-raw` is never called automatically.
- No tools are given to the model.
- Destination paths are validated: must start with `raw/`, no `..`, no absolute paths.
- `needsReview` is always forced `true` regardless of model output.

### Archive safety rules

- Only **routed** files can be archived. Proposed, edited, approved, skipped, or missing files are rejected.
- Archive uses `shutil.move` — the file is moved, not deleted.
- Archive files are **never overwritten** — a UUID suffix is appended if a name collision exists.
- The archive destination is always inside `backend/data/archive/`. Path traversal is validated.
- The Obsidian vault copy is never touched by the archive operation.
- `brain sync-raw` is never called automatically by archive.
- `backend/data/` is gitignored. Archive files are local only.

### Backend data layout

```
backend/data/
  staging/
    index.json          active staged file metadata
    proposals.json      all proposals (all statuses, including archived)
    <stored files>      uploaded file copies
  archive/
    <moved files>       staged originals after archive action
```

## Backend structure

```
backend/
  app/
    main.py       FastAPI app, CORS, all routes
    config.py     env-var overrides + defaults
    models.py     Pydantic request/response models
    brain.py      safe subprocess wrapper
    security.py   allowlist definition
    intake.py     staging + proposals + routing + archive
    classify.py   heuristic file classifier (filename + MIME)
  requirements.txt
```

## What's NOT implemented yet

- OpenClaw / NemoClaw / brain CLI calls beyond the allowlist
- AI classification (OpenClaw replaces heuristic classifier)
- Real research runs
- Calendar export UI
- Vault read/write beyond staging
- Gmail / MCP
- Browser harness / computer use
- Backend config file persistence (settings lost on backend restart)
- Archive restore (manual only — files are in `backend/data/archive/`)
- Bulk archive
