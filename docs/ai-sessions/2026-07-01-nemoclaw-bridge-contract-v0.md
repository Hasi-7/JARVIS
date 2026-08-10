# NemoClaw/OpenShell Bridge Contract v0

**Date:** 2026-07-01
**Sprint:** NemoClaw/OpenShell Bridge Contract v0 — dry-run validator for future bridge requests.

## Goal

Define the backend request/response **contract** for a future NemoClaw/OpenShell bridge
and add a **dry-run validator** that evaluates whether a proposed bridge request would be
blocked, requires approval, or is structurally acceptable for a bridge to be *designed* —
without implementing the bridge and without executing anything.

## Files changed

### Backend
- **`backend/app/runtime_bridge_contract.py`** (new) — `validate_bridge_request(...)` runs
  the dry-run pipeline (schema → mode → readiness → risk map → gateway dry-run → log).
  `readiness_fn`/`log_fn` injectable for tests; never raises.
- **`backend/app/permission_gateway.py`** — added `log_bridge_validation(...)` (source
  `runtime_bridge_validation`, result `validated_only`, `allowed`/`executionEnabled` false),
  reusing the existing log store + redaction/truncation helpers.
- **`backend/app/models.py`** — `RuntimeBridgeAction`, `RuntimeBridgeValidationRequest`,
  `RuntimeBridgeValidationChecks`, `RuntimeBridgeValidationResponse`.
- **`backend/app/main.py`** — `POST /api/runtime/bridge/validate`.
- **`backend/tests/test_runtime_bridge_contract.py`** (new) — 34 tests.

### Frontend
- **`src/lib/api.ts`** — bridge types + `validateRuntimeBridgeRequest()`.
- **`src/lib/runtimeStatus.ts`** — `bridgeStatusLabel/Tone`, `riskTone`,
  `BRIDGE_ACTION_KINDS`, `BRIDGE_COPY`.
- **`src/components/runtime/RuntimeStatus.tsx`** — `BridgeContractValidatorPanel` inside
  `RuntimeGuardrails`.
- **`src/pages/DashboardPage.tsx`** — static "Runtime bridge: contract validator only" line.

### Docs
- `README.md`, `context/current-task.md`, this session summary.

## Bridge request schema

```
RuntimeBridgeValidationRequest {
  source: string = "openclaw"
  mode?: string                         // normalized via agent mode policy
  requestedAction: { kind, target?, args? }   // args untrusted; summarized only
  reason?: string
  conversationId?: string
}
```

Response carries `status` (`blocked_by_mode | blocked | validated | error`), `allowed`
(always false), `executionEnabled` (always false), `mode`, `source`, `actionKind`,
`riskLevel`, `decision`, `message`, a `checks` object, `blockers[]`, `warnings[]`, `logId`.

## Validation behavior / mode / readiness / risk

- **Schema:** a blank/missing action kind → `schemaValid: false` and `actionKind: unknown`.
- **Mode:** `locked`/`observe`/`computer_use` → `blocked_by_mode`; `draft`/`assist`/
  `research`/`escalation` validate only; `assist` notes safe-local review-handoff-eligible
  later (still never executes here).
- **Readiness:** `get_guardrail_readiness()` is read **cached — no fresh probe**. Not
  `ready_for_bridge_design` → blocker "Runtime guardrail is not ready for bridge design";
  when ready, a safe-local request is `validated` (schema acceptable) but still does not run.
- **Risk (conservative):** safe-local reads (`brain.*`, `vault.read`) `low`;
  browser/MCP/Gmail/calendar `medium`; computer-use/`vault.write`/`unknown` `high`.
- **Permission gateway:** the action kind maps to a representative existing policy tool and
  is classified **dry-run** (`evaluate_tool_request`) — no execution path is touched.

## Logging behavior

Each validation writes one sanitized entry to the existing tool-log store with source
`runtime_bridge_validation` and result `validated_only`. Only the redacted args summary is
stored (secret-bearing keys redacted, long values truncated) — never raw args, full page
contents, or credentials. `allowed`/`executionEnabled` are false on the entry.

## UI behavior

Tool Connections → Runtime Guardrails: **Bridge Contract Validator** panel (source, current
mode read-only, action-kind dropdown, reason, JSON args) + **Validate bridge request**
button. Invalid JSON is caught client-side and does not submit. Result shows status,
decision, risk, mode, action kind, checks, allowed/approval/execution posture, blockers,
warnings, and the log id. Required copy present. Dashboard shows a compact "Runtime bridge:
contract validator only" line. No execute/approve/start-bridge/connect controls.

## What remains not implemented

Actual OpenClaw / NemoClaw/OpenShell bridge, browser harness, computer-use, MCP execution,
Gmail execution, Google Calendar API, runtime launch/auth, policy enforcement, execution
from chat or from the validator, vault writes, shell/arbitrary-brain execution, capability
unlocks — all still disabled.

## Tests run

```
python -m pytest backend/tests      → 507 passed, 1 warning
npm run build                       → 88 modules, 0 TypeScript errors
```

Backend tests cover: never-allows/executes across kinds; locked/observe/computer_use
blocked-by-mode; draft/assist/research/escalation validate-only; browser/computer/MCP/
Gmail/calendar/vault.write blockers; unknown + blank kind → high/denied; safe-local
validated-when-ready and not-executed; guardrail-not-ready blocker; guardrail-ready still
no execution; secrets redacted in log + response; no full page content stored; a source
guard that the module never references `probe_nemoclaw`; no subprocess/socket/brain; no
vault write; never raises; endpoint smoke.

## Safety constraints

Dry-run only: no call to NemoClaw/OpenShell/OpenClaw, no browser/computer-use/MCP/Gmail/
Calendar/vault/brain action, no fresh probe, no shell/`brain`/subprocess, no vault write,
no credential read, no capability unlock. `allowed`/`executionEnabled`/
`runtimeBridgeImplemented` are always false.

## Recommended next sprint

**Bridge request queue + manual review handoff (still no execution):** let a `validated`
safe-local bridge request be recorded to a review queue and opened in Tool Connections for
the existing manual safe-local run — closing the loop from proposed-bridge-request →
validated → manual review, without wiring any runtime or auto-execution.
