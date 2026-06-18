# Session Summary: Chat/AI Consolidation v1 (manual paste/import)

Date: 2026-06-12
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Make Chat/AI Consolidation useful now, within the existing safety model. The page was previously gated as "planned / not wired." This sprint implements **manual paste/import only**: paste a ChatGPT / Claude / Claude Code / OpenCode transcript → create a backend draft → preview/edit a structured summary → explicitly save one Markdown summary into the vault under `raw/chats/<source>/`. No browser automation, computer-use, MCP, AI summarization, or automatic capture.

This also extends the generalized proposal spine: unsaved consolidation drafts now appear in the Proposal Queue.

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/consolidation.py` (new) | Draft model + JSON storage (`backend/data/consolidation/drafts.json`) + `create_draft` / `list_drafts` / `get_draft` / `update_draft` / `save_draft` + Markdown renderer + `normalized_proposals()` for the queue. |
| `backend/app/proposals.py` | `list_normalized_proposals()` now also appends consolidation drafts (independent try/except → per-source error entry). |
| `backend/app/models.py` | `ConsolidationDraftResponse`, `ConsolidationDraftsResponse`, `CreateConsolidationDraftRequest` (extra=forbid), `UpdateConsolidationDraftRequest` (extra=forbid), `SaveConsolidationDraftResponse`. |
| `backend/app/main.py` | `POST/GET /api/consolidation/drafts`, `GET/PATCH /api/consolidation/drafts/{id}`, `POST /api/consolidation/drafts/{id}/save`; `_consolidation_to_response` mapper. |
| `backend/tests/test_consolidation.py` (new) | 27 tests. |

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/api.ts` | Consolidation types (`ConsolidationSourceTool`, `ConsolidationDomain`, `ConsolidationDraft`, request/response types) + `createConsolidationDraft` / `listConsolidationDrafts` / `getConsolidationDraft` / `updateConsolidationDraft` / `saveConsolidationDraft`. Extended proposal unions with `chat-consolidation` / `chat_consolidation` / `open_consolidation`. |
| `src/pages/ConsolidatePage.tsx` | Rewritten: new-draft form, drafts list with status + destination/saved path, edit modal (locked transcript/source), Save-to-vault confirmation, saved notice, safety notice. |
| `src/pages/ProposalsPage.tsx` | Renders `chat-consolidation` proposals; "Open in Consolidation" button → `navigate('consolidate')`. |

## Draft lifecycle

```text
create  → status "draft"  (backend metadata only; proposedDestination = raw/chats/<tool>/<date>-<slug>.md)
edit    → PATCH editable fields (title/domain/entity/summary/decisions/actionItems/codeOrFilesReferenced)
save    → status "saved" (one Markdown file written; savedPath set)
```

Locked after creation: `id`, `createdAt`, `sourceTool`, `transcript`, `status`, `savedPath`.
Status maps into the queue as: `draft → pending`, `saved → applied`.

## Vault save behavior

- Writes exactly **one** Markdown file under `vault/raw/chats/<sourceTool>/`. Directory derived only from the validated `sourceTool` (no user path input).
- **Never overwrites** — UUID suffix on filename collision.
- Resolved directory and file must stay under the vault root (traversal rejected); a draft with a tampered `sourceTool` is rejected.
- Markdown: title, source/captured-at/domain/entity/status header, Summary, Decisions, Action Items, Code or Files Referenced, and the Original Transcript inside a fenced block whose fence is widened past any backticks in the transcript.
- No `brain`, no AI, no tasks/calendar/resume side effects.

## Proposal Queue integration

`GET /api/proposals` now aggregates Raw Inbox proposals **and** consolidation drafts. Consolidation items: `source=chat-consolidation`, `type=chat_consolidation`, `riskLevel=medium`, `targetPath` = savedPath or proposedDestination, `actions=["open_consolidation"]`. The queue still has **no** apply/save action — it only navigates to the Consolidate page.

## Safety constraints honored

- Transcript treated as untrusted: only stored and embedded in a fenced block; never executed, never sent to an LLM, never interpreted as instructions.
- Creating a draft writes nothing to the vault. Saving is the only vault write and is explicit/confirmed.
- No browser/computer-use/MCP, no external tool launch, no `brain sync-raw`, no AI summarization (missing summary → deterministic transcript-preview fallback), no automatic tasks/calendar/resume.
- `extra="forbid"` on create/update request models.

## Tests run

- `python -m pytest backend/tests` → **185 passed**, 1 pre-existing warning (`VaultFolders.schema` shadow). 27 new consolidation tests cover create/validation, destination mapping, list/get, editable-vs-locked updates, save (write-once, no-overwrite, traversal rejected, marks saved), backtick fencing, and queue aggregation (read-only).
- `npm run build` → clean, **83 modules**, 0 TypeScript errors.

## What remains not implemented

Browser capture, computer-use capture, ChatGPT/Claude web automation, MCP, Gmail, AI summarization, automatic tasks/calendar/resume, Proposal Queue apply/save, OpenClaw/NemoClaw runtime, tool logs, Google Calendar API.

## Recommended next sprint

Optional opt-in **local-AI summary assist** for consolidation (metadata-style prompt, still preview-before-save, transcript still untrusted), plus a **Proposal Queue deep-link** that opens the specific draft for editing (mirroring the existing `agentConvTarget` handoff). Higher-risk capture (browser/computer-use) stays deferred.
