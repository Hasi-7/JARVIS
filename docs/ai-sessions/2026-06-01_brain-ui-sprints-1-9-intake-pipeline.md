# Session Summary: Brain UI — Backend + Full Intake Pipeline (Sprints 1–9)

Date: 2026-06-01
Tool: Claude Code (claude-sonnet-4-6)
Project: JARVIS / Brain UI (`D:\Hasnain\Personal\dev\JARVIS`)

---

## Goal

Build the complete backend and intake pipeline for Brain UI, covering Sprints 1–9:

- Sprint 1: Editable Settings page, localStorage persistence
- Sprint 2: FastAPI backend skeleton, safe allowlisted brain.cmd wrapper, config/status endpoints, Dashboard buttons wired
- Sprint 3: Unify frontend Settings with backend config (PUT /api/config)
- Sprint 4: Raw Inbox staging — drag/drop upload, list, delete staged files
- Sprint 5: Heuristic classification proposals for staged files + proposal CRUD + edit modal
- Sprint 6: Batch approval UI — checkboxes, batch action bar, confirmation modal
- Sprint 7: Vault routing — copy approved staged files into configured vault path
- Sprint 8: Manual brain sync-raw action panel after routing
- Sprint 9: Staged file cleanup — archive routed files to `backend/data/archive/` (INCOMPLETE — only `ARCHIVE_DIR` constant added before context limit)

---

## Context

- Continuing from the previous session (`2026-05-31_brain-ui-frontend-foundation.md`), which established the React/Vite/TypeScript UI shell with all mock data.
- All sprint work in this session was committed as **working tree changes only** — no commits were made. All changes remain unstaged.
- The backend (`backend/`) is entirely new (untracked). `src/lib/api.ts` is also new (untracked).
- Stack: React 18 + Vite 5 + TypeScript + Tailwind CSS v3 + Zustand (frontend); FastAPI + Pydantic v2 + Uvicorn (backend).
- This session ran across multiple context windows. Sprint 9 was interrupted by context limit after adding `ARCHIVE_DIR` to `intake.py` — archive functions were not implemented.

---

## Files Changed

### New (untracked)

**`backend/`** — entire Python backend created from scratch:
- `backend/requirements.txt` — fastapi, uvicorn[standard], pydantic>=2.7, python-multipart
- `backend/app/__init__.py`
- `backend/app/main.py` — FastAPI app; all endpoints through Sprint 8
- `backend/app/config.py` — `RuntimeConfig` dataclass, `get_config()`, `update_config()`, env var overrides
- `backend/app/security.py` — `ALLOWED_COMMANDS` frozenset + `is_allowed()` guard
- `backend/app/brain.py` — `run_brain_command()` using `subprocess.run` with `cmd.exe /c`, shell=False
- `backend/app/models.py` — all Pydantic v2 response/request models
- `backend/app/classify.py` — pure heuristic classifier (filename + MIME → domain/sourceType/confidence), 13 rules, no I/O
- `backend/app/intake.py` — staging + proposal + routing module (core of the intake pipeline)

**`src/lib/api.ts`** — full typed frontend API client for all backend endpoints

### Modified

| File | What changed |
|---|---|
| `src/lib/config.ts` | Added `String.raw` for Windows paths in DEFAULTS; `hasLocalSettings()` helper |
| `src/store/useAppStore.ts` | Added backend state, `checkBackend()`, `syncConfigToBackend()`, `runBrainCommand()`, `setStagedCount`, `setPendingProposalCount`, `addCmdEntry`, `loadStagedCount` |
| `src/components/layout/AppShell.tsx` | `checkBackend()` + `loadStagedCount()` on mount; BRAIN_ACTION_MAP for palette commands |
| `src/pages/SettingsPage.tsx` | Full editable form (vault path, brain.cmd), PUT /api/config on save, localStorage sync, status indicators |
| `src/pages/DashboardPage.tsx` | Wired quick actions to backend (`today`, `weekly`, `sync-raw`, `calendar-export`); live stagedCount + pendingProposalCount badges |
| `src/pages/InboxPage.tsx` | Entire intake workflow (~1020 lines added): drag/drop upload, staged file list, proposals grid, edit modal, batch approval, routing confirmation modal, SyncPanel (sync-raw after routing) |
| `.gitignore` | Added `backend/.venv/`, `backend/data/`, `__pycache__/`, `*.py[cod]` |
| `README.md` | Added backend setup and run instructions |

---

## Commands Run

None were run during coding (read/edit only). The following commands are needed to run the project:

```powershell
# Backend
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Frontend
npm run dev
```

Build validation (`npm run build`) was confirmed passing at Sprint 8 end (85 modules, 0 TS errors). Not re-run after Sprint 9 partial changes.

---

## Decisions Made

| Decision | Reason |
|---|---|
| `subprocess.run` with `shell=False` + `cmd.exe /c` for .cmd files | Prevents shell injection; Windows requires cmd.exe to execute .cmd scripts |
| `shutil.copy2` for routing (not move) | Staged originals kept until explicitly archived; safer for accidental re-route |
| `threading.Lock()` guards both `index.json` and `proposals.json` | Atomic writes prevent index/proposal desync during concurrent upload/delete/route |
| `validate_destination()` enforces `raw/` prefix + no `..` + no absolute paths | Path traversal prevention; all staged files must land in vault's raw/ folder |
| `String.raw` for Windows paths in frontend config defaults | Avoids `\H` etc. being interpreted as escape sequences in TypeScript |
| `batch_approve_proposals()` uses single lock acquisition with tolerance | Invalid IDs go to 'skipped' rather than aborting the entire batch |
| Config reconciliation on `checkBackend()`: push local if localStorage exists, else seed from backend | Avoids overwriting user's local path customizations; first-run gets backend defaults |
| CORS allows `GET, POST, PUT, DELETE` | Required for staged file DELETE endpoints and config PUT |
| `ARCHIVE_DIR = backend/data/archive/` (never permanent delete) | Safety-first: staged originals survive until user explicitly archives |
| Allowlist approach for brain commands (frozenset) | Prevents arbitrary shell execution; only 9 safe subcommands exposed |

---

## Bugs Fixed

- `StatusDot` component does not accept `style` prop — wrapped in `<span style={{marginTop: 3, flexShrink: 0, lineHeight: 0}}>` in SettingsPage
- Windows path strings with backslashes caused TS escape warnings — fixed with `String.raw` template literals in `config.ts`
- `approve-batch` route must be placed before `{file_id}/approve` in `main.py` to avoid path ambiguity (different HTTP methods, but ordering made explicit for clarity)
- CORS initially only had GET/POST — progressively expanded to include PUT (Sprint 3) and DELETE (Sprint 4)
- `main.py` initially imported `BRAIN_CMD, VAULT_PATH` as module-level constants — refactored to `get_config()` calls after `config.py` was introduced

---

## Tests / Validation

- `npm run build` passed at end of Sprint 8 — 85 modules, 0 TypeScript errors.
- Backend endpoints were not formally tested; Sprint 9 was interrupted before completing archive implementation.
- No automated test suite exists. All validation was done through the browser UI (Needs manual confirmation for current state).

---

## Open Issues

1. **Sprint 9 incomplete**: `ARCHIVE_DIR` constant was added to `intake.py` but archive functions are not implemented:
   - `Proposal.__slots__` not yet extended with `archived_at`, `archived_path`, `archived_name`
   - `archive_staged_file(file_id)` function not written
   - `list_archived()` function not written
   - `models.py` not updated with `ArchiveInfo`, `ArchiveResponse`, `ArchivedFilesResponse`
   - `main.py` missing `POST /api/intake/staged/{fileId}/archive` and `GET /api/intake/archived` endpoints
   - Frontend (`api.ts`, `InboxPage.tsx`) not updated for archive feature

2. **Nothing committed**: All sprint work (backend + frontend) is still in working tree. Needs commit before next session.

3. **Backend config not file-persisted**: `RuntimeConfig` is in-memory only; settings are lost on backend restart. Vault path and brain.cmd must be re-synced from localStorage on each startup.

4. **`context/current-task.md` is stale**: Still describes Sprint 0 (frontend foundation). Should be updated to reflect current sprint.

---

## Next Actions

1. **Commit the current working tree** — commit all unstaged changes (backend/ + modified frontend files) before starting Sprint 9 completion.
2. **Complete Sprint 9** — finish the archive feature:
   - Extend `Proposal` class in `intake.py`
   - Add `archive_staged_file()` and `list_archived()` functions
   - Update `models.py`, `main.py`, `api.ts`, `InboxPage.tsx`
   - Verify `npm run build` passes
3. **After Sprint 9**: Consider Sprint 10 options:
   - Backend config file persistence (`brain-ui-config.json`)
   - Agent cockpit / Ollama integration
   - Backfill a stub page with real vault data via brain CLI

---

## What Should Go to Obsidian raw/

None — this is a pure development session log. No reference material or research was generated.

---

## What Should Go to Obsidian wiki/

- **Brain UI architecture note**: The intake pipeline design (stage → propose → approve → route → sync → archive) is worth capturing as a permanent architecture decision in `wiki/projects/brain-ui-architecture.md`.
- **Windows brain.cmd execution pattern**: `subprocess.run(["cmd.exe", "/c", brain_cmd, subcommand], shell=False)` — worth noting in a dev patterns note.

---

## What Should Go to Obsidian ops/

- **Brain UI dev runbook**: How to start the backend + frontend. Useful for `ops/dev/brain-ui-runbook.md`.

---

## What Should Not Be Saved

- The sprint-by-sprint implementation details — they are derivable from the code and git history.
- Specific line numbers, function signatures, or file paths — those will drift as the code evolves.

---

## Next brain / brain-ingest Command

Before running any brain command, commit the working tree:

```powershell
git add backend/ src/lib/api.ts .gitignore README.md src/components/layout/AppShell.tsx src/lib/config.ts src/pages/DashboardPage.tsx src/pages/InboxPage.tsx src/pages/SettingsPage.tsx src/store/useAppStore.ts
git commit -m "Sprints 1-9: FastAPI backend, intake pipeline, vault routing, sync-raw panel"
```

Then to start the intake cycle manually:

```
brain sync-raw
```

Or via Brain UI's "Run brain sync-raw" button in the Raw Inbox page after routing files.
