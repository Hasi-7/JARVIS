# Guardrail Readiness v0

**Date:** 2026-06-30
**Sprint:** Guardrail Readiness v0 — read-only correlation of the runtime guardrail surfaces.

## Goal

Add a read-only "Guardrail Readiness" summary that correlates runtime status, the last
NemoClaw/OpenShell health probe, policy inspection, and the agent mode policy into a
single honest answer: *is the system ready for a future bridge to be **designed**?* It
must not enforce policy, unlock browser/computer-use/MCP/OpenClaw/Gmail, or execute
anything. This is the final honest readiness view before an actual bridge **contract**
is designed.

## Files changed

### Backend
- **`backend/app/guardrail_readiness.py`** (new) — `get_guardrail_readiness(...)` correlates
  the four surfaces. Data-source callables are injectable (defaults read existing
  cached/inspection data only). Never raises (defensive `error` fallback).
- **`backend/app/models.py`** — added `GuardrailReadinessComponents`,
  `GuardrailCapabilityUnlocks`, `GuardrailReadinessResponse`.
- **`backend/app/main.py`** — imports + endpoint `GET /api/runtime/guardrail-readiness`.
- **`backend/tests/test_guardrail_readiness.py`** (new) — 21 tests.

### Frontend
- **`src/lib/api.ts`** — types `GuardrailReadinessStatus`, `GuardrailReadinessComponents`,
  `GuardrailCapabilityUnlocks`, `GuardrailReadinessResponse` + `getGuardrailReadiness()`.
- **`src/lib/runtimeStatus.ts`** — `readinessStatusLabel`, `readinessStatusTone`,
  `readinessDashboardLine`, `READINESS_COPY`.
- **`src/components/runtime/RuntimeStatus.tsx`** — `GuardrailReadinessPanel` inside
  `RuntimeGuardrails`; readiness line added to `RuntimeGuardrailNote` (Local Agent).
- **`src/pages/DashboardPage.tsx`** — compact "Guardrail readiness:" line on the runtime card.

### Docs
- `README.md`, `context/current-task.md`, this session summary.

## Readiness status behavior / correlation logic

- **`not_ready`** — no reachable probe AND no loaded policy.
- **`partially_ready`** — reachable probe XOR loaded policy.
- **`ready_for_bridge_design`** — last probe reachable AND policy loaded/valid AND mode
  policy present AND no dependent falsely reporting browser/computer-use as enabled.
- **`error`** — defensive only (inputs unreadable); never raised.

`ready: true` is set **only** for `ready_for_bridge_design`, and it means "ready for a
bridge to be *designed*," never "ready to execute." `capabilityUnlocks.*` is **false in
every state**.

## UI behavior

- Tool Connections → Runtime Guardrails: new **Guardrail Readiness** panel (status, summary,
  component chips, blockers, suggested next steps, capability unlocks all shown `disabled`,
  warnings) + **Refresh readiness** button. Refresh calls the read-only endpoint only —
  **no** health probe.
- Dashboard runtime card: compact "Guardrail readiness: Not ready / Partial / Ready for
  bridge design" line.
- Local Agent runtime-guardrail note: same readiness line + "Guardrail readiness does not
  enable execution."
- Required copy present: *"Guardrail readiness is informational only…"* and *"Ready for
  bridge design does not mean ready for execution."*
- No enable / start / bridge / execute controls added.

## What remains not enabled / not wired

- OpenClaw / NemoClaw / OpenShell runtime bridge — still **not implemented**.
- Browser harness, computer-use, MCP gateway, Gmail — all remain **disabled**.
- Policy enforcement — still not wired (inspection/readiness are read-only).
- No fresh health probe runs from readiness; readiness reads the cached last probe only.

## Tests run

```
python -m pytest backend/tests -q      → 473 passed, 1 warning
npm run build                          → 88 modules, 0 TypeScript errors
```

Backend tests cover: the full correlation matrix (no probe + no policy → not_ready;
reachable probe + no policy → partially_ready; loaded policy + no reachable probe →
partially_ready; reachable probe + loaded policy → ready_for_bridge_design); capabilities
false in all states; `ready` ≠ execution-ready; falsely-enabled-dependent guard; mode-
unavailable guard; next-steps; a source guard that the module never references
`probe_nemoclaw`; `read_probe` default is `read_last_probe`; no subprocess/socket; never
raises; no vault write; endpoint smoke.

## Safety constraints

Endpoint is pure/read-only: no fresh probe, no network call, no process launch, no
shell/`brain`, no credential read, no vault write, no tool execution. It never enforces
policy and never unlocks a capability.

## Recommended next sprint

Design the **NemoClaw/OpenShell bridge contract** (interface/schema only — request shape,
policy-gate handshake, audit expectations) with no execution wired. Readiness now gives an
honest signal for when that design work is worth starting.
