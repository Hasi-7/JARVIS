# Current Task

## Goal

Sprint 26 complete: Backfill row creation from the UI — safe capture of prior work.

Next possibilities:
- Backfill field editing (type, value, path, notes, agent) after creation
- Resume Pipeline row creation (same pattern as Backfill)
- Escalation Queue: mark items done from Dashboard quick actions
- Dashboard refresh interval / background polling

## Relevant Files

- PRD.md
- DESIGN.md
- backend/app/vault.py
- backend/app/models.py
- backend/app/main.py
- src/lib/api.ts
- src/pages/BackfillPage.tsx
- backend/tests/test_backfill_creation.py  ← new
- context/current-task.md

## Current State

- `GET /api/vault/backfill` reads `ops/backfill.md` or `ops/backfill-last-year.md`
- `POST /api/vault/backfill/create` creates `ops/backfill.md` starter file if missing (never overwrites)
- `POST /api/vault/backfill` appends a new row to `ops/backfill.md` with backup
- `PATCH /api/vault/backfill/{id}/status` updates status cell with backup
- `ops/backfill-last-year.md` is always read-only — appends rejected with clear message
- BackfillPage: missing state shows "Create Backfill file" button
- BackfillPage: fallback-only state (last-year file) shows notice + "Create ops/backfill.md" button
- BackfillPage: "New Backfill Item" button appears when primary file is in markdown-table mode
- BackfillPage: Add Item modal with item/type/status/value/agent/path/notes fields
- BackfillPage: safety note in modal; error stays in modal on failure; modal closes and list reloads on success
- Closeout prompt, filters, status editing all still work unchanged
- 53/53 backend tests pass; npm run build passes

## Constraints

- No Claude Code/OpenCode launch from Brain UI.
- No shell commands.
- No repo modifications.
- Backups before every write.
- Only `ops/backfill.md` is ever written.
- Allowed statuses: new | triaged | in-progress | done | skipped.
- Allowed types: project | repo | hackathon | course | business | other.
- Allowed values: high | medium | low.
- Allowed agents: claude-code | opencode | manual.

## Do Not Touch

- Raw Inbox routing/sync/archive behavior
- Calendar candidates workflow
- Tasks write behavior (still only editable from Tasks page)
- Entity creation command mapping
- Conversation files (read-only from Dashboard)
- `ops/backfill-last-year.md` (read-only fallback, never written)

## Acceptance Criteria — all met

- `POST /api/vault/backfill/create` creates `ops/backfill.md` only when missing. ✓
- Existing `ops/backfill.md` is not overwritten. ✓
- `POST /api/vault/backfill` appends a valid row to `ops/backfill.md`. ✓
- Append rejects if only fallback file exists (clear message). ✓
- Append rejects malformed `ops/backfill.md`. ✓
- Backup created before append. ✓
- Invalid status/type/value/agent rejected (400). ✓
- Raw newlines rejected. ✓
- Pipe characters sanitized. ✓
- No repo/path is modified. ✓
- Backfill page has "New Backfill Item" action (enabled when primary file + markdown-table). ✓
- Create-file button works when missing or fallback-only. ✓
- Add modal validates required fields. ✓
- Successful add reloads list. ✓
- Errors visible in modal. ✓
- Existing filters/status/prompt behavior still works. ✓
- npm run build passes. ✓
- 53/53 backend tests pass. ✓

## Test Plan

- python -m pytest backend/tests/
- npm run build
