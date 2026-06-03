# Brain UI — Backend

FastAPI backend for Brain UI. Provides health/config endpoints and a safe
allowlisted wrapper around the `brain.cmd` CLI.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

The frontend dev server runs on `http://localhost:5173`. CORS is pre-configured
for that origin.

## Environment variables

| Variable                | Default                                                              |
|-------------------------|----------------------------------------------------------------------|
| `BRAIN_UI_VAULT_PATH`   | `D:\Hasnain\Personal\OneDrive - University of Toronto\AI-Command-Center` |
| `BRAIN_UI_BRAIN_CMD`    | `D:\Hasnain\Personal\bin\brain.cmd`                                  |

Set these to override the defaults without editing source.

## Endpoints

| Method | Path                      | Description                              |
|--------|---------------------------|------------------------------------------|
| GET    | `/api/health`             | Liveness check                           |
| GET    | `/api/config`             | Current backend config (vault, brain)    |
| GET    | `/api/brain/commands`     | List allowlisted subcommands             |
| GET    | `/api/brain/vault-path`   | Run `brain vault-path`, return output    |
| GET    | `/api/brain/status`       | Run `brain status`, return output        |
| POST   | `/api/brain/run`          | Run any allowlisted brain subcommand     |

Interactive docs: `http://localhost:8000/docs`

## Allowlisted commands

Only these `brain` subcommands may be executed via the API:

```
doctor  status  vault-path  today  weekly
raw-status  sync-raw  calendar-export  calendar-open
```

Non-allowlisted commands return HTTP 400. No arbitrary shell execution is
possible through this backend.

## Safety notes

- `subprocess.run` is used with an explicit argument list and `shell=False`.
- On Windows, `.cmd` files are invoked via `cmd.exe /c <path> <subcommand>`
  (still `shell=False` — `cmd.exe` itself is the interpreter, not the shell
  string-eval path).
- User input (the `command` field) is validated against the allowlist before
  execution; it is never concatenated into a shell string.
- Timeout is 60 seconds per command.

## What is real vs mocked

**Real (this sprint):**
- Health, config, and brain command endpoints
- Safe `brain.cmd` execution for allowlisted subcommands
- CORS for the Vite dev server

**Still mocked in frontend:**
- OpenClaw — not wired
- NemoClaw / OpenShell — not wired
- Browser harness — not wired
- Computer use — not wired
- MCP gateway — not wired

## Config unification (future)

Currently two separate config layers exist:

1. **Frontend localStorage** (`brain-ui.settings`) — edited in Settings UI.
2. **Backend env vars / defaults** — read at startup.

A future run should add a `PUT /api/config` endpoint so the frontend can
push its settings to the backend, unifying both layers.
