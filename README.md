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

Brain UI can read metadata from your configured Obsidian vault to populate the Work pages. The inspection endpoints in this section are read-only; entity creation endpoints intentionally perform the narrow writes documented later.

**What is read:**

| Page | Vault locations scanned |
|---|---|
| Projects | `wiki/projects/*.md`, `raw/projects/*/` |
| Courses | `wiki/courses/*.md`, `raw/courses/*/` |
| Hackathons | `wiki/projects/hackathons/*.md`, `raw/hackathons/*/` |
| Business | `wiki/business/*.md`, `raw/business/*/` |
| Resume Pipeline | `ops/resume-pipeline.md` (structured table) |
| Backfill | `ops/backfill.md` or `ops/backfill-last-year.md` (structured table) |

**Safety:**
- Read-only. No vault files are created, modified, moved, or deleted.
- Previews are limited to the first 2000 characters.
- Path traversal is prevented: all paths are resolved and validated to stay inside the configured vault root.
- Missing folders return empty results, not errors.

**Endpoints:**

```
GET  /api/vault/summary       — vault exists + top-level folder presence
GET  /api/vault/projects      — project items from wiki/projects + raw/projects
GET  /api/vault/courses       — course items from wiki/courses + raw/courses
GET  /api/vault/hackathons    — hackathon items
GET  /api/vault/business      — business entity items
GET  /api/vault/ops/{kind}    — single ops file: resume-pipeline | backfill | tasks

GET  /api/vault/backfill               — structured backfill items from ops/backfill.md (or ops/backfill-last-year.md fallback)
POST /api/vault/backfill/create        — create ops/backfill.md starter (never overwrites)
POST /api/vault/backfill               — append a new backfill row (backup-safe)
PATCH /api/vault/backfill/{id}/status  — update one backfill item's status (backup-safe)
PATCH /api/vault/backfill/{id}         — edit non-status fields: item, type, value, path, agent, notes (backup-safe)

GET  /api/vault/resume-pipeline               — structured resume/application rows from ops/resume-pipeline.md
POST /api/vault/resume-pipeline/create        — create ops/resume-pipeline.md starter (never overwrites)
POST /api/vault/resume-pipeline               — append a new resume row (backup-safe)
PATCH /api/vault/resume-pipeline/{id}/status  — update one resume item's status (backup-safe)
PATCH /api/vault/resume-pipeline/{id}         — edit non-status fields: target, company, role, priority, deadline, link, notes (backup-safe)

GET  /api/vault/escalations               — structured escalation items from ops/escalation-queue.md
POST /api/vault/escalations/create        — create ops/escalation-queue.md starter (never overwrites)
POST /api/vault/escalations               — append a new escalation item (backup-safe)
PATCH /api/vault/escalations/{id}/status  — update one escalation item's status (backup-safe)
PATCH /api/vault/escalations/{id}         — edit non-status fields: task, target, priority, source, path, notes (backup-safe)
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

**Status editing** is available for structured tasks (table and checklist formats). See the [Task Status Editing](#task-status-editing) section below.

**Endpoint:** `GET /api/vault/tasks` — returns `{path, exists, lastModified, preview, tasks[], parseMode}`.

---

## Task status editing

Brain UI supports safe, narrow status updates for structured task files.

### Supported formats

| Format | Editing behavior |
|--------|-----------------|
| Markdown table | Status dropdown per row (`todo` / `in progress` / `blocked` / `done`) |
| Checklist | Checkbox toggle per item (done ↔ todo) |
| Preview-only | No editing — message shown |

### Allowed statuses

`todo` · `in progress` · `blocked` · `done`

Only the status field is editable in this sprint. Title, area, priority, due, and source are read-only.

### Write safety

Every status edit follows this sequence before touching any file:

1. **Re-read** the task file from disk (no stale state).
2. **Re-parse** to locate the exact target line.
3. **Conflict check** — verify the task's title still matches the expected value at that line position. If the file changed since the page last loaded, the write is rejected.
4. **Backup** — create a timestamped copy under `backend/data/backups/tasks/` (e.g. `task-db_20260603_142233_ab12.md`). The write is aborted if the backup fails.
5. **Write** — replace only the status cell (table) or checkbox marker (checklist). All other content is preserved exactly.

If any step fails, the file is **not modified** and an error is returned to the UI.

### Backups

Backups are stored locally under `backend/data/backups/tasks/`. They are never overwritten (random suffix ensures uniqueness). They are **not** synced to the vault and are excluded from git.

There is no backup manager UI in this sprint. To restore a backup, copy it manually over the task file.

### Confirmation UX

Clicking a status dropdown or checkbox does not write immediately. A confirmation dialog appears showing:

- Task title
- Old status → new status
- File path
- Backup notice

User must click **Apply** to write. **Cancel** discards the change.

### Endpoint

```
PATCH /api/vault/tasks/{taskId}/status
Body: { "status": "todo | in progress | blocked | done" }
Response: { "ok": true, "task": {...}, "path": "ops/...", "updatedAt": "..." }
```

Errors return HTTP 400 with a descriptive message. The file is never modified on error.

### What is NOT editable yet

- Task title
- Area, priority, due date, source
- Adding new tasks
- Deleting tasks
- Bulk status changes

---

## Obsidian deep-links

Brain UI generates `obsidian://open` deep-links so you can jump from the UI directly into the canonical Obsidian note. This is **read-only navigation only** — no vault writes occur when you click a link.

### Requirements

- Obsidian must be installed on the machine.
- The Obsidian URI handler must be registered (Obsidian registers it automatically on Windows/macOS/Linux during installation).
- The vault must be open in Obsidian (or Obsidian must be set to open the vault on URI activation).

### URI format

```
obsidian://open?vault=<vaultName>&file=<vault-relative-path>
```

- `vaultName` is derived automatically from the last path segment of your configured vault root. For example, if your vault path is `D:\...\AI-Command-Center`, the vault name is `AI-Command-Center`.
- `file` is the vault-relative path to the note (e.g. `wiki/projects/My Project.md`). Backslashes are normalized to forward slashes. Both values are URL-encoded.

**Example:**

```
Vault path:  D:\Hasnain\...\AI-Command-Center
Note path:   wiki/projects/JARVIS.md

URI: obsidian://open?vault=AI-Command-Center&file=wiki%2Fprojects%2FJARVIS.md
```

### Where links appear

| Page | Link shown when |
|------|----------------|
| Projects | Card has a `wikiPath` (wiki note exists in vault) |
| Courses | Card has a `wikiPath` |
| Hackathons | Card has a `wikiPath` |
| Business | Card has a `wikiPath` |
| Resume Pipeline | `ops/resume-pipeline.md` exists in vault |
| Backfill | `ops/backfill.md` exists in vault |
| Tasks | `ops/task-db.md` or `ops/tasks.md` exists in vault |

Cards that only have a `rawPath` (raw folder exists but no wiki note) show a disabled **Raw folder** placeholder — no link is generated because Obsidian's URI scheme is for notes, not folders.

### No vault writes

Clicking "Open note" or "Open in Obsidian" does **not** write, modify, or delete any vault files. The link is a browser-level URI handoff to the Obsidian desktop application.

### Frontend utility

Deep-link generation is implemented in `src/lib/obsidian.ts`:

```ts
// Extracts the vault name from the last path segment
getVaultNameFromPath(vaultPath: string): string

// Builds a safe obsidian://open URI from a vault-relative file path
createObsidianOpenUrl(vaultPath: string, relativeFilePath: string): string
```

Both helpers accept Windows backslashes and forward slashes. Only paths returned by the backend are used — no user input reaches path construction.

---

## Dashboard real metrics

The Dashboard page calls `GET /api/dashboard/summary` on mount and on manual refresh. This endpoint aggregates counts from all major vault systems in a single backend round-trip.

### Summary endpoint

```
GET /api/dashboard/summary
```

**Read-only.** No files are written, no brain commands run, no Ollama chat called, no vault mutations occur.

**Aggregated sections:**

| Section | Source |
|---|---|
| `raw.staged` | Count of files in `backend/data/staging/` |
| `raw.proposed/edited/approved/routed/archived` | Proposal status counts |
| `tasks.total/todo/inProgress/blocked/done` | Parsed `ops/task-db.md` or `ops/tasks.md` |
| `calendar.total/approved/pending` | Parsed `ops/calendar-candidates.md` (pending = Approved ≠ Yes) |
| `entities.projects/courses/hackathons/business` | Wiki + raw folder scanner counts |
| `backfill.total/new/triaged/inProgress/done/skipped` | Parsed `ops/backfill.md` |
| `resume.total/new/tailoring/applied/interview/offer/rejected/archived` | Parsed `ops/resume-pipeline.md` |
| `runtime.brain` | `available` if `brain.cmd` path exists; `unavailable` otherwise |
| `runtime.agent` | `available` if Ollama is reachable and model is installed; `unavailable` otherwise |
| `runtime.vaultExists` | `true` if configured vault path is a directory |
| `activeWork.backfill[]` | Up to 3 active backfill items (new/triaged/in-progress), sorted by status urgency then value |
| `activeWork.escalations[]` | Up to 3 active escalations (new/ready/in-progress/blocked), sorted blocked first then priority |
| `activeWork.resume[]` | Up to 3 active resume items (new/tailoring/applied/interview), sorted interview first then priority |
| `activeWork.calendar[]` | Up to 3 unapproved calendar candidates, sorted by date |
| `activeWork.raw[]` | Up to 3 pending raw proposals (proposed/edited), edited first |
| `errors[]` | Partial-failure log — one entry per subsystem that fails |

**Partial failure handling:** if one subsystem fails, its section is zeroed and an entry is appended to `errors`. Other sections still load. The endpoint never returns a 500.

### Dashboard Active Work panel

The Dashboard **Active Work** panel shows compact read-only lists of items that need attention across five workflows: Backfill, Escalations, Resume Pipeline, Calendar, and Raw Inbox.

- Each group shows up to 3 items with a status chip, priority indicator, and secondary metadata.
- Clicking any item or "View all" navigates to the dedicated workflow page.
- **Limited quick actions:** Backfill and Escalation items show a **Mark done** action that sets their status to `done` directly from the Dashboard. Every action requires a confirmation modal, runs through the existing backup-before-write status endpoints (`PATCH /api/vault/backfill/{itemId}/status` and `PATCH /api/vault/escalations/{itemId}/status`), and reloads the Dashboard summary on success. On failure the error is shown and the Dashboard stays usable.
  - No other Dashboard quick actions exist. There are **no** quick actions for Raw Inbox, Calendar Candidates, Resume Pipeline, or Tasks.
  - No approvals, task edits, calendar changes, deletes, bulk actions, AI calls, or external tool launches happen from the Dashboard — only the two safe `done` status updates above.
- Empty state: if all lists are empty, "No active work items found." is shown.
- Partial errors: if one source fails, its list is empty and an error is appended to `errors[]`. Other groups still render.
- The panel respects the same loading/error behavior as the rest of the dashboard summary.

### Dashboard Recent AI Work deep-links

The Dashboard **Recent AI Work** panel lists up to 5 recent Local Agent conversations (summaries only — from `GET /api/conversations`).

- Clicking a conversation row opens **Local Agent** with that exact conversation selected and its messages loaded (`GET /api/conversations/{conversationId}`).
- This is **read-navigation only**: opening a conversation does not call Ollama, does not send or generate a message, and does not mutate, rename, or delete any conversation.
- Navigation is app-state-based (the app has no URL router): the Dashboard hands off the conversation id via store state, and AgentPage consumes it on mount. The header chevron still opens Local Agent without a selection.
- If the requested conversation no longer exists, AgentPage shows a clear error and stays usable — the conversation list is still shown so the user can pick another or start a new one. A missing/blank id falls back to opening Local Agent normally.
- The Dashboard only ever fetches conversation **summaries**; full message bodies are loaded by AgentPage, not the Dashboard.

### Dashboard metric wiring

| Count strip tile | Source |
|---|---|
| Approvals | `raw.proposed + raw.edited + calendar.pending` |
| Raw pending | `raw.staged` |
| Escalations | Always `0` — not wired |
| Calendar | `calendar.pending` |
| Backfill | `backfill.new + backfill.triaged + backfill.inProgress` |
| Resume | `resume.new + resume.tailoring + resume.applied + resume.interview` |

### Today's plan — deterministic task selection

The Dashboard Today's plan panel shows up to 5 active tasks derived from the vault task file using deterministic priority bucketing. No AI planning or scheduling is involved.

**Selection order:**

1. Blocked tasks
2. In-progress tasks
3. Tasks due today or overdue (parsed from the `due` field)
4. High-priority tasks
5. Remaining open/todo tasks

**Exclusions:** done, completed, archived, closed tasks are never shown.

**Reason labels:** each item carries a plain-text reason — `Blocked`, `In progress`, `Due today`, `Overdue`, `High priority`, `Open task`.

**Date parsing:** common formats are tried (`YYYY-MM-DD`, `DD-MM-YYYY`, etc.). Parsing failures do not crash the endpoint.

**Failure isolation:** if the task file cannot be parsed, `todayPlan.items` is empty and an error entry is added to `errors[]`. The rest of the dashboard summary still loads.

**No AI planning, no scheduling, no automation.** This is a deterministic read-only view of existing tasks.

### Recent AI work — local conversation history

The Dashboard "Recent AI work" panel loads from `GET /api/conversations` independently of the main dashboard summary. It shows up to 5 conversations sorted by `updatedAt` descending, with title, message count, and a relative timestamp.

- Clicking a row navigates to the Local Agent page (deep-linking to a specific conversation is deferred — AgentPage uses local component state for `convId`).
- Empty, loading, and failed states are handled independently.
- **No AI or summarization involved.** Titles are whatever the conversation was saved with; counts and timestamps are raw metadata.

### Planned runtimes — shown honestly as "Not wired"

The Dashboard runtime panel separates **real, backend-derived status** (Backend, Brain CLI, Vault, Local model) from **planned PRD runtimes that are not implemented**. The planned runtimes are displayed under a "Planned — not wired yet" divider with neutral/grey styling and a `Not wired` status label — they are **never shown as ready/connected/partial**.

| Section | Status |
|---|---|
| OpenClaw tool bridge, NemoClaw/OpenShell, Browser harness, Computer use, MCP gateway | **Not wired** — displayed honestly as planned, neutral styling, no fake "ready" state |

### Current real safety controls

The **Tool Safety** page distinguishes planned runtimes (shown as "Not wired") from what is actually enforced today. The real, code-backed controls are:

- Safe `brain` command allowlist (no arbitrary commands)
- No arbitrary shell execution
- Backup-before-write on every vault write workflow
- No external tool launches
- No Gmail mutations (no email integration at all)
- No Google Calendar API writes (`.ics` export only)
- No browser / computer-use actions
- Local agent has no tools (chat only)

NemoClaw/OpenShell, OpenClaw tool bridge, Browser, Computer use, MCP, Gmail, Research, and Chat/AI Consolidation are **not wired** in this build. The UI no longer presents any of them as ready, connected, or enforcing.

---

## What is real now vs still mocked

| Feature | Status |
|---|---|
| Health / config endpoints | **Real** — FastAPI backend |
| brain command execution | **Real** — allowlisted subprocess calls |
| Dashboard "Run today" / "Weekly" | **Real** — calls backend |
| Dashboard "Sync Raw" / "Export Calendar" | **Real** — calls backend |
| ⌘K palette brain commands | **Real** — calls backend |
| Command output panel | **Real** — live output from backend |
| Dashboard count strip | **Real** — `GET /api/dashboard/summary` |
| Dashboard pending approvals panel | **Real** — raw proposal + calendar candidate counts |
| Dashboard entity counts | **Real** — wiki/raw scanner counts |
| Dashboard runtime: Backend, Brain CLI, Vault, Local model | **Real** — backend-derived status |
| Runtime status: Backend row | **Real** — reflects actual connection |
| Runtime status: Brain CLI row | **Real** — reflects `brain.cmd` path existence |
| Runtime status: Vault row | **Real** — reflects vault path existence |
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
| Tasks page — read | **Real** — reads `ops/task-db.md` or `ops/tasks.md`, parses table/checklist |
| Tasks page — status edit | **Real** — `PATCH /api/vault/tasks/{id}/status`, backup + conflict detection |
| Tasks page — create task | **Real** — `POST /api/vault/tasks`, appends row to task file, backup before write |
| Calendar page — candidates read | **Real** — reads `ops/calendar-candidates.md`, parses Markdown tables |
| Calendar page — starter/create | **Real** — creates missing `ops/calendar-candidates.md` only by explicit button |
| Calendar page — add candidate | **Real** — appends one candidate row after creating a backup |
| Calendar page — edit / approve | **Real** — updates one candidate row after creating a backup |
| Calendar page — export/open | **Real** — calls allowlisted `brain calendar-export` / `brain calendar-open` manually |
| Projects / Courses / Hackathons — create | **Real** — calls safe entity-specific `brain new-*` endpoints |
| Business — create | **Real** — creates safe wiki note, raw folder, and pipeline row |
| Backfill page — structured table | **Real** — reads `ops/backfill.md`, parses Markdown table |
| Backfill page — status edit | **Real** — `PATCH /api/vault/backfill/{id}/status`, backup + conflict detection |
| Backfill page — create starter file | **Real** — `POST /api/vault/backfill/create`, never overwrites existing |
| Backfill page — add item | **Real** — `POST /api/vault/backfill`, appends row to `ops/backfill.md`, backup before write |
| Backfill page — field edit | **Real** — `PATCH /api/vault/backfill/{id}`, edits non-status fields, backup + conflict detection |
| Backfill page — closeout prompt | **Real** (frontend only) — generates prompt, copies to clipboard, no agent launched |
| Resume Pipeline page — structured table | **Real** — reads `ops/resume-pipeline.md`, parses Markdown table |
| Resume Pipeline page — create starter file | **Real** — `POST /api/vault/resume-pipeline/create`, never overwrites existing |
| Resume Pipeline page — add item | **Real** — `POST /api/vault/resume-pipeline`, appends row to `ops/resume-pipeline.md`, backup before write |
| Resume Pipeline page — status edit | **Real** — `PATCH /api/vault/resume-pipeline/{id}/status`, backup + conflict detection |
| Resume Pipeline page — field edit | **Real** — `PATCH /api/vault/resume-pipeline/{id}`, edits non-status fields, backup + conflict detection |
| Resume Pipeline page — tailoring prompt | **Real** (frontend only) — generates tailoring prompt, copies to clipboard, no AI called |
| Dashboard Recent AI work | **Real** — `GET /api/conversations`, up to 5 latest conversations (summaries only). Rows deep-link into Local Agent with that conversation selected (`GET /api/conversations/{id}`); read-navigation only — no AI call, no mutation |
| Dashboard Active Work panel | **Real** — `activeWork` section of `GET /api/dashboard/summary`; up to 3 items per workflow. Read-only except a **Mark done** quick action on Backfill and Escalation items (confirmation modal → existing backup-before-write status endpoint → reload) |
| Escalation Queue — read | **Real** — `GET /api/vault/escalations`, parses `ops/escalation-queue.md` |
| Escalation Queue — create file | **Real** — `POST /api/vault/escalations/create`, creates starter if missing |
| Escalation Queue — add item | **Real** — `POST /api/vault/escalations`, appends row with backup |
| Escalation Queue — status edit | **Real** — `PATCH /api/vault/escalations/{id}/status`, status cell only with backup |
| Escalation Queue — field edit | **Real** — `PATCH /api/vault/escalations/{id}`, edits non-status fields, backup + conflict detection |
| Escalation Queue — copy handoff prompt | **Real** (frontend only) — copies prompt to clipboard, no process launched |
| Dashboard Escalations count | **Real** — `summary.escalations.active` (new + ready + in-progress + blocked) |
| Proposal Queue page | **Real (read-only)** — `GET /api/proposals` aggregates Raw Inbox classification proposals, Chat/AI Consolidation drafts, **and** Research drafts into a normalized shape; lists/filters/searches only. No approve/apply here — actions **deep-link to the exact source item** (Open in Raw Inbox / Consolidation / Research, which highlight the related row/draft) |
| Chat/AI Consolidation — manual paste/import | **Real v1** — paste a transcript → `POST /api/consolidation/drafts` creates a backend draft (no vault write); edit summary fields; **Save to vault** writes one Markdown summary under `raw/chats/<source>/`. No AI, no brain, no browser/computer-use capture |
| Research — manual capture | **Real v1** — capture notes/links/findings → `POST /api/research/drafts` creates a backend draft (no vault write); edit fields; **Save to vault** writes one Markdown note under `raw/research/<topic>/`. No AI, no URL fetch, no web search, no browser/computer-use |
| OpenClaw tool bridge | **Not wired** — read-only readiness via `GET /api/runtime/status` (status `not_configured`); no bridge, no execution |
| NemoClaw / OpenShell | **Not wired (probe + policy inspection + readiness + bridge-contract dry-run only)** — read-only readiness via `GET /api/runtime/status`; an explicit opt-in reachability probe (`POST /api/runtime/probe/nemoclaw`) can check a configured *local* runtime URL; a read-only policy inspection (`GET /api/runtime/policy/nemoclaw`) summarizes the configured policy file; a read-only **Guardrail Readiness** correlation (`GET /api/runtime/guardrail-readiness`) reports whether the system is ready for future *bridge design* (`ready_for_bridge_design` ≠ execution-ready); a **Bridge Contract Validator** (`POST /api/runtime/bridge/validate`) dry-run-validates a proposed future bridge request (shape + mode + readiness + permission-gateway dry-run) and executes nothing. All unlock nothing, start no runtime, run no fresh probe, and enforce no policy; dependents stay blocked |
| Browser harness | **Not wired** — `disabled`/blocked while NemoClaw/OpenShell is unavailable (shown via `GET /api/runtime/status`) |
| Computer use | **Not wired** — `disabled`/blocked while NemoClaw/OpenShell is unavailable (shown via `GET /api/runtime/status`) |
| MCP gateway | **Not wired** — read-only readiness via `GET /api/runtime/status` (status `not_configured`) |
| Research — browser/computer-use automation | **Not wired** — browser research, web search, and computer-use capture remain planned; v1 is manual capture only |
| Chat/AI Consolidation — browser/computer-use capture | **Not wired** — automatic capture from ChatGPT/Claude web and computer-use remain planned; v1 is manual paste/import only |
| Agent modes | **Enforced (v0) + globally visible** — backend policy gates tool-request evaluation. Locked/Observe/Computer-Use block evaluation; Draft/Assist/Research/Escalation allow evaluate-only; only Assist offers the Review-in-Tool-Connections handoff. The selected mode + its policy is shown in the top bar and on the Dashboard. No mode executes tools from chat |
| Tool / action log (`ops/tool-logs/`) | **Not wired** — planned; no agent tools run, so nothing to log |

## Research (v1 — manual capture)

Captures research by hand — notes, links, source snippets, and findings — into one structured Markdown note in the vault. The PRD's Research Mode ultimately uses a browser harness; v1 is **manual capture only** with no browser automation, web search, URL fetching, computer-use, MCP, or AI.

### Flow

```text
manual notes / links / source snippets → structured draft → preview destination
→ user confirms → backend writes one Markdown research note to raw/research/<topic>/
```

### Endpoints (`backend/app/research.py`)

- **`POST /api/research/drafts`** — create a draft from manually captured fields. Stores backend metadata only (`backend/data/research/drafts.json`); **no vault write**. Requires a non-empty `title` and at least one of `rawNotes` / `summary` / a key finding. `domain` ∈ {project, course, business, personal, technical, market, general, unknown}. Path-traversal markers in `title`/`topic`/`entity` are rejected.
- **`GET /api/research/drafts`** — list drafts, newest first.
- **`GET /api/research/drafts/{id}`** — read one draft.
- **`PATCH /api/research/drafts/{id}`** — edit `title`, `topic`, `domain`, `entity`, `researchQuestion`, `summary`, `keyFindings`, `sources`, `openQuestions`, `recommendedNextActions`, `rawNotes`. `id`, `createdAt`, `updatedAt`, `status`, and `savedPath` are locked.
- **`POST /api/research/drafts/{id}/save`** — write **one** Markdown note to `raw/research/<slug(topic|title)>/<YYYY-MM-DD>-<slug(title)>.md`, mark the draft `saved`, store `savedPath`.

### Safety constraints

- Pasted notes and source snippets are treated as **untrusted external content**: stored and embedded only (raw notes inside a fenced block widened past any backticks). Never executed, **never fetched**, never sent to an LLM, never interpreted as instructions.
- Save writes exactly one file, **never overwrites** (UUID suffix on collision), must stay under `raw/research/`, and can never escape the vault root (traversal rejected).
- Saving does **not** run `brain`, call AI, fetch URLs, or create tasks/calendar/resume rows.
- Unsaved drafts appear in the **Proposal Queue** as `research` proposals (status `pending`); saved drafts show as `applied`. The Proposal Queue only navigates to this page — it never saves.

## Chat/AI Consolidation (v1 — manual paste/import)

Captures useful work from ChatGPT, Claude, Claude Code, and OpenCode into the Obsidian vault so it does not get lost. v1 is **manual paste/import only** — there is no browser automation, computer-use, or MCP capture.

### Flow

```text
paste transcript → classify source/domain/entity → review/edit summary, decisions, action items
→ preview destination → user confirms → backend writes one Markdown summary to raw/chats/<source>/
```

### Endpoints (`backend/app/consolidation.py`)

- **`POST /api/consolidation/drafts`** — create a draft from a pasted transcript. Stores backend metadata only (`backend/data/consolidation/drafts.json`); **no vault write**. If no summary is supplied, a conservative deterministic preview is generated (no AI). Requires non-empty `conversationTitle` and `transcript`; `sourceTool` ∈ {chatgpt, claude, claude-code, opencode, other}; `domain` ∈ {project, course, business, research, personal, unknown}.
- **`GET /api/consolidation/drafts`** — list drafts, newest first.
- **`GET /api/consolidation/drafts/{id}`** — read one draft.
- **`PATCH /api/consolidation/drafts/{id}`** — edit `conversationTitle`, `domain`, `entity`, `summary`, `decisions`, `actionItems`, `codeOrFilesReferenced`. `id`, `createdAt`, `sourceTool`, `transcript`, `status`, and `savedPath` are locked.
- **`POST /api/consolidation/drafts/{id}/save`** — write **one** Markdown summary under `raw/chats/<sourceTool>/<YYYY-MM-DD>-<slug>.md`, mark the draft `saved`, store `savedPath`.

### Destination mapping

```text
chatgpt → raw/chats/chatgpt/     claude → raw/chats/claude/
claude-code → raw/chats/claude-code/   opencode → raw/chats/opencode/   other → raw/chats/other/
```

### Safety constraints

- The transcript is treated as **untrusted external content**: it is only stored and embedded in a fenced code block (the fence is widened past any backticks in the text). It is never executed, never sent to an LLM, and never interpreted as instructions.
- Save writes exactly one file, **never overwrites** (UUID suffix on collision), and the resolved path can never escape the vault root (traversal rejected; the destination directory is derived only from the validated `sourceTool`).
- Saving does **not** run `brain`, call AI, or create tasks/calendar/resume rows automatically.
- Unsaved drafts appear in the **Proposal Queue** as `chat-consolidation` proposals (status `pending`); saved drafts show as `applied`. The Proposal Queue only navigates to this page — it never saves.

## Email Intake (v0 — manual paste/import)

The **Email Intake** page (nav: Intake → Email Intake) is the PRD's **manual fallback** for Gmail/email intake (§33) while Gmail stays disconnected. The user pastes raw email content, reviews/edits the extracted fields, and explicitly saves one Markdown summary into the vault. **Gmail MCP is not wired**; there is no email search/read and **all Gmail mutations (send/delete/archive/labels) are disabled**. No AI is called.

```text
paste email content → create structured draft → review/edit fields → Save to vault → one Markdown file under an allowed raw email path
```

### Endpoints (`backend/app/email_intake.py`)

- **`POST /api/email-intake/drafts`** — create a draft (backend JSON only at `backend/data/email-intake/drafts.json`, **no vault write**). Requires non-empty `subject` and `rawEmail`; validates `domain` and `confidence`; missing summary → conservative deterministic fallback (subject + body preview, no AI).
- **`GET /api/email-intake/drafts`** / **`GET /api/email-intake/drafts/{id}`** — list (newest first) / read.
- **`PATCH /api/email-intake/drafts/{id}`** — edit `subject/sender/receivedAt/domain/entity/summary/actionRequired/dueDate/confidence/proposedTaskRows/proposedCalendarRows`. Locked: `id/createdAt/updatedAt/status/savedPath/rawEmail`.
- **`POST /api/email-intake/drafts/{id}/save`** — write **one** Markdown summary, mark `saved`, store `savedPath`.

### Destination mapping

| Domain (+entity) | Path |
|---|---|
| `course` (with or without entity) | `raw/quercus/emails/` |
| `business` + entity | `raw/business/<slug-entity>/emails/` |
| `business` no entity | `raw/business/unknown/emails/` |
| `personal` | `raw/personal/email/` |
| `unknown` | `raw/inbox/email/` |

Filename: `<date>-<slug-subject>.md`. The only variable path component (business entity) is **slugified**, so caller input cannot introduce traversal.

### Safety constraints

- No Gmail API/MCP/auth, no email search/read, **no Gmail mutation** (send/delete/archive/labels), no browser/computer-use, no MCP, no AI.
- Email content is **untrusted**: stored and embedded in a widened fenced code block only — never executed, never sent to an LLM, never interpreted as instructions.
- Save writes exactly one file under an **allowlisted raw email path**, **never overwrites** (UUID suffix on collision), never escapes the vault root (traversal rejected), and **never creates tasks/calendar rows** or runs `brain`. Proposed task/calendar rows are **informational only** in v0.
- Unsaved drafts appear in the **Proposal Queue** as `email-intake` / `email_summary` proposals (status `pending`; saved → `applied`); the queue only navigates here via **Open in Email Intake** and never saves.

## Proposal Queue (v1)

The Proposal Queue is the first piece of the generalized **propose → preview → approve → apply** spine the PRD requires before Research Mode, Chat/AI Consolidation, Gmail intake, MCP tools, and OpenClaw tool requests are built. It gives the app one consistent surface to review proposed changes and distinguish `pending` / `approved` / `applied` / `skipped` / `rejected`.

### What it is

- **`GET /api/proposals`** — a thin, **read-only** aggregation layer (`backend/app/proposals.py`) that normalizes proposal-like items into a single shape.
- Aggregates **Raw Inbox classification proposals**, **Chat/AI Consolidation drafts**, **Research drafts**, and **Email Intake drafts**. Each source contributes independently — a failing source yields an error entry, not a failed request.
- The frontend **Proposal Queue** page (`src/pages/ProposalsPage.tsx`) shows total / pending / applied / skipped-rejected counts, filters (status, type, source, confidence, search), and a card per proposal (title, source, type, status, risk, confidence, target path, summary, key details).

### Normalized shape

Each item has: `id`, `source`, `type`, `riskLevel`, `title`, `summary`, `status`, `confidence`, `targetPath`, `createdAt`, `updatedAt`, `relatedId`, `actions[]`, and a `details` object (`filename`, `domain`, `entity`, `sourceType`, `reason`).

Raw Inbox intake status maps to the generalized status as: `proposed`/`edited` → `pending`, `approved` → `approved`, `routed` → `applied`, `archived` → `applied`, `skipped` → `skipped`.

### Actions

Actions **deep-link to the exact source item** — **Open in Raw Inbox**, **Open in Consolidation**, **Open in Research**, or **Open in Email Intake** — where the existing approve / edit / route / save flow continues unchanged. The clicked item is highlighted (and scrolled into view) on the source page via an app-state handoff (`proposalTarget` in the zustand store, mirroring `agentConvTarget`); the page consumes and clears the target on mount and shows an unobtrusive "Opened from Proposal Queue." notice. A missing/deleted target falls back to plain page navigation with a non-blocking notice. **There is no approve/apply/save button in the Proposal Queue** — it is a read-only, shared review surface that does not duplicate or increase mutation power.

### Safety constraints

- `GET /api/proposals` is **read-only**: listing never approves, routes, writes vault files, writes intake metadata, runs `brain`, or calls Ollama.
- A failing proposal source contributes an error entry and an empty contribution (the rest of the queue still loads) rather than failing the whole request.
- Existing Raw Inbox approval/routing behavior is untouched.

### Future sources

MCP tools and Agent proposals should all plug into this same normalized queue as they are wired (by extending `list_normalized_proposals()`). Raw Inbox, Chat/AI Consolidation, Research, and Email Intake already do.

## Tool Connections (v0 — read-only readiness)

The **Tool Connections** page (nav: Control → Tool Connections) is an **honest status/config readiness surface** for the privileged tool systems the PRD plans (§13, §31, §32, §33). It exists so the user can see — before any privileged integration is built — that everything privileged is still unavailable.

It is **read-only status/config inventory only**. It makes **no MCP/Gmail/browser/computer-use calls**, no Google/GitHub/Drive API calls, runs no shell commands, never invokes `brain`, reads no credentials, and launches/executes no tool.

### Endpoint (`backend/app/tools.py`)

- **`GET /api/tools/status`** → `{ items: ToolConnectionStatus[] }` — a static, read-only inventory. Each item: `id`, `name`, `category`, `status`, `enabled`, `riskLevel`, `capabilities[]`, `allowedNow[]`, `blockedNow[]`, `requires[]`, `lastCheckedAt`, `lastError`, `notes`.
- **Status values:** `available` · `unavailable` · `not_configured` · `disabled` · `planned` · `error`. Nothing is reported `available` — no real check runs in this build, so privileged systems are `not_configured`, `planned`, or `disabled`.
- **Categories:** `runtime` (Agent Runtime), `mcp` (MCP), `browser` (Browser / Computer Use), `external` (External Services), `developer` (Developer Tools).

### Tool systems listed

`obsidian-mcp`, `gmail-mcp`, `google-calendar-api`, `browser-harness`, `computer-use`, `openclaw`, `nemoclaw-openshell`, `github`, `google-drive`, `graphify`.

- **Gmail** is shown not connected; search/read/intake are planned through the backend gateway and **all mutations (send/delete/archive/labels) are listed as blocked**.
- **Obsidian MCP** is not connected; current vault workflows use the **filesystem adapter and backup-before-write** protections.
- **Browser harness / Computer Use** are **disabled** until NemoClaw/OpenShell (or equivalent runtime safety) is wired.
- **OpenClaw / NemoClaw/OpenShell** are **planned** runtime layers; current Local Agent chat has no tools.

### Page UI & actions

Cards grouped by category, each with a status badge, risk badge, enabled/disabled indicator, capabilities, allowed-now, blocked-now, requirements, and notes. The only live actions are **Refresh status** and **Settings** navigation. There is **no** Connect / Enable / Authenticate / Test / Launch action — the per-card control is clearly disabled and labelled **"Not wired yet."**

### Safety constraints

- `GET /api/tools/status` is read-only and performs no external calls, no shell, no `brain`, no credential reads, and no tool execution.
- `list_tool_connections()` returns fresh copies, so callers cannot mutate the inventory.
- Privileged integrations (MCP, Gmail, browser, computer-use, Google Calendar/Drive, GitHub, OpenClaw, NemoClaw/OpenShell) remain **not wired**.

## Permission Gateway (v0 — deny-by-default classification)

The **Permission Gateway** is the backend "app-specific permission gateway" the PRD requires (§4.3, §9.2, §32) — the layer that decides whether a requested tool action is allowed, needs approval, is unavailable, or is disabled. It classifies a tool request into a decision and explains it. As of **Safe-local Execution v0**, it can also *execute* a tiny allowlist of low-risk, read-only local `brain` status tools through the existing safe brain wrapper — **everything else is classification-only and nothing privileged runs.**

```text
classify:  request → decision (denied / requires_approval / not_wired / disabled / allowed) → UI shows result
execute:   request → evaluate + log → if safe-local tool: run via safe brain wrapper + log → return output
```

It is surfaced on the **Tool Connections** page (Permission Gateway section): a tool-policy table, a manual evaluator (tool + reason + JSON args → decision), a *Run safe-local tool* action, and the evaluation/execution log.

### Endpoints (`backend/app/permission_gateway.py`)

- **`GET /api/permissions/policies`** → `{ policies: PermissionPolicy[] }`. Each policy: `tool`, `category`, `riskLevel` (`low|medium|high|disabled`), `status` (`not_wired|available|disabled`), `requiresApproval`, `executionEnabled`, `notes`. Covers `obsidian.*`, `gmail.*`, `calendar.*`, `browser.*`, `computer.*`, `brain.*`, `filesystem.*` (19 tools). `executionEnabled` is **`true` only for** `brain.status`, `brain.raw_status`, `brain.vault_path` — **`false` for every other tool**.
- **`POST /api/permissions/evaluate`** → classify one request (no execution). Body: `{ tool, args?, reason?, requestedBy? }`. Response includes `allowed`, `decision`, `riskLevel`, `requiresApproval`, `executionEnabled`, `sanitizedArgsSummary`, `wouldLog`, and `logId`.
- **`POST /api/permissions/execute`** → evaluate + log, then execute **only** the three safe-local tools via the safe brain wrapper. Response: `{ tool, allowed, decision, riskLevel, requiresApproval, executionEnabled, evaluationLogId, executionLogId, ok, exitCode, stdout, stderr, durationMs, error }`. For any non-executable tool it returns a **safe** response (`allowed:false`, `executionLogId:null`, `error:"Tool is not executable in this build."`) — never a 500.

### Decision logic (deny-by-default)

- MCP / Gmail / calendar-read tools → **`not_wired`**.
- Browser / computer-use, `gmail.send`, `calendar.create_event` → **`disabled`**.
- Unknown tools → **`denied`**; unknown destructive-looking names (`shell.run`, `filesystem.delete`, `browser.submit_form`, `gmail.delete/archive/modify_labels`, …) → **`disabled`**.
- Safe-local executable tools (`brain.status`, `brain.raw_status`, `brain.vault_path`) → **`allowed`** (low risk, no approval); `/execute` runs them and the decision becomes **`executed`**.
- Other `available` tools (`brain.today`, `brain.sync_raw`, `filesystem.read_vault`, `filesystem.write_vault`) → **`requires_approval`** — not executable through the gateway in this build.

### Safe-local Tool Execution v0

**Exactly three tools** can execute, each mapped to an allowlisted safe brain subcommand:

| Tool | brain command |
|---|---|
| `brain.status` | `brain status` |
| `brain.raw_status` | `brain raw-status` |
| `brain.vault_path` | `brain vault-path` |

Execution flow: evaluate → log evaluation → if `is_executable(tool)` run via the existing `run_brain_command` wrapper (`shell=False`, allowlisted, **no args passed to brain**) → log execution → return output. `brain.today`, `brain.weekly`, `brain.sync_raw`, `brain.calendar_*` are **not** executable here. There is **no new subprocess path, no shell, no arbitrary command name, and no arbitrary `brain` command** — only the existing safe wrapper.

### Argument handling

Args are **untrusted**: never executed, only summarized for display/logging. Keys containing `password`, `token`, `secret`, `key`, `credential`, `authorization`, or `cookie` are **redacted**; long values are **truncated**; the summary is capped and the pair count limited. Invalid JSON args are rejected client-side with a clear message. (The three executable brain tools take no args; any provided args are summarized only, never forwarded to `brain`.)

### Safety constraints

- Executes **only** the three low-risk read-only brain status tools, and **only** through the existing safe brain wrapper. Makes no MCP/Gmail/browser/computer-use/Google/GitHub/Drive call; launches no OpenClaw/NemoClaw/OpenShell; runs no shell; runs no arbitrary `brain` command; writes no vault files; reads no credentials; creates no tasks/calendar rows; calls no AI.
- `EXECUTION_ENABLED` (the privileged-execution kill-switch) stays `False`; safe-local execution is opt-in **per tool** via a small allowlist and does not flip it.
- The UI exposes a *Run safe-local tool* button **only** for the three tools; for everything else it is disabled and labelled *Execution disabled in this build.* There is no approve-and-execute or replay action.

### Tool Log v0 — backend-local audit of evaluations + executions

Every Permission Gateway request writes **redacted, backend-local audit entries** — one `gateway_eval` per request, plus one `gateway_execution` when a safe-local tool actually runs. This makes the PRD's tool-log/audit spine real (§32).

- **Storage:** `backend/data/tool-logs/evaluations.json` (backend app-data, **not** the vault). Latest **500** entries kept (simple cap, no rotation). Vault `ops/tool-logs/` writes remain future work.
- **`GET /api/permissions/logs`** — read-only, newest first. Query params: `limit` (default 50, clamped to [1, 200]), `tool` (exact match), `decision` (exact match).
- **Entry fields:** `id`, `timestamp`, `source` (`gateway_eval` | `gateway_execution` | `runtime_bridge_validation`), `tool`, `requestedBy`, `reason`, `decision`, `riskLevel`, `allowed`, `requiresApproval`, `executionEnabled`, `sanitizedArgsSummary`, `policyNotes`, `result` (`evaluated_only` | `success` | `failure` | `validated_only`), and execution-only `exitCode`, `stdoutPreview`, `stderrPreview`, `durationMs`. (Runtime Bridge Contract dry-run validations write `runtime_bridge_validation` / `validated_only` entries — `allowed` and `executionEnabled` always false.)
- **Redaction:** only the already-sanitized args summary is stored — **raw args and secret values are never persisted**. `reason`/`requestedBy` are truncated; stdout/stderr are stored only as **truncated previews**.
- **UI:** a *Permission Evaluation Logs* panel lists recent entries (eval + execution badges, decision/risk/result/exit/duration/stdout-preview); filters by decision and tool; **Refresh only** + auto-refresh after evaluate/execute — there is no clear / delete / replay / approve-and-execute action.

### Agent Tool Request v0 — evaluate-only agent → gateway bridge

The Local Agent surface can create a **structured tool-request proposal** that the backend evaluates through the Permission Gateway and logs — **without any execution power**. This prepares the Local Agent page for future OpenClaw tool requests while keeping the current agent tool-less.

```text
agent (or manual stand-in) proposes a tool request → backend evaluates via gateway + writes the gateway eval log → UI shows the decision → NOTHING runs
```

- **`POST /api/agent/tool-request`** (`backend/app/agent_tool_requests.py`) — body `{ tool, args?, reason?, requestedBy?, conversationId? }`. Evaluates via `evaluate_tool_request`, writes the existing `gateway_eval` log, stores a redacted record, and returns `{ id, tool, argsSummary, reason, requestedBy, conversationId, evaluation{ allowed, decision, riskLevel, requiresApproval, executionEnabled, reason, policyNotes, logId }, createdAt, status }`. `status` is always `evaluated_only`.
- **`GET /api/agent/tool-requests?limit=`** — read-only, newest first (limit clamped to [1, 200]).
- **Never executes:** this path does **not** call `/api/permissions/execute`, the brain wrapper, any subprocess, or any external tool — even for the safe-local tools (a `brain.status` request returns `allowed`/`executionEnabled:true` but is **not run**). Safe-local execution stays manual on the Tool Connections page.
- **Storage/redaction:** records live in `backend/data/agent-tool-requests/requests.json` (backend app-data, not the vault, cap 200). Only the **sanitized args summary** is stored — raw args and secrets are never persisted; `reason`/`requestedBy` are truncated. Instructions inside `reason`/`args` are never followed.
- **UI:** an *Agent Tool Requests* panel on the **Local Agent** page (right rail) with a small manual/simulated request form (tool + reason + JSON args) and a recent-requests list (tool, decision, risk, execution-enabled, status, log id). It states requests are evaluated only, and has **no run / approve-and-execute / auto-run** control.

### Local Agent Structured Output v0 — agent-emitted tool requests (evaluate-only)

The Local Agent can include an **optional structured JSON block** in its reply proposing tool requests; the backend defensively parses it and routes each request through the evaluate-only Agent Tool Request path. **Nothing is executed.**

- **Parser (`backend/app/agent_structured_output.py`):** extracts a fenced ` ```json ` block **or** an `AGENT_STRUCTURED_OUTPUT:` labelled JSON object from the assistant reply. Defensive: tolerates a missing block (empty result, no error), tolerates malformed JSON (returns a parse error, never throws), caps `tool_requests` at **5**, requires a non-empty `tool`, requires `args` to be a JSON object (default `{}`), falls back/truncates `reason`, and ignores unsupported fields. All parsed content is untrusted.
- **Chat integration:** after the assistant reply is produced, both `POST /api/agent/chat` (response field `structured: { toolRequests, parseErrors }`) and `POST /api/agent/chat/stream` (an SSE `event: structured` emitted after streaming completes, before `done`) parse + evaluate the block. Each valid request is created via the Agent Tool Request path (one `gateway_eval` log each); **no execution, no `/execute`, no brain wrapper, no execution log.** Streaming token behavior is unchanged.
- **System prompt:** updated to describe the optional block, that requests are **evaluated only** (the agent must not claim a tool ran), to avoid secrets, and to not request privileged tools unless clearly relevant.
- **UI:** evaluated structured requests render in a compact *Structured tool requests detected* panel under the assistant message (tool, decision, risk, execution-enabled, status, log id) and also refresh the right-rail Agent Tool Requests list. Malformed structured output shows a small notice and never breaks the chat. There is **no run / approve-and-execute** control in chat — safe-local execution remains manual on Tool Connections.

### Review in Tool Connections — agent → manual-execution handoff

An evaluated Local Agent tool request can be handed off to the Tool Connections evaluator for **manual** execution. This closes the safe loop without giving chat any execution power:

```text
agent proposes tool request → backend evaluates/logs → user clicks "Review in Tool Connections" → form prefilled → user manually runs the safe-local tool → gateway logs execution
```

- **Where it shows:** in both the per-message *Structured tool requests detected* panel and the right-rail *Agent Tool Requests* list, a **Review in Tool Connections** button appears **only** when the gateway said the request is executable safe-local — i.e. `evaluation.executionEnabled === true` **and** `evaluation.allowed === true` **and** the tool is `brain.status` / `brain.raw_status` / `brain.vault_path`. Every other request shows *Evaluation only — not executable in this build* with no handoff.
- **Handoff mechanism:** a Zustand app-state field `toolReviewTarget` (mirroring `proposalTarget` / `agentConvTarget`) carries `{ tool, argsSummary?, reason?, requestedBy?, source, relatedId }`. Clicking sets it and navigates to Tool Connections; **nothing executes during navigation.**
- **On Tool Connections:** the evaluator form is prefilled with the tool and reason (and `args` is set to `{}` — raw args are **never** reconstructed from the sanitized summary), a notice *"Opened from Local Agent. Review before running."* is shown along with *"This request came from the Local Agent. It has not been executed. Only low-risk local brain status tools can run here."*, and the target is cleared. The form does **not** auto-evaluate or auto-execute — the user must click **Run safe-local tool**.
- **No backend change:** this sprint is frontend-only; the existing evaluation response already carries `executionEnabled`/`allowed`/`tool`.

### Agent Mode Enforcement v0 — modes enforced by backend policy

Agent modes are no longer purely frontend labels. A single backend module
(`backend/app/agent_modes.py`) is the source of truth for what the Local Agent surface may do in
each mode, and the chat + manual-tool-request paths enforce it server-side. **No mode executes tools
from chat** — safe-local execution stays manual on the Tool Connections page.

```text
chat / manual tool request (+ mode)
  → backend resolves the mode and enforces policy
  → Locked / Observe / Computer-Use: tool requests BLOCKED (not evaluated, not stored, not logged)
  → Draft / Assist / Research / Escalation: tool requests EVALUATED ONLY
  → only Assist offers the Review-in-Tool-Connections handoff
  → NOTHING executes from any mode
```

| mode | available | evaluate tool requests | review handoff |
|---|---|---|---|
| locked | yes | no | no |
| observe | yes | no | no |
| draft | yes | **yes** | no |
| assist | yes | **yes** | **yes** |
| research | yes | **yes** | no |
| escalation | yes | **yes** | no |
| computer_use | **no** | no | no |

- **Computer-Use** is recognized but **unavailable/not wired** — it enables nothing.
- Unknown / missing / malformed modes fall back to the **safest** mode (`locked` → blocked). Frontend
  aliases: `manual → locked`, `computer → computer_use`. Rules are kept safer, not looser.

**Policy helpers** (`agent_modes.py`): `can_evaluate_tool_requests(mode)`,
`can_offer_review_handoff(mode)`, `is_mode_available(mode)`, plus `normalize_mode`, `blocked_message`,
and `list_modes`. The module executes nothing — it only resolves and reports policy.

**Endpoints:**
- **`GET /api/agent/modes`** → `{ modes: [{ id, label, available, canEvaluateToolRequests, canOfferReviewHandoff, notes }] }` — read-only; lets the frontend show honest mode behavior.
- **`POST /api/agent/tool-request`** accepts an optional `mode`. In `locked`/`observe`/`computer_use` it returns `{ status: "blocked_by_mode", mode, message }` (HTTP 200) and evaluates / stores / logs **nothing**. In `draft`/`assist`/`research`/`escalation` it evaluates-only as before.
- **`POST /api/agent/chat`** and **`/api/agent/chat/stream`** carry the selected `mode`. In evaluating modes, structured tool requests are routed through the existing evaluate-only path. In blocking modes the reply is parsed for **visibility only** and the response/SSE carries `blockedByMode: true` with a clear message — nothing is evaluated, stored, or logged.

**Frontend** (`src/pages/AgentPage.tsx`): the mode selector shows real per-mode policy copy (tool
requests evaluated-only / blocked / unavailable; review handoff allowed-in-Assist / not offered).
The manual request form is disabled with blocked copy when the mode can't evaluate; chat shows a
**Blocked by mode** notice (not a gateway failure); the **Review in Tool Connections** button appears
**only in Assist** for safe-local executable requests. There is no execute button anywhere on the
Agent page.

**Safety:** blocked modes write no records and no logs (no execution logs are ever created from
agent-mode paths); no path calls `/api/permissions/execute`, the brain wrapper, a subprocess, MCP,
Gmail, browser/computer-use, Google Calendar, or writes the vault.

### Global Agent Mode Display v0 — enforced mode visible app-wide

The enforced agent mode is now shown beyond the Local Agent page. The selected mode is already global
app state (`useAppStore().agentMode`); this sprint loads the backend policy once into the store and
renders it honestly in two more places. **No tool execution behavior changes** — display only.

- **Mode policy loading:** `loadAgentModes()` (store action) calls `GET /api/agent/modes` once on app
  mount (`AppShell`) into `agentModes`. If the fetch fails, consumers fall back to a static policy copy
  (`src/lib/agentModes.ts` → `MODE_POLICY_FALLBACK`/`resolveModePolicy`) so the app never blocks and
  degrades clearly. Frontend ids map to backend ids via `toBackendMode` (`manual→locked`, `computer→computer_use`).
- **Top command bar:** the `ModeBadge` now shows an availability dot + a policy tooltip
  ("Evaluates tool requests. Safe-local review handoff is available. Chat does not execute tools."), and
  reads `<mode> · unavailable` for Computer-Use. It does **not** imply browser/computer-use is wired.
- **Dashboard:** a compact **Agent mode** card shows the selected mode, availability, Evaluation
  (Allowed/Blocked/Unavailable), Review handoff (Safe-local only/Disabled), and **Execution from chat:
  Disabled**, plus the three standing truths: *Agent tools are mode-gated by backend policy* · *No mode
  executes tools from chat* · *Safe-local execution remains manual in Tool Connections*.
- **In sync:** the Local Agent page, top bar, and Dashboard all read the same store `agentMode` +
  `agentModes`; changing the mode anywhere updates everywhere. The mode selector/dropdown stays the
  existing single `ModeBadge` control.

### OpenClaw / NemoClaw Runtime Status v0 — honest runtime readiness

A read-only backend surface reports what is configured / missing / disabled / blocked for the five
privileged runtimes, so the UI can show readiness without pretending anything is wired. **This is
status/readiness only** — it launches no runtime, makes no network/health call, reads no credentials,
runs no shell/`brain`, writes no vault, and executes no tool.

- **`GET /api/runtime/status`** (`backend/app/runtime_status.py`) → `{ items: [{ id, name, status,
  available, enabled, requiredFor[], dependsOn[], blocks[], configured{}, notes }] }` for
  `openclaw`, `nemoclaw_openshell`, `browser_harness`, `computer_use`, `mcp_gateway`. Status ∈
  `available | unavailable | not_configured | disabled | planned | error`.
- **Honesty rule:** **no runtime is ever reported `available`** — v0 performs no verified health check
  (and must not), so even fully-configured runtimes stay `unavailable` (configured-but-unverified) and
  every runtime's `available`/`enabled` is `false`.
- **Config detection (env only, read-only):** `OPENCLAW_ENABLED`/`OPENCLAW_BASE_URL`,
  `NEMOCLAW_ENABLED`/`NEMOCLAW_RUNTIME_URL`/`NEMOCLAW_POLICY_PATH`,
  `ENABLE_BROWSER_HARNESS`/`ENABLE_COMPUTER_USE`/`ENABLE_MCP_GATEWAY`. These knobs do not exist
  elsewhere in the app yet; when unset the runtime is `not_configured`. Only presence/enabled-flag is
  read — values are never stored and no credential is read.
- **Dependency/blocking:** browser harness and computer-use **depend on** NemoClaw/OpenShell and stay
  **blocked** (`disabled`, with a blocker reason) while it is unavailable — even if their own enable
  flag is set. MCP/OpenClaw privileged actions likewise require the runtime guardrail.
- **Frontend** (`src/lib/runtimeStatus.ts` + `src/components/runtime/RuntimeStatus.tsx`):
  `getRuntimeStatus()` + a `useRuntimeStatus()` hook with a static fallback (`RUNTIME_FALLBACK`) so a
  backend-down state degrades honestly (shows "backend unreachable — showing fallback"). The
  **Dashboard** runtime panel now shows real backend-derived rows (replacing the old mock "Planned"
  rows) + the truths *Privileged agent runtimes are not wired yet.* / *Browser and computer-use remain
  blocked until NemoClaw/OpenShell is available.* **Tool Connections** adds a **Runtime Guardrails**
  section (dependency chain, per-runtime status, what each would unlock, why it is blocked) — the only
  per-runtime control is a disabled **Not wired yet** button. **Local Agent** shows a small runtime
  guardrail note (NemoClaw/OpenShell + OpenClaw bridge status; "Agent remains local chat +
  evaluate-only tool requests"). Nothing is ever shown ready/connected/active unless the backend truly
  reports `available`.

### NemoClaw/OpenShell Health Probe v0 — explicit, opt-in reachability check

Runtime Status reads env/config only. This adds **one** narrowly-scoped capability: when the user
explicitly clicks **Check NemoClaw/OpenShell**, the backend performs a single **bounded HTTP GET** to
a *configured local* runtime URL and reports whether it is reachable. It **verifies readiness only** —
it unlocks nothing.

- **`POST /api/runtime/probe/nemoclaw`** (`backend/app/runtime_probe.py`), body optional
  `{ timeoutMs }` (clamped to `[1, 3000]`, default 1500). Response: `{ id, checkedAt, configured,
  reachable, status, durationMs, message, details{ urlConfigured, policyPathConfigured, enabledFlag,
  remoteProbeAllowed, hostRedacted } }`. `status` ∈ `reachable | unavailable | not_configured | error`.
- **`GET /api/runtime/probe/nemoclaw/last`** returns the cached last result (backend-local
  `backend/data/runtime/last-probe.json`, **not** the vault). Loading it is **not** a probe (no network).
- **Config (env only):** `NEMOCLAW_ENABLED`, `NEMOCLAW_RUNTIME_URL`, `NEMOCLAW_POLICY_PATH`, and
  `NEMOCLAW_ALLOW_REMOTE_PROBE`. No URL configured or not enabled → `not_configured` with **no network
  call**.
- **Network safety (enforced):** only `NEMOCLAW_RUNTIME_URL` is probed (the frontend cannot supply a
  URL — only `timeoutMs`); **only loopback hosts** (`localhost` / `127.0.0.0/8` / `::1`) are allowed by
  default — public/LAN hosts are rejected with `error` unless `NEMOCLAW_ALLOW_REMOTE_PROBE=true`; URLs
  carrying `user:pass@` are rejected; **redirects are disabled**; no cookies/auth headers are sent; the
  timeout is clamped to ≤ 3000ms.
- **Unlocks nothing:** even when the runtime is reachable, browser/computer-use stay `disabled` and no
  capability changes — the runtime bridge is still not implemented. The probe starts no process, runs
  no shell/`brain`, reads no credentials, writes no vault, and executes no tool.
- **Frontend:** the Tool Connections **Runtime Guardrails** section adds an explicit **Check
  NemoClaw/OpenShell** button + result (status, checked time, duration, message, URL/policy configured,
  redacted host) and the copy *"Browser and computer-use remain disabled until a separate runtime
  bridge is implemented and explicitly enabled."* No start/connect/enable control is added.

### NemoClaw/OpenShell Policy Inspection v0 — read-only, no enforcement

Makes the future runtime guardrail **inspectable** before any privileged bridge is built. It reads a
configured NemoClaw/OpenShell policy file, parses it **defensively**, and shows a safe summarized view
of declared scopes. It **inspects only** — it does **not** enforce the policy, start NemoClaw/OpenShell,
execute tools, or enable browser/computer-use/MCP/OpenClaw.

- **`GET /api/runtime/policy/nemoclaw`** (`backend/app/runtime_policy.py`). Response:
  `{ id, configured, pathConfigured, pathExists, readable, valid, status, message, policyPathDisplay,
  format, summary{ declaredModes, networkPolicy, filesystemScopes, browserAllowed, computerUseAllowed,
  mcpAllowed, credentialAccess, unknownKeys }, warnings[], errors[] }`. `status` ∈
  `not_configured | missing | unreadable | invalid | loaded | error`.
- **Reads only the configured path.** Only `NEMOCLAW_POLICY_PATH` is read — **never a frontend-supplied
  path** (the endpoint takes no path argument). No directory listing, no symlink chasing beyond the OS
  resolve, no arbitrary path traversal. If no path is configured → `not_configured` with **no file read**.
- **Path safety:** the configured path is resolved; a missing target → `missing`, a directory (or other
  non-file) → `unreadable`. The file is read as **UTF-8 text only**, capped at **256 KB** (oversized →
  `invalid`, rejected before contents are read). The policy file is **never executed or imported as code**.
- **Format support:** **JSON** always (stdlib `json`); **YAML** only if PyYAML is importable — parsed with
  `yaml.safe_load` (SafeLoader, never the unsafe full loader). PyYAML is **optional**, not a hard
  dependency: when absent, YAML files are reported honestly as unsupported (`invalid`) rather than failing.
- **Defensive summary:** an unrecognized-but-parseable object is `loaded` with its **unknown keys
  surfaced**; capabilities (`browserAllowed` / `computerUseAllowed` / `mcpAllowed`) default to **unknown**
  (`null`) and are only reported `Allowed` when the policy **clearly** declares them so — we never imply a
  capability is allowed. `credentialAccess` defaults to `unknown`. A non-object root → `invalid`.
- **Enforces nothing / unlocks nothing:** capabilities remain disabled regardless of what the policy
  declares. No network call, no process launch, no shell/`brain`, no credential read, no vault write, no
  tool execution.
- **Frontend:** the Tool Connections **Runtime Guardrails** section adds a read-only **NemoClaw/OpenShell
  Policy** panel (configured/exists/readable/valid, status, path display, declared modes, network policy,
  filesystem scopes, browser/computer-use/MCP allowed-blocked-unknown, credential access, warnings/errors)
  plus a **Reload inspection** button and the required copy *"Policy inspection is read-only. It does not
  enforce policy or enable runtime actions."* / *"Capabilities remain disabled until the runtime bridge is
  implemented separately."* The Dashboard runtime card shows one compact honest **Policy:** line. There is
  **no** edit / apply / enable / start control.

### Guardrail Readiness v0 — read-only correlation, no enforcement

Correlates the four guardrail surfaces into a single honest readiness view — the final readiness view
before an actual NemoClaw/OpenShell bridge **contract** is designed. It **correlates only**: it does
**not** enforce policy, run a fresh health probe, make a network call, start any runtime, execute tools,
or unlock browser / computer-use / MCP / OpenClaw / Gmail.

- **`GET /api/runtime/guardrail-readiness`** (`backend/app/guardrail_readiness.py`) correlates runtime
  status, the **cached last** NemoClaw/OpenShell probe, policy inspection, and the agent mode policy.
  Response: `{ id, status, ready, checkedAt, summary, components{ runtimeStatus, lastProbe, policy,
  modePolicy }, blockers[], warnings[], nextSteps[], capabilityUnlocks{ openclawBridge, browserHarness,
  computerUse, mcpGateway, gmail }, notes }`. `status` ∈
  `not_ready | partially_ready | ready_for_bridge_design | error`.
- **Correlation rules:** `not_ready` = no reachable probe **and** no loaded policy; `partially_ready` =
  reachable probe **xor** loaded policy; `ready_for_bridge_design` = reachable (per the last probe) **and**
  loaded/valid policy **and** mode policy present **and** no dependent falsely reporting browser/computer-use
  as enabled.
- **`ready_for_bridge_design` does not mean execution-ready.** `ready: true` is set **only** for that
  status and means only "ready for a bridge to be *designed*". `capabilityUnlocks.*` is **false in every
  state** — readiness enables nothing.
- **Reads the cached last probe only** (loading it is not a probe). It makes **no** fresh probe, network
  call, process launch, shell/`brain`, credential read, or vault write; refreshing readiness triggers **no**
  health probe.
- **Frontend:** the Tool Connections **Runtime Guardrails** section adds a read-only **Guardrail Readiness**
  panel (status, summary, component chips, blockers, suggested next steps, capability unlocks all disabled,
  warnings) with a **Refresh readiness** button (no probe) and the required copy *"Guardrail readiness is
  informational only. It does not enable OpenClaw, browser, computer-use, MCP, or Gmail actions."* /
  *"Ready for bridge design does not mean ready for execution."* The Dashboard runtime card shows one
  compact **Guardrail readiness:** line; the Local Agent runtime-guardrail note shows the same. There is
  **no** enable / start / bridge / execute control.

### NemoClaw/OpenShell Bridge Contract v0 — dry-run validator, no execution

Defines the backend **request/response contract** for a future NemoClaw/OpenShell bridge and a **dry-run
validator** that answers, for a proposed bridge request: would it be blocked, would it require approval, and
is its shape structurally acceptable for a future bridge to be *designed*? It **validates only** — it does
**not** call NemoClaw/OpenShell or OpenClaw, execute browser/computer-use/MCP/Gmail/Calendar/vault/brain
actions, start a runtime, run a fresh probe, run shell/`brain`, write the vault, or unlock any capability.

- **`POST /api/runtime/bridge/validate`** (`backend/app/runtime_bridge_contract.py`). Request:
  `{ source, mode, requestedAction{ kind, target?, args? }, reason?, conversationId? }`. Response:
  `{ id, status, allowed, requiresApproval, executionEnabled, mode, source, actionKind, riskLevel, decision,
  message, checks{ schemaValid, modeAllowsEvaluation, guardrailReadyForBridgeDesign, runtimeBridgeImplemented,
  permissionGatewayDecision }, blockers[], warnings[], logId, createdAt }`. `status` ∈
  `blocked_by_mode | blocked | validated | error`.
- **Dry-run pipeline:** validate request shape → normalize mode via the agent mode policy → check the mode
  allows evaluation → read Guardrail Readiness (**cached — no probe**) → map the action kind to a
  conservative risk → run a Permission Gateway **dry-run** classification → write one sanitized audit entry
  (log source `runtime_bridge_validation`) → return a clear blocked/validated result.
- **Recognized future action kinds** (none execute): `browser.open`, `browser.search`, `browser.read_page`,
  `computer.click`, `computer.type`, `computer.screenshot`, `mcp.call`, `gmail.search`, `gmail.read`,
  `calendar.read`, `vault.read`, `vault.write`, `brain.status`, `brain.raw_status`, `brain.vault_path`,
  `unknown`. Conservative risk: safe-local reads (`brain.*`, `vault.read`) `low`; browser/MCP/Gmail/calendar
  `medium`; computer-use/`vault.write`/`unknown` `high`.
- **Mode rules:** `locked`/`observe`/`computer_use` → `blocked_by_mode`; `draft`/`assist`/`research`/
  `escalation` validate only; in `assist`, a safe-local action may be noted as review-handoff-eligible later
  (still never executed here).
- **Honesty rule:** `allowed` and `executionEnabled` are **always false** — a valid bridge request is *not*
  an approval to run it — and `runtimeBridgeImplemented` is **always false**. Even safe-local `brain.status`
  does **not** execute here; manual safe-local execution remains only in Tool Connections. When Guardrail
  Readiness is not `ready_for_bridge_design` the response includes a blocker saying so; when it *is* ready a
  safe-local request is marked `validated` (schema acceptable for future design) but **still** does not run.
- **Logging:** only a sanitized summary is stored (secret-bearing keys redacted, long values truncated) —
  never raw args, full page contents, or credentials.
- **Frontend:** the Tool Connections **Runtime Guardrails** section adds a **Bridge Contract Validator**
  panel (source, current mode, action-kind dropdown, reason, JSON args) with a **Validate bridge request**
  button (invalid JSON is caught client-side and does not submit) and the required copy *"This validates a
  future runtime bridge request. It does not call NemoClaw/OpenShell or execute the action."* / *"A valid
  bridge request is not an approval to run it."* The result shows status, decision, risk, mode, action kind,
  checks, blockers, warnings, and the log id. The Dashboard runtime card shows a compact **Runtime bridge:
  contract validator only** line. There is **no** execute / approve / start-bridge / connect control.

## Escalation Queue

The Escalation Queue is for tasks too complex for the local agent or simple UI workflows.

### Workflow

```text
capture task → choose target agent → review/copy prompt → run Claude Code/OpenCode manually → update status
```

### File location

`ops/escalation-queue.md` — a Markdown pipe table with columns: Task, Target, Status, Priority, Source, Path, Notes, Created.

### Statuses

`new` → `ready` → `in-progress` → `done` | `blocked` | `skipped`

Active statuses (counted on Dashboard): `new`, `ready`, `in-progress`, `blocked`.

### Targets

- `claude-code` — for Claude Code CLI handoffs
- `opencode` — for OpenCode handoffs
- `manual` — for manual or human escalation

### Handoff prompt

Each item has a "Copy handoff prompt" action that generates a structured prompt containing the task, target, priority, source, path, notes, and safe instructions. The prompt is copied to the clipboard only — **no process is launched**.

Run the prompt manually in Claude Code (`claude`) or OpenCode after copying.

### Backups

A timestamped backup is created under `backend/data/backups/escalations/` before every write. Backups are never overwritten.

### Safety constraints

- Brain UI does not launch Claude Code, OpenCode, or any shell command.
- The `path` field is metadata only — no repo files are read, modified, or deleted by Brain UI.
- `POST /api/vault/escalations/create` never overwrites an existing file.
- `PATCH /api/vault/escalations/{id}/status` modifies only the status cell of a single row.
- All path operations are validated to stay inside the vault root (traversal rejected).
- `extra="forbid"` on the create request model rejects unknown fields.

## Brain command allowlist

Only these `brain` subcommands may run through the backend API:

```
doctor  status  vault-path  today  weekly
raw-status  sync-raw  calendar-export  calendar-open
new-project  new-course  new-hackathon
```

Non-allowlisted commands are rejected with HTTP 400. No arbitrary shell
execution is possible. The `new-*` commands require typed entity endpoints and
are rejected by generic `/api/brain/run`.

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
- Right rail: Agent panel (sphere + mode + ask input), Runtime status (Backend/Brain/Vault/Local-model real; OpenClaw/NemoClaw/Browser/Computer/MCP shown honestly as "Not wired" under a Planned divider), Quick actions grid
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

## Entity creation

Projects, Courses, Hackathons, and Business pages include first-class creation actions so entity setup does not require PowerShell or manual folder-path work.

### Brain-backed entity creation

These flows call existing `brain` commands through entity-specific backend endpoints:

| Page | Endpoint | Safe command |
|---|---|---|
| Projects | `POST /api/entities/projects` | `brain new-project` |
| Courses | `POST /api/entities/courses` | `brain new-course` |
| Hackathons | `POST /api/entities/hackathons` | `brain new-hackathon` |

The frontend never sends raw shell text. Arguments are modeled as typed fields, validated by the backend, and passed as a subprocess argument array with `shell=False`. The generic `/api/brain/run` endpoint rejects these argument-requiring `new-*` commands; they must use the entity-specific endpoints.

Verified CLI signatures from the existing `brain` source and live `brain.cmd --help` output:

```text
brain new-project <name>
brain new-course <code> [--title <title>] [--term <term>]
brain new-hackathon <name>
```

Current endpoint mapping:

| Endpoint | Request field | CLI mapping |
|---|---|---|
| `POST /api/entities/projects` | `name` | positional `<name>` |
| `POST /api/entities/projects` | `repoPath` | rejected when non-empty; current CLI does not support it |
| `POST /api/entities/courses` | `code` | positional `<code>` |
| `POST /api/entities/courses` | `name` | optional `--title <name>` |
| `POST /api/entities/hackathons` | `name` | positional `<name>` |
| `POST /api/entities/hackathons` | `date` | rejected when non-empty; current CLI does not support it |

### Business scaffold

Business areas use a safe filesystem scaffold because there may not be a `brain new-business` command.

`POST /api/entities/business` creates:

```
raw/business/<safe-name>/
wiki/business/<safe-name>.md
ops/business-pipeline.md
```

The business note starter is:

```md
# <Business Area Name>

## Summary

<description or blank>

## Status

Active

## Notes
```

If `ops/business-pipeline.md` is missing, it is created with:

```md
# Business Pipeline

| Name | Status | Description | Created |
|---|---|---|---|
```

Then a row is appended:

```md
| <name> | Active | <description> | <date> |
```

### Entity creation safety

- Only `new-project`, `new-course`, and `new-hackathon` were added to the command allowlist.
- No arbitrary command arguments or shell strings are accepted.
- Empty required names/codes are rejected.
- Newlines and control characters are rejected.
- Unsafe Windows CMD metacharacters are rejected before calling `.cmd` brain commands.
- Business scaffold writes only under `raw/business/`, `wiki/business/`, and `ops/business-pipeline.md`.
- Business notes and raw folders are never overwritten.
- The configured vault root must already exist before business scaffold writes run.
- Existing `ops/business-pipeline.md` is backed up under `backend/data/backups/business/` before modification.
- If business pipeline update fails after the wiki note or raw folder is created, the API returns `ok: false` with `stdout`, `stderr`, and exact created paths instead of claiming full success.
- No delete, rename, AI generation, OpenClaw tooling, or automatic Raw Inbox routing is implemented.

### Backend safety tests

Run focused backend tests with:

```bash
python -m pytest backend\tests
```

The tests cover command allowlist/argument validation, `new-*` rejection through generic `/api/brain/run`, course `--title` mapping, unsupported optional args, business scaffold creation, duplicate rejection, backup creation, and partial-failure reporting. They use temporary directories and do not require Ollama, the real vault, or the real `brain` CLI.

## Calendar candidates workflow

Calendar remains proposal-based. Google Calendar is still the final source of truth, and Brain UI does not create Google Calendar events directly.

Expected flow:

```
create candidate
  → ops/calendar-candidates.md
  → view candidates in Calendar page
  → edit or approve rows
  → run brain calendar-export
  → run brain calendar-open
  → manually import/open the generated .ics
```

The Calendar page reads only `<vaultPath>/ops/calendar-candidates.md`. Markdown tables are parsed first. Common column variants are normalized, including `date`, `time`/`start`, `duration`/`length`, `title`/`name`/`event`, `reason`/`why`, `source`/`from`, and `approved`/`approve`.

If the file is missing, the UI shows an empty state with **Create calendar candidates file**. This explicit action creates `ops/` if needed and writes the starter Markdown table:

```md
# Calendar Candidates

| Date | Time | Duration | Title | Reason | Source | Approved |
|---|---|---|---|---|---|---|
```

Existing calendar candidate files are never overwritten by starter creation. If the file exists but has no supported Markdown table, the UI shows a preview-only warning and disables row editing and adding.

### Adding candidates

Use **Add candidate** on the Calendar page to append one row to an existing parseable table. Date and Title are required. Time, Duration, Reason, and Source are optional. Approved defaults to `No`.

Adding a candidate only writes a candidate row. It is not a calendar event, does not call Google Calendar, and does not run export/open automatically.

### Calendar edit safety

- `PATCH /api/vault/calendar-candidates/{candidateId}` updates one parsed table row.
- `POST /api/vault/calendar-candidates/create` creates the starter file only if missing.
- `POST /api/vault/calendar-candidates` appends one candidate row to a parseable table.
- `POST /api/vault/calendar-candidates/{candidateId}/approve` changes only the `Approved` cell to `Yes`.
- Candidate IDs are row-based for now: `c1`, `c2`, `c3`.
- The backend re-reads and re-parses the file before each write.
- Unknown table columns are preserved.
- Missing files must be created explicitly before candidates can be added.
- Malformed/non-table files are not modified by add/edit/approve.
- Pipe characters in user input are sanitized, and raw newlines are rejected.
- The backend only writes `ops/calendar-candidates.md`; no unrelated vault files are edited.

### Calendar backups

Before every modification to an existing calendar candidate file, the backend creates a UTF-8 Markdown backup under:

```
backend/data/backups/calendar/
```

Backup names use the source stem, UTC timestamp, and a random suffix, for example:

```
calendar-candidates_20260603_142233_ab12.md
```

If backup creation fails, the write is aborted.

### Calendar export/open

`Export .ics` and `Open calendar export` are manual buttons. They call the existing safe command wrapper with:

```
calendar-export
calendar-open
```

These commands are never run automatically after adding, editing, or approval. Command output and errors are shown on the Calendar page and logged in the app command output.

Google Calendar API integration is not implemented yet.

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
    calendar.py   calendar candidates Markdown table parser/writer
  requirements.txt
```

## Structured Resume Pipeline workflow

Resume Pipeline tracks job opportunities, applications, and resume tailoring work without manually editing Markdown for every status change.

Expected flow:

```
job opportunity / application target
  → listed in ops/resume-pipeline.md as a Markdown table row
  → filtered by status/company/priority in the Resume Pipeline page
  → status updated via the UI (confirmation required, backup created)
  → "Copy tailoring prompt" generates a ready-to-paste prompt for Claude or ChatGPT
  → user tailors resume/cover letter manually using the prompt
  → status updated to applied, interview, offer, etc.
```

### Supported file

`ops/resume-pipeline.md` only. No fallback.

### Expected table format

```md
| Target | Company | Role | Status | Priority | Deadline | Link | Notes |
|---|---|---|---|---|---|---|---|
| SWE Intern | Acme Corp | Software Engineer Intern | new | high | 2026-09-01 | https://acme.com/careers | Apply via portal |
```

**Column aliases** (any of these names are recognized):

| Canonical | Aliases |
|---|---|
| target | name, title, job |
| company | org, employer |
| role | position |
| status | state, stage |
| priority | value, importance |
| deadline | due, date |
| link | url, source |
| notes | summary, description |

### Allowed statuses

`new` · `tailoring` · `applied` · `interview` · `offer` · `rejected` · `archived`

### Status update safety

Same backup-before-write pattern as Tasks, Calendar, and Backfill:

1. Re-read file from disk.
2. Re-parse table.
3. Conflict check — verify target name still matches the expected row.
4. Backup — create a timestamped copy under `backend/data/backups/resume/`. Write aborted if backup fails.
5. Write — replace only the status cell. All other cells preserved.

### Backups

Stored under `backend/data/backups/resume/` with timestamped names, for example:

```
resume-pipeline_20260608_142233_ab12.md
```

### Tailoring prompt generation

Each row has a **Tailor** button. This is frontend-only — no backend call, no AI invoked, no browser opened, no application submitted.

The prompt includes:
- Target, company, role, priority, deadline, link, notes
- Task list: tailor resume bullets, identify missing keywords, draft cover-letter outline, list prep tasks
- Safety rule: do not invent experience; ask for resume/JD if missing

### Link handling

If `link` starts with `http://` or `https://`, it renders as an external anchor (`target="_blank" rel="noopener noreferrer"`). Otherwise it renders as muted mono text. Links are never auto-opened.

### Filters

Client-side filters for status, company, priority, and free text search. Filter options derived from the loaded table.

### Endpoints

```
GET /api/vault/resume-pipeline
  → { path, exists, lastModified, parseMode, preview, items[] }
  parseMode: "markdown-table" | "preview-only" | "missing"

POST /api/vault/resume-pipeline/create
  → same shape as GET; creates ops/resume-pipeline.md if missing, never overwrites

POST /api/vault/resume-pipeline
  Body: { target, company?, role?, status?, priority?, deadline?, link?, notes? }
  → { ok, item, path, updatedAt }

PATCH /api/vault/resume-pipeline/{itemId}/status
  Body: { "status": "new | tailoring | applied | interview | offer | rejected | archived" }
  → { ok, item, path, updatedAt }

PATCH /api/vault/resume-pipeline/{itemId}
  Body: { target, company?, role?, priority?, deadline?, link?, notes? }
  → { ok, item, path, updatedAt }
  status is preserved; use /status to change it
```

---

## Structured Backfill workflow

Backfill is the workflow for converting old scattered work (repos, projects, hackathons, courses) into structured vault records.

Expected flow:

```
old repo / old project
  → listed in ops/backfill.md as a Markdown table row
  → triaged and filtered by status/value/type in the Backfill page
  → status updated via the UI (confirmation required, backup created)
  → "Copy closeout prompt" generates a ready-to-paste prompt for Claude Code or OpenCode
  → user runs the agent manually in the relevant repo
  → status updated to done
```

### Supported files

The Backfill page reads (in priority order):

1. `ops/backfill.md`
2. `ops/backfill-last-year.md`

If neither file exists, the page shows a missing state with the expected table format.

### Expected table format

```md
| Item | Type | Status | Value | Path | Agent | Notes |
|---|---|---|---|---|---|---|
| JARVIS repo | project | in-progress | high | D:\dev\JARVIS | claude-code | Needs closeout sprint |
| ECE244 notes | course | new | medium | | opencode | |
```

**Column aliases** (any of these names are recognized):

| Canonical | Aliases |
|---|---|
| item | name, title |
| type | kind, category |
| status | state |
| value | priority, importance |
| path | repo, folder, link |
| notes | summary, description |
| agent | tool |

### Allowed statuses

`new` · `triaged` · `in-progress` · `done` · `skipped`

### Status update safety

Every status edit follows the same pattern as task and calendar editing:

1. Re-read the file from disk (no stale state).
2. Re-parse the table to locate the exact target row.
3. Conflict check — verify the item name still matches the expected value at that line. If the file changed, the write is rejected.
4. Backup — create a timestamped copy under `backend/data/backups/backfill/`. Write is aborted if backup fails.
5. Write — replace only the status cell. All other cells and content are preserved exactly.

If any step fails, the file is **not modified** and an error is returned to the UI.

### Backups

Backups are stored locally under `backend/data/backups/backfill/` with timestamped names, for example:

```
backfill_20260608_142233_ab12.md
```

Backups are never overwritten. There is no restore UI — copy the backup manually over the file if needed.

### Closeout prompt generation

Each backfill row has a **Copy closeout prompt** button. This is frontend-only — no commands are run, no repos are touched.

The prompt includes:
- Item name, type, path/repo, notes, value/priority
- Task list: summarize what it was, identify useful artifacts, create/update vault notes, suggest archive actions
- Safety rules: do not delete anything, ask before destructive actions

If `agent` is `claude-code`, the prompt header says "Claude Code Closeout Prompt".
If `agent` is `opencode`, the prompt header says "OpenCode Closeout Prompt".
Otherwise it uses "Backfill Closeout Prompt".

**Nothing is launched automatically.** The user pastes the prompt into Claude Code or OpenCode manually.

### Filters

The Backfill page includes client-side filters for status, type, value, agent, and a free text search. Filter options are derived from the loaded table (only values that exist in the file appear).

### Supported files

- **Read**: tries `ops/backfill.md` first, then `ops/backfill-last-year.md` as fallback.
- **Write** (create/append): only ever writes `ops/backfill.md`. `ops/backfill-last-year.md` is permanently read-only.
- **Backups**: created before every write under `backend/data/backups/backfill/`.

### Adding new items

New items are added from the Backfill page using the **New Backfill Item** button. On success the list reloads and the new row is visible immediately.

If `ops/backfill.md` does not exist (but the fallback file may), a **Create Backfill file** / **Create ops/backfill.md** button appears. Clicking it creates the starter file and enables adding items.

### Editing existing items

Each row has an **Edit** button that opens a modal pre-populated with the current values. The user can update item name, type, value, agent, path, and notes.

Status is intentionally excluded from the edit modal — use the inline status dropdown on each row.

Edit is hidden/disabled when the displayed data comes from `ops/backfill-last-year.md` (the fallback file is read-only).

### Workflow

```text
capture row → edit/refine fields → triage status → copy closeout prompt
```

No repo scanning, agent launching, or shell execution occurs at any point.

### Endpoints

```
GET /api/vault/backfill
  → { path, exists, lastModified, parseMode, preview, items[] }
  parseMode: "markdown-table" | "preview-only" | "missing"

POST /api/vault/backfill/create
  → same shape as GET; creates ops/backfill.md if missing, no-op if it exists

POST /api/vault/backfill
  Body: { item, type?, status?, value?, path?, agent?, notes? }
  → { ok, item, path, updatedAt }
  Appends row to ops/backfill.md. Backup created before write.
  Rejects if only fallback file exists, if file is malformed, or if enums are invalid.

PATCH /api/vault/backfill/{itemId}
  Body: { item, type?, value?, path?, agent?, notes? }
  → { ok, item, path, updatedAt }
  Edits non-status fields of one row in ops/backfill.md.
  status and unknown columns are preserved.
  Backup created before write. Rejects fallback-only, malformed, or missing file.

PATCH /api/vault/backfill/{itemId}/status
  Body: { "status": "new | triaged | in-progress | done | skipped" }
  → { ok, item, path, updatedAt }
```

Errors return HTTP 400 with a descriptive message. File is never modified on error.

---

## What's NOT implemented yet

- OpenClaw / NemoClaw integrations
- Real research runs
- Google Calendar API writes or automatic calendar imports
- Deleting calendar candidates from the UI (adding is implemented via `POST /api/vault/calendar-candidates`)
- Deleting backfill rows from the UI
- Deleting resume pipeline rows from the UI
- Deleting escalation queue items from the UI
- Deleting tasks from the UI
- Automatic job application or browser automation
- AI resume rewriting (tailoring prompt generation only — no AI called)
- Arbitrary vault Markdown editing
- Gmail / MCP
- Browser harness / computer use
- Archive restore (manual only — files are in `backend/data/archive/`)
- Bulk archive
- Automatic closeout (Claude/OpenCode are never launched by the app)
- Dashboard deep-link from Recent AI Work row to a specific conversation in AgentPage

## Technical Debt

Several vault workflows use similar Markdown table parse/update/backup logic. A future refactor may extract shared helpers once behavior stabilizes.
