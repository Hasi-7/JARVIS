# Entity Creation Hardening Session — 2026-06-03

## Goal

Harden and verify Brain UI entity creation for Projects, Courses, Hackathons, and Business areas.

## Source Of Truth Used

- `PRD.md`
- `DESIGN.md`
- Current Brain UI implementation
- Existing old CLI source: `D:\Hasnain\Personal\dev\ai-command-tools\brain.py`
- Live help output from `D:\Hasnain\Personal\bin\brain.cmd`

## CLI Signatures Verified

Verified from source and live help output:

```text
brain new-project <name>
brain new-course <code> [--title <title>] [--term <term>]
brain new-hackathon <name>
```

## Files Changed

- `backend/app/brain.py`: exact command argument mapping, unsupported optional arg rejection, safe `--title` mapping.
- `backend/app/entities.py`: business partial-failure response support and exclusive pipeline starter creation.
- `backend/app/main.py`: business partial-failure response handling.
- `backend/requirements.txt`: added `pytest` for backend tests.
- `backend/tests/conftest.py`: backend import path setup for tests.
- `backend/tests/test_entity_creation_safety.py`: command validation and business scaffold tests.
- `README.md`: verified CLI signatures, endpoint mapping, partial-failure behavior, and test command.

## Decisions Made

- Project `repoPath` is rejected when non-empty because the current `brain new-project` CLI does not support it.
- Hackathon `date` is rejected when non-empty because the current `brain new-hackathon` CLI does not support it.
- Course `name` maps to the CLI `--title` flag.
- Business scaffold does not auto-rollback. If pipeline update fails after note/folder creation, the API returns `ok: false` with exact created paths.

## Manual Verification

Real API-level creation was run against the configured vault and `brain.cmd`.

Created test entities, not automatically deleted:

- Project: `UI Test Project Delete Later 2026 06 03`
- Course: `UITEST101` with title `UI Test Course Delete Later`
- Hackathon: `UI Test Hackathon Delete Later 2026 06 03`
- Business: `UI Test Business Delete Later 2026 06 03`

Vault scanners confirmed all four entities appear in the same data sources used by the UI pages.

## Commands Run

```powershell
python brain.py new-project --help
python brain.py new-course --help
python brain.py new-hackathon --help
& "D:\Hasnain\Personal\bin\brain.cmd" new-project --help
& "D:\Hasnain\Personal\bin\brain.cmd" new-course --help
& "D:\Hasnain\Personal\bin\brain.cmd" new-hackathon --help
python -m pip install -r backend\requirements.txt
python -m pytest backend\tests
python -m py_compile backend\app\brain.py backend\app\entities.py backend\app\main.py backend\app\models.py backend\app\security.py
npm run build
```

## Validation Results

- `python -m pytest backend\tests`: 11 passed, 1 existing Pydantic warning.
- Python compile check: passed.
- `npm run build`: passed.

## Open Issues

- Browser/UI modal behavior was not manually tested in a browser; API-level creation and scanner reload behavior were verified.
- Real `brain` commands update active files as part of old CLI behavior, including active project/course/hackathon files.
- Test entities remain in the real vault for manual cleanup if desired.

## What To Save To Second Brain

- Verified entity CLI signatures and endpoint mappings.
- Test entity names created in the real vault.
- Decision that unsupported optional UI fields are rejected rather than silently ignored.
