# Current Task

## Current State

**Proposal Queue source deep-linking (latest):** clicking a Proposal Queue item now opens the correct source page **and highlights the exact related item** (not just the page). Implemented as a navigation/state-restoration handoff only — no new writes, no backend change. A new store field `proposalTarget: { source: 'raw-inbox' | 'chat-consolidation' | 'research'; relatedId } | null` (with `setProposalTarget`) mirrors the existing `agentConvTarget` pattern. `ProposalsPage` sets the target (from each proposal's `relatedId`) before navigating; if `relatedId` is missing it falls back to plain navigation. Each source page (`InboxPage`, `ConsolidatePage`, `ResearchPage`) consumes and clears the target on mount, then once its list has loaded it highlights + scrolls the matching row/card into view and shows an unobtrusive "Opened from Proposal Queue." notice; the highlight fades after ~4s. A missing/deleted target shows a non-blocking notice ("Target proposal was not found. Showing Raw Inbox." / "That draft could not be found. It may have been deleted.") and keeps the page usable. No proposal is approved/routed/skipped/saved by deep-linking, and the Proposal Queue stays read-only. 216/216 backend tests pass (no backend change), `npm run build` clean.

**Research manual v1:** the Research page is now real (was gated). A new backend module (`backend/app/research.py`) lets the user capture research by hand — title, topic, domain, entity, research question, summary, key findings, sources (`{title,url,notes}`), open questions, recommended next actions, raw notes — and create a **draft** (`POST /api/research/drafts`) stored as backend metadata only (`backend/data/research/drafts.json`), **no vault write at create time**. Requires a non-empty title plus at least one of rawNotes/summary/a key finding; domain validated against 8 values; path-traversal markers in title/topic/entity rejected. Drafts list/read/edit (`GET`/`PATCH`; locked = id/createdAt/updatedAt/status/savedPath). **Save to vault** (`POST .../{id}/save`) writes exactly one Markdown note under `raw/research/<slug(topic|title)>/<date>-<slug(title)>.md`, never overwrites (UUID suffix), must stay under `raw/research/` and inside the vault root (traversal rejected), marks the draft `saved`, stores `savedPath`. No AI, no URL fetch, no web search, no `brain`, no tasks/calendar/resume. Pasted notes/sources treated as **untrusted** (stored + raw notes embedded in a widened code fence; URLs never fetched). **Browser/computer-use/web-search automation remains not wired.** Proposal Queue now aggregates Raw Inbox + Consolidation + Research drafts (`research`/`research_note`, draft→pending, saved→applied, action `open_research` → navigates to Research). No apply/save from the queue. 216/216 backend tests pass (31 new research tests), `npm run build` clean.

**Chat/AI Consolidation manual v1:** the Consolidate page is now real (was gated). A new backend module (`backend/app/consolidation.py`) lets the user paste a ChatGPT / Claude / Claude Code / OpenCode transcript and create a **draft** (`POST /api/consolidation/drafts`) stored as backend metadata only (`backend/data/consolidation/drafts.json`) — **no vault write at create time**. Drafts can be listed/read/edited (`GET`/`PATCH`; editable = title/domain/entity/summary/decisions/actionItems/codeOrFilesReferenced; id/createdAt/sourceTool/transcript/status/savedPath locked). **Save to vault** (`POST .../{id}/save`) writes exactly one Markdown summary under `raw/chats/<sourceTool>/<date>-<slug>.md`, never overwrites (UUID suffix on collision), can't escape the vault root, marks the draft `saved`, and stores `savedPath`. No AI call (missing summary → deterministic transcript-preview fallback), no `brain`, no tasks/calendar/resume side effects. The transcript is treated as **untrusted**: only stored + embedded in a widened code fence, never executed or sent to an LLM. **Browser/computer-use capture remains not wired** — v1 is manual paste/import only. Proposal Queue now aggregates Raw Inbox + Consolidation drafts (`chat-consolidation`/`chat_consolidation`, draft→pending, saved→applied, action `open_consolidation` → navigates to Consolidate). No apply/save from the queue. 185/185 backend tests pass (27 new consolidation tests), `npm run build` clean.

**Proposal Queue v1:** the first piece of the generalized proposal/apply spine is real but intentionally minimal. A new **read-only** aggregation layer (`backend/app/proposals.py`) exposes `GET /api/proposals`, normalizing existing Raw Inbox classification proposals into a shared shape (`id`, `source`, `type`, `riskLevel`, `title`, `summary`, `status`, `confidence`, `targetPath`, `createdAt`, `updatedAt`, `relatedId`, `actions[]`, `details{}`). Intake status maps to generalized status (`proposed`/`edited`→`pending`, `approved`→`approved`, `routed`/`archived`→`applied`, `skipped`→`skipped`). A new **Proposal Queue** page (`src/pages/ProposalsPage.tsx`, nav under the same group as Raw Inbox) lists/filters/searches proposals; the only action is **Open in Raw Inbox** (navigates to the existing approve/edit/route workflow). There is **no approve/apply in the queue** — this sprint creates the shared review surface without increasing mutation power. The generalized proposal/apply foundation is **started, not complete**: only Raw Inbox feeds it; Research, Chat/AI Consolidation, Gmail, MCP, and Agent sources will plug into the same `list_normalized_proposals()` later. No new AI or privileged tool behavior exists. Listing is read-only: no intake metadata change, no vault write, no `brain`, no Ollama. 158/158 backend tests pass (15 new proposal-queue tests), `npm run build` clean.

Dashboard Active Work drill-down is complete, plus the first Dashboard write action: **Mark done** quick actions on Backfill and Escalation active-work items. Each opens a confirmation modal, calls the existing backup-before-write status endpoint (`PATCH /api/vault/backfill/{itemId}/status` and `.../escalations/{itemId}/status`) with `done`, reloads the Dashboard summary on success, and shows an inline error on failure. No other Dashboard mutations exist.

Dashboard **Recent AI Work** rows now deep-link into Local Agent: clicking a row opens AgentPage with that conversation selected and its messages loaded (`GET /api/conversations/{id}`). Read-navigation only — no Ollama/chat call, no mutation. The deep-link is an app-state handoff (`agentConvTarget` in the zustand store, mirroring `agentPrefill`) since the app has no URL router; AgentPage consumes it on mount. A missing conversation shows a clear error and keeps the page usable.

**Runtime honesty pass (latest):** the UI no longer presents unimplemented privileged systems as ready. OpenClaw tool bridge, NemoClaw/OpenShell, Browser harness, Computer use, and MCP gateway now display as **Not wired** with neutral styling on the Dashboard runtime panel (under a "Planned — not wired yet" divider) and the Tool Safety page. Backend, Brain CLI, Vault, and Local model remain real backend-derived status. The Tool Safety page now lists the actual enforced controls (brain allowlist, no arbitrary shell, backup-before-write, no Gmail mutations, no Google Calendar API writes, no browser/computer-use). Agent modes are labeled **UI-only** (not enforced yet). *(Both Research and Chat/AI Consolidation have since shipped real manual v1 capture flows — see latest entries above. The browser/computer-use runtimes they ultimately need remain Not wired.)* No backend changes in that pass.

## Real Workflows

| Workflow | What is wired |
|---|---|
| **Dashboard** | `GET /api/dashboard/summary` — aggregated counts, Today's Plan (deterministic), Recent AI Work (deep-links into Local Agent conversation), Active Work drill-down (backfill/escalations/resume/calendar/raw) + Mark-done quick actions |
| **Raw Inbox** | Stage / heuristic classify / AI classify (metadata only) / edit / approve / batch-approve / route to vault / brain sync-raw / archive staged original |
| **Proposal Queue** | Read-only — `GET /api/proposals` normalizes Raw Inbox proposals **+ Consolidation drafts + Research drafts**; filter/search/counts; actions **deep-link to the exact source item** (highlight + scroll on Inbox/Consolidate/Research) — no approve/apply/save in-queue |
| **Chat/AI Consolidation** | Manual paste/import — create/list/edit drafts; Save to vault writes one Markdown summary to `raw/chats/<source>/`. No AI, no brain, no browser/computer-use capture |
| **Research** | Manual capture — create/list/edit drafts; Save to vault writes one Markdown note to `raw/research/<topic>/`. No AI, no URL fetch, no web search, no browser/computer-use |
| **Tasks** | Read (`ops/task-db.md` or `ops/tasks.md`), status edit, create new row — `GET /PATCH /POST /api/vault/tasks` |
| **Calendar Candidates** | Read / create file / add candidate / edit / approve / export-open manual — `ops/calendar-candidates.md` |
| **Entity creation** | Projects, Courses, Hackathons (brain CLI), Business (filesystem scaffold) |
| **Backfill** | Read / create file / add item / status edit / field edit — `ops/backfill.md` (or read-only fallback `ops/backfill-last-year.md`) |
| **Resume Pipeline** | Read / create file / add item / status edit / field edit / tailoring prompt — `ops/resume-pipeline.md` |
| **Escalation Queue** | Read / create file / add item / status edit / field edit / handoff prompt — `ops/escalation-queue.md` |
| **Local Agent** | Ollama streaming chat, conversation history, context window, `GET /api/agent/status` |
| **Settings / Config** | Vault path + brain.cmd path, env-var/file/default layering |

## Still Not Implemented

- OpenClaw / NemoClaw / OpenShell runtime wiring
- MCP gateway
- Browser harness / computer use / web search (incl. automatic ChatGPT/Claude transcript capture and automated research — Consolidation and Research are manual capture only; no URL fetching)
- Gmail intake
- Google Calendar API writes or automatic import
- Autonomous Claude Code / OpenCode launch (prompt generation only — no process launched)
- Arbitrary shell execution or file modification
- Repo scanning / automatic closeout
- Job application automation

## Safety Constraints

- No Claude Code / OpenCode process launched by Brain UI at any point.
- No shell commands beyond the strict `brain` allowlist.
- Every vault write: re-read → re-parse → conflict check → backup → write.
- `ops/backfill-last-year.md` permanently read-only.
- `POST **/create` endpoints never overwrite existing files.
- Path traversal rejected on all vault operations.
- `extra="forbid"` on all Pydantic create/update request models.
- Dashboard summary endpoint is entirely read-only — no mutations in activeWork building.
- Consolidation: transcript treated as untrusted (stored + fenced only, never executed or sent to AI); creating a draft writes no vault file; saving writes exactly one file under `raw/chats/<source>/`, never overwrites, never escapes the vault; no brain/AI/tasks/calendar/resume side effects.
- Research: pasted notes/sources treated as untrusted (stored + fenced only, URLs never fetched, never sent to AI); creating a draft writes no vault file; saving writes exactly one file under `raw/research/`, never overwrites, never escapes the vault; no web fetch/search/brain/AI/tasks/calendar/resume side effects.

## Next Recommended Sprints

1. **Capture polish** — optional opt-in local-AI summary assist for Consolidation and Research (metadata-style prompt, still preview-before-save, content still untrusted/no fetch).
2. **Open-to-edit on deep-link** — optionally auto-open the edit modal (not just highlight) for an unsaved Consolidation/Research draft arriving from the Proposal Queue, if that proves more useful than highlight-only.
3. **Filtered today view** — Tasks page "Today" filter showing only blocked/overdue/due-today items, matching the Dashboard Today's Plan logic.

## Test Plan

```bash
# Backend (includes 31 new research tests)
python -m pytest backend/tests/ -q
# Expected: 216 passed, 1 warning

# Frontend
npm run build
# Expected: 83 modules, 0 TypeScript errors, built in ~1s

# Python compile check
python -m py_compile backend\app\dashboard.py backend\app\vault.py backend\app\main.py backend\app\models.py
```
