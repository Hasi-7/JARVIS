# Session Summary: Global Agent Mode Display v0

Date: 2026-06-28
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Make the **enforced** agent mode visible app-wide instead of Local-Agent-page-only. The mode now
affects backend behavior (Agent Mode Enforcement v0), so the top bar and Dashboard should show the
current mode and what it allows — honestly, with Computer-Use shown as unavailable. **No tool
execution behavior changes; no new privileged integrations.** Display only.

```text
Current mode: Assist
Tool request evaluation: Allowed
Review handoff: Safe-local only
Execution from chat: Disabled
Computer-Use: Unavailable
```

---

## Backend files changed

**None.** Reuses the existing read-only `GET /api/agent/modes`. No enforcement change, no new
execution path. Backend tests unchanged: **391 passed**.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/agentModes.ts` | **New.** Shared policy helpers lifted out of `AgentPage.tsx`: `toBackendMode` (`manual→locked`, `computer→computer_use`), `MODE_POLICY_FALLBACK` (static offline copy mirroring `backend/app/agent_modes.py`), `resolveModePolicy`, `modePolicySummary` (Evaluation / Review handoff / tooltip), and `MODE_TRUTHS` (the three standing statements). |
| `src/store/useAppStore.ts` | Added `agentModes: AgentModePolicy[] | null` + `loadAgentModes()` (calls `getAgentModes()`; non-fatal — leaves `null` on failure so consumers use the fallback). |
| `src/components/layout/AppShell.tsx` | Calls `loadAgentModes()` once on mount (alongside `checkBackend`/`loadStagedCount`). |
| `src/components/ui/ModeBadge.tsx` | Optional `policy` prop → availability dot + policy tooltip; renders `<mode> · unavailable` (muted amber) for not-wired Computer-Use. |
| `src/components/layout/TopCommandBar.tsx` | Resolves the current policy from the store and passes it to `ModeBadge`; labels it "Mode". |
| `src/pages/DashboardPage.tsx` | New compact **Agent mode** card: selected mode, availability, Evaluation (Allowed/Blocked/Unavailable), Review handoff (Safe-local only/Disabled), **Execution from chat: Disabled**, plus the three truths. Passes `policy` to the agent-panel `ModeBadge`. |
| `src/pages/AgentPage.tsx` | Now reads `agentModes` from the store and imports `resolveModePolicy` from the shared lib (removed the local duplicated helpers + per-page fetch); passes `policy` to its cockpit `ModeBadge`. Ensures policy is loaded if it mounts first. |

---

## Global mode state behavior

The selected mode was **already** global (`useAppStore().agentMode` / `setAgentMode`), shared by the
Local Agent page, top bar, and Dashboard. This sprint adds the **policy** (`agentModes`) to the same
store. Changing the mode anywhere updates the badge + Dashboard card everywhere; there is a single
`ModeBadge` control (no conflicting selectors).

## Dashboard / top bar display

- **Top bar:** `Mode` label + `ModeBadge` with an availability dot, a policy tooltip, and a
  `· unavailable` suffix for Computer-Use.
- **Dashboard:** an "Agent mode" card with the policy summary rows and the three truths.

## Mode policy loading & degraded behavior

`GET /api/agent/modes` is fetched once on app mount into the store. On failure, `agentModes` stays
`null` and every consumer resolves via `MODE_POLICY_FALLBACK` (static copy), so the UI stays honest
and the app never blocks. Frontend ids map to backend ids via `toBackendMode`.

---

## What remains disabled / not wired

OpenClaw bridge, NemoClaw/OpenShell, browser harness, computer-use, MCP, Gmail, Google Calendar API —
all **not wired**. Computer-Use mode is shown unavailable. No mode executes tools from chat; safe-local
execution stays manual on Tool Connections. No new execute/run controls were added.

---

## Tests run

```bash
python -m pytest backend/tests -q   # 391 passed (no backend change)
npm run build                        # 86 modules, 0 TypeScript errors
```

---

## Safety constraints

- No backend change; no enforcement regression; no new execution path.
- Policy is resolved client-side for display only; the backend remains authoritative for enforcement.
- Degraded (backend-down) state falls back to a static policy and is shown honestly.
- Computer-Use is never presented as wired.

---

## Recommended next sprint

Begin the **OpenClaw/NemoClaw bridge** behind the now-enforced, now-visible mode policy: add a
read-only runtime status surface (is the agent runtime reachable?) and gate any future privileged
tool path on both the mode policy **and** the runtime guardrail — still no execution from chat until
the NemoClaw/OpenShell sandbox is in place.
