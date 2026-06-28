# Session Summary: Agent Mode Enforcement + Runtime Guardrails (4 sprints)

Date: 2026-06-28
Tool: Claude Code
Project: Brain UI / Personal AI Command Center (JARVIS)

## Goal

Make agent modes real (backend-enforced, not UI labels), surface that state app-wide, and build an
honest, read-only runtime-readiness layer for OpenClaw / NemoClaw/OpenShell — culminating in an
explicit, opt-in reachability probe for the NemoClaw/OpenShell guardrail. Throughout: the Local Agent
stays non-executing and no new privileged capability is wired.

This single working session delivered four consecutive sprints:

1. **Agent Mode Enforcement v0** — backend policy gates structured tool-request evaluation + manual
   tool requests by mode.
2. **Global Agent Mode Display v0** — selected mode + policy shown in the top bar and Dashboard.
3. **OpenClaw / NemoClaw Runtime Status v0** — read-only `GET /api/runtime/status` readiness surface.
4. **NemoClaw/OpenShell Health Probe v0** — explicit, opt-in, localhost-only reachability check.

## Context

Prior state had agent modes as UI-only labels and privileged runtimes shown as static "Not wired"
mock rows. The PRD requires modes to gate behavior and requires NemoClaw/OpenShell as the runtime
guardrail before any privileged OpenClaw action. These sprints lay that groundwork **without** wiring
execution: nothing runs from chat, and even a reachable runtime unlocks nothing.

Per-sprint detail lives in sibling files (also created this session):
- `docs/ai-sessions/2026-06-28_agent-mode-enforcement-v0.md`
- `docs/ai-sessions/2026-06-28_global-agent-mode-display-v0.md`
- `docs/ai-sessions/2026-06-28_openclaw-nemoclaw-runtime-status-v0.md`
- `docs/ai-sessions/2026-06-28_nemoclaw-health-probe-v0.md`

Repo conventions checked: `AGENTS.md` (present but an **unfilled template** — `Needs manual
confirmation` whether it should be populated), `docs/decisions/decisions.md` (present but **empty** —
only a table header), `context/current-task.md` (updated this session), `README.md` (updated).

## Files Changed

New backend modules:
- `backend/app/agent_modes.py` — central mode policy (normalize, evaluate/review/available helpers).
- `backend/app/runtime_status.py` — read-only runtime readiness inventory (5 runtimes).
- `backend/app/runtime_probe.py` — explicit NemoClaw/OpenShell reachability probe + last-probe cache.

New backend tests:
- `backend/tests/test_agent_modes.py` (38), `backend/tests/test_runtime_status.py` (16),
  `backend/tests/test_runtime_probe.py` (22).

Modified backend:
- `backend/app/main.py` — new endpoints: `GET /api/agent/modes`, `GET /api/runtime/status`,
  `POST /api/runtime/probe/nemoclaw`, `GET /api/runtime/probe/nemoclaw/last`; mode-gating on
  `POST /api/agent/tool-request` and both chat endpoints.
- `backend/app/models.py` — agent-mode, runtime-status, and probe Pydantic models.
- `backend/tests/test_agent_tool_requests.py`, `backend/tests/test_agent_structured_output.py` — two
  existing tests updated to pass an evaluating mode (mode-less now safely defaults to locked/blocked).

New frontend modules:
- `src/lib/agentModes.ts`, `src/lib/runtimeStatus.ts`, `src/components/runtime/RuntimeStatus.tsx`.

Modified frontend:
- `src/lib/api.ts` (types + `getAgentModes`/`getRuntimeStatus`/`probeNemoclawRuntime`/`getLastNemoclawProbe`),
  `src/store/useAppStore.ts` (`agentModes` + `loadAgentModes`), `src/components/layout/AppShell.tsx`,
  `src/components/layout/TopCommandBar.tsx`, `src/components/ui/ModeBadge.tsx`,
  `src/pages/AgentPage.tsx`, `src/pages/DashboardPage.tsx`, `src/pages/ToolConnectionsPage.tsx`,
  `src/data/mock.ts`, `src/types/index.ts`.

Docs: `README.md`, `context/current-task.md`, and the four sibling session summaries above.

All changes are currently **uncommitted** (working tree only; branch `main`).

## Commands Run

- `python -m pytest backend/tests/ -q` — final run: **429 passed, 1 warning**.
- `python -m pytest` on individual new test files during development (`test_agent_modes.py` 38,
  `test_runtime_status.py` 16, `test_runtime_probe.py` 22).
- `npm run build` — final run: **88 modules transformed, 0 TypeScript errors**.
- `python -c "..."` import/smoke checks for the new backend modules.
- `git status` / `git diff --stat` / `git log` for this closeout.

(No `git commit`, no `git push`, no `brain` command, no deploy was run this session.)

## Decisions Made

- **Mode normalization is fail-safe:** unknown/missing mode → `locked` (safest). Frontend aliases
  `manual → locked`, `computer → computer_use`. Documented in `agent_modes.py`.
- **Blocked manual tool-request returns HTTP 200** with `{status:"blocked_by_mode", mode, message}`
  (cleaner for the frontend to distinguish from a gateway failure) rather than 403.
- **Honesty rule for runtime status:** no runtime is ever reported `available` (no verified health
  check exists), so dependents (browser/computer-use) stay blocked.
- **Probe is localhost-only by default**, opt-in, bounded; remote allowed only via
  `NEMOCLAW_ALLOW_REMOTE_PROBE=true`; reachable ≠ unlocked.
- These decisions are **not yet recorded in `docs/decisions/decisions.md`** (still empty) —
  `Needs manual confirmation` on whether to add them there.

## Bugs Fixed

- No standalone bug investigation. The only corrective change: two pre-existing tests assumed a
  mode-less request would evaluate; after mode enforcement, mode-less safely defaults to
  locked/blocked, so both tests were updated to pass `mode="draft"`. This was an intended
  behavior-contract change, not a regression fix.

## Tests / Validation

- Backend: `429 passed` (76 new across the three new test files; 2 existing updated).
- Frontend: `npm run build` clean — 88 modules, 0 TypeScript errors.
- Probe tests use an injected fake HTTP client (no real network); runtime/probe tests assert no
  shell/`brain`/subprocess calls and that browser/computer-use stay disabled after a probe.
- Not validated this session: live end-to-end run against a real running backend + Ollama, and a real
  reachable NemoClaw URL (no such runtime exists). `Needs manual confirmation` via the manual test
  plans in the per-sprint summaries.

## Open Issues

- `AGENTS.md` is an empty template; `docs/decisions/decisions.md` has no rows. `Needs manual
  confirmation` whether to populate them.
- All work is uncommitted — needs a commit (and the repo's recent commit messages are terse
  "update"; consider a clearer message).
- `RUNTIME_VERIFICATION_WIRED = False` is a deliberate constant; flipping it requires a real verified
  check (future sprint).
- LF→CRLF line-ending warnings from git on touched files (cosmetic; `Needs manual confirmation` on
  whether a `.gitattributes` policy is wanted).

## Next Actions

- Commit the four sprints (suggest grouping or a single descriptive commit).
- Optionally populate `AGENTS.md` and add the decisions above to `docs/decisions/decisions.md`.
- Next feature candidate (from the last sprint): read-only **NemoClaw policy inspection** (parse
  `NEMOCLAW_POLICY_PATH`, display declared allow/deny scopes; still no enforcement/execution).

## What Should Go to Obsidian raw/

- A copy of this session summary as raw session capture, e.g.
  `raw/chats/claude-code/2026-06-28-agent-runtime-guardrails-session.md`.
- Source of truth remains the repo at `docs/ai-sessions/`; the vault copy is for the second brain.
- `Needs manual confirmation` — do not write until you explicitly ask.

## What Should Go to Obsidian wiki/

- A short JARVIS project-state note under `wiki/projects/` recording that agent modes are now
  backend-enforced and globally visible, and that runtime guardrails (OpenClaw/NemoClaw) are
  status-only with an opt-in NemoClaw reachability probe — **nothing executes, nothing is unlocked**.
- `Needs manual confirmation` on the exact wiki note path/name.

## What Should Go to Obsidian ops/

- Optionally a one-line entry in an ops log / decision log capturing the safety posture: "Agent
  modes enforced; no mode executes tools from chat; NemoClaw probe is localhost-only and unlocks
  nothing." Better placed in `docs/decisions/decisions.md` first.
- No task/calendar rows are warranted from this session.

## What Should Not Be Saved

- No secrets or credentials were involved; nothing secret to save.
- Do not save `backend/data/` (gitignored app-data, incl. `runtime/last-probe.json`).
- Do not save build artifacts (`dist/`), `node_modules`, or `.venv`.
- Do not duplicate full source diffs into the vault — link to the repo instead.

---

**Suggested next command (run from the repo root; reads the repo, does not write the vault):**

```
brain raw-status
```

To ingest this summary into the vault once you confirm, run the OpenCode/Claude slash command:

```
/brain-ingest docs/ai-sessions/2026-06-28_agent-runtime-guardrails-session.md
```

`Needs manual confirmation` — I have not run either command, and I will not write to the vault unless
you explicitly ask.
