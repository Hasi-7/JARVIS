# Session Summary: Calendar Candidates and Entity Creation Workflows

Date: 2026-06-03
Tool: OpenCode
Project: Brain UI / Personal AI Command Center

## Goal

Build the next Brain UI implementation passes for safe calendar candidate workflows and safe entity creation workflows.

The session focused on:

- Calendar candidates read/edit/approve workflow.
- Calendar candidate starter-file creation.
- Manual candidate creation from the Calendar page.
- Safe creation flows for Projects, Courses, Hackathons, and Business areas.
- Documentation updates for the new workflows and safety constraints.

## Context

Source of truth used:

- `PRD.md`
- `DESIGN.md`
- Current implementation
- `AGENTS.md`
- `context/current-task.md`
- `README.md`
- `docs/decisions/decisions.md`

Notes:

- `AGENTS.md` requires reading `context/current-task.md`, avoiding broad architecture changes, documenting major sessions, and recording major decisions when needed.
- `context/current-task.md` is stale relative to this implementation pass; it still describes the original frontend foundation sprint. Needs manual confirmation whether it should be updated.
- `docs/decisions/decisions.md` currently contains only an empty decisions table.
- Worktree was already dirty and contains changes beyond the final entity-creation pass, including prior task/calendar work.

## Files Changed

Observed changed files from `git status --short`:

- `README.md`
- `backend/app/brain.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/security.py`
- `backend/app/vault.py`
- `src/lib/api.ts`
- `src/pages/BusinessPage.tsx`
- `src/pages/CalendarPage.tsx`
- `src/pages/CoursesPage.tsx`
- `src/pages/HackathonsPage.tsx`
- `src/pages/ProjectsPage.tsx`
- `src/pages/TasksPage.tsx`
- `backend/app/calendar.py` untracked
- `backend/app/entities.py` untracked
- `src/components/ui/EntityCreateModal.tsx` untracked
- `docs/ai-sessions/2026-06-03_sprint19-20-obsidian-links-task-editing.md` untracked
- `docs/ai-sessions/2026-06-03_calendar-entities-session.md` added by this closeout

Main session-relevant files:

- `backend/app/calendar.py`: calendar candidate parser/writer, starter creation, add/edit/approve behavior, backups.
- `backend/app/entities.py`: business-area scaffold helper.
- `backend/app/brain.py`: safe command runner with explicit argument schema support.
- `backend/app/security.py`: added `new-project`, `new-course`, `new-hackathon` to allowlist.
- `backend/app/main.py`: added calendar and entity endpoints.
- `backend/app/models.py`: added calendar and entity request/response models.
- `src/lib/api.ts`: added typed calendar and entity API functions/types.
- `src/pages/CalendarPage.tsx`: implemented real Calendar Candidates workflow.
- `src/components/ui/EntityCreateModal.tsx`: shared modal for entity creation forms.
- `src/pages/ProjectsPage.tsx`: added New Project flow.
- `src/pages/CoursesPage.tsx`: added New Course flow.
- `src/pages/HackathonsPage.tsx`: added New Hackathon flow.
- `src/pages/BusinessPage.tsx`: added New Business Area flow.
- `README.md`: documented calendar candidate workflow, entity creation, command allowlist, and safety constraints.

## Commands Run

Shell commands run during the implementation and closeout:

```powershell
npm run build
python -m py_compile backend\app\calendar.py backend\app\main.py backend\app\models.py
python -m py_compile backend\app\brain.py backend\app\entities.py backend\app\main.py backend\app\models.py backend\app\security.py
git status --short
git diff --stat
git diff --name-only
git diff -- README.md backend\app\brain.py backend\app\entities.py backend\app\main.py backend\app\models.py backend\app\security.py src\lib\api.ts src\components\ui\EntityCreateModal.tsx src\pages\ProjectsPage.tsx src\pages\CoursesPage.tsx src\pages\HackathonsPage.tsx src\pages\BusinessPage.tsx
```

Notes:

- `npm run build` was run multiple times after frontend changes and passed.
- Python compile checks were run multiple times after backend changes and passed.
- `git diff --stat` showed a large diff because the worktree includes prior task/calendar changes as well as this session's entity work.

## Decisions Made

- Calendar candidates remain the safe intermediate layer; the app does not create Google Calendar events directly.
- Calendar export/open remain manual actions through `calendar-export` and `calendar-open`.
- Missing `ops/calendar-candidates.md` is created only by explicit user action.
- Adding a calendar candidate requires an existing parseable Markdown table and creates a backup before appending.
- `new-project`, `new-course`, and `new-hackathon` are exposed only through entity-specific endpoints with typed payloads.
- Generic `/api/brain/run` rejects argument-requiring `new-*` commands to avoid raw argument exposure.
- Business area creation uses a safe filesystem scaffold rather than a `brain` command.
- Business scaffold writes only to `raw/business/`, `wiki/business/`, and `ops/business-pipeline.md`.
- Business pipeline is backed up before modification if it already exists.

## Bugs Fixed

- Fixed Calendar page export/open so each button runs the safe command once and logs the result without rerunning through the global command helper.
- Fixed calendar empty starter table parsing so an empty but valid Markdown table is treated as `markdown-table`, enabling the first candidate append.
- Fixed an intermediate `backend/app/brain.py` edit that temporarily interrupted the no-argument command runner; the final file supports both no-argument and argument-aware safe command execution.

## Tests / Validation

Validation performed:

- Frontend production build passed with `npm run build`.
- Backend syntax checks passed with `python -m py_compile` for calendar, entity, command wrapper, main routes, models, and security files.
- Git status/diff inspection performed for closeout.

Not performed:

- No backend unit tests were added or run.
- No manual browser testing was performed in this closeout.
- No real `brain new-project`, `brain new-course`, or `brain new-hackathon` command execution was performed in this session summary step. Needs manual confirmation in runtime.
- No actual Obsidian vault writes were performed during closeout.

## Open Issues

- `context/current-task.md` is stale and still describes the initial frontend foundation sprint. Needs manual confirmation before updating.
- `README.md` still says "Adding or deleting calendar candidates from the UI" under "What's NOT implemented yet", even though adding candidates is now implemented. Needs cleanup.
- No automated tests exist for the new calendar candidate and entity creation endpoints.
- Business scaffold rollback is not implemented if a later write fails after an earlier file/folder was created. Needs manual review if stronger transactional behavior is required.
- CLI argument order for `brain new-project`, `brain new-course`, and `brain new-hackathon` is based on current assumptions from prompt requirements. Needs manual confirmation against the actual `brain` CLI.
- Existing worktree includes unrelated/prior modifications (`backend/app/vault.py`, `src/pages/TasksPage.tsx`, prior session summary). Review before commit.

## Next Actions

- Manually test Calendar page against a real vault with `ops/calendar-candidates.md`.
- Manually test `Create calendar candidates file`, `Add candidate`, edit, approve, export, and open flows.
- Manually test Project, Course, Hackathon creation against actual `brain` CLI behavior.
- Manually test Business area creation and confirm expected files:
  - `raw/business/<safe-name>/`
  - `wiki/business/<safe-name>.md`
  - `ops/business-pipeline.md`
- Add backend unit tests for:
  - Calendar table parsing and starter-file creation.
  - Calendar candidate append/edit/approve validation and backups.
  - Entity command argument validation.
  - Business scaffold path safety, no-overwrite behavior, and pipeline backup.
- Clean up README's outdated "What's NOT implemented yet" calendar add-candidate line.
- Review `docs/decisions/decisions.md` and decide whether these safety choices should be recorded as durable decisions.

## What Should Go to Obsidian raw/

Suggested only; no vault write performed.

- Save this session summary as raw AI-session evidence if preserving implementation trace is useful.
- Suggested raw destination:
  - `raw/ai-sessions/2026-06-03_calendar-entities-session.md`

## What Should Go to Obsidian wiki/

Suggested only; no vault write performed.

- Durable Brain UI implementation note summarizing the workflows now available:
  - Calendar Candidates workflow.
  - Safe Entity Creation workflow.
  - Manual calendar export/open constraint.
- Suggested wiki destination:
  - `wiki/projects/brain-ui.md` or `wiki/projects/Brain UI.md`
- Mark uncertain claims as `Needs manual confirmation`, especially actual `brain new-*` CLI argument behavior.

## What Should Go to Obsidian ops/

Suggested only; no vault write performed.

- Add follow-up implementation tasks:
  - Test calendar candidate workflows manually.
  - Test entity creation against actual `brain` CLI.
  - Add backend tests for calendar and entity safety.
  - Clean stale README "not implemented" item.
  - Review/update `context/current-task.md`.
- Suggested ops destination:
  - `ops/task-db.md` or relevant Brain UI project ops note.

## What Should Not Be Saved

- Do not save secrets, credentials, environment-specific private paths beyond the already user-provided vault/project paths.
- Do not save full git diffs unless explicitly needed; the summary is enough.
- Do not save generated build output.
- Do not save command output logs beyond concise validation notes.
- Do not save assumptions as facts; mark CLI argument behavior as `Needs manual confirmation`.
