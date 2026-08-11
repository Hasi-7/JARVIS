# Session Summary: Google OAuth B0 Setup

Date: 2026-08-10
Tool: OpenCode
Project: JARVIS / Brain UI

## Goal

Complete the B0 Google OAuth setup checkpoint for future read-only Gmail and
Google Calendar integrations, without exposing credentials or adding API data
access prematurely.

## Context

The user had created Google OAuth desktop credentials and downloaded the client
JSON. The repository did not yet contain `backend/data/google/`, Google client
dependencies, or a local consent entry point. The approved project sequence in
`context/HANDOFF.md` requires B0 before B1 Gmail read intake.

The worktree already contained substantial uncommitted A2/A3 changes before this
OAuth task. This summary does not attribute those unrelated changes to B0.

## Files Changed

- `backend/requirements.txt`: added `google-api-python-client` and
  `google-auth-oauthlib`.
- `backend/app/google_auth.py`: added credential-file discovery, setup status,
  token load/refresh, explicit browser consent, atomic token persistence, and a
  small `status`/`authorize` CLI.
- `backend/tests/test_google_auth.py`: added eight focused tests using fake OAuth
  objects; tests make no live Google calls.
- `backend/GOOGLE_OAUTH.md`: documented Google Cloud and local authorization steps.
- `context/current-task.md`: marked B0 complete and B1 as the next checkpoint.
- `context/HANDOFF.md`: updated the checkpoint and backend test baseline.
- `docs/ai-sessions/2026-08-10_google-oauth-b0-session.md`: recorded the initial
  implementation session notes.
- `docs/ai-sessions/2026-08-10_google-oauth-b0-closeout.md`: this closeout.

Local ignored artifacts were also created under `backend/.venv/` and
`backend/data/google/`. Their sensitive contents are intentionally excluded.

## Commands Run

```powershell
# Created and verified the local Google data directory.
Test-Path -LiteralPath "backend\data"
New-Item -ItemType Directory -Path "backend\data\google"

# Initial setup and focused validation.
python -m app.google_auth status
python -m pytest tests/test_google_auth.py -q
git diff --check

# Created an isolated backend environment and installed project dependencies.
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Ran the explicit local browser consent flow and checked resulting status.
.venv\Scripts\python.exe -m app.google_auth authorize
.venv\Scripts\python.exe -m app.google_auth status

# Final validation.
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m py_compile app\google_auth.py
git check-ignore -v backend/data/google/<credential-file> backend/data/google/token.json
git status --short
git diff
git diff --stat
git log --oneline -10
```

The placeholder `<credential-file>` above intentionally avoids recording the
local credential filename.

## Decisions Made

- Use standalone installed-app OAuth rather than an MCP connector so the backend
  remains self-contained.
- Request exactly `gmail.readonly` and `calendar.readonly`.
- Open the browser only after the explicit `authorize` command.
- Accept Google's generated `client_secret*.json` filename when exactly one
  candidate exists; prefer `client_secret.json` if present.
- Store the generated token only under gitignored `backend/data/google/`.
- Keep B0 authorization-only. No Gmail message retrieval, Calendar event
  retrieval, Gmail mutation, or Calendar write was added.

## Bugs Fixed

- Resolved the missing local Google data directory.
- Resolved the missing Google OAuth dependencies and authorization entry point.
- No existing application behavior bug was diagnosed or fixed in this session.

## Tests / Validation

- Focused OAuth tests: 8 passed.
- Full backend suite: 654 passed, with one existing Pydantic warning about the
  `VaultFolders.schema` field shadowing a parent attribute.
- Python compilation check for `app/google_auth.py`: passed.
- OAuth status after consent: client configured and token present.
- Git ignore verification: both the downloaded credential and generated token
  are ignored by `backend/data/`.
- Live Google consent completed successfully using only the two read-only scopes.
- Frontend build was not run during this B0 session. The 90-module clean build in
  project context belongs to the preceding A2/A3 work, not this validation.

## Open Issues

- B1 Gmail thread search and message retrieval are not implemented.
- B2 Calendar event reads and reconciliation are not implemented.
- Gmail send, delete, archive, and label mutations remain disabled by design.
- Google Calendar writes remain unavailable in this phase.
- OAuth app publication status: Needs manual confirmation. Test-user access is
  sufficient while the Google Cloud app remains in Testing mode.
- The repository remains dirty with broader A2/A3 changes that were not committed
  during this session.

## Next Actions

1. Implement B1 Gmail read intake behind the permission gateway.
2. Add mocked Google client tests that assert read-only scopes and prove no Gmail
   mutation methods are reachable.
3. Treat all retrieved email headers and bodies as untrusted input before feeding
   the existing email-intake draft workflow.
4. Update tool/runtime status only after a real authenticated read check exists.
5. Review and commit the broader dirty worktree separately when ready.

## What Should Go to Obsidian raw/

- Ingest this closeout as session evidence under a JARVIS/Brain UI development
  session location. Suggested destination:
  `raw/dev/jarvis/sessions/2026-08-10-google-oauth-b0.md`.
- Destination naming is `Needs manual confirmation` against the vault's current
  raw schema.

## What Should Go to Obsidian wiki/

- A durable Brain UI integration note stating that Google OAuth uses installed-app
  local consent, requests Gmail readonly plus Calendar readonly, and stores local
  credentials/tokens outside tracked files.
- A durable safety statement that B0 authorizes only; Gmail mutations and Calendar
  writes remain disabled.
- Suggested note: `wiki/projects/brain-ui.md` or a dedicated Google integration
  architecture note. Exact target is `Needs manual confirmation`.

## What Should Go to Obsidian ops/

- Project status: B0 complete on 2026-08-10; next checkpoint is B1 Gmail read
  intake.
- Validation status: 654 backend tests passed; frontend build not rerun for B0.
- Suggested target: the existing Brain UI project status note under `ops/`.
  Exact path is `Needs manual confirmation`.

## What Should Not Be Saved

- OAuth client JSON contents, client secret, refresh token, access token, consent
  URL, callback state, authorization code, or generated token file.
- The local credential filename or identifiers embedded in it.
- `backend/.venv/` contents.
- Raw terminal output that might reveal machine-specific paths or authentication
  metadata.
- Claims that Gmail or Calendar data access is implemented; only authorization is
  complete.
