# Session Summary: Proposal Queue source deep-linking

Date: 2026-06-12
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Connect the Proposal Queue back to the **exact** source item, not just the source page. Clicking a queue item now opens the correct source page and highlights/scrolls to the related row or draft, so the user lands on the precise place where approval / edit / save happens. This is navigation/state-restoration only — no new writes, no backend change, and the Proposal Queue stays read-only.

---

## Handoff / deep-link mechanism

Mirrors the existing `agentConvTarget` pattern (Dashboard → Agent conversation):

- **Store (`src/store/useAppStore.ts`)** — new `proposalTarget: { source: 'raw-inbox' | 'chat-consolidation' | 'research'; relatedId: string } | null` plus `setProposalTarget`. Exported types `ProposalTarget` / `ProposalTargetSource`.
- **Proposal Queue (`src/pages/ProposalsPage.tsx`)** — `handleOpen` sets `proposalTarget` from the proposal's `relatedId` (which is the intake file id for Raw Inbox, the draft id for Consolidation/Research) and then navigates. If `relatedId` is missing it falls back to plain navigation.
- **Each source page** consumes the target on mount (capturing `relatedId`, immediately clearing the store), then — once its own list has loaded — highlights + scrolls the matching item into view and shows an unobtrusive "Opened from Proposal Queue." notice. The highlight fades after ~4s. A missing/deleted target shows a non-blocking notice and keeps the page usable.

The app has no URL router, so this app-state handoff is the established deep-link idiom.

---

## Frontend files changed

| File | Change |
|---|---|
| `src/store/useAppStore.ts` | Added `proposalTarget` state, `setProposalTarget`, and `ProposalTarget`/`ProposalTargetSource` types. |
| `src/pages/ProposalsPage.tsx` | `handleOpen` now sets `proposalTarget` (by `relatedId`) before navigating; missing id → plain navigation. |
| `src/pages/InboxPage.tsx` | Consumes a `raw-inbox` target; highlights + scrolls the matching staged row (`inset` accent + `--live-bg`); "Opened from Proposal Queue." / "Target proposal was not found. Showing Raw Inbox." notice. |
| `src/pages/ConsolidatePage.tsx` | Consumes a `chat-consolidation` target; highlights + scrolls the matching draft card; same notices (deleted → "That draft could not be found…"). |
| `src/pages/ResearchPage.tsx` | Consumes a `research` target; same highlight/scroll/notice behavior. |

## Backend files changed

None. The prompt's existing endpoints were sufficient (`GET /api/intake/proposals`, `GET /api/consolidation/drafts`, `GET /api/research/drafts`, `GET /api/proposals`). No new endpoints, no mutations, no vault writes.

---

## Per-source behavior

- **Raw Inbox** — matches `entry.file.id === relatedId`; the row gets a left accent bar + tinted background and scrolls into center; highlight only — nothing is approved, routed, or skipped.
- **Consolidation** — matches `draft.id === relatedId`; the draft card gets an outline + ring and scrolls into view. No auto-edit, no auto-save (the edit modal still opens only when the user clicks Edit).
- **Research** — identical to Consolidation for research drafts.

All three clear the target as soon as it is captured (so a refresh or re-navigation without a fresh click won't re-trigger), and the highlight auto-clears after ~4s or when the user interacts.

---

## What remains read-only

The Proposal Queue itself: no approve/apply/save/delete, no bulk actions, no vault writes. Deep-linking is pure selection/highlight — all mutation continues to live in the source workflows (Raw Inbox approve/route, Consolidation/Research Save to vault).

---

## Safety constraints honored

No backend changes, no new mutation endpoints, no vault writes, no AI/browser/computer-use/MCP. Deep-linking never approves, routes, skips, edits, or saves anything. Existing Dashboard/Agent `agentConvTarget` deep-link behavior, Proposal Queue filters/read-only behavior, and all source-page workflows are preserved.

---

## Docs updated

- `README.md` — Proposal Queue section + capability row now describe exact-item deep-linking via `proposalTarget`, still read-only.
- `context/current-task.md` — deep-linking documented in Current State + Real Workflows; next-sprint list updated.
- This session summary.

---

## Tests run

- `python -m pytest backend/tests` → **216 passed**, 1 pre-existing warning (no backend change).
- `npm run build` → clean, **83 modules**, 0 TypeScript errors.

---

## Recommended next sprint

Optional **open-to-edit on deep-link** — auto-open the edit modal (not just highlight) for an unsaved Consolidation/Research draft arriving from the Proposal Queue, if that proves more useful than highlight-only. Otherwise, opt-in local-AI summary assist for Consolidation/Research (preview-before-save, content still untrusted / never fetched). Higher-risk browser/computer-use capture stays deferred.
