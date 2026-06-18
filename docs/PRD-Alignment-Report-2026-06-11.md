# Brain UI PRD Alignment Report

_Audit date: 2026-06-11 · Branch: main · Build: clean (83 modules) · Backend tests: 143/143 passed_

## 1. Executive Summary

Brain UI is **on track for the early MVP band (v1–v3) and the read/track layer of v6**, and is notably *safer* than the PRD minimum requires. The deterministic spine — `brain` CLI wrapper, vault-path detection, Dashboard, Raw Inbox staging/classification/routing, and structured ops-file editors (Tasks, Calendar Candidates, Backfill, Resume, Escalations) — is **real, tested, and backup-guarded**. The Local Agent is a real Ollama chat with **no tools**, exactly matching the PRD's "agent proposes, never directly mutates" stance.

The gap is the entire **privileged-agent half of the product**: NemoClaw/OpenShell runtime, OpenClaw tool bridge, browser harness, computer-use, MCP gateway, Gmail intake, research mode, chat consolidation, and Google Calendar API. None of these are implemented.

The single most important **drift/risk** is **fake status theater**: the Dashboard runtime panel and Safety page render NemoClaw/OpenShell, OpenClaw, Browser harness, Computer use, and MCP as hard-coded mock services (`SYSTEM` in `src/data/mock.ts`) — e.g. `NemoClaw/OpenShell: ready · policy v3`, `OpenClaw: ready · qwen2.5:14b` — even though **no such integrations exist**. This directly violates PRD §4.7 ("Real Agent State, Not Fake AI Theater") and §31 acceptance criteria. It is cosmetic, not a data-safety bug, but it is the highest-priority correctness/integrity item.

**Verdict: On track, disciplined, safe — but must stop displaying unbuilt runtimes as "ready."**

## 2. Current Implementation Snapshot

- **Stack:** React + Vite + TS frontend (state-based nav via zustand `route`, **no react-router**); FastAPI backend; Python subprocess wrapper for allowlisted `brain`; Ollama for local chat. Matches PRD §9.1.
- **Build/tests:** `npm run build` clean (83 modules, 0 TS errors); **143/143** backend tests pass.
- **Backend modules:** `brain.py`, `vault.py`, `calendar.py`, `classify.py`, `classify_ai.py`, `intake.py`, `entities.py`, `escalations.py`, `conversations.py`, `agent.py`, `dashboard.py`, `security.py`, `config.py`, `models.py`, `main.py`.
- **Pages (16 routes):** dashboard, agent, research, inbox, consolidate, calendar, tasks, projects, hackathons, courses, business, resume, backfill, escalation, safety, settings.
- **Working-tree diff (uncommitted at audit time):** the two prior sprints — Dashboard Mark-done quick actions + Recent-AI-Work deep-link (`README.md`, `context/current-task.md`, `AgentPage.tsx`, `DashboardPage.tsx`, `useAppStore.ts`).

## 3. PRD Goals Already Satisfied

- **MVP v1** — Safe `brain.cmd` wrapper (allowlist, `shell=False`, metachar sanitation, timeout), vault-path detection, Dashboard, command-output panel, Settings (vault + brain path layering). ✅
- **MVP v3 (core)** — Upload staging, filename sanitation, path-traversal prevention, heuristic + local-AI classification proposals, batch approval, route into `raw/`, archive original (never auto-delete). ✅
- **Tasks / Calendar Candidates / Backfill / Resume / Escalations** — real read + structured write with backup-before-write, conflict re-read, `extra="forbid"`, pipe/newline sanitation. ✅ (exceeds PRD §25–27 which only required some of these).
- **Entity creation** — Projects/Courses/Hackathons via `brain new-*`; Business via filesystem scaffold. ✅
- **Local Agent (chat only)** — `/api/agent/status`, streaming `/chat`, conversation history, context window, no tools. ✅ Matches PRD §10.1 "must not directly perform risky mutations."
- **Dashboard daily view** — real counts, deterministic Today's Plan, Recent AI Work (now deep-links to a conversation), Active Work drill-down, Mark-done quick actions (Backfill/Escalation, confirm + backup). ✅
- **Degrade-gracefully** — every page handles backend-down with clear errors. ✅ (PRD §43).

## 4. PRD Goals Partially Satisfied

| Area | Built | Missing |
|---|---|---|
| **Dashboard required content (§16)** | counts, brain status, today plan, entity counts, vault path, local-model status | OpenClaw/NemoClaw/browser/computer/MCP status are **mock**, not real; agent *mode* shown but not enforced |
| **Local Agent page (§17)** | sphere states, transcript, mode selector, context panel | tool-request panel, approval queue, research timer, escalate/stop buttons are **absent or decorative**; sphere states not driven by real tool activity |
| **Agent Modes (§11)** | mode badge/selector in UI | **no runtime meaning** — Observe/Draft/Assist/Research/Computer-Use/Locked do not gate anything |
| **Escalation (§29, MVP v6)** | escalation queue read/write, handoff-prompt copy, closeout-prompt copy | repo/context picker, structured handoff package schema, launch |
| **Calendar (§24)** | candidates read/edit/approve, `.ics` export-open via `brain calendar-open` | warnings-before-import surface is minimal; no Google API |
| **Raw classification rules (§19)** | classification implemented in code | `schema/classification-rules.md` artifact + untrusted-content prompt rule not verified present |

## 5. PRD Goals Not Started

- **NemoClaw/OpenShell runtime** (§31) — no backend bridge, no status endpoint, no mode enforcement, no config vars.
- **OpenClaw tool bridge** (§30) — `/api/agent/propose`, `/research`, `/tool-request`, `/stop` endpoints **do not exist**; only chat exists.
- **Research mode + browser harness** (§14, MVP v4) — page is a static UI stub (buttons have no handlers).
- **Chat/AI consolidation** (§28, MVP v5) — page renders `CONSOLIDATED` mock; no capture/import/write.
- **Computer-use harness** (§13, MVP v7) — none.
- **MCP gateway + tool logs** (§32, MVP v8) — none; `ops/tool-logs/` not written.
- **Gmail/email intake** (§33) — none.
- **Google Calendar direct API** (§24, MVP v9) — none (`.ics` only, which is the correct first step).
- **Proposal/apply engine (generalized)** (§35.4) — only the intake-classification flow exists; no unified Proposal object across note/task/calendar/research/chat.
- **Graphify viewer / GitHub / Drive / Canvas / vector search** (MVP v10) — none.
- **Obsidian MCP** — none.

## 6. Current Product Drift / Risks

1. **Fake runtime status (highest priority).** `SYSTEM` mock renders NemoClaw "ready · policy v3", OpenClaw "ready · qwen2.5:14b", Browser "Playwright · ready", MCP "3 of 5 connected" on the Dashboard right rail and Safety page. The Dashboard code even labels them `{/* not wired */}` while still showing "ready" — the UI contradicts its own comment. Violates §4.7 and §31 acceptance ("runtime blocks are visible/understandable", "show NemoClaw status").
2. **Agent modes are cosmetic.** Selecting Research/Computer-Use changes a badge but enforces nothing — risks future false confidence that a gate exists.
3. **Stub pages look functional.** Research and Consolidate present full input UIs with no wiring; a user could reasonably believe they work.
4. **Documentation drift.** README/`current-task.md` correctly call most things mock, but the *running UI* presents mocks as live — the drift is UI-vs-reality, not doc-vs-code.

## 7. Safety Alignment

Strong. Verified against the PRD's "must avoid" list:

| Must avoid | Status |
|---|---|
| Arbitrary shell execution | ✅ Blocked — `is_allowed()` frozenset allowlist, `shell=False`, metachar regex reject |
| Unrestricted file writes | ✅ `_safe_subpath()` blocks traversal; writes confined to designated ops files / `raw/` |
| Vault writes without backup | ✅ Every mutating path (tasks, calendar, backfill, resume, escalations) calls `_backup_*` (`shutil.copy2`) before write; `create` endpoints skip backup only because they never overwrite |
| Google Calendar writes | ✅ None — `.ics` export only |
| Gmail mutations | ✅ No Gmail integration at all |
| External tool launches | ✅ None — escalation only *copies* prompts |
| OpenClaw privileged actions w/o NemoClaw | ✅ N/A — agent has zero tools |
| Browser/computer-use w/o approval | ✅ N/A — not implemented |
| AI file mutation without preview | ✅ AI only writes classification *metadata*; routing **copies** files (no content transform, no overwrite); user previews proposal first |
| External content as trusted instructions | ✅ Agent system prompt is baked-in, tool-less; classification operates on extracted text only. **Caveat:** confirm the §44 untrusted-content boilerplate is present in the AI-classify prompt. |

No data-safety violations found. The safety posture currently *exceeds* the PRD minimum.

## 8. Navigation / UX Alignment

- **15/16 PRD nav sections present.** PRD §15 lists "Browser/Computer Use" and "MCP/Tool Connections" as separate sections; implementation folds runtime status into a **Safety** page instead, and has no MCP page. Reasonable for current scope, but a deviation to note.
- **Navigation is state-based (no URL router).** Deep-linking is done via store handoff (`agentConvTarget`), which is the correct least-invasive choice given no router — but means no shareable/bookmarkable URLs and no browser back/forward.
- Jarvis theme, agent sphere, command palette, compact tables, real status dots — all align with §36. Sphere states exist but aren't yet bound to real tool activity (acceptable until tools exist).

## 9. Backend/API Alignment

PRD §30 specifies `/api/agent/message|propose|research|tool-request|stop`. Implementation provides `/api/agent/chat` (+ `/chat/stream`) and `/status` only. **Naming and surface diverge**; propose/research/tool-request/stop are unbuilt. All other implemented routes are real and read-only-or-backed-up. No mock endpoints exist on the backend — mocking is purely frontend.

### Endpoint Audit

| Endpoint | Purpose | Real/Mocked | Write? | Backup? | PRD Area |
|---|---|---|---|---|---|
| GET /api/health | Backend liveness | Real | No | – | Foundation |
| GET /api/config | Read vault/brain config | Real | No | – | Settings §34.5 |
| PUT /api/config | Update settings.json | Real | Write (app-state) | n/a | Settings |
| GET /api/dashboard/summary | Aggregated read-only counts/plan/active-work | Real | No | – | Dashboard §16 |
| GET /api/brain/commands | List allowlist | Real | No | – | brain wrapper §34.1 |
| GET /api/brain/vault-path | `brain vault-path` | Real | No | – | Vault §34.4 |
| GET /api/brain/status | `brain status` | Real | No | – | Dashboard |
| POST /api/brain/run | Run allowlisted brain cmd | Real | Indirect (brain may write vault) | brain-owned | brain wrapper |
| POST /api/entities/{projects,courses,hackathons} | `brain new-*` scaffold | Real | Write (via brain) | brain-owned | Entities §20–22 |
| POST /api/entities/business | Filesystem business scaffold | Real | Write (vault dirs, no overwrite) | n/a (new) | Business §23 |
| POST /api/intake/upload | Stage uploaded files | Real | Write (staging) | n/a | Raw Inbox §18 |
| GET /api/intake/staged | List staged | Real | No | – | Raw Inbox |
| DELETE /api/intake/staged/{id} | Remove staged file | Real | Write (staging) | n/a | Raw Inbox |
| GET /api/intake/proposals | List classification proposals | Real | No | – | Raw Inbox |
| PUT /api/intake/proposals/{id} | Edit proposal metadata | Real | Write (app-state) | n/a | Raw Inbox |
| POST /api/intake/proposals/approve-batch | Batch approve | Real | Write (metadata) | n/a | Raw Inbox §18 |
| POST /api/intake/proposals/{id}/approve | Approve one | Real | Write (metadata) | n/a | Raw Inbox |
| POST /api/intake/proposals/{id}/skip | Skip one | Real | Write (metadata) | n/a | Raw Inbox |
| POST /api/intake/proposals/{id}/route | Copy file into raw/ | Real | Write (vault copy, no overwrite) | copy-not-overwrite | Raw Inbox |
| POST /api/intake/staged/{id}/archive | Archive original | Real | Write (move) | n/a | Raw Inbox §18 |
| GET /api/intake/archived | List archived | Real | No | – | Raw Inbox |
| POST /api/intake/proposals/ai-classify-batch | Local-AI classify (metadata) | Real (Ollama) | Write (metadata) | n/a | AI classify §19 |
| POST /api/intake/proposals/{id}/ai-classify | Local-AI classify one | Real (Ollama) | Write (metadata) | n/a | AI classify |
| GET /api/vault/{summary,projects,courses,hackathons,business} | Read entities | Real | No | – | Entities §20–23 |
| GET /api/vault/tasks | Read task-db | Real | No | – | Tasks §25 |
| POST /api/vault/tasks | Add task row | Real | Write (vault) | ✅ Yes | Tasks |
| PATCH /api/vault/tasks/{id}/status | Edit task status | Real | Write (vault) | ✅ Yes | Tasks |
| GET /api/vault/calendar-candidates | Read candidates | Real | No | – | Calendar §24 |
| POST /api/vault/calendar-candidates/create | Create file | Real | Write (no overwrite) | n/a (new) | Calendar |
| POST /api/vault/calendar-candidates | Add row | Real | Write (vault) | ✅ Yes | Calendar |
| PATCH /api/vault/calendar-candidates/{id} | Edit row | Real | Write (vault) | ✅ Yes | Calendar |
| POST /api/vault/calendar-candidates/{id}/approve | Set Approved=Yes | Real | Write (vault) | ✅ Yes | Calendar |
| GET /api/vault/ops/{kind} | Read ops file | Real | No | – | Vault |
| GET /api/vault/backfill | Read backfill | Real | No | – | Backfill §27 |
| POST /api/vault/backfill/create | Create file | Real | Write (no overwrite) | n/a (new) | Backfill |
| POST /api/vault/backfill | Add row | Real | Write (vault) | ✅ Yes | Backfill |
| PATCH /api/vault/backfill/{id}/status | Status edit | Real | Write (vault) | ✅ Yes | Backfill |
| PATCH /api/vault/backfill/{id} | Field edit | Real | Write (vault) | ✅ Yes | Backfill |
| GET /api/vault/resume-pipeline | Read resume | Real | No | – | Resume §26 |
| POST /api/vault/resume-pipeline/create | Create file | Real | Write (no overwrite) | n/a (new) | Resume |
| POST /api/vault/resume-pipeline | Add row | Real | Write (vault) | ✅ Yes | Resume |
| PATCH /api/vault/resume-pipeline/{id}/status | Status edit | Real | Write (vault) | ✅ Yes | Resume |
| PATCH /api/vault/resume-pipeline/{id} | Field edit | Real | Write (vault) | ✅ Yes | Resume |
| GET /api/vault/escalations | Read escalations | Real | No | – | Escalation §29 |
| POST /api/vault/escalations/create | Create file | Real | Write (no overwrite) | n/a (new) | Escalation |
| POST /api/vault/escalations | Add row | Real | Write (vault) | ✅ Yes | Escalation |
| PATCH /api/vault/escalations/{id}/status | Status edit | Real | Write (vault) | ✅ Yes | Escalation |
| PATCH /api/vault/escalations/{id} | Field edit | Real | Write (vault) | ✅ Yes | Escalation |
| GET /api/agent/status | Ollama/local-model status | Real | No | – | Local Agent §30 |
| POST /api/agent/chat | Local chat (no tools) | Real (Ollama) | No vault write | n/a | Local Agent |
| POST /api/agent/chat/stream | Streaming chat (SSE) | Real (Ollama) | No vault write | n/a | Local Agent |
| POST /api/conversations | Create conversation | Real | Write (app-state JSON) | n/a | Local Agent |
| GET /api/conversations | List conversations | Real | No | – | Local Agent |
| GET /api/conversations/{id} | Conversation detail | Real | No | – | Local Agent |
| DELETE /api/conversations/{id} | Delete conversation | Real | Write (app-state JSON) | n/a | Local Agent |

**No `/api/agent/propose`, `/research`, `/tool-request`, `/stop`, MCP, browser, computer-use, gmail, or calendar-API routes exist.**

## 10. Data/Vault Alignment

- Vault path resolved via `brain vault-path`, cached, configurable. ✅ §34.4
- Writes restricted to designated ops files + `raw/`; `_safe_subpath` enforces containment. ✅
- App state minimal/local (settings.json, conversations, intake proposals). ✅ §34.5 — though `agent-permissions.json`, `tool-registry.json`, `recent-actions.json`, `pending-proposals.json` are not yet present (only needed once tools land).
- **Generalized Proposal data model (§35.4) not implemented** — intake has its own proposal shape; no unified cross-domain proposal/apply engine.
- `schema/classification-rules.md` and `ops/tool-logs/` artifacts: **not verified present** — likely missing.

## 11. AI/Agent Alignment

- OpenClaw = currently a tool-less Ollama chat behind a baked system prompt. Honest, safe, matches "agent proposes, backend controls." ✅
- Local-AI classification is the only place AI touches workflow data — and only writes metadata, never file content. ✅
- **Not aligned:** structured agent output schema (§30 `proposals/tool_requests/escalation_recommendation`), research planner, tool-request generator, escalation-package generator. The agent cannot yet produce machine-actionable proposals.

## 12. OpenClaw / NemoClaw / OpenShell Status

- **OpenClaw bridge:** ❌ Not started (chat only; no propose/research/tool-request/stop).
- **NemoClaw/OpenShell runtime:** ❌ Not started — **and falsely shown as "ready · policy v3."** No sandbox, no policy, no mode enforcement, no config vars (`NEMOCLAW_*`). This is the largest architecture-vs-PRD gap and the source of the top drift item.

## 13. MCP / Gmail / Browser / Computer-Use Status

- **MCP gateway:** ❌ Not started; shown as "partial · 3 of 5 connected" (mock).
- **Gmail intake:** ❌ Not started (correctly absent — no false UI).
- **Browser harness:** ❌ Not started; shown "Playwright · ready" (mock); Research page is a non-wired stub.
- **Computer-use:** ❌ Not started; shown "disabled in settings" (mock, but at least reads as off).

## 14. Test and Build Status

- **Frontend:** `npm run build` → ✅ 83 modules, 0 TypeScript errors, ~1.1s.
- **Backend:** `pytest backend/tests/` → ✅ **143 passed**, 1 warning (`schema` field-name shadow in `VaultFolders` — cosmetic Pydantic warning).
- **No frontend unit tests exist** (no Vitest/RTL harness); frontend correctness is build-time + manual only.
- Working tree has uncommitted changes from the last two sprints (build/tests green with them applied).

## 15. Recommended Next 5 Sprints

Ordered by risk, preferring PRD-aligned, testable, safety-preserving increments.

1. **(Low-risk, read-only) Honest runtime status.** Replace mock `SYSTEM` rows (NemoClaw, OpenClaw, Browser, Computer-use, MCP) with real or explicitly "Not configured / Unavailable" states. Removes fake theater; satisfies §4.7/§31. *No writes, fully testable.*
2. **(Low-risk, read-only) Truthful stub-page gating.** Make Research and Consolidate pages clearly "Not available yet — requires NemoClaw/OpenShell + browser harness," disabling dead buttons. Prevents false-functional impression.
3. **(Low-risk) Classification-rules + untrusted-content audit.** Ensure `schema/classification-rules.md` exists and the AI-classify prompt embeds the §44 untrusted-content rule. Closes a real prompt-injection gap with a tiny, reviewable change.
4. **(Medium-risk, write) Generalized Proposal/Apply foundation.** Introduce the §35.4 Proposal object + a single preview/apply surface, starting by re-expressing the *existing* intake routing through it (no new mutation power). Sets the spine for all future agent writes.
5. **(Medium-risk, write) Agent structured-proposal endpoint (Draft mode only).** Add `/api/agent/propose` returning proposals that are **never auto-applied** — they flow into the sprint-4 preview/apply queue. First real OpenClaw→backend handoff, with zero autonomous mutation.

High-risk agent/browser/MCP/NemoClaw runtime work is intentionally deferred until (a) honest status exists and (b) the proposal/apply + mode-enforcement spine is in place.

## 16. Immediate Cleanup Items

- Remove/replace `SYSTEM` mock "ready" states (Dashboard right rail + SafetyPage).
- Reconcile the Dashboard `{/* not wired */}` comment with what is actually rendered.
- Add a visible "stub / not implemented" treatment to Research & Consolidate.
- Confirm `schema/classification-rules.md` presence; add §44 untrusted-content guard to AI-classify prompt if absent.
- Fix the `VaultFolders.schema` Pydantic shadow warning (rename or alias).
- Commit the two pending sprints (currently uncommitted in the working tree).
- Note in README that nav lacks dedicated Browser/Computer-Use and MCP sections (folded into Safety / absent).

## 17. Final Verdict

**On track and commendably safe for its phase.** Brain UI has delivered a real, tested, backup-guarded operating console over `brain` + the vault, with a tool-less local agent — fully honoring the PRD's friction-vs-safety philosophy. The deterministic foundation is solid. The dominant problem is **integrity of presentation**: unbuilt runtimes (NemoClaw/OpenClaw tools/browser/MCP) are displayed as live. Fix the status honesty and lay the proposal/apply + mode-enforcement spine *before* touching any privileged-agent capability. Do not jump to browser/computer-use/MCP until NemoClaw/OpenShell status is real and modes actually gate behavior.

## Recommended Next Prompt

```text
You are building the next implementation pass for Brain UI.

Source of truth: PRD.md, DESIGN.md, current implementation, README.md, context/current-task.md.
If this prompt conflicts with the PRD or DESIGN.md, follow the PRD and DESIGN.md.

## Goal
Replace fake/mocked runtime status with honest status. The Dashboard runtime panel and
the Safety page currently render hard-coded mock services (NemoClaw/OpenShell "ready · policy v3",
OpenClaw "ready · qwen2.5:14b", Browser harness "Playwright · ready", Computer use, MCP gateway
"3 of 5 connected") from src/data/mock.ts SYSTEM. None of these integrations exist. This violates
PRD §4.7 (no fake AI theater) and §31 acceptance criteria. This sprint makes status truthful.

## Scope (read-only, no new mutations)
For these five runtime services — NemoClaw/OpenShell, OpenClaw tool bridge, Browser harness,
Computer-use, MCP gateway — stop showing mock "ready/connected/partial" states.

Show each as one of:
- "Not configured" (no backend integration exists), or
- "Unavailable" (integration exists but not reachable).

Keep the two services that ARE real and already wired exactly as they are:
- Backend (FastAPI health) and Local model (GET /api/agent/status) must remain real.
- Brain CLI and Vault status (already real via /api/dashboard/summary runtime block) stay real.

## Backend
Prefer NO backend changes. Do NOT add NemoClaw/OpenClaw/browser/MCP integrations or endpoints.
If a single read-only capability flag is genuinely needed, expose it as static config booleans
already present (e.g. ENABLE_BROWSER_HARNESS/ENABLE_MCP_GATEWAY style env, default false) surfaced
through the existing /api/config or /api/dashboard/summary response — but do not invent runtime probes.
No new mutation endpoints. No vault writes. No tool/process launches.

## Frontend
- In src/data/mock.ts (or wherever SYSTEM lives), change the five mock services so their default
  state is 'disabled' (Not configured) — not 'ready'/'partial'.
- DashboardPage runtime panel: render NemoClaw/OpenShell, OpenClaw bridge, Browser, Computer-use,
  MCP as "Not configured" with a neutral grey dot and a one-line "Requires NemoClaw/OpenShell runtime"
  (or equivalent) sub-label. Remove the contradiction between the {/* not wired */} comment and a
  "ready" appearance.
- SafetyPage: same treatment; add a short banner: "These runtimes are not yet integrated. Status is
  shown as Not configured until the runtime bridge exists."
- Do NOT alter Backend, Local model, Brain CLI, or Vault status wiring.
- Also gate the Research and Consolidate pages: keep the layout but disable the action buttons and add
  an EmptyState/notice that the feature requires the (not-yet-built) browser harness / NemoClaw runtime.

## UI constraints
- No new colors implying "live" for unbuilt services. Use the existing 'disabled'/grey treatment.
- Keep everything read-only. No confirmation modals needed (no writes).

## Do not implement
NemoClaw/OpenShell, OpenClaw tool bridge, browser harness, computer-use, MCP, Gmail, calendar API,
research execution, chat consolidation, any new endpoint, any vault write, any process launch.

## Acceptance criteria
- npm run build passes.
- Backend tests still pass (no backend behavior change expected).
- Dashboard and Safety no longer show NemoClaw/OpenClaw/Browser/Computer/MCP as "ready"/"connected"/"partial".
- Each of those five shows "Not configured" (or "Unavailable") with a neutral indicator.
- Backend, Local model, Brain CLI, Vault status remain real and unchanged.
- Research and Consolidate pages no longer present working-looking controls.
- No new write actions, endpoints, or external calls introduced.

## Final response
Summarize: files changed, exactly which services changed state, what remains real, that no backend
mutation/endpoint was added, tests run, and the recommended next sprint (generalized Proposal/Apply
foundation, medium-risk).
```
