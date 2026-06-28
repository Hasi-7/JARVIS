# Session Summary: NemoClaw/OpenShell Health Probe v0

Date: 2026-06-28
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Add an **explicit, opt-in** reachability probe for NemoClaw/OpenShell **only**. When the user clicks
**Check NemoClaw/OpenShell**, the backend performs a single **bounded HTTP GET** to a *configured
local* runtime URL and reports reachable/unreachable. It **verifies readiness only** — it unlocks no
capability, starts no runtime, and changes no enforcement.

```text
configured runtime URL → explicit user-triggered probe → bounded health check → UI result
(no capability unlocks · no process start · no tool execution · no credentials)
```

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/runtime_probe.py` | **New.** `probe_nemoclaw(timeout_ms, env, http_get)` — bounded GET to the configured local URL; `http_get` is injectable so tests mock the HTTP client. `read_last_probe()` + a backend-local cache (`backend/data/runtime/last-probe.json`). Enforces local-only + no-credential + no-redirect rules. Never raises. |
| `backend/app/models.py` | `NemoclawProbeRequest`, `NemoclawProbeDetails`, `NemoclawProbeResponse`, `NemoclawLastProbeResponse`. |
| `backend/app/main.py` | `POST /api/runtime/probe/nemoclaw` + `GET /api/runtime/probe/nemoclaw/last`. |
| `backend/tests/test_runtime_probe.py` | **New.** 22 tests. |

---

## Probe behavior

- Reads env config only: `NEMOCLAW_ENABLED`, `NEMOCLAW_RUNTIME_URL`, `NEMOCLAW_POLICY_PATH`,
  `NEMOCLAW_ALLOW_REMOTE_PROBE`.
- **No URL configured** or **not enabled** → `not_configured`, with **no network call**.
- Otherwise validates the URL, then performs one bounded GET. Result `status` ∈
  `reachable` (2xx) | `unavailable` (non-2xx / timeout / refused) | `not_configured` | `error`
  (validation failure). `reachable` is true only for a 2xx response.
- Response carries `configured`, `reachable`, `durationMs`, `message`, and `details`
  (`urlConfigured`, `policyPathConfigured`, `enabledFlag`, `remoteProbeAllowed`, `hostRedacted`).
- Every result is cached to `backend/data/runtime/last-probe.json`; `GET …/last` reads it (loading is
  not a probe — no network).

---

## URL / network safety constraints

- Only `NEMOCLAW_RUNTIME_URL` is probed — the frontend can supply **only** `timeoutMs`, never a URL.
- **Loopback hosts only** by default (`localhost` / `127.0.0.0/8` / `::1`, via `ipaddress.is_loopback`).
  Public/LAN hosts are rejected (`error`) unless `NEMOCLAW_ALLOW_REMOTE_PROBE=true`.
- URLs carrying `user:pass@` (userinfo) are rejected; non-http(s) schemes rejected.
- **Redirects disabled** (`_NoRedirect` handler); no cookies, no auth headers.
- Timeout clamped to `[1, 3000]ms` (default 1500).
- `hostRedacted` exposes only `scheme://host[:port]` — never userinfo / path / query (no secret leak).

---

## UI behavior

- Tool Connections → **Runtime Guardrails** gains a **NemoClaw/OpenShell health probe** block with an
  explicit **Check NemoClaw/OpenShell** button (loading state), and a result panel: status + checked
  time + duration + message + URL configured (yes/no) + policy path (yes/no) + redacted host.
- It loads the cached last result on mount (read-only; **not** a probe).
- Copy: *"This checks whether a configured NemoClaw/OpenShell runtime is reachable. It does not start
  the runtime or enable browser/computer-use."* and *"Browser and computer-use remain disabled until a
  separate runtime bridge is implemented and explicitly enabled."*
- No Start / Connect / Enable / Execute control is added.

---

## What remains disabled / not wired

The runtime bridge is **not implemented**. Even a reachable probe unlocks nothing: browser,
computer-use, MCP, Gmail, OpenClaw execution all stay disabled. `/api/runtime/status` is unchanged —
browser/computer-use remain `disabled` after any probe.

---

## Tests run

```bash
python -m pytest backend/tests -q   # 429 passed (22 new probe tests)
npm run build                        # 88 modules, 0 TypeScript errors
```

Probe tests cover: no URL / disabled / missing-enabled → not_configured with no network call; localhost
success → reachable; timeout/non-2xx → unavailable; non-local + public rejected by default; remote
allowed only with the flag; credentials/non-http rejected; host redaction; timeout clamp (min/max/
default); no shell/`brain`/subprocess; probe does not enable browser/computer-use; cache read/write;
endpoints.

---

## Safety constraints

- Probes only a configured **local** URL; no frontend-supplied URL; no remote without an explicit flag.
- No credentials/cookies/auth headers; no redirects; bounded timeout.
- Starts no process, runs no shell/`brain`, reads no credentials, writes no vault, executes no tool.
- Unlocks no capability — reachability is informational only.

---

## Recommended next sprint

Add a **read-only NemoClaw policy inspection** (parse a configured `NEMOCLAW_POLICY_PATH` and display
the declared allow/deny scopes) — still no enforcement, no execution — so the eventual bridge can be
designed against a visible, verified policy before any privileged path is gated on it.
