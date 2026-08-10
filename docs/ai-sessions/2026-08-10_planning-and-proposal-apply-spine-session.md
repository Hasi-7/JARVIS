# Session Summary: Execution Planning + Proposal-Apply Spine (A1)

Date: 2026-08-10
Tool: Claude Code
Project: Brain UI / Personal AI Command Center (`D:\Hasnain\Personal\dev\JARVIS`)

## Goal

Search the repo, compare the current build against `PRD.md`, identify what's missing,
produce an approved execution plan to finish the project, then begin implementation.
This session: finalize the plan and ship the first sprint (A1 — Proposal-Apply spine).

## Context

The pre-existing build is a deliberately "safe spine": ~507 backend tests, all 19
frontend pages, everything read-only / evaluate-only / manual paste. The entire
privileged execution layer (PRD MVP v4–v10) had been deferred. This session mapped that
gap, got user direction on scope/priorities, wrote the plan, and delivered A1. Ollama —
the local LLM the agent/AI-assist features depend on — was found **not installed** on the
machine, so AI-dependent work (A2) is blocked pending setup.

Plan file: `C:\Users\Hasnain\.claude\plans\zany-squishing-goose.md`
Handoff doc (for continuing under usage limits): `context/HANDOFF.md`

## Files Changed

Modified (source + docs):
- `backend/app/proposals.py` — added `apply_proposal`, `apply_batch`, `reject_proposal`, `_split_proposal_id`.
- `backend/app/models.py` — added `ApplyProposalRequest`, `ApplyBatchRequest`, `ApplyProposalResult`, `ApplyBatchResponse`.
- `backend/app/main.py` — added `POST /api/proposals/apply`, `/apply-batch`, `/reject` + imports.
- `src/lib/api.ts` — added `applyProposal`/`applyProposalBatch`/`rejectProposal` + result types.
- `src/pages/ProposalsPage.tsx` — Apply / Reject / Apply-all-safe (confirm modal), inline results.
- `context/current-task.md` — prepended A1 sprint entry.

Added (new files):
- `backend/tests/test_proposals_apply.py` — 27 tests for the apply spine.
- `backend/.env.example` — documents `BRAIN_UI_*` / `NEMOCLAW_*` / `OPENCLAW_*` env vars.
- `context/HANDOFF.md` — self-contained handoff for the next agent.
- `docs/ai-sessions/2026-08-10_planning-and-proposal-apply-spine-session.md` — this file.

Note: nothing has been committed yet (all changes are in the working tree).

## Commands Run

- `git status` / `git diff --stat` / `git ls-files --others` / `git log --oneline` — repo inspection.
- `python -m pytest tests/test_proposals_queue.py -q` — passed (15).
- `python -m pytest tests/test_proposals_apply.py -q` — passed (27).
- `python -m pytest tests/ -q` — **534 passed, 1 warning** (pre-existing `VaultFolders` shadow warning).
- `python -m py_compile app/proposals.py app/models.py app/main.py` — OK.
- `npm run build` — clean, 88 modules (pre-existing >500 kB chunk advisory only).
- Ollama checks: `ollama --version` / `ollama list` (bash) and PowerShell `Get-Command ollama` + `Invoke-WebRequest http://localhost:11434/api/tags` — **not installed / server not reachable**.

## Decisions Made

- **Scope of "finish the project" = the privileged execution layer** (PRD MVP v4–v10),
  built in phases A (Ollama-only) → B (Gmail/Calendar) → C (browser) → D (voice + Calendar writes).
- **OpenClaw/NemoClaw/OpenShell not treated as verified products** — no evidence they exist
  with usable APIs. Handled as intended integrations gated behind **setup checkpoints**;
  local agent = Ollama; the runtime guardrail = a Python sandbox we will build.
- **External systems = reads only this round**; writes stay proposals/`.ics` (Calendar
  writes deferred to Phase D2 behind explicit confirmation).
- **In scope:** voice I/O and direct Google Calendar API (read now). **Gmail send/delete/
  archive/label permanently disabled.**
- **A1 design:** the apply spine **adds no new write primitive** — it dispatches to the
  existing per-source save/route, inheriting all safety (never-overwrite, stay-in-vault,
  path-traversal reject, no brain/AI side effects).
- **A1 endpoints are body-based** (`{id}`) rather than path params, because normalized ids
  contain a colon (`consolidation:<uuid>`).
- **Model recommendation for the RX 7900 GRE (16 GB):** default `gemma3:12b` (fully on GPU,
  fast); heavy = `gemma3:27b-it-qat` (QAT 4-bit, partial CPU offload on 16 GB). Advised
  **against 2-bit 27B** on quality grounds. Dual-model support is an open question.

## Bugs Fixed

- `ProposalsPage.tsx` used an invalid `Icon name="alert"` for the failure result line;
  caught before build and changed to `name="x"` (a defined icon). No runtime bug shipped.

## Tests / Validation

- Backend: `python -m pytest tests/ -q` → **534 passed** (+27 new from `test_proposals_apply.py`; was 507).
- Frontend: `npm run build` → clean, 0 TS errors, 88 modules.
- New apply-spine tests cover: id parsing (valid/malformed/unknown prefix), draft +
  raw-inbox dispatch (via patched source functions), idempotency on already-applied,
  batch never-raises-on-single-failure, reject rules, and endpoint smoke via direct
  route-function calls with patched `get_config`.
- Manual end-to-end apply flow was **not** exercised against a live vault this session
  (`Needs manual confirmation`).

## Open Issues

- **Ollama not installed** — blocks A2 (local-AI assist) and the Local Agent entirely.
- **Dual-model decision open** — single `BRAIN_UI_LOCAL_MODEL` vs adding `BRAIN_UI_LOCAL_MODEL_HEAVY`.
- **Changes not committed** — working tree only; no commit/push performed this session.
- **Reject for draft sources not supported in v1** (raw-inbox only) — intentional; revisit if needed.
- **`backend/.env` is not auto-loaded** — the backend reads process env directly; a `.env`
  file won't take effect without exporting vars or adding dotenv loading (`Needs manual confirmation` on preference).

## Next Actions

1. Install Ollama (Windows), `ollama pull gemma3:12b`, set `BRAIN_UI_LOCAL_MODEL=gemma3:12b`.
2. Decide single vs dual model (affects A2 API shape).
3. Build **A3 — gated agent tool execution** (Ollama-independent, can start immediately).
4. Then A2 once Ollama is ready; then B0 setup → Phase B, etc.
5. Commit A1 (suggested message: "A1: proposal-apply spine + apply/reject endpoints + tests").

## What Should Go to Obsidian raw/

- This session summary, as a session record for the JARVIS project — e.g.
  `raw/projects/JARVIS/session-summaries/2026-08-10_planning-and-proposal-apply-spine.md`
  (or `raw/chats/claude-code/`). `Needs manual confirmation` on exact route.

## What Should Go to Obsidian wiki/

- Update the JARVIS project wiki page (`wiki/projects/...JARVIS...`) with: the approved
  4-phase execution plan, the "safe spine → execution layer" milestone, and that A1
  (proposal-apply) is complete. `Needs manual confirmation` on exact page path.

## What Should Go to Obsidian ops/

- A task-db row: "Install Ollama + pull gemma3:12b (unblocks Brain UI A2)".
- A task-db row: "Decide Brain UI single vs dual local model".
- Optionally a resume-pipeline note that JARVIS now has an apply/approve workflow shipped.
- `Needs manual confirmation` before adding rows.

## What Should Not Be Saved

- No secrets/tokens were produced or handled; nothing sensitive to save.
- Do not save raw code diffs to the vault — git already tracks them.
- Do not save the full plan/handoff verbatim into the vault; they live in the repo
  (`context/HANDOFF.md`, plan file) — link to them instead.

---

### Recommended next command

This summary lives in the repo, not the vault. To ingest it, copy it into the vault raw/
area and run the sync + ingest pipeline. Recommended:

```powershell
# 1) Copy this summary into the vault (confirm the destination folder first)
Copy-Item "D:\Hasnain\Personal\dev\JARVIS\docs\ai-sessions\2026-08-10_planning-and-proposal-apply-spine-session.md" `
  "D:\Hasnain\Personal\OneDrive - University of Toronto\AI-Command-Center\raw\chats\claude-code\"

# 2) Sync raw, then ingest
brain sync-raw
brain ingest
```

Or, if you prefer the guided flow, run the **`/brain-session-closeout`** skill and point it
at this file. `Needs manual confirmation` on the exact `raw/` destination folder before copying.
