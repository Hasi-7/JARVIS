# Session Summary — NemoClaw/OpenShell Policy Inspection v0

**Date:** 2026-06-30
**Sprint:** NemoClaw/OpenShell Policy Inspection v0

## Goal

Make the future NemoClaw/OpenShell runtime guardrail **inspectable** before any privileged
bridge is built: read a configured policy file, parse it defensively, and display a safe
summarized view of declared scopes — **without enforcing the policy, starting the runtime,
executing tools, or enabling browser/computer-use/MCP/OpenClaw.**

## Files changed

### Backend
- **`backend/app/runtime_policy.py`** (new) — `inspect_nemoclaw_policy(env)`: reads only
  `NEMOCLAW_POLICY_PATH`, resolves + size-caps (256 KB) + UTF-8-decodes the file, parses
  JSON (stdlib) / YAML (`yaml.safe_load`, only if PyYAML importable), and builds a defensive
  summary. Never executes/imports the file, makes no network/process/shell call.
- **`backend/app/models.py`** — added `NemoclawPolicySummary`, `NemoclawPolicyResponse`.
- **`backend/app/main.py`** — added `GET /api/runtime/policy/nemoclaw` + imports.
- **`backend/tests/test_runtime_policy.py`** (new) — 23 tests.

### Frontend
- **`src/lib/api.ts`** — `NemoclawPolicyStatus`, `NemoclawPolicySummary`,
  `NemoclawPolicyResponse` types + `getNemoclawPolicy()` client.
- **`src/lib/runtimeStatus.ts`** — `policyStatusLabel/policyStatusTone`,
  `capabilityLabel/capabilityTone`, `policyDashboardLine`, `POLICY_COPY`.
- **`src/components/runtime/RuntimeStatus.tsx`** — `NemoclawPolicyPanel` (read-only) inside
  `RuntimeGuardrails` (Tool Connections), with a **Reload inspection** button.
- **`src/pages/DashboardPage.tsx`** — one compact honest **Policy:** line in the runtime card.

### Docs
- `README.md` — new "NemoClaw/OpenShell Policy Inspection v0" section + updated status table.
- `context/current-task.md` — new Current State entry (health probe demoted from "latest").

## Policy inspection behavior

`configured path → resolve → size/UTF-8 check → JSON/YAML safe-parse → defensive summary → display`

- No path configured → `not_configured` (no file read).
- Missing → `missing`; directory/non-file → `unreadable`; oversized (>256 KB) → `invalid`
  (rejected before contents read); non-UTF-8 → `unreadable`.
- Parse failure or non-object root → `invalid` (error surfaced).
- Parseable object → `loaded`; unknown keys surfaced; capabilities default **unknown**.

## Parsing behavior

- **JSON** always (stdlib `json`). **YAML** only when PyYAML is importable, via
  `yaml.safe_load` (SafeLoader) — never the unsafe full loader. PyYAML is **optional** (not
  added to `requirements.txt`); when absent, YAML files are reported honestly as unsupported.
- Recognizes `modes`, `network`/`network_policy`, `filesystem`/`filesystem_scopes`,
  `browser`/`browser_harness`, `computer_use`, `mcp`, `credentials`, plus nested `{allowed}`
  / `{scopes}` / `{policy}` shapes. Capabilities are tri-state: allowed / blocked / **unknown**,
  and only reported allowed when clearly declared.

## UI behavior

- Tool Connections → Runtime Guardrails: read-only policy panel (status, path, modes, network,
  fs scopes, browser/computer-use/MCP allowed·blocked·unknown, credential access, warnings/errors)
  + **Reload inspection** button + required read-only/disabled copy.
- Dashboard runtime card: one compact `Policy: …` line.
- **No** edit / apply / enable / start / capability-toggle control anywhere.

## What remains not enforced / not wired

- Policy **enforcement**, OpenClaw bridge, NemoClaw/OpenShell bridge, browser/computer-use
  harness, MCP execution, Gmail/Calendar/Drive, runtime launch/auth, credential storage,
  tool execution from runtime/chat, vault writes, shell — **all still not implemented.**
- Capabilities remain disabled regardless of what any policy declares.

## Tests run

```
python -m pytest backend/tests    → 452 passed (23 new)
npm run build                     → 88 modules, 0 TS errors, clean
```

## Safety constraints

- Reads only `NEMOCLAW_POLICY_PATH`; endpoint accepts **no** path argument (no frontend path).
- No directory listing, no code execution/import of the policy file, text-only, 256 KB cap.
- No network / process / shell / `brain` / credential read / vault write / tool execution.
- `yaml.safe_load` only (guarded by a source-level test); no capability unlock from policy.

## Recommended next sprint

Wire the **policy ↔ probe correlation** (still read-only): when both a reachable local runtime
probe and a `loaded` policy exist, show a combined "guardrail readiness" summary — still with
**no enforcement and no capability unlock** — as the last honest step before designing the
actual NemoClaw/OpenShell bridge contract.
