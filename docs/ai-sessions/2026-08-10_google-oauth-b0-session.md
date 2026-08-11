# Google OAuth B0 Session

## Goal

Complete the Google OAuth setup checkpoint for future read-only Gmail and Google
Calendar integrations.

## Files Changed

- `backend/requirements.txt`
- `backend/app/google_auth.py`
- `backend/tests/test_google_auth.py`
- `backend/GOOGLE_OAUTH.md`
- `context/current-task.md`
- `context/HANDOFF.md`

Local-only files created under ignored paths:

- `backend/.venv/`
- Google OAuth token under `backend/data/google/`

No credential or token contents were read into the session or written to tracked
documentation.

## Commands Run

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m app.google_auth status
.venv\Scripts\python.exe -m app.google_auth authorize
.venv\Scripts\python.exe -m pytest tests -q
git check-ignore -v backend/data/google/<credential-file> backend/data/google/token.json
```

## Decisions Made

- Use standalone installed-app OAuth for the self-contained backend.
- Request exactly Gmail readonly and Calendar readonly scopes.
- Require an explicit CLI `authorize` action before opening a browser.
- Keep downloaded credentials and generated tokens under gitignored
  `backend/data/google/`.
- B0 performs authorization only; it adds no Gmail or Calendar data access.

## Tests Run

- `backend/tests/test_google_auth.py`: 8 passed.
- Full backend suite: 654 passed, 1 existing Pydantic warning.
- Git ignore verification succeeded for both local OAuth files.

## Open Issues

- Gmail and Calendar API clients are not implemented yet.
- OAuth remains in Google Testing mode unless the Cloud project is published;
  configured test users can authorize normally.

## Next Actions

- Implement B1 Gmail readonly thread search and message retrieval behind the
  permission gateway, with mocked Google clients in tests.
- Preserve email bodies as untrusted input and keep all Gmail mutations disabled.

## Save To Second Brain

- B0 is complete and locally authorized.
- The reusable auth entry point is `app.google_auth.authorize_google()`.
- The next project checkpoint is B1 Gmail read intake.
