# Session Summary: Research v1 (manual capture)

Date: 2026-06-12
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Give Research a useful, PRD-aligned v1 within the existing safety model. The page was previously gated as "planned / not wired." This sprint implements **manual capture only**: the user pastes research notes, links, source snippets, and findings → a structured backend draft → preview/edit → explicit Save writes one Markdown research note under `raw/research/<topic>/`. No browser automation, web search, URL fetching, computer-use, MCP, or AI.

It also extends the generalized proposal spine: unsaved research drafts now appear in the Proposal Queue (third source, after Raw Inbox and Consolidation).

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/research.py` (new) | Draft model + JSON storage (`backend/data/research/drafts.json`) + `create_draft` / `list_drafts` / `get_draft` / `update_draft` / `save_draft` + Markdown renderer + `normalized_proposals()` for the queue. |
| `backend/app/proposals.py` | `list_normalized_proposals()` now also appends research drafts (independent try/except → per-source error entry). |
| `backend/app/models.py` | `ResearchSource`, `ResearchDraftResponse`, `ResearchDraftsResponse`, `CreateResearchDraftRequest` (extra=forbid), `UpdateResearchDraftRequest` (extra=forbid), `SaveResearchDraftResponse`. |
| `backend/app/main.py` | `POST/GET /api/research/drafts`, `GET/PATCH /api/research/drafts/{id}`, `POST /api/research/drafts/{id}/save`; `_research_to_response` mapper. |
| `backend/tests/test_research.py` (new) | 31 tests. |

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/api.ts` | Research types (`ResearchDomain`, `ResearchSource`, `ResearchDraft`, request/response types) + `createResearchDraft` / `listResearchDrafts` / `getResearchDraft` / `updateResearchDraft` / `saveResearchDraft`. Extended proposal unions with `research` / `research_note` / `open_research`. |
| `src/pages/ResearchPage.tsx` | Rewritten: new-draft form, shared `DraftFieldSet`, repeatable `SourcesEditor` ({title,url,notes}), drafts list with status + destination/saved path, edit modal, Save-to-vault confirmation, saved notice, safety notice. |
| `src/pages/ProposalsPage.tsx` | Renders `research` proposals; "Open in Research" button → `navigate('research')`. |

## Draft lifecycle

```text
create  → status "draft"  (backend metadata only; proposedDestination = raw/research/<slug(topic|title)>/<date>-<slug(title)>.md)
edit    → PATCH editable fields (title/topic/domain/entity/researchQuestion/summary/keyFindings/sources/openQuestions/recommendedNextActions/rawNotes)
save    → status "saved" (one Markdown note written; savedPath set)
```

Locked after creation: `id`, `createdAt`, `updatedAt`, `status`, `savedPath`. Status maps into the queue as `draft → pending`, `saved → applied`.

Create validation: non-empty `title`; at least one of `rawNotes` / `summary` / a key finding; `domain` ∈ {project, course, business, personal, technical, market, general, unknown}; path-traversal markers (`..`, null) in `title`/`topic`/`entity` rejected.

## Vault save behavior

- Writes exactly **one** Markdown note under `vault/raw/research/<slug(topic|title)>/`. Sections: header (captured-at/domain/entity/topic/status), Research Question, Summary, Key Findings, Sources (Markdown links when a URL is present), Open Questions, Recommended Next Actions, and Raw Notes inside a fenced block whose fence is widened past any backticks in the notes.
- **Never overwrites** — UUID suffix on filename collision.
- The stored relative destination is re-validated at save (must start with `raw/research/`, no `..`, not absolute) and the resolved path must stay under the vault root.
- No `brain`, no AI, no URL fetch, no web search, no tasks/calendar/resume side effects.

## Proposal Queue integration

`GET /api/proposals` now aggregates Raw Inbox proposals, consolidation drafts, **and** research drafts. Research items: `source=research`, `type=research_note`, `riskLevel=medium`, `summary` = summary → first key finding → fallback, `targetPath` = savedPath or proposedDestination, `actions=["open_research"]`. The queue still has **no** apply/save action — it only navigates to the Research page.

## Safety constraints honored

- Pasted notes and source snippets treated as untrusted: stored and embedded only; never executed, **never fetched**, never sent to an LLM, never interpreted as instructions.
- Creating a draft writes nothing to the vault. Saving is the only vault write and is explicit/confirmed.
- No browser/computer-use/MCP/web-search/URL-fetch, no external tool launch, no `brain sync-raw`, no AI, no automatic tasks/calendar/resume.
- `extra="forbid"` on create/update request models.

## Tests run

- `python -m pytest backend/tests` → **216 passed**, 1 pre-existing warning (`VaultFolders.schema` shadow). 31 new research tests cover create/validation (title, content-presence, domain, traversal), source cleaning, destination mapping (topic vs title slug), list/get, editable-vs-locked updates, title→destination resync, save (write-once, no-overwrite, traversal/out-of-scope rejected, marks saved), backtick fencing, and queue aggregation (read-only).
- `npm run build` → clean, **83 modules**, 0 TypeScript errors.

## What remains not implemented

Browser research automation, web search, URL fetching, computer-use, MCP, Gmail, AI research/summarization, automatic tasks/calendar/resume, Proposal Queue apply/save, OpenClaw/NemoClaw runtime, tool logs, Google Calendar API.

## Recommended next sprint

**Proposal Queue deep-links** — open a specific Consolidation/Research draft for editing directly from the queue (mirroring the existing `agentConvTarget` app-state handoff), now that all three manual sources feed it. Optionally, an opt-in local-AI summary assist for Consolidation and Research (metadata-style prompt, preview-before-save, content still untrusted / never fetched). Higher-risk browser/computer-use capture stays deferred.
