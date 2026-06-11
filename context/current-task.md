# Current Task

## Current State

Dashboard Active Work drill-down is complete. The Dashboard now shows compact read-only lists of active items (up to 3 per workflow) behind the count-strip numbers. 143/143 backend tests pass, npm run build clean.

## Real Workflows

| Workflow | What is wired |
|---|---|
| **Dashboard** | `GET /api/dashboard/summary` — aggregated counts, Today's Plan (deterministic), Recent AI Work, Active Work drill-down (backfill/escalations/resume/calendar/raw) |
| **Raw Inbox** | Stage / heuristic classify / AI classify (metadata only) / edit / approve / batch-approve / route to vault / brain sync-raw / archive staged original |
| **Tasks** | Read (`ops/task-db.md` or `ops/tasks.md`), status edit, create new row — `GET /PATCH /POST /api/vault/tasks` |
| **Calendar Candidates** | Read / create file / add candidate / edit / approve / export-open manual — `ops/calendar-candidates.md` |
| **Entity creation** | Projects, Courses, Hackathons (brain CLI), Business (filesystem scaffold) |
| **Backfill** | Read / create file / add item / status edit / field edit — `ops/backfill.md` (or read-only fallback `ops/backfill-last-year.md`) |
| **Resume Pipeline** | Read / create file / add item / status edit / field edit / tailoring prompt — `ops/resume-pipeline.md` |
| **Escalation Queue** | Read / create file / add item / status edit / field edit / handoff prompt — `ops/escalation-queue.md` |
| **Local Agent** | Ollama streaming chat, conversation history, context window, `GET /api/agent/status` |
| **Settings / Config** | Vault path + brain.cmd path, env-var/file/default layering |

## Still Not Implemented

- OpenClaw / NemoClaw / OpenShell runtime wiring
- MCP gateway
- Browser harness / computer use
- Gmail intake
- Google Calendar API writes or automatic import
- Autonomous Claude Code / OpenCode launch (prompt generation only — no process launched)
- Arbitrary shell execution or file modification
- Repo scanning / automatic closeout
- Job application automation
- Dashboard quick actions (status changes from Dashboard)
- Dashboard deep-link from Recent AI Work row into AgentPage for a specific conversation

## Safety Constraints

- No Claude Code / OpenCode process launched by Brain UI at any point.
- No shell commands beyond the strict `brain` allowlist.
- Every vault write: re-read → re-parse → conflict check → backup → write.
- `ops/backfill-last-year.md` permanently read-only.
- `POST **/create` endpoints never overwrite existing files.
- Path traversal rejected on all vault operations.
- `extra="forbid"` on all Pydantic create/update request models.
- Dashboard summary endpoint is entirely read-only — no mutations in activeWork building.

## Next Recommended Sprints

1. **Dashboard quick actions** — mark a backfill or escalation item done/in-progress directly from the Dashboard Active Work panel (requires mutation endpoints from Dashboard, not part of this sprint).
2. **Deep-link from Dashboard → AgentPage** — clicking a Recent AI Work row should open AgentPage with that conversation selected.
3. **Dashboard refresh interval** — optional background polling for dashboard summary (configurable interval, off by default).
4. **Filtered today view** — Tasks page "Today" filter showing only blocked/overdue/due-today items, matching the Dashboard Today's Plan logic.
5. **Bulk status update** — select multiple backfill or resume-pipeline rows and change status in one action.

## Test Plan

```bash
# Backend (includes 25 new activeWork tests)
python -m pytest backend/tests/ -q
# Expected: 143 passed, 1 warning

# Frontend
npm run build
# Expected: 83 modules, 0 TypeScript errors, built in ~1s

# Python compile check
python -m py_compile backend\app\dashboard.py backend\app\vault.py backend\app\main.py backend\app\models.py
```
