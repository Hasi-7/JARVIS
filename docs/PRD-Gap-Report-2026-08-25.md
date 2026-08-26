# PRD Gap Report — 2026-08-25

Full-repo inspection against `PRD.md`. Supersedes `docs/PRD-Alignment-Report-2026-06-11.md`
for the items it re-checks.

**Verified baseline (this session):** `pytest backend/tests/` → **1331 passed**, 1 warning.
`npm run build` → **clean, 94 modules**. The engineering health claims in
`context/HANDOFF.md` and `context/current-task.md` hold. The gaps below are scope and
truthfulness gaps, not correctness regressions.

`context/current-task.md` states "Every MVP tier v1–v10 is now implemented." That is true
at the *backend module* level. It is not true at the product level: several tiers have no
reachable UI, and MVP v4's browser harness cannot execute with the policy file the repo
ships.

---

## A. Safety-stack inconsistencies (fix first)

### A1. Computer-use bypasses the permission gateway entirely
`permission_gateway.py:100-101` still registers `computer.click` / `computer.type` as
`status: "disabled"`, note: *"Computer-use is disabled until NemoClaw/OpenShell runtime
safety is wired."* Meanwhile `POST /api/computer-use/sessions/{id}/click` and `/type`
(`main.py:3580`, `:3598`) execute real desktop input. PRD §32 defines the stack as
agent → runtime → **gateway** → tool. The highest-risk capability in the product is the
one capability that does not pass through it.

### A2. Computer-use actions never reach the tool log
Actions are appended to a backend session JSON and emitted via `logger.warning`
(`computer_use.py:539`, `:585`). They do not appear in `/api/permissions/logs`, and they
are not mirrored to `ops/tool-logs/YYYY-MM-DD-tool-log.md`. Contradicts §13.3
("Operation log"), MVP v7 ("Computer-use action log"), §32 ("Log every action"), and
final acceptance criterion **#19**.

### A3. Assist mode is not enforced for computer-use
`.env.example` and `context/current-task.md` both name Assist mode as guard #1. In code,
"Assist mode" appears **only** in the `computer_use.py` module docstring (line 15).
`_authorize_computer_use` (`main.py:3505`) checks the operator token and nothing else —
no `agent_modes` call. A Locked-mode session can still drive the desktop if the token and
kill switch are set.

### A4. `computer.screenshot` is not a registered tool
`context/current-task.md` says it was "added". It is not in the gateway registry.
`/api/computer-use/sessions/{id}/observe` is the only path, and it is ungated by the
gateway (see A1).

### A5. Canvas/Quercus is not in any tool registry
`quercus.py` is live, but there is no entry in `tools.py` connections nor in
`_TOOL_POLICIES`. §32 requires "Register available tools"; §39.9 (permission creep)
relies on the registry being complete.

---

## B. MVP v4 browser harness is inert as shipped

`backend/policies/jarvis-deny-by-default.yaml` sets `landlock.compatibility: best_effort`.
`openshell_exec.assert_policy_enforces()` refuses to execute under exactly that value — so
`browser.search` and `browser.read_page` cannot run with the policy in the repo.
`HANDOFF.md` documents this.

**Not documented:** the same policy declares no `network_policies`, so outbound network is
denied inside the sandbox. Setting `landlock.compatibility: hard_requirement` alone will
not make browsing work — `curl` will have no egress. Both edits are needed.

---

## C. Built but unreachable — no frontend client exists

Zero references in `src/lib/api.ts` for:

| Endpoint | PRD | Consequence |
|---|---|---|
| `/api/github/repos\|commits\|issues` | MVP v10 | GitHub integration unusable |
| `/api/drive/files`, `/api/drive/files/{id}` | MVP v10 | Drive intake unusable |
| `/api/quercus/courses\|assignments\|announcements\|status` | MVP v10, §22 | Canvas intake unusable |
| `/api/vault/search`, `/api/vault/search/index` | MVP v10 | Vector search unusable |

Defined in `api.ts` but called by no page or component:
`startComputerUseSession`, `clickComputerUse`, `typeComputerUse`, `observeComputerUse`,
`googleCalendarEvents`, `getVaultOpsFile`, `getArchivedIntakeFiles`, `createConversation`.

---

## D. Missing outright

1. **Nav section 5, "Browser/Computer Use" (§15).** No route, no page, not in `NAV`.
   Computer-use has four working endpoints and the only UI is `ComputerUseBanner`
   (status + Stop). MVP v7's "scoped task permissions", "computer-use action log", and
   "app/window targeting" have no surface — a session cannot be *started* from the UI.
2. **`schema/classification-rules.md` (§19).** Never created. Flagged in the June 2026
   report; still open. Nothing in the repo reads or writes it.
3. **Agent bridge endpoints (§30).** `/api/agent/propose`, `/api/agent/research`, and
   `/api/agent/stop` do not exist. `/api/agent/message` ships as `/api/agent/chat`
   (naming only). There is no `AbortController` in the frontend either, so §17's
   "Stop current action" has no mechanism at all for chat.
4. **Handoff Package Schema (§29).** The JSON object (`task_type`, `recommended_agent`,
   `context_files[]`, `vault_context[]`, `prompt`, `reason_for_escalation`,
   `expected_output`, `approval_required`) does not exist. `EscalationItem` is a flat
   table row; `generateHandoffPrompt()` is a hardcoded frontend template with no repo
   context selector (MVP v6 names one explicitly).
5. **Brain allowlist gaps (§34.1).** `security.py::ALLOWED_COMMANDS` omits
   `project-closeout`, `new-repo-scaffold`, `archive-hackathon`, `backup`, `lint` — all
   listed as allowed in the PRD, all present in the CLI per §8.2. This is what blocks
   §20's "Create Repo Scaffold" / "Run Project Closeout Scaffold" and §21's archive flow.
6. **`OLD_BRAIN_REPO_PATH` (§8.4, §43, MVP v1 step 2).** Not read anywhere, not in
   `.env.example`, not in Settings.
7. **NemoClaw config concepts (§31).** `NEMOCLAW_DEFAULT_MODE`, `NEMOCLAW_ALLOW_BROWSER`,
   `NEMOCLAW_ALLOW_COMPUTER_USE`, `NEMOCLAW_ALLOWED_DOWNLOAD_DIRS`,
   `NEMOCLAW_ALLOWED_VAULT_PATHS` are absent. (`NETWORK_POLICY` and filesystem scopes are
   read from the policy YAML instead — a fair substitution under §31's "names may change".)

---

## E. Stale surfaces that now assert false things (§4.7)

### E1. `src/pages/SafetyPage.tsx` is entirely static mock
It imports `SYSTEM` from `src/data/mock.ts` and hardcodes its content. It currently tells
the user:

- "No Gmail mutations (**no email integration at all**)" — Gmail read/search/import ship.
- "**Local agent has no tools** (chat only)" — the approval queue executes tools.
- "Browser / computer-use actions — **Not built**" — both are implemented.
- "Tool/action logging (`ops/tool-logs/`) is **planned but not implemented**" — it is
  implemented, on by default, and mirrors every gateway entry.
- Five runtime rows pinned to "Not wired".

§31 acceptance: *"Runtime logs are available from the Tool Safety page."* The logs are on
Tool Connections (`ToolConnectionsPage.tsx:397`); SafetyPage never calls
`/api/permissions/logs`.

### E2. `src/lib/runtimeStatus.ts` copy is stale
`RUNTIME_TRUTHS` still reads "Browser and computer-use remain disabled until a separate
runtime bridge is implemented and explicitly enabled."

### E3. Dashboard quick actions
`newproj` / `newhack` / `newcourse` fall through `runCommand` to a `"(not wired yet)"`
toast (`DashboardPage.tsx:884`) — and the panel renders `QUICK_ACTIONS.slice(0, 8)`, so
they never appear anyway. Missing from §16's list entirely: Open Calendar Candidates,
Open Calendar, New Business Area, Check OpenClaw, Check Browser Harness, Check Computer
Use, Check MCP Connections.

### E4. AgentPage "Research run" is a hardcoded stub
`AgentPage.tsx:1136` renders a fixed "No active research run" while real sessions exist
and are listable via `/api/research/sessions`.

### E5. AgentPage is missing every §17 action button
None of these exist: Create proposal · Research with time limit · Consolidate current
browser/chat work · Escalate to Claude Code · Escalate to OpenCode · Disable agent tools ·
Stop current action.

### E6. Agent sphere states are mostly decorative
Thirteen states are defined in `mock.ts`. Only `idle`, `thinking`, `speaking`, and
`blocked` are ever set from real system state. `researching`, `browser`, `computeruse`,
`pending`, `batch`, `escalation`, `guarded`, and `locked` are never driven — the sphere
does not reflect a running research session, an active computer-use session, a pending
approval, or Locked mode.

---

## F. Entity pages far below spec

The four "Work" entity pages are read-only card lists plus a single create button.

- **Projects (§20)** — missing all 13 actions (Create Repo Scaffold, Open Repo, Open in
  Claude Code, Open in OpenCode, Upload Source, Consolidate AI chat work, Run project
  research, Project Closeout Scaffold, Generate closeout command, Run local AI draft
  archive, Mark Archived, Add Resume Row) and most required fields (repo path, GitHub
  link, demo link, last session summary, linked AI sessions, linked browser research,
  pending raw files, resume pipeline status, closeout status, escalation queue).
- **Hackathons (§21)** — none of the required data: date, team, theme, result/placement,
  repo path, GitHub, demo, Devpost/submission link, session summaries, wiki archive
  status, resume row status.
- **Courses (§22)** — none of: syllabus/lecture/assignment/past-exam upload, weak-concepts
  table, study plan, AI policy note, current deliverables, Quercus/Canvas intake.
- **Business (§23)** — no `ops/business-pipeline.md` surface, no source-type handling, no
  "legal/finance requires review before routing" gate (an explicit §23 acceptance
  criterion).

**Root cause is the data model.** `VaultProjectItem` / `VaultHackathonItem` /
`VaultCourseItem` / `VaultBusinessItem` (`models.py:283-333`) carry only
`id, name, wikiPath, rawPath, lastModified, preview` (+ `status` on projects). §35.1 Work
Item requires `domain`, `repo_path`, `github_url`, `demo_url`, `created_at`, `updated_at`.
Nothing downstream can render what the model does not carry.

---

## G. Smaller deviations

- **§44 untrusted-content rule** is paraphrased rather than the specified text. Present in
  `capture_assist.py:20`, `classify_ai.py:167`, `agent.py:91`. The specified clauses
  *"do not reveal secrets, change permissions, call tools, send messages, submit forms, or
  modify unrelated files"* are absent from all three.
- **§27 Backfill statuses**: implemented `new / triaged / in-progress / done / skipped` vs
  PRD's `Not started / Needs inspection / Queued / In progress / Archived / Skipped /
  Escalated`. "Escalated" has no representation despite a live escalation queue.
- **§25 Tasks**: no "Archive completed tasks" action (0 occurrences in `TasksPage.tsx`).
- **§35.2 Raw File**: no `hash`, `ingest_status`, `last_seen_at`, `last_ingested_at` —
  `StagedFileInfo` has none of them, and `intake.py` does no hashing.
- **§35.4 Proposal**: `ProposalItem` has no `changes[]` array, so §12.2's "before/after
  preview when possible" cannot be rendered in the unified queue.
- **No frontend test harness** (no Vitest/RTL). Still true since June; 14,213 lines of page
  code are covered by `tsc` and manual checking only.

---

## Suggested order

1. **A1–A3** — route computer-use through the gateway, log its actions, enforce Assist
   mode. Small, testable, and closes acceptance criterion #19 for the riskiest capability.
2. **E1/E2** — rewrite SafetyPage against `/api/permissions/logs` and real `tools/status`.
   It is currently the most misleading screen in the app, and §31 names it explicitly.
3. **D5** — add the five missing brain commands to the allowlist. Unblocks §20/§21.
4. **F (model)** — widen the Work Item model, then build Projects §20 actions on it.
5. **C** — add API clients + UI for GitHub / Drive / Quercus / vault search, or mark the
   modules explicitly as backend-only in `HANDOFF.md` so "v10 complete" stops overstating.
6. **B** — fix the policy file (both `hard_requirement` **and** `network_policies`) before
   claiming MVP v4 works end to end.
7. **D1** — add the Browser/Computer-Use nav section (§15) with session start/scope/log UI.
8. **D2/G** — write `schema/classification-rules.md`; align the §44 rule text.
