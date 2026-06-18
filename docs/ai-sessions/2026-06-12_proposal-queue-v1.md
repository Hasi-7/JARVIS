# Session Summary: Proposal Queue v1 (generalized proposal/apply spine — read-only)

Date: 2026-06-12
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Add the first piece of the generalized **propose → preview → approve → apply** spine the PRD requires before Research Mode, Chat/AI Consolidation, Gmail intake, MCP tools, and OpenClaw tool requests are built. This was the recommended next sprint from the 2026-06-11 runtime-honesty session.

Scope was deliberately minimal and safe: create a shared *review surface* and a normalized proposal shape **without increasing mutation power**. v1 aggregates only the existing Raw Inbox classification proposals. No new AI capability, no new persistence DB, no new autonomous writes, and no change to existing Raw Inbox approval/routing.

---

## Context

Entering this session the working tree already contained an in-progress implementation (untracked `backend/app/proposals.py`, `backend/tests/test_proposals_queue.py`, `src/pages/ProposalsPage.tsx`, plus edits to `main.py`, `models.py`, `api.ts`, `App.tsx`, `useAppStore.ts`, `types/index.ts`, `data/mock.ts`). This session verified the implementation end-to-end and completed the documentation, which had not been updated.

---

## What was built (verified this session)

### Backend

| File | Role |
|---|---|
| `backend/app/proposals.py` | Read-only aggregation layer. `list_normalized_proposals() -> (items, errors)` maps Raw Inbox intake proposals into the normalized shape. A failing source yields an error entry + empty contribution rather than failing the request. |
| `backend/app/models.py` | `ProposalDetails`, `ProposalItem`, `ProposalListError`, `ProposalListResponse`. |
| `backend/app/main.py` | `GET /api/proposals` → `ProposalListResponse`. Read-only; listing mutates nothing. |
| `backend/tests/test_proposals_queue.py` | 15 tests: empty list, basic mapping, status mapping (incl. unknown→pending), routed targetPath/updatedAt, title fallbacks, blank-confidence normalization, failing-source-returns-error, listing-writes-no-files. |

### Frontend

| File | Role |
|---|---|
| `src/lib/api.ts` | `ProposalStatus`, `ProposalRiskLevel`, `ProposalType`, `ProposalSource`, `ProposalAction`, `ProposalDetails`, `ProposalItem`, `ProposalListError`, `ProposalListResponse`; `api.getProposals()`. |
| `src/pages/ProposalsPage.tsx` | Proposal Queue page: total/pending/applied/skipped-rejected counts, filters (status, type, source, confidence, search), proposal cards, empty state, v1 banner, read-only footer note. Only action: **Open in Raw Inbox** → `navigate('inbox')`. |
| `src/types/index.ts` | `'proposals'` added to `RouteId`. |
| `src/data/mock.ts` | `Proposal Queue` nav item (glyph `check`). |
| `src/App.tsx` | `case 'proposals'` → `<ProposalsPage />`. |

### Proposal model / mapping

Normalized shape: `id`, `source`, `type`, `riskLevel`, `title`, `summary`, `status`, `confidence`, `targetPath`, `createdAt`, `updatedAt`, `relatedId`, `actions[]`, `details{ filename, domain, entity, sourceType, reason }`.

Raw Inbox status mapping: `proposed`/`edited` → `pending`, `approved` → `approved`, `routed` → `applied`, `archived` → `applied`, `skipped` → `skipped`, unknown → `pending`. `type` is `file_route` (risk `medium`); `targetPath` is the routed path for routed/archived items, otherwise the proposed destination; `relatedId` is the intake file id; `title` is the original/staged/routed filename (falling back to file id).

### Docs

- `README.md` — new "Proposal Queue (v1)" section + capability-table row.
- `context/current-task.md` — Proposal Queue v1 documented in Current State + Real Workflows row; test counts refreshed 143→158.
- This session summary.

---

## What remains read-only / deferred

- `GET /api/proposals` never approves, routes, writes vault files, writes intake metadata, runs `brain`, or calls Ollama.
- No approve/apply button exists in the Proposal Queue — apply still happens in the Raw Inbox source workflow, unchanged.
- The generalized foundation is **started, not complete**: only Raw Inbox feeds it. Research, Chat/AI Consolidation, Gmail, MCP, and Agent proposals are intentionally deferred and will extend `list_normalized_proposals()` later.
- No new persistence DB, no Dashboard apply actions, no bulk apply, no delete.

---

## Tests

- `python -m pytest backend/tests` → **158 passed**, 1 pre-existing warning (`VaultFolders.schema` shadow). 15 new proposal-queue tests.
- `npm run build` → clean, **83 modules**, 0 TypeScript errors.

---

## Safety constraints honored

Listing is read-only and side-effect-free (a test asserts no files are written). No new AI, no new privileged tools, no new vault writes, no brain commands, no external calls. Existing Raw Inbox behavior is untouched.

---

## Recommended next sprint

Extend the proposal spine to a **second source** to prove the abstraction (e.g., Calendar Candidates as normalized proposals, still read-only / open-in-source), or design the **apply path** (`POST /api/proposals/{id}/apply`) that re-expresses an existing backup-before-write flow through the queue without adding new mutation power. High-risk agent/browser/MCP/NemoClaw runtime work stays deferred until the spine and real mode-gating exist.
