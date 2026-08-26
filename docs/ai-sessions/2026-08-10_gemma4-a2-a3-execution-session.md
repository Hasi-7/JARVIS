  # Session Summary: Gemma 4 A2 + A3 Execution

Date: 2026-08-10
Project: Brain UI / JARVIS

## Goal

Replace the planned Gemma 3 setup with a hardware-appropriate dual Gemma 4 system,
deliver preview-only local AI assistance, and add authenticated approval-gated local
agent execution without weakening the existing safe spine.

## Files Changed

- Local AI: `backend/app/agent.py`, `classify_ai.py`, `capture_assist.py`, `intake.py`,
  `models.py`, `main.py`, and `backend/.env.example`.
- Approval execution: `backend/app/tool_approvals.py`, `agent_tool_requests.py`,
  `agent_structured_output.py`, `permission_gateway.py`, `write_lock.py`, `vault.py`,
  `calendar.py`, `models.py`, and `main.py`.
- Frontend: `src/lib/api.ts`, `DraftAssistPreview.tsx`, `ToolApprovalQueue.tsx`,
  `ConsolidatePage.tsx`, `ResearchPage.tsx`, `EmailIntakePage.tsx`, `AgentPage.tsx`,
  and `ToolConnectionsPage.tsx`.
- Tests: `test_agent_models.py`, `test_capture_assist.py`, `test_tool_approvals.py`, and
  updates to `test_tool_logs.py`.
- Project records: `README.md`, `context/HANDOFF.md`, `context/current-task.md`, and
  `docs/decisions/decisions.md`.

## Decisions

- Everyday model: `gemma4:12b-it-qat`; heavy model: `gemma4:26b-a4b-it-qat`.
- APIs accept only `everyday|heavy`; model tags remain server-controlled.
- AI assistance is opt-in, JSON-structured, preview-only, and never writes a draft/vault.
- All Ollama requests share one inference gate to protect the 16 GB GPU.
- Privileged execution requires canonical Assist mode, an operator token, an explicit
  approve confirmation, an explicit execute confirmation, and an enabled kill switch.
- Only four narrow approval tools exist; calendar candidates always begin unapproved.
- Queue reads are authenticated because review fields may contain private task/calendar data.
- Cross-process locks serialize approval claims and cooperating vault writes.

## Commands Run

- `ollama list`
- Live everyday and heavy structured-output calls through `app.agent.complete_ollama_chat`
- `python -m pytest tests/ -q`
- `python -m compileall -q app tests`
- `npm run build`
- `git diff --check`

## Tests

- Backend: **646 passed**, one pre-existing `VaultFolders.schema` warning.
- Frontend: production build clean, **90 modules**.
- Live Gemma 4 smoke tests: everyday returned valid JSON in about 9.9 seconds; heavy in
  about 20.7 seconds. Timings are load/context dependent.

## Safety Evidence

- No arbitrary model names, shell commands, brain subcommands, paths, or generic writes.
- Untrusted source data is separated from immutable system policy and bounded before inference.
- Draft snapshots are revalidated after inference, including timestamp-collision-safe content checks.
- Approval canonical arguments stay backend-only; authenticated review fields are immutable.
- Operator token is constant-time checked and never persisted or logged.
- Approval replay, argument substitution, double execution, missing audit evidence, queue flooding,
  concurrent claims, and direct-versus-agent vault write races are covered by tests.
- Successful side effects remain truthfully marked executed if audit persistence later fails.

## Open Issues

- `backend/.env` is not auto-loaded; environment variables must be exported before Uvicorn.
- The production JS bundle remains above Vite's 500 kB advisory threshold.
- B0 Google OAuth is the next mandatory setup checkpoint.
- Gmail send/delete/archive/label remain permanently disabled.

## Next Actions

1. Configure `BRAIN_UI_PRIVILEGED_EXECUTION_ENABLED` and a strong
   `BRAIN_UI_APPROVAL_TOKEN` when approved local execution is desired.
2. Manually exercise one task and one calendar-candidate approval against the real vault.
3. Complete B0 Google OAuth desktop setup before implementing Gmail/Calendar reads.

## Second Brain

Save the durable decisions, model benchmarks, safety architecture, test baseline, and next
Google OAuth checkpoint. Do not save the approval token or raw canonical approval arguments.
