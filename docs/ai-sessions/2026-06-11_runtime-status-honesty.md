# Session Summary: Runtime status honesty + stub-page gating

Date: 2026-06-11
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Fix fake runtime status and stub-page trust drift surfaced by the PRD alignment audit. The app was generally safe and on track, but the UI presented unimplemented privileged systems (NemoClaw/OpenShell, OpenClaw tool bridge, Browser harness, Computer use, MCP gateway) as if they were **ready/connected**, and the Research + Chat/AI Consolidation pages looked functional. This violated PRD §4.7 ("Real Agent State, Not Fake AI Theater") and §31 acceptance criteria.

This was a **presentation-honesty sprint only** — no privileged systems were implemented.

---

## Context

Entering this session:

- Dashboard runtime panel and Tool Safety page rendered hard-coded mock services from `src/data/mock.ts` `SYSTEM` with fake states: OpenClaw `ready · qwen2.5:14b`, NemoClaw `ready · policy v3`, Browser `Playwright · ready`, MCP `partial · 3 of 5 connected`.
- The Dashboard code even labeled them `{/* not wired */}` while still showing "ready".
- Research page had working-looking controls (no handlers); Consolidate page rendered a fake `CONSOLIDATED` list of "past consolidations".
- Agent modes were selectable but enforced nothing.
- Real status (Backend, Brain CLI, Vault, Local model) was already backend-derived and correct.

---

## Files Changed

### Modified

| File | Changes |
|---|---|
| `src/types/index.ts` | Added optional `statusLabel?: string` to `SystemService` to override the right-side status text honestly. |
| `src/components/dashboard/SystemRow.tsx` | Render `service.statusLabel ?? service.state`. |
| `src/data/mock.ts` | `SYSTEM` openclaw/nemoclaw/browser/computer/mcp → `state: 'disabled'`, `statusLabel: 'Not wired'`, detail "Planned PRD runtime — not wired yet". Unused fake `model` neutralized. |
| `src/pages/DashboardPage.tsx` | Added a "Planned — not wired yet" divider between real backend-derived rows and the planned-runtime rows. |
| `src/pages/SafetyPage.tsx` | Rewritten: honesty banner, "Planned runtimes" (Not wired), "Current real safety controls" (Active), realistic risk posture (email/calendar/delete/browser = "Not built", not "requires confirm"), honest tool-log copy. |
| `src/pages/ResearchPage.tsx` | Gated to truthful v0: "planned but not wired" banner + requirements list, all controls `disabled`, "Start research — not available". |
| `src/pages/ConsolidatePage.tsx` | Gated to truthful v0: removed fake `CONSOLIDATED` list, "planned but not wired" banner, disabled action, planned-workflow list. |
| `src/pages/AgentPage.tsx` | Added note under the Mode panel: "Mode selection is currently UI-only. Tool gating will be enforced after the OpenClaw/NemoClaw bridge is implemented." |
| `README.md` | "Planned runtimes — shown honestly as Not wired" section, "Current real safety controls" list, capability rows updated, runtime-panel description corrected. |
| `context/current-task.md` | Documented the runtime-honesty pass in Current State. |

No backend files changed. No new endpoints. No vault writes. No external calls.

---

## What now shows as "Not wired" / planned

- OpenClaw tool bridge, NemoClaw/OpenShell, Browser harness, Computer use, MCP gateway — neutral/grey, `Not wired`, under a "Planned — not wired yet" divider on the Dashboard and on the Tool Safety page.
- Research page and Chat/AI Consolidation page — disabled controls, "planned but not wired" copy.
- Agent modes — labeled UI-only.
- Tool/action log — labeled planned (`ops/tool-logs/`), nothing to log.

## What remains real (unchanged)

Backend (FastAPI health), Brain CLI, Vault path, Local model (Ollama `/api/agent/status`), command output, Raw Inbox counts, Dashboard metrics, Today's Plan, Recent AI Work, Active Work, and all backup-before-write vault editors.

---

## Tests

- `npm run build` → clean, 82 modules, 0 TypeScript errors. (Module count dropped 83→82 because ConsolidatePage no longer imports the mock list / SourceGlyph / EmptyState.)
- `python -m pytest backend/tests` → 143 passed, 1 pre-existing warning (`VaultFolders.schema` shadow). No backend behavior change.

---

## Safety constraints honored

No privileged systems implemented. No backend mutation endpoints, no shell, no external calls, no vault writes, no AI calls. This sprint only changed how status and stub pages are presented.

---

## Recommended next sprint

**Generalized Proposal/Apply foundation (medium-risk, write).** Introduce the PRD §35.4 Proposal object and a single preview/apply surface, starting by re-expressing the existing intake routing through it (no new mutation power). This lays the spine for any future OpenClaw→backend handoff while preserving backup-before-write and preview-before-apply. High-risk agent/browser/MCP/NemoClaw runtime work stays deferred until that spine and real mode-gating exist.
