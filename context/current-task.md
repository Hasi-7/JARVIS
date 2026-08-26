# Current Task

## Current State

**All five PRD gap items complete (2026-08-24). 1331 backend tests pass; build
clean (94 modules). Every MVP tier v1–v10 is now implemented.**

**Computer-use harness (MVP v7) — the last unbuilt tier.** New
`backend/app/computer_use.py`. The user chose **full desktop control** over
browser-only (PRD §41 Q5/Q6, previously unanswered); the advice on record was
browser-only, because host control has no sandbox boundary. That decision means
the guards ARE the safety:
1. Assist mode · 2. operator token (`X-Brain-Approval-Token`) · 3.
`BRAIN_UI_COMPUTER_USE_ENABLED` kill switch, default OFF · 4. an active session
within its wall-clock budget · 5. **the foreground window must match the session
allowlist — if focus moved, the action is REFUSED, never retargeted.**
PRD §13.4's nine risky categories need per-action confirmation (never sticky —
a test asserts a confirmed action does not unlock the next one). Typing into a
credential window is **refused outright and cannot be confirmed away**.
Also: typed text capped and control-characters rejected, a system-hotkey denylist,
`pyautogui.FAILSAFE` on, screenshots downscaled and stored backend-local only
(never the vault), and typed CONTENT never logged — only its length.
`computer.click`/`computer.type` are approval-gated and `computer.screenshot`
added. Frontend `ComputerUseBanner` is mounted app-wide with a Stop control;
both status and stop are deliberately unauthenticated so the indicator always
renders and the emergency stop always works.

**A false positive the tests caught, which would have made the tool useless
here:** the credential-detection pattern matched the bare word "vault" — and this
entire app is built around an Obsidian *vault*, so every ordinary window would
have been flagged as a password surface. Password managers are now matched by
name instead.

**Vault tool-log mirror (PRD §32, closes acceptance criterion #19).** Every
gateway entry is mirrored append-only to `ops/tool-logs/YYYY-MM-DD-tool-log.md`
through `vault.py`'s `_safe_subpath`. JSON stays the queryable source; a mirror
failure is swallowed so it can never break the action it records. Pipes are
escaped and newlines flattened so untrusted values cannot break the table.
**Caught during implementation:** the first full test run wrote 395 rows of
synthetic log data into the REAL vault, because the mirror resolves the live
config. Removed, and `conftest.py` now pins the mirror off for the whole suite.

**Email → task / calendar apply (closes MVP v8).** `proposals.py` gained
`email-task:` / `email-calendar:` id prefixes dispatching to `vault.create_task`
and `calendar.create_calendar_candidate` — the same adapters A3 uses, so backup /
conflict-check / traversal rejection are inherited. Calendar candidates are always
written `Approved=No`. Row parsing **refuses to invent dates**: a calendar row with
no recognisable date is reported skipped rather than scheduled on a guessed day,
and ambiguous numeric forms like `03/04/2026` are deliberately not parsed.

**Browser search (closes MVP v4 / §13.2).** One fixed privacy-respecting provider
(host pinned as a constant, never caller-supplied); every result is then run
through the same `validate_url()` allowlist that guards `open_page`, so appearing
in results grants a URL nothing. Provider redirect wrappers are unwrapped.

**Canvas/Quercus intake (closes MVP v10).** `backend/app/quercus.py`: read-only
Canvas REST, GET-only, host pinned, redirects disabled, numeric course-id
validation, HTML stripped from untrusted descriptions, token never logged or
returned. Assignment SUBMISSION is deliberately out of scope. Needs
`BRAIN_UI_QUERCUS_TOKEN` to run live.

**Two latent bugs found and fixed:** `strip_html`/`_truncate` bound their size cap
as a default argument, freezing it at import so the limit was not actually
configurable (same pattern previously fixed in `graph.py`). And `spin` — referenced
by inline styles across the app for loading indicators — was never defined in CSS,
so every spinner was static; added alongside the new `pulse` keyframe.

**C1b + D3d complete (2026-08-24). Every planned task is now implemented.
1130 backend tests pass; `npm run build` clean (93 modules).**

**C1b sandboxed fetch driver.** New `backend/app/openshell_exec.py` — the one place
that runs a command inside an OpenShell sandbox, kept separate from the
provably-read-only `openshell_client.py`. `browser.sandboxed_fetch` now really
fetches, via `curl` executed INSIDE the sandbox over the streaming `ExecSandbox`
RPC. `browser.read_page` moved from `disabled` to approval-gated and joined
`_APPROVAL_REQUIRED_TOOLS`, so a page read runs only after the full A3 flow.
**The fail-open policy concern is now enforced in code, not just advised:**
`assert_policy_enforces()` REFUSES to execute when the sandbox policy sets
`landlock.compatibility: best_effort`, because isolation may silently not apply
(OpenShell#803, NemoClaw#1739; Docker's seccomp blocks the Landlock syscalls).
Override is explicit and logged: `BRAIN_UI_ALLOW_FAIL_OPEN_SANDBOX=true`.
Commands are an argv allowlist (`curl` only) — never a shell string, no `sh -c`.
Two bugs my own tests caught: the `--write-out` value contained a newline that
failed the argv validator, and the validator itself was over-broad — it rejected
`&`, which would have broken every URL with a query string. Since argv goes
straight to exec over gRPC and no shell ever interprets it, the guard is now
control-characters-only, with the reasoning recorded in the code.

**D3d vault graph viewer.** The PRD names a "Graphify viewer" once, with no data
format, and `brain graphify-setup` is not in the brain allowlist — so rather than
guess, `backend/app/graph.py` derives the graph from a source that IS well
defined: **Obsidian wikilinks**. Links inside code fences and inline code are
ignored; dangling links become real (hollow) nodes rather than being hidden;
resolution is case-insensitive by note name, matching Obsidian. `load_export()`
additionally reads standard node-link JSON if a real export ever appears, and
reports an unrecognized shape instead of rendering it wrongly.
Frontend `VaultGraph.tsx` renders it as an SVG force-directed graph with a
deterministic layout (no external graph library), click-to-focus neighbourhoods,
and an orphan filter.

**Honest-reporting fix found by running it live:** the real vault has 245 files but
only 94 nodes, because **151 files share a note name with another file** (one name
occurs 99 times). Collapsing them is correct for link resolution, but silently
showing 245 files as 94 notes misrepresents the vault — so `fileCount` per node and
a `collapsed` stat are now surfaced, with a warning and a per-node note in the UI.

**Real bug found by the same live run:** three endpoints I added (calendar
reconcile, vault index, vault graph) called `cfg.vaultPath`, but `RuntimeConfig`
exposes `vault_path` — they would have raised `AttributeError` in production. The
tests passed only because I had stubbed the config with the wrong attribute name,
so they validated my mistake rather than the real contract. Endpoints fixed and
the stubs corrected to match `RuntimeConfig`.

**C1 / C2 / D1 / D2 / D3 complete (2026-08-24). 1051 backend tests pass; build clean.**

**C1 time-boxed research (session layer).** `backend/app/browser.py`: sessions with a
wall-clock budget, a MANDATORY domain allowlist (empty = deny everything, and a
dot-boundary suffix match so `evil-rust-lang.org` never matches `rust-lang.org`),
SSRF guards (non-http(s), embedded credentials, and loopback/private/link-local
literals all rejected), page/char caps, and stop-now. Page text is untrusted:
scripts/styles stripped, size-capped, stored for review only. **Browsing fails
CLOSED** — `sandboxed_fetch` refuses when the OpenShell guardrail is unhealthy AND
still refuses when it is healthy, because ExecSandbox must route through the
approval queue first. There is deliberately no direct-HTTP fallback (source-guard
test). Endpoints `POST/GET /api/research/sessions...`; opening a page is classified
as `browser.read_page`, which is `disabled`, so fetches correctly 409 today.
Frontend `ResearchSessionPanel`. **Remaining: the real fetch driver — tracked as C1b.**

**C2 chat capture.** `backend/app/chat_capture.py` maps captured pages to
Consolidation draft fields: host→sourceTool detection (lookalike hosts like
`evil-claude.ai` correctly fall through to `other`), speaker-label parsing into
user/assistant turns, and an honest single `unknown` turn when no labels are found
rather than inventing structure. Creates no draft, writes no vault file.

**D1 voice.** `backend/app/voice.py` + faster-whisper, fully on-device. Validation
runs BEFORE decode; uploaded filenames are reduced to a basename so
`../../../etc/passwd.wav` cannot build a path; temp files are deleted even when
decode raises; transcription shares `agent.py`'s inference gate so speech never
races the LLM for the GPU (busy → HTTP 429). **Live-verified**: Windows SAPI spoke
a sentence, local Whisper returned it verbatim.

**D2 approved Calendar writes — THE ONLY EXTERNAL WRITE.** `backend/app/gcal_write.py`
is a SEPARATE module so `gcal.py` stays provably read-only. Create-only; update/
patch/delete/move are absent and source-guarded. The request body is REBUILT from a
fixed allowlist, so a candidate row cannot smuggle in attendees, conferencing, or
reminder overrides; `sendUpdates` is forced to `none`, so creating an event can
never email anyone. Reached only through the A3 approval queue. Requires the
opt-in `calendar.events` scope (`BRAIN_UI_CALENDAR_WRITE_ENABLED` + re-consent).
NOTE: granting that scope would have BROKEN Gmail reads, because
`_assert_readonly_scopes` rejected any extra scope — now it allows exactly
calendar.events and drive.readonly while still refusing every Gmail write scope.

**D3.** `github.py` (read-only: GET-only, host-pinned to api.github.com, redirects
disabled, `owner/name` validated, token never logged/echoed/returned even in
errors), `gdrive.py` (read-only listing + text export; binary types refused rather
than downloaded; trashed files never listed; Drive query apostrophes escaped),
`vector_search.py` (local Ollama embeddings, vault read-only, and **honest
degradation** — with no embedding model it reports `mode: lexical, degraded: true`
instead of pretending results are semantic).

**Test hermeticity, again.** `vector_search` tests were taking 19 s because
`embedder=None` fell through to a live Ollama call; pinned in the fixture → 0.42 s.
`conftest.py` also pins `github_read_ready_fn`, so GitHub policy results no longer
depend on whether the dev machine has a token.

**D1 Voice I/O complete (2026-08-23, LOCAL-ONLY, live-verified).** New
`backend/app/voice.py` wraps faster-whisper 1.2.1 for fully on-device speech-to-text.
The user chose local Whisper over the browser Web Speech API precisely so audio
never leaves the machine — Chrome streams mic audio to Google's servers; this does
not, and a source-guard test asserts the module references no HTTP client, socket,
or cloud speech vendor.
Endpoints `GET /api/agent/voice/status` (loads no model, no network) and
`POST /api/agent/transcribe` (multipart upload).
**Safety:** size cap 25 MB and extension allowlist enforced BEFORE any decode (test
asserts the model is never touched for a rejected upload); uploaded filenames are
reduced to their basename so `../../../etc/passwd.wav` cannot build a path; audio
length capped at 300 s; segments capped 500; text capped 20 000 chars; the temp file
used for decoding is deleted in a `finally` (test asserts deletion even when decode
raises). Transcripts are UNTRUSTED — returned for review, never auto-sent, never
routed to a tool (test feeds a command-shaped transcript and asserts it is only echoed).
**GPU contention:** transcription shares `agent.py`'s single `_INFERENCE_GATE`, so
speech and the local LLM never compete; the gate is released on both success and
failure, and a busy LLM yields HTTP 429 rather than a stall. Device defaults to
**cpu** — the RX 7900 GRE is AMD, so faster-whisper's CUDA path does not apply.
Model is cached and re-loaded only when config changes.
Frontend: `src/components/ui/VoiceControls.tsx` (MediaRecorder capture, elapsed
timer with auto-stop at the cap, transcript appended to the composer for review,
`Speak replies` toggle using the browser's local SpeechSynthesis voices) mounted
above the AgentPage composer, driving real `AgentSphere` states
(listening → thinking → idle) via the existing store `setAgentState`.
**Live end-to-end proof:** Windows SAPI synthesized "Add a task to review the
calendar tomorrow morning"; local transcription returned that sentence exactly
(3.5 s audio, 3.8 s including first-run model load, language `en`).
40 new tests → **841/841 backend pass**, `npm run build` clean.

**Policy inspector aligned to the real OpenShell schema (2026-08-23).** The
sandbox policy `backend/policies/jarvis-deny-by-default.yaml` is written and
`NEMOCLAW_POLICY_PATH` is set, but `runtime_policy.py`'s `_summarize()` predated
the real schema: it reported `filesystem_policy`, `landlock`, and `version` as
*unrecognized*, and showed `networkPolicy: null` / `filesystemScopes: []` for a
policy that actually denies all outbound traffic and restricts the filesystem —
i.e. the UI displayed nothing about a genuinely restrictive policy.

Schema taken from the vendored `proto/openshell/sandbox.proto` (`SandboxPolicy`:
`version`, `filesystem`/`filesystem_policy`, `landlock`, `process`,
`network_policies`, `network_middlewares`). Note the YAML key is
`filesystem_policy` while the proto field is `filesystem` — serde renaming; both
are accepted. `KNOWN_KEYS` is now `OPENSHELL_KEYS | LEGACY_KEYS` so hand-written
or non-OpenShell policies still summarize.
- `filesystemScopes` now renders `FilesystemPolicy` as `ro:`/`rw:` entries plus
  `include_workdir`.
- `networkPolicy` now reports `deny (no network_policies declared)` when the key
  is absent/empty, or `allow (<names>)` when rules exist — but **only** for
  documents that look like OpenShell policies, so a foreign document reads
  `unknown` rather than falsely reading `deny`.
- New **fail-open advisory**: `landlock.compatibility: best_effort` applies only
  what the host supports and otherwise just warns, so filesystem isolation can
  silently not take effect (see NVIDIA/OpenShell#803 and NemoClaw#1739 — and
  Docker's default seccomp profile blocks the Landlock syscalls 444–446). The
  inspector now warns and points at `hard_requirement`, which aborts sandbox
  startup instead. **The current policy uses `best_effort` and should move to
  `hard_requirement` before anything privileged runs in a sandbox.**

Inspection still enables nothing — capabilities stay `unknown`/disabled even for
a permissive policy (test asserts it). 9 new tests → **801/801 backend pass**.
The policy has NOT been applied to a sandbox (none exists yet).

**C0 OpenShell runtime RESOLVED (2026-08-23, READ-ONLY, live-verified).** The
NemoClaw/OpenShell guardrail is no longer hypothetical — a real NVIDIA OpenShell
0.0.111 gateway is running in WSL2 and the Windows backend talks to it over
typed gRPC.

*Setup:* user installed OpenShell in WSL2 Ubuntu 26.04 (kernel 6.6.114, so
Landlock is available). The `openshell sandbox list` "connection refused" was NOT
networking — the gateway crash-looped 28× with `no compute driver configured`;
OpenShell needs Docker/Podman underneath. Resolved with a compute driver
(gateway now reports `docker 29.7.2`).

*Verified connection facts (all tested from Windows):* endpoint
`https://127.0.0.1:17670`, `auth_mode: mtls`; **transport is gRPC over HTTP/2**
(ALPN negotiates `h2`, TLS 1.3) — every REST path returns 404 and server
reflection is `UNIMPLEMENTED`. Reachable from Windows at `localhost:17670` via
WSL2 localhost forwarding, so **the probe's loopback-only default is correct and
`NEMOCLAW_ALLOW_REMOTE_PROBE` is NOT needed** (earlier guidance to set it was
wrong). Client certs live under the WSL path and are readable from Windows over
`\\wsl.localhost\...`. Server cert SAN covers `localhost`, `127.0.0.1`, and
`host.openshell.internal`. Note for any stdlib-`ssl` consumer: the gateway CA
omits an Authority Key Identifier, so OpenSSL 3.x rejects it under
`VERIFY_X509_STRICT` — clear that flag rather than disabling verification.

*Protos:* vendored to `backend/proto/openshell/` from NVIDIA/OpenShell at tag
**v0.0.111** (matched to the installed binary, not `main` — wire format drifts
between releases). Stubs generated into `backend/app/openshell_pb/`;
`protoc`'s flat imports are rewritten to package-relative or they only import
with that directory on `sys.path`. Full procedure in
`backend/proto/openshell/REGENERATE.md`.

*New module `backend/app/openshell_client.py` — READ-ONLY.* Exposes only
`health()`, `gateway_info()`, `list_sandboxes()`, `current_user()`. **Privileged
RPCs are unreachable**: it never calls CreateSandbox/DeleteSandbox/Stop/Start/
ExecSandbox/ExecSandboxInteractive/CreateSshSession/ForwardTcp/UpdateConfig/
ExposeService/IssueSandboxToken, and a source-guard test asserts it — those
belong behind the approval queue in C1. mTLS material is read for the handshake
only and never logged, echoed, or returned (test asserts key bytes never reach an
error string). URL validation rejects embedded credentials, non-http(s)/grpc
schemes, and missing ports; timeouts clamp to [0.1, 15]s.

*`runtime_probe.py` fixed.* It did a plain HTTP GET with no client cert, which
against a gRPC+mTLS gateway would report a perfectly healthy runtime as
`unavailable` — exactly the dishonest status the module exists to prevent. The
default transport now calls the typed `openshell.v1.OpenShell/Health` RPC and
maps healthy→200, falling back to the old plain GET (`_plain_http_get`) when
grpcio/stubs are unusable so non-gRPC runtimes still probe as before. The
injection point is unchanged, so all 22 existing probe tests pass untouched.

*Deps:* added `grpcio`, `grpcio-tools`, and `PyYAML` (the latter so
`runtime_policy.py` can actually parse OpenShell's YAML policies — it was
previously optional and reported YAML as unsupported). `.env.example` documents
`NEMOCLAW_RUNTIME_URL`, new `NEMOCLAW_MTLS_DIR`, new `NEMOCLAW_TLS_SERVER_NAME`,
and `NEMOCLAW_POLICY_PATH`.

*Live results:* `Health` → `SERVICE_STATUS_HEALTHY` v0.0.111; `GetGatewayInfo` →
docker 29.7.2; `ListSandboxes` → 0; `GetCurrentUser` → role `openshell-user`.
42 new tests → **792/792 backend pass**, `npm run build` clean (90 modules).

**Still open before C1:** `backend/policies/jarvis-deny-by-default.yaml` now
provides an OpenShell v1 policy with no outbound network grants, and the
gitignored `backend/.env` points `NEMOCLAW_POLICY_PATH` to it. The policy is not
applied because `openshell sandbox list` currently returns no sandboxes; apply it
to the intended sandbox with `openshell policy set <name> --policy
/mnt/d/Hasnain/Personal/dev/JARVIS/backend/policies/jarvis-deny-by-default.yaml
--wait` after that sandbox exists. C1 must decide how `ExecSandbox`
(server-streaming) is gated — it is the first genuinely privileged RPC and must
route through the Permission Gateway approval queue, never through
`openshell_client.py`.

**B2 Calendar read + reconciliation complete (2026-08-23, READ-ONLY, live-verified).
Phase B is done.** New `backend/app/gcal.py`: `list_events(time_min, time_max)`
(events.list, `singleEvents=True`, cancelled filtered, cap 250) and `reconcile(
candidates, events)` — a **PURE** function (no I/O, no network, no writes) that
compares vault calendar candidates to real events. Only **approved** candidates
reconcile; each lands in exactly one bucket: `matched` (same normalized title +
same date), `conflicting` (no title match but time windows overlap), `missing`
(approved, parseable, nothing matches), `unparseable` (date/time unreadable).
Helpers `parse_duration_minutes` ('1h'/'90m'/'1h30m'/'1.5h'/'45'→minutes, default
60, capped 24h), `parse_candidate_window` (4 date formats × 6 time formats;
date-only rows are whole-day and therefore cannot conflict), `parse_event_window`
(all-day vs timed, `Z` suffix handled), `normalize_title`.
Endpoints `GET /api/calendar/google/{status,events,reconcile}`, each classified
through `evaluate_tool_request("calendar.read")` + tool-logged before the Google
client is touched. `calendar.read` policy flipped `not_wired → available` and
joined `_EXTERNAL_READ_TOOLS` (readiness hook renamed `_gmail_ready` →
`_google_reads_ready`; Gmail and Calendar share one token). `executionEnabled`
stays False. **Writes unreachable:** `gcal.py` never references insert/update/
patch/delete/move/import (source-guard test); `calendar.create_event` stays
`disabled`; `calendar.create_candidate` remains a separate vault-only,
approval-gated tool. `tools.py` `google-calendar-api` entry now resolves per call
with writes always in `blockedNow`. `CalendarStatusResponse.writesEnabled` is
hardcoded False until D2.
**Live-verified bug the mocks could not catch:** `datetime.now()` is naive, so
`timeMin`/`timeMax` had no UTC offset and Google returned **HTTP 400**. Added
`_rfc3339()` + `_utc_now()` normalizing datetimes *and* caller-supplied strings
(offset-less → `Z`, existing offsets preserved), plus 4 regression tests. Live
read then returned 2 events (1 all-day, 1 timed) and reconciliation ran clean.
Frontend: `api.ts` Calendar types + `googleCalendarStatus/Events/Reconcile` (no
event-write function exists); `CalendarPage.tsx` `GoogleCalendarReconcilePanel`
above the candidates table — authorization state, **Reconcile** button, counts
line, and four grouped result sections (conflicts red / missing amber / matched
green / unparseable). 56 new tests → **750/750 backend pass**, `npm run build`
clean (90 modules).

**B1 Gmail read intake complete (2026-08-23, READ-ONLY, live-verified).** New
`backend/app/gmail.py`: `search_threads(query, max_results)` (threads.list +
threads.get metadata) and `get_message(id)` (messages.get, format=full), plus
`build_intake_draft()` which reuses `email_intake.create_draft` unchanged — so
importing creates a **backend draft only, NO vault write**, and the existing
never-overwrite/stay-in-vault/untrusted-fence guarantees are inherited. Endpoints
`GET /api/gmail/status`, `POST /api/gmail/search`, `GET /api/gmail/messages/{id}`,
`POST /api/gmail/import`; every one classifies through
`permission_gateway.evaluate_tool_request` and writes a `gateway_eval` tool-log
entry **before** the Google client is touched, and returns the `logId`.
**Mutations are unreachable:** `gmail.py` never references send/trash/delete/
modify/batchModify/insert/labels/drafts, and a source-guard test asserts it.
`gmail.send` stays `disabled`; `trash` was added to `_DANGEROUS_SUBSTRINGS` so
`gmail.trash` classifies `disabled` rather than merely `denied`.
**Gateway:** `gmail.search`/`gmail.read` policies flipped `not_wired → available`
(requiresApproval False — they mutate nothing) behind a new
`_EXTERNAL_READ_TOOLS` branch. These are `allowed` **only when credentials exist
on disk** (`external_read_ready_fn`, default `gmail_configured()`), and
`executionEnabled` stays **False** — they run on their own read endpoints, never
through `/permissions/execute` (which remains brain-only). `list_policies()` and
`tools.py` resolve Gmail state **per call**, not at import time.
**Safety:** scopes re-asserted before every call (non-readonly scope → refuse);
query single-line + length-capped; `maxResults` clamped [1,50]; body capped at
100 KB with `bodyTruncated`; headers capped 500 chars; MIME walk has a 200-node
budget; malformed base64 never raises; one bad thread degrades to
`(metadata unavailable)` instead of failing the search. Bodies/headers are
UNTRUSTED — stored and displayed only, never followed as instructions, never
auto-routed to a tool.
**Also fixed:** `google_auth.authorize_google()` dead-ended when a refresh token
was revoked/expired/scope-changed, forcing the operator to hand-delete
`token.json`. It now falls back to browser consent (matters for D2, where adding
`calendar.events` invalidates the token the same way).
**Test hermeticity:** `conftest.py` gained an autouse fixture pinning
`permission_gateway.external_read_ready_fn` and `tools._gmail_reads_ready` to
False, because Gmail policy decisions otherwise depended on whether the dev
machine happened to be authorized — the same test passed before `authorize` and
failed after. All 654 pre-existing tests pass **unmodified**.
Frontend: `api.ts` Gmail types + `gmailStatus/gmailSearch/gmailMessage/gmailImport`
(no mutation function exists); `EmailIntakePage.tsx` `GmailImportPanel` replaces
the old static "Gmail MCP is not wired" banner with real authorization state,
search, and per-thread **Import as draft**. 40 new tests → **694/694 backend
pass**, `npm run build` clean (90 modules). Live smoke test against real Gmail
confirmed search + message read (3 threads, 1208-char body).

**A2 + A3 complete (2026-08-10).** Brain UI now uses a fixed dual Gemma 4 setup:
`gemma4:12b-it-qat` for everyday work and `gemma4:26b-a4b-it-qat` for explicit heavy
assistance. Consolidation, Research, and Email Intake expose opt-in preview-only AI assist;
prompts separate immutable system policy from bounded untrusted source JSON, Ollama JSON
mode is enforced, drafts are revalidated after inference, and applying a preview changes
form state only. A single inference gate covers streaming and non-streaming Ollama calls.
The Agent now has an authenticated approval queue for `brain.today`, `brain.sync_raw`,
`vault.create_task`, and `calendar.create_candidate`. Only Assist-mode requests can enter;
queue reads and mutations require `X-Brain-Approval-Token`, approve and execute are separate
confirmations, privileged execution defaults off, calendar candidates always begin
`Approved=No`, canonical args stay backend-only, and shared cross-process locks serialize
vault writes and approval claims. The three existing read-only brain status tools remain
immediately executable. **Baseline: 646 backend tests; frontend build clean (90 modules).**
**B0 Google OAuth setup complete (2026-08-10).** Desktop credentials are stored under
`backend/data/google/`; the local consent flow authorized Gmail readonly + Calendar
readonly and generated a gitignored token. Next mandatory step: **B1 Gmail read intake**.

**Proposal-Apply spine v1 (A1, latest) — the Proposal Queue can now APPLY, not just list.** New in `backend/app/proposals.py`: `apply_proposal(id, vault_path)`, `apply_batch(ids, vault_path)`, `reject_proposal(id)`, plus `_split_proposal_id()` (parses `"<prefix>:<relatedId>"`; prefixes `raw-inbox|consolidation|research|email-intake`). **Adds NO new write primitive** — it dispatches to the SAME source save/route the page already uses: raw-inbox → `intake.approve_proposal` + `route_proposal`; consolidation/research/email-intake → that module's `save_draft(id, vault_path)`. Every safety guarantee (never-overwrite/UUID-suffix, stay-in-vault, path-traversal reject, no brain/AI/tasks/calendar side effects) is inherited unchanged. Raw-inbox already-routed/archived → idempotent `alreadyApplied:true`; skipped → error; draft already-saved → source raises → caught per-item. `apply_batch` never raises for one failure (per-item error result). Reject: raw-inbox → `skip_proposal`; draft sources not rejectable in v1 (edit/leave unsaved). New endpoints `POST /api/proposals/apply` (`{id}`), `POST /api/proposals/apply-batch` (`{ids}`), `POST /api/proposals/reject` (`{id}`) — body-based (id contains a colon; avoids path-encoding). Models `ApplyProposalRequest`/`ApplyBatchRequest`(extra=forbid)/`ApplyProposalResult`/`ApplyBatchResponse` (models.py after ProposalListResponse). Frontend `ProposalsPage.tsx`: per-card **Apply** (pending|approved), **Reject** (raw-inbox only), inline success/error result line; header **Apply all safe (N)** → confirm modal listing items (applies filtered pending low/medium-risk; high-risk excluded, applied individually); action-error banner; reload after each apply to reflect new status. api.ts `ApplyProposalResult`/`ApplyBatchResponse` + `applyProposal()/applyProposalBatch()/rejectProposal()`. Tests `test_proposals_apply.py` (27; id-parse, draft/raw-inbox dispatch via patched source fns, idempotency, batch never-raises, reject rules, endpoint smoke via direct route-fn calls + patched get_config). 27 new → 534/534 backend pass, `npm run build` clean (88 modules). Also added `backend/.env.example` (documents BRAIN_UI_*/NEMOCLAW_*/OPENCLAW_* env). **Ollama NOT installed on this machine** — A2 (local-AI assist) is blocked on install; A3 (gated execution) is independent and next.

**NemoClaw/OpenShell Bridge Contract v0:** defines the backend **request/response contract** for a future NemoClaw/OpenShell bridge + a **dry-run validator** that answers, for a proposed bridge request, whether it would be blocked / requires approval / is structurally acceptable for future *bridge design* — **executes nothing**. New module `backend/app/runtime_bridge_contract.py` `validate_bridge_request(source, mode, action_kind, target, args, reason, conversation_id, readiness_fn, log_fn)` (readiness/log injectable for tests) + endpoint **`POST /api/runtime/bridge/validate`**. Request `{source, mode, requestedAction{kind,target?,args?}, reason?, conversationId?}` → response `{id, status, allowed, requiresApproval, executionEnabled, mode, source, actionKind, riskLevel, decision, message, checks{schemaValid,modeAllowsEvaluation,guardrailReadyForBridgeDesign,runtimeBridgeImplemented,permissionGatewayDecision}, blockers[], warnings[], logId, createdAt}`; `status ∈ blocked_by_mode|blocked|validated|error`. **Pipeline:** schema validate → normalize mode (agent_modes) → mode-allows-eval check → guardrail readiness (get_guardrail_readiness, **cached — no probe**) → action-kind→conservative-risk map → Permission Gateway **dry-run** classify (evaluate_tool_request on a representative policy tool) → sanitized audit log (`permission_gateway.log_bridge_validation`, source `runtime_bridge_validation`, result `validated_only`) → clear blocked/validated result. **Action kinds** (none execute): browser.open/search/read_page, computer.click/type/screenshot, mcp.call, gmail.search/read, calendar.read, vault.read/write, brain.status/raw_status/vault_path, unknown. **Conservative risk:** safe-local reads (brain.*, vault.read)=low; browser/mcp/gmail/calendar=medium; computer-use/vault.write/unknown=high. **Mode rules:** locked/observe/computer_use→`blocked_by_mode`; draft/assist/research/escalation validate-only; assist notes safe-local review-handoff-eligible-later (still never executes). **Honesty (load-bearing):** `allowed`+`executionEnabled` **always False** (a valid request is NOT approval to run); `runtimeBridgeImplemented` **always False**; even safe-local brain.status does NOT execute here (manual safe-local exec stays only in Tool Connections). Guardrail not `ready_for_bridge_design` → blocker "Runtime guardrail is not ready for bridge design"; ready → safe-local marked `validated` (schema acceptable) but still no run. **Logging:** only sanitized summary (secret keys redacted, values truncated) — never raw args/page content/creds. Never calls NemoClaw/OpenShell/OpenClaw/browser/computer-use/MCP/Gmail/Calendar, no fresh probe, no shell/`brain`/subprocess, no vault write, no capability unlock; never raises (defensive `error`). Models `RuntimeBridgeAction`/`RuntimeBridgeValidationRequest`(extra=forbid)/`RuntimeBridgeValidationChecks`/`RuntimeBridgeValidationResponse` (models.py). Frontend: api.ts `RuntimeBridgeActionKind`/`RuntimeBridgeValidationStatus`/`RuntimeBridgeAction`/`RuntimeBridgeValidationRequest`/`RuntimeBridgeValidationChecks`/`RuntimeBridgeValidationResponse` + `validateRuntimeBridgeRequest()`; `src/lib/runtimeStatus.ts` `bridgeStatusLabel/bridgeStatusTone/riskTone/BRIDGE_ACTION_KINDS/BRIDGE_COPY`; `src/components/runtime/RuntimeStatus.tsx` `BridgeContractValidatorPanel` inside `RuntimeGuardrails` (Tool Connections) — source input, current mode (read-only, from store via `toBackendMode(agentMode.id)`), action-kind dropdown, reason, JSON args textarea + **Validate bridge request** button (invalid JSON caught client-side, does NOT submit) + result (status/decision/risk/mode/kind/checks/allowed·approval·execution/blockers/warnings/logId) + required copy "This validates a future runtime bridge request. It does not call NemoClaw/OpenShell or execute the action." / "A valid bridge request is not an approval to run it." Dashboard runtime card adds static "Runtime bridge: contract validator only" line. **No execute/approve/start-bridge/connect control.** Runtime bridge remains NOT implemented; browser/computer-use/MCP/Gmail/OpenClaw remain disabled; nothing unlocked. Tests `test_runtime_bridge_contract.py` (34; injected readiness + isolated log dir; never-allows/executes matrix, locked/observe/computer_use blocked_by_mode, draft/assist/research/escalation validate-only, browser/computer/mcp/gmail/calendar/vault.write blockers, unknown+blank→high/denied, safe-local validated-when-ready, guardrail-not-ready blocker, ready-still-no-exec, secrets-redacted-in-log, no-raw-page-content, source-guard no `probe_nemoclaw`, no subprocess/socket/brain, no vault write, never-raises, endpoint smoke). 34 new → 507/507 backend pass, `npm run build` clean (88 modules).

**Guardrail Readiness v0:** a **read-only** correlation view answers one honest question — *is the runtime guardrail ready for a bridge to be **designed**?* — by combining the four existing guardrail surfaces. New module `backend/app/guardrail_readiness.py` `get_guardrail_readiness(list_runtime, read_probe, inspect_policy, list_agent_modes, env)` (data sources injectable for tests; defaults read existing cached/inspection data only) + endpoint **`GET /api/runtime/guardrail-readiness`** → `{id:"nemoclaw_openshell_guardrail", status, ready, checkedAt, summary, components{runtimeStatus,lastProbe,policy,modePolicy}, blockers[], warnings[], nextSteps[], capabilityUnlocks{openclawBridge,browserHarness,computerUse,mcpGateway,gmail}, notes}`; `status ∈ not_ready|partially_ready|ready_for_bridge_design|error`. **Correlation:** `not_ready` = no reachable probe AND no loaded policy; `partially_ready` = reachable probe XOR loaded policy; `ready_for_bridge_design` = last probe reachable AND policy loaded/valid AND mode policy present AND no dependent falsely reporting browser/computer-use enabled. **Honesty rule (load-bearing):** `ready:true` is set **only** for `ready_for_bridge_design` and means "ready for a bridge to be **designed**," never "ready to execute"; `capabilityUnlocks.*` is **False in every state**. Reads the **cached last probe only** (`read_last_probe`, never `probe_nemoclaw`) — makes **no fresh probe, no network call, no process launch, no shell/`brain`, no cred read, no vault write**; refreshing readiness triggers **no** health probe. Never raises (defensive `error` fallback). Models `GuardrailReadinessComponents`/`GuardrailCapabilityUnlocks`/`GuardrailReadinessResponse` (models.py). Frontend: api.ts `GuardrailReadinessStatus`/`GuardrailReadinessComponents`/`GuardrailCapabilityUnlocks`/`GuardrailReadinessResponse` + `getGuardrailReadiness()`; `src/lib/runtimeStatus.ts` `readinessStatusLabel/readinessStatusTone/readinessDashboardLine` + `READINESS_COPY`; `src/components/runtime/RuntimeStatus.tsx` `GuardrailReadinessPanel` inside `RuntimeGuardrails` (Tool Connections) — status, summary, component chips, blockers, suggested next steps, capability unlocks all `disabled`, warnings + **Refresh readiness** button (no probe) + required copy "Guardrail readiness is informational only. It does not enable OpenClaw, browser, computer-use, MCP, or Gmail actions." / "Ready for bridge design does not mean ready for execution." Dashboard runtime card shows one compact **Guardrail readiness:** line; Local Agent `RuntimeGuardrailNote` shows the same line. **No enable/start/bridge/execute control.** Runtime bridge remains NOT implemented; browser/computer-use remain disabled; nothing unlocked. Tests `test_guardrail_readiness.py` (21; injected fakes for the full correlation matrix, capabilities-false-in-all-states, ready≠execution guard, falsely-enabled-dependent guard, mode-unavailable guard, next-steps, source guard that the module never references `probe_nemoclaw`, default `read_probe is read_last_probe`, no subprocess/socket, never-raises, no-vault-write, endpoint smoke). 21 new → 473/473 backend pass, `npm run build` clean (88 modules).

**NemoClaw/OpenShell Policy Inspection v0:** the future runtime guardrail is now **inspectable** before any privileged bridge exists — a **read-only** view of the configured policy file with **no enforcement**. New module `backend/app/runtime_policy.py` `inspect_nemoclaw_policy(env)` + endpoint **`GET /api/runtime/policy/nemoclaw`** → `{id,configured,pathConfigured,pathExists,readable,valid,status,message,policyPathDisplay,format,summary{declaredModes,networkPolicy,filesystemScopes,browserAllowed,computerUseAllowed,mcpAllowed,credentialAccess,unknownKeys},warnings[],errors[]}`; `status ∈ not_configured|missing|unreadable|invalid|loaded|error`. **Reads only `NEMOCLAW_POLICY_PATH`** — the endpoint takes **no path argument** (frontend cannot supply a path); no configured path → `not_configured` with **no file read**. **Path safety:** resolve the path; missing → `missing`, directory/non-file → `unreadable` (no dir listing); **UTF-8 text only**, capped **256 KB** (oversized → `invalid`, rejected before read); policy file **never executed/imported as code**. **Formats:** JSON always (stdlib), **YAML only if PyYAML importable** via `yaml.safe_load` (SafeLoader, never unsafe `load`); PyYAML **optional** (not added to requirements) — absent → YAML reported honestly as `invalid`/unsupported. **Defensive summary:** parseable object → `loaded` with **unknownKeys surfaced**; capabilities default **unknown (null)**, only `Allowed` when clearly declared (never implied); `credentialAccess` defaults `unknown`; non-object root → `invalid`. **Enforces/unlocks nothing** — capabilities stay disabled regardless; no network/process/shell/`brain`/creds/vault/tool. Models `NemoclawPolicySummary`/`NemoclawPolicyResponse` (models.py). Frontend: api.ts `NemoclawPolicyStatus`/`NemoclawPolicySummary`/`NemoclawPolicyResponse` + `getNemoclawPolicy()`; `src/lib/runtimeStatus.ts` `policyStatusLabel/policyStatusTone/capabilityLabel/capabilityTone/policyDashboardLine` + `POLICY_COPY`; `src/components/runtime/RuntimeStatus.tsx` `NemoclawPolicyPanel` inside `RuntimeGuardrails` (Tool Connections) — read-only fields (configured/exists/readable/valid, status, path, modes, network, fs scopes, browser/computer-use/MCP allowed·blocked·unknown, credential access, warnings/errors) + **Reload inspection** button + required copy "Policy inspection is read-only. It does not enforce policy or enable runtime actions." / "Capabilities remain disabled until the runtime bridge is implemented separately." Dashboard runtime card shows one compact **Policy:** line. **No edit/apply/enable/start control.** Health probe remains explicit/opt-in; runtime bridge remains NOT implemented; browser/computer-use remain disabled. Tests `test_runtime_policy.py` (23; real temp files, no-frontend-path signature guard, oversized/invalid/missing/directory/non-UTF-8 cases, unknown-keys surfaced, capabilities default unknown, `safe_load`-not-`load` source guard, no subprocess/socket, no file written beside policy). 23 new → 452/452 backend pass, `npm run build` clean (88 modules).

**NemoClaw/OpenShell Health Probe v0:** an **explicit, opt-in** reachability check for NemoClaw/OpenShell **only** — verifies readiness, **unlocks nothing**. New module `backend/app/runtime_probe.py` `probe_nemoclaw(timeout_ms, env, http_get)` (http_get injectable for tests) + endpoints **`POST /api/runtime/probe/nemoclaw`** (body optional `{timeoutMs}`, clamped [1,3000]ms default 1500) and **`GET /api/runtime/probe/nemoclaw/last`** (reads backend-local cache `backend/data/runtime/last-probe.json`; loading it is NOT a probe). Response `{id,checkedAt,configured,reachable,status,durationMs,message,details{urlConfigured,policyPathConfigured,enabledFlag,remoteProbeAllowed,hostRedacted}}`; status ∈ reachable|unavailable|not_configured|error. Config from ENV only: NEMOCLAW_ENABLED, NEMOCLAW_RUNTIME_URL, NEMOCLAW_POLICY_PATH, NEMOCLAW_ALLOW_REMOTE_PROBE. **No URL or not enabled → not_configured with NO network call.** **Network safety enforced:** only NEMOCLAW_RUNTIME_URL is probed (frontend cannot supply a URL, only timeoutMs); **loopback hosts only** (localhost/127.0.0.0/8/::1) by default — public/LAN → `error` unless NEMOCLAW_ALLOW_REMOTE_PROBE=true; `user:pass@` URLs rejected; redirects disabled (`_NoRedirect`); no cookies/auth headers; timeout ≤3000ms. **Even when reachable, browser/computer-use stay disabled** (runtime bridge still not implemented). No process start/stop, no shell/`brain`, no creds, no vault write, no tool exec, no capability unlock. Models NemoclawProbeRequest/NemoclawProbeDetails/NemoclawProbeResponse/NemoclawLastProbeResponse (models.py). Frontend: api.ts RuntimeProbeStatus/NemoclawProbe* types + `probeNemoclawRuntime()`/`getLastNemoclawProbe()`; `src/lib/runtimeStatus.ts` probeStatusLabel/probeStatusTone + PROBE_COPY; `src/components/runtime/RuntimeStatus.tsx` `NemoclawProbePanel` inside `RuntimeGuardrails` (Tool Connections) — explicit **Check NemoClaw/OpenShell** button, loads cached last on mount (not a probe), shows status/checked-time/duration/message/URL+policy configured/redacted host, + copy "Browser and computer-use remain disabled until a separate runtime bridge is implemented and explicitly enabled." No start/connect/enable control. Runtime bridge remains NOT implemented; browser/computer-use remain disabled. Tests test_runtime_probe.py (22; inject fake http_get, isolate cache dir, assert no-network when not configured, local-only enforcement, timeout clamp, no shell/brain/subprocess, probe doesn't enable browser/computer-use). 22 new → 429/429 backend pass, `npm run build` clean (88 modules).

**OpenClaw / NemoClaw Runtime Status v0:** an honest, **read-only** backend surface reports what is configured / missing / disabled / blocked for the five privileged runtimes — status/readiness only, **launches nothing, executes nothing**. New module `backend/app/runtime_status.py` + endpoint **`GET /api/runtime/status`** → `{items:[{id,name,status,available,enabled,requiredFor[],dependsOn[],blocks[],configured{},notes}]}` for `openclaw`, `nemoclaw_openshell`, `browser_harness`, `computer_use`, `mcp_gateway` (status ∈ available|unavailable|not_configured|disabled|planned|error). **Honesty rule: no runtime is ever reported `available`** — v0 runs no verified health check (and must not), so even fully-configured runtimes stay `unavailable` and every item's `available`/`enabled` is False. Config detection reads **env only** (no network, no creds): `OPENCLAW_ENABLED`/`OPENCLAW_BASE_URL`, `NEMOCLAW_ENABLED`/`NEMOCLAW_RUNTIME_URL`/`NEMOCLAW_POLICY_PATH`, `ENABLE_BROWSER_HARNESS`/`ENABLE_COMPUTER_USE`/`ENABLE_MCP_GATEWAY` (unset → `not_configured`; only presence/flag read, values never stored). **Dependency blocking:** browser harness + computer-use depend on NemoClaw/OpenShell and stay `disabled`/blocked while it's unavailable — even if their own enable flag is set; MCP/OpenClaw privileged actions likewise require the guardrail. Models `RuntimeStatusItem`/`RuntimeStatusResponse` (models.py). Frontend: `src/lib/runtimeStatus.ts` (`getRuntimeStatus()`, `useRuntimeStatus()` hook + `RUNTIME_FALLBACK` static fallback so backend-down degrades honestly, `runtimeStatusLabel`/`runtimeStatusTone`/`isBlocked`, `RUNTIME_TRUTHS`) + `src/components/runtime/RuntimeStatus.tsx` (`RuntimeStatusRows` compact, `RuntimeGuardrails` full section w/ dependency chain + Not-wired-yet disabled button, `RuntimeGuardrailNote` small). **Dashboard** runtime panel now shows real backend-derived rows (replaced the old mock SYSTEM "Planned" rows) + truths "Privileged agent runtimes are not wired yet." / "Browser and computer-use remain blocked until NemoClaw/OpenShell is available."; **Tool Connections** adds a Runtime Guardrails section; **Local Agent** right rail adds a small runtime guardrail note. No connect/start/test/enable control (only a disabled "Not wired yet"). No backend execution path: no network/health call, no process launch, no shell/`brain`, no creds, no vault write, no tool exec. OpenClaw/NemoClaw/browser/computer-use/MCP remain **not wired**. 407/407 backend tests pass (16 new runtime-status tests), `npm run build` clean (88 modules).

**Global Agent Mode Display v0 (frontend-only):** the **enforced** agent mode is now visible app-wide, not just on the Local Agent page — **no tool behavior changes** (display only). The selected mode was already global app state (`useAppStore().agentMode`/`setAgentMode`); this sprint loads the backend policy once into the store and renders it honestly in the top bar + Dashboard. New shared lib `src/lib/agentModes.ts` (`toBackendMode`, `MODE_POLICY_FALLBACK`, `resolveModePolicy`, `modePolicySummary`, `MODE_TRUTHS`) — lifted out of `AgentPage.tsx` so all surfaces reuse one policy resolver. Store gains `agentModes: AgentModePolicy[] | null` + `loadAgentModes()` (calls `GET /api/agent/modes`; **non-fatal** — consumers fall back to the static `MODE_POLICY_FALLBACK` when the backend is down, app never blocks); `AppShell` calls `loadAgentModes()` once on mount alongside `checkBackend`/`loadStagedCount`. `ModeBadge` gains an optional `policy` prop → availability dot + policy tooltip ("Evaluates tool requests. Safe-local review handoff is available. Chat does not execute tools.") and reads `<mode> · unavailable` for Computer-Use (never implies browser/computer-use is wired). `TopCommandBar` resolves the policy and labels the badge "Mode". `DashboardPage` adds a compact **Agent mode** card (selected mode, availability, Evaluation Allowed/Blocked/Unavailable, Review handoff Safe-local only/Disabled, **Execution from chat: Disabled**) + the three truths (*Agent tools are mode-gated by backend policy* · *No mode executes tools from chat* · *Safe-local execution remains manual in Tool Connections*). `AgentPage` now reads `agentModes` from the store (removed its local fetch/duplicated helpers) and passes `policy` to its cockpit `ModeBadge`; all three surfaces stay in sync via the single store `agentMode`/`agentModes` (one `ModeBadge` control). **No backend change**; reuses existing `getAgentModes()`. OpenClaw/NemoClaw/browser/computer-use remain **not wired**. 391/391 backend tests pass (unchanged), `npm run build` clean (86 modules).

**Agent Mode Enforcement v0:** agent modes are no longer purely UI-only — they are now **enforced by backend policy**. A new module `backend/app/agent_modes.py` is the single source of truth: canonical modes `locked/observe/draft/assist/research/escalation/computer_use` with helpers `can_evaluate_tool_requests(mode)`, `can_offer_review_handoff(mode)`, `is_mode_available(mode)`, plus `normalize_mode` (alias `computer→computer_use`, `manual→locked`; unknown/missing → safest `locked`; never raises), `blocked_message`, and `list_modes`. Policy: `locked`/`observe` → evaluate=false/review=false/available=true; `draft`/`research`/`escalation` → evaluate=true/review=false; `assist` → evaluate=true/**review=true**; `computer_use` → evaluate=false/review=false/**available=false** (recognized but unavailable/not wired). The module **executes nothing** — it only resolves and reports policy. New read-only **`GET /api/agent/modes`** returns `{modes:[{id,label,available,canEvaluateToolRequests,canOfferReviewHandoff,notes}]}`. **`POST /api/agent/tool-request`** now takes an optional `mode` and, in `locked`/`observe`/`computer_use` (and anything that can't evaluate), returns `{status:"blocked_by_mode",mode,message}` (HTTP 200) **without evaluating, storing, or logging anything**; `draft`/`assist`/`research`/`escalation` evaluate-only as before. **`POST /api/agent/chat`** and **`/api/agent/chat/stream`** resolve the selected mode once: evaluating modes route structured output through the existing evaluate-only path; blocking modes parse the reply for **visibility only** (`parse_structured_output`) and return/emit `blockedByMode:true` + a clear message — nothing evaluated/stored/logged. Models: `AgentModePolicy`/`AgentModesResponse`/`AgentModeBlockedResponse`, `mode` added to `CreateAgentToolRequestRequest`, `mode`/`blockedByMode`/`message` added to `AgentChatStructured`. Frontend (`AgentPage.tsx`): fetches `getAgentModes()` (static fallback offline), replaced the "UI-only" note with **real per-mode policy copy** (tool requests evaluated-only/blocked/unavailable; review handoff allowed-in-Assist/not offered); manual request form disabled with blocked copy when the mode can't evaluate (sends `mode`, handles `blocked_by_mode`); chat shows a **Blocked by mode** notice (not a gateway failure); **Review in Tool Connections** button appears **only in Assist** for safe-local executable requests; no execute button anywhere. `mock.ts` adds an `escalation` mode (assist stays index 3 → store default unchanged); `types/index.ts` adds `escalation` to `AgentModeId`; `api.ts` adds mode types + `getAgentModes()` + `isBlockedByMode()`. **Local Agent remains non-executing; safe-local execution stays manual in Tool Connections.** Blocked modes create no execution logs; no path calls `/execute`, the brain wrapper, a subprocess, MCP/Gmail/browser/computer-use, Google Calendar, or writes the vault. 391/391 backend tests pass (38 new mode tests; 2 existing tests updated to pass an evaluating mode since mode-less now safely defaults to locked/blocked), `npm run build` clean (85 modules).

**Review in Tool Connections handoff (frontend-only):** an evaluated Local Agent tool request can be handed off to the Tool Connections evaluator for **manual** execution — closing the safe loop (agent proposes → backend evaluates/logs → user reviews in Tool Connections → user manually runs the safe-local tool → gateway logs execution). A **Review in Tool Connections** button shows in the per-message *Structured tool requests detected* panel and the right-rail *Agent Tool Requests* list **only** when `evaluation.executionEnabled === true && evaluation.allowed === true` and the tool is `brain.status`/`brain.raw_status`/`brain.vault_path`; all other requests show *Evaluation only — not executable in this build* (no handoff). Mechanism: new Zustand field `toolReviewTarget` (`{tool, argsSummary?, reason?, requestedBy?, source: 'agent-chat'|'agent-tool-request'|'manual', relatedId?}`, mirrors `proposalTarget`/`agentConvTarget`) + `setToolReviewTarget`; clicking sets it and `navigate('tools')` — **nothing executes during navigation**. ToolConnectionsPage (`PermissionGatewaySection`) consumes it once on mount: prefills tool + reason, sets `args` to `{}` (**never** reconstructs raw args from the sanitized summary), shows "Opened from Local Agent. Review before running." + "This request came from the Local Agent. It has not been executed. Only low-risk local brain status tools can run here.", clears the target, and does **not** auto-evaluate/execute (user must click **Run safe-local tool**). **No backend changes** (evaluation response already has executionEnabled/allowed/tool); **no new endpoints, no new execution capabilities, no new tools.** 353/353 backend tests pass (unchanged), `npm run build` clean (85 modules).

**Local Agent Structured Output v0:** the Local Agent can now emit an **optional structured JSON block** proposing tool requests, which the backend defensively parses and routes through the evaluate-only Agent Tool Request path — **still no execution**. New module `backend/app/agent_structured_output.py`: `parse_structured_output(text)` extracts a fenced ` ```json ` block **or** an `AGENT_STRUCTURED_OUTPUT:` labelled JSON object, validating `tool_requests` (cap 5, non-empty `tool`, `args` must be an object defaulting `{}`, `reason` fallback+truncate, unsupported fields ignored, untrusted); malformed JSON → a parse error, never an exception; no block → empty result. `evaluate_structured_output(text, conversationId)` creates an Agent Tool Request (gateway evaluate + `gateway_eval` log) per valid spec and returns `{toolRequests:[records], parseErrors:[...]}` — never calls `/execute`, the brain wrapper, a subprocess, or any tool. Both chat endpoints integrate it: `POST /api/agent/chat` adds a `structured` response field; `POST /api/agent/chat/stream` emits an SSE `event: structured` after streaming completes (streaming tokens unchanged; failures there are caught and never break the stream). The Local Agent system prompt now documents the optional block (evaluate-only, no claiming execution, no secrets, no privileged tools unless relevant, external content untrusted). Models: `AgentChatStructured` + `structured` forward-ref field on `AgentChatResponse` (`model_rebuild()`). Frontend (`AgentPage.tsx`): a *Structured tool requests detected* panel renders under each assistant message (tool/decision/risk/exec/status/logId + parse-error notices), and chat-evaluated requests also refresh the right-rail Agent Tool Requests list; api.ts adds `AgentStructuredOutput` + `onStructured` stream handler + `structured` on the chat response. Malformed output never breaks chat; **no run/approve-execute control in chat.** No MCP/Gmail/browser/computer-use, no OpenClaw/NemoClaw, no shell/brain, no vault write, no AI mutation. 353/353 backend tests pass (16 new structured-output tests), `npm run build` clean (85 modules).

**Agent Tool Request v0:** the Local Agent surface can now create a **structured tool-request proposal** that the backend evaluates through the Permission Gateway and logs — **with no execution power**. New module `backend/app/agent_tool_requests.py` + endpoint `POST /api/agent/tool-request` (body `{tool, args?, reason?, requestedBy?, conversationId?}`) calls `evaluate_tool_request` (classification only), writes the existing `gateway_eval` log, stores a redacted record (`backend/data/agent-tool-requests/requests.json`, cap 200), and returns `{id, tool, argsSummary, reason, requestedBy, conversationId, evaluation{allowed, decision, riskLevel, requiresApproval, executionEnabled, reason, policyNotes, logId}, createdAt, status}` with `status` always `evaluated_only`. `GET /api/agent/tool-requests?limit=` lists newest-first (clamped [1,200]). **It never executes:** does not call `/api/permissions/execute`, the brain wrapper, any subprocess, or any external tool — even a `brain.status` request returns `allowed`/`executionEnabled:true` but is **not run** (safe-local execution stays manual on Tool Connections). Only the **sanitized args summary** is stored (raw args/secrets never persisted; reason/requestedBy truncated; instructions in reason/args never followed). Models: `CreateAgentToolRequestRequest`(extra=forbid)/`AgentToolRequestEvaluation`/`AgentToolRequestResponse`/`AgentToolRequestListResponse`. Frontend: **Agent Tool Requests** panel on the Local Agent page right rail (`AgentPage.tsx`, replaces the old stub) — manual/simulated request form (tool dropdown + reason + JSON args, invalid JSON → clear error) + recent-requests list (tool/decision/risk/exec/status/logId); **no run/approve-execute/auto-run** control; api.ts adds `createAgentToolRequest()`/`listAgentToolRequests()` + types. No MCP/Gmail/browser/computer-use, no OpenClaw/NemoClaw, no shell/brain, no vault write, no AI, no tasks/calendar. 337/337 backend tests pass (19 new agent-tool-request tests), `npm run build` clean (85 modules).

**Safe-local Tool Execution v0:** the Permission Gateway can now **execute** a tiny allowlist of low-risk, read-only local tools — and only those — through the existing safe brain wrapper. Exactly three tools are executable: `brain.status`→`brain status`, `brain.raw_status`→`brain raw-status`, `brain.vault_path`→`brain vault-path` (policies updated to `status: available, riskLevel: low, requiresApproval: false, executionEnabled: true`; every other policy stays `executionEnabled: false`). New endpoint `POST /api/permissions/execute` evaluates + logs the request, and **only if `is_executable(tool)`** runs it via `run_brain_command` (`shell=False`, allowlisted, no args forwarded to brain), logs the execution, and returns `{tool, allowed, decision, riskLevel, requiresApproval, executionEnabled, evaluationLogId, executionLogId, ok, exitCode, stdout, stderr, durationMs, error}`. Non-executable tools (gmail/shell/unknown/dangerous/other available) get a **safe** response (`allowed:false`, `executionLogId:null`, `error:"Tool is not executable in this build."`) — never a 500, and the brain wrapper is never called. `evaluate_tool_request` now returns `decision: "allowed"` (allowed/executionEnabled true) for the three safe tools and still `requires_approval` for other available tools; the privileged kill-switch `EXECUTION_ENABLED` stays False (execution is opt-in per-tool via a small allowlist). Tool Log extended: entries carry a `source` (`gateway_eval` | `gateway_execution`); executions log `result` (success/failure), `exitCode`, truncated `stdoutPreview`/`stderrPreview`, `durationMs`. Frontend: Tool Connections page adds a **Run safe-local tool** button (enabled only for the 3 tools; otherwise disabled + "Execution disabled in this build."), an execution result panel (status/exit/duration/stdout/stderr/log ids), and the logs panel now distinguishes eval vs execution entries; api.ts adds `executePermissionTool()` + `ToolExecutionRequest`/`ToolExecutionResponse` + log source/exec fields. No shell, no arbitrary brain command, no MCP/Gmail/browser/computer-use, no vault write, no AI, no tasks/calendar. 318/318 backend tests pass (18 new execution tests; gateway tests updated), `npm run build` clean (85 modules).

**Tool Log v0:** the PRD tool-log/audit spine is real but records **Permission Gateway evaluations only** — nothing executes. Every `POST /api/permissions/evaluate` now writes one redacted, backend-local audit entry (`backend/app/permission_gateway.py` → `log_evaluation()`, storage `backend/data/tool-logs/evaluations.json`, **not** the vault; latest 500 kept) and returns its `logId`. New read-only endpoint `GET /api/permissions/logs?limit=&tool=&decision=` returns entries newest-first (limit default 50, clamped [1,200], exact-match tool/decision filters). Entry fields: id/timestamp/tool/requestedBy/reason/decision/riskLevel/allowed/requiresApproval/executionEnabled/sanitizedArgsSummary/policyNotes/result(`evaluated_only`). **Only the sanitized args summary is stored — raw args and secret values are never persisted** (password/token/secret/key/credential/authorization/cookie redacted; long values truncated; reason/requestedBy truncated). New Pydantic models `PermissionEvaluationLog`/`PermissionEvaluationLogsResponse`; `logId` added to `ToolRequestEvaluationResponse`. Frontend: a **Permission Evaluation Logs** panel on the Tool Connections page (`ToolConnectionsPage.tsx`) lists recent entries with tool/decision/risk/requestedBy/reason/sanitized-args, filters by decision + tool, **Refresh only** (no clear/delete/replay/run/approve-execute), and auto-refreshes after an evaluation; api.ts adds `getPermissionLogs()` + types + `logId`. No tool execution, no MCP/Gmail/browser/computer-use/Google/GitHub/Drive call, no shell, no brain, no vault write. 299/299 backend tests pass (12 new tool-log tests), `npm run build` clean.

**Email Intake manual v0:** the PRD's manual fallback for Gmail/email intake is real — Gmail stays disconnected. A new backend module (`backend/app/email_intake.py`) lets the user paste raw email content and create a **draft** (`POST /api/email-intake/drafts`) stored as backend metadata only (`backend/data/email-intake/drafts.json`), **no vault write at create time**. Requires non-empty subject + rawEmail; domain validated against `course|business|personal|unknown`; confidence validated (`High|Medium|Low`) if provided; missing summary → deterministic fallback (subject + body preview, no AI). Drafts list/get/edit (`GET`/`PATCH`; editable = subject/sender/receivedAt/domain/entity/summary/actionRequired/dueDate/confidence/proposedTaskRows/proposedCalendarRows; locked = id/createdAt/updatedAt/status/savedPath/**rawEmail**). **Save to vault** (`POST .../{id}/save`) writes exactly one Markdown summary under an allowlisted raw email path — `course→raw/quercus/emails/`, `business+entity→raw/business/<slug>/emails/`, `business no entity→raw/business/unknown/emails/`, `personal→raw/personal/email/`, `unknown→raw/inbox/email/` — filename `<date>-<slug-subject>.md`, never overwrites (UUID suffix), never escapes the vault (the only variable path part, business entity, is slugified), marks draft `saved`, stores `savedPath`. **No Gmail API/MCP/auth, no email search/read, no Gmail mutation (send/delete/archive/labels), no browser/computer-use, no MCP, no AI, no brain, no tasks/calendar rows.** Email content is **untrusted** (stored + embedded in a widened code fence; never executed/sent to AI/followed as instructions). Proposed task/calendar rows are **informational only** in v0. Proposal Queue now aggregates Raw Inbox + Consolidation + Research + **Email Intake** drafts (source `email-intake`, type `email_summary`, riskLevel medium, draft→pending, saved→applied, action `open_email_intake` → navigates to Email Intake + highlights the exact draft). No apply/save from the queue. Frontend: `EmailIntakePage.tsx` (form + list + edit modal + save-confirm + deep-link highlight), nav `Email Intake` under Intake, route id `email`, api.ts types/functions, ProposalsPage Open-in-Email-Intake. 287/287 backend tests pass (30 new email-intake tests), `npm run build` clean (85 modules).

**Permission Gateway v0:** the backend app-specific permission-gateway shape is real, **deny-by-default**, and **executes nothing**. A new module (`backend/app/permission_gateway.py`) exposes `GET /api/permissions/policies` (18 tool policies across obsidian/gmail/calendar/browser/computer/brain/filesystem; each with `tool/category/riskLevel/status/requiresApproval/executionEnabled/notes`, `executionEnabled` always false) and `POST /api/permissions/evaluate` (classifies one simulated `{tool,args,reason,requestedBy}` request into `{allowed:false, decision, riskLevel, tool, requiresApproval, executionEnabled:false, reason, policyNotes, sanitizedArgsSummary, wouldLog:true}`). Decision logic: MCP/Gmail/calendar-read → `not_wired`; browser/computer-use + `gmail.send` + `calendar.create_event` → `disabled`; unknown tools → `denied`; unknown destructive names (shell.run, filesystem.delete, browser.submit_form, gmail.delete/archive/modify_labels…) → `disabled`; safe available tools (brain.status, filesystem.read_vault…) → `requires_approval` (still not executed — even allowlisted brain is NOT run via the gateway). Args are untrusted: never executed, summarized only, secret-bearing keys (password/token/secret/key/credential/authorization/cookie) redacted, long values truncated, pair count capped. `EXECUTION_ENABLED` is a module constant fixed to False. No tool execution, no MCP/Gmail/browser/computer-use/Google/GitHub/Drive call, no shell, no brain, no vault write, no credentials, no tool log written (`wouldLog` returned but nothing persisted). Frontend: Permission Gateway section added to the Tool Connections page (`src/pages/ToolConnectionsPage.tsx`) — policy table (tool/category/risk/status/approval/execution/notes) + manual evaluator (tool datalist + reason + JSON args textarea → result panel showing decision/risk/allowed=false/execution=off/approval/sanitized args/reason/policy notes). Invalid JSON shows a clear validation error; there is **no Run / Approve-and-execute** button. api.ts: `getPermissionPolicies()`, `evaluateToolRequest()`, types `PermissionPolicy`/`PermissionPolicyResponse`/`ToolRequestEvaluationRequest`/`ToolRequestEvaluationResponse`/`ToolDecision`. 257/257 backend tests pass (26 new permission-gateway tests), `npm run build` clean (84 modules).

**Tool Connections v0:** a new **read-only** Tool Connections / MCP Connections page is real (nav: Control → Tool Connections). A new backend module (`backend/app/tools.py`) exposes `GET /api/tools/status`, returning a static readiness inventory of the privileged tool systems the PRD plans — `obsidian-mcp`, `gmail-mcp`, `google-calendar-api`, `browser-harness`, `computer-use`, `openclaw`, `nemoclaw-openshell`, `github`, `google-drive`, `graphify`. Each item carries `id/name/category/status/enabled/riskLevel/capabilities/allowedNow/blockedNow/requires/lastCheckedAt/lastError/notes` (Pydantic `ToolConnectionStatus` / `ToolConnectionStatusResponse`). Status values are `available|unavailable|not_configured|disabled|planned|error`; **nothing is reported `available`** (no real check runs), so privileged systems are `not_configured`/`planned`/`disabled`. Gmail is shown not connected with all mutations (send/delete/archive/labels) listed as blocked; Obsidian MCP not connected (filesystem adapter + backup-before-write noted); browser/computer-use **disabled** pending NemoClaw/OpenShell; OpenClaw/NemoClaw **planned**. The page (`src/pages/ToolConnectionsPage.tsx`) groups cards by category (Agent Runtime / MCP / Browser-Computer Use / External Services / Developer Tools) with status + risk badges, enabled/disabled, capabilities, allowed-now, blocked-now, requirements, and notes; the only live actions are **Refresh status** and Settings nav, and the per-card Connect/Enable control is clearly disabled and labelled "Not wired yet." This is a **status/config inventory and readiness surface only** — no MCP/Gmail/browser/computer-use/Google/GitHub/Drive calls, no shell, no `brain`, no credentials, no tool execution. 231/231 backend tests pass (15 new tools-status tests), `npm run build` clean (84 modules).

**Proposal Queue source deep-linking:** clicking a Proposal Queue item now opens the correct source page **and highlights the exact related item** (not just the page). Implemented as a navigation/state-restoration handoff only — no new writes, no backend change. A new store field `proposalTarget: { source: 'raw-inbox' | 'chat-consolidation' | 'research'; relatedId } | null` (with `setProposalTarget`) mirrors the existing `agentConvTarget` pattern. `ProposalsPage` sets the target (from each proposal's `relatedId`) before navigating; if `relatedId` is missing it falls back to plain navigation. Each source page (`InboxPage`, `ConsolidatePage`, `ResearchPage`) consumes and clears the target on mount, then once its list has loaded it highlights + scrolls the matching row/card into view and shows an unobtrusive "Opened from Proposal Queue." notice; the highlight fades after ~4s. A missing/deleted target shows a non-blocking notice ("Target proposal was not found. Showing Raw Inbox." / "That draft could not be found. It may have been deleted.") and keeps the page usable. No proposal is approved/routed/skipped/saved by deep-linking, and the Proposal Queue stays read-only. 216/216 backend tests pass (no backend change), `npm run build` clean.

**Research manual v1:** the Research page is now real (was gated). A new backend module (`backend/app/research.py`) lets the user capture research by hand — title, topic, domain, entity, research question, summary, key findings, sources (`{title,url,notes}`), open questions, recommended next actions, raw notes — and create a **draft** (`POST /api/research/drafts`) stored as backend metadata only (`backend/data/research/drafts.json`), **no vault write at create time**. Requires a non-empty title plus at least one of rawNotes/summary/a key finding; domain validated against 8 values; path-traversal markers in title/topic/entity rejected. Drafts list/read/edit (`GET`/`PATCH`; locked = id/createdAt/updatedAt/status/savedPath). **Save to vault** (`POST .../{id}/save`) writes exactly one Markdown note under `raw/research/<slug(topic|title)>/<date>-<slug(title)>.md`, never overwrites (UUID suffix), must stay under `raw/research/` and inside the vault root (traversal rejected), marks the draft `saved`, stores `savedPath`. No AI, no URL fetch, no web search, no `brain`, no tasks/calendar/resume. Pasted notes/sources treated as **untrusted** (stored + raw notes embedded in a widened code fence; URLs never fetched). **Browser/computer-use/web-search automation remains not wired.** Proposal Queue now aggregates Raw Inbox + Consolidation + Research drafts (`research`/`research_note`, draft→pending, saved→applied, action `open_research` → navigates to Research). No apply/save from the queue. 216/216 backend tests pass (31 new research tests), `npm run build` clean.

**Chat/AI Consolidation manual v1:** the Consolidate page is now real (was gated). A new backend module (`backend/app/consolidation.py`) lets the user paste a ChatGPT / Claude / Claude Code / OpenCode transcript and create a **draft** (`POST /api/consolidation/drafts`) stored as backend metadata only (`backend/data/consolidation/drafts.json`) — **no vault write at create time**. Drafts can be listed/read/edited (`GET`/`PATCH`; editable = title/domain/entity/summary/decisions/actionItems/codeOrFilesReferenced; id/createdAt/sourceTool/transcript/status/savedPath locked). **Save to vault** (`POST .../{id}/save`) writes exactly one Markdown summary under `raw/chats/<sourceTool>/<date>-<slug>.md`, never overwrites (UUID suffix on collision), can't escape the vault root, marks the draft `saved`, and stores `savedPath`. No AI call (missing summary → deterministic transcript-preview fallback), no `brain`, no tasks/calendar/resume side effects. The transcript is treated as **untrusted**: only stored + embedded in a widened code fence, never executed or sent to an LLM. **Browser/computer-use capture remains not wired** — v1 is manual paste/import only. Proposal Queue now aggregates Raw Inbox + Consolidation drafts (`chat-consolidation`/`chat_consolidation`, draft→pending, saved→applied, action `open_consolidation` → navigates to Consolidate). No apply/save from the queue. 185/185 backend tests pass (27 new consolidation tests), `npm run build` clean.

**Proposal Queue v1:** the first piece of the generalized proposal/apply spine is real but intentionally minimal. A new **read-only** aggregation layer (`backend/app/proposals.py`) exposes `GET /api/proposals`, normalizing existing Raw Inbox classification proposals into a shared shape (`id`, `source`, `type`, `riskLevel`, `title`, `summary`, `status`, `confidence`, `targetPath`, `createdAt`, `updatedAt`, `relatedId`, `actions[]`, `details{}`). Intake status maps to generalized status (`proposed`/`edited`→`pending`, `approved`→`approved`, `routed`/`archived`→`applied`, `skipped`→`skipped`). A new **Proposal Queue** page (`src/pages/ProposalsPage.tsx`, nav under the same group as Raw Inbox) lists/filters/searches proposals; the only action is **Open in Raw Inbox** (navigates to the existing approve/edit/route workflow). There is **no approve/apply in the queue** — this sprint creates the shared review surface without increasing mutation power. The generalized proposal/apply foundation is **started, not complete**: only Raw Inbox feeds it; Research, Chat/AI Consolidation, Gmail, MCP, and Agent sources will plug into the same `list_normalized_proposals()` later. No new AI or privileged tool behavior exists. Listing is read-only: no intake metadata change, no vault write, no `brain`, no Ollama. 158/158 backend tests pass (15 new proposal-queue tests), `npm run build` clean.

Dashboard Active Work drill-down is complete, plus the first Dashboard write action: **Mark done** quick actions on Backfill and Escalation active-work items. Each opens a confirmation modal, calls the existing backup-before-write status endpoint (`PATCH /api/vault/backfill/{itemId}/status` and `.../escalations/{itemId}/status`) with `done`, reloads the Dashboard summary on success, and shows an inline error on failure. No other Dashboard mutations exist.

Dashboard **Recent AI Work** rows now deep-link into Local Agent: clicking a row opens AgentPage with that conversation selected and its messages loaded (`GET /api/conversations/{id}`). Read-navigation only — no Ollama/chat call, no mutation. The deep-link is an app-state handoff (`agentConvTarget` in the zustand store, mirroring `agentPrefill`) since the app has no URL router; AgentPage consumes it on mount. A missing conversation shows a clear error and keeps the page usable.

**Runtime honesty pass (latest):** the UI no longer presents unimplemented privileged systems as ready. OpenClaw tool bridge, NemoClaw/OpenShell, Browser harness, Computer use, and MCP gateway now display as **Not wired** with neutral styling on the Dashboard runtime panel (under a "Planned — not wired yet" divider) and the Tool Safety page. Backend, Brain CLI, Vault, and Local model remain real backend-derived status. The Tool Safety page now lists the actual enforced controls (brain allowlist, no arbitrary shell, backup-before-write, no Gmail mutations, no Google Calendar API writes, no browser/computer-use). Agent modes are labeled **UI-only** (not enforced yet). *(Both Research and Chat/AI Consolidation have since shipped real manual v1 capture flows — see latest entries above. The browser/computer-use runtimes they ultimately need remain Not wired.)* No backend changes in that pass.

## Real Workflows

| Workflow | What is wired |
|---|---|
| **Dashboard** | `GET /api/dashboard/summary` — aggregated counts, Today's Plan (deterministic), Recent AI Work (deep-links into Local Agent conversation), Active Work drill-down (backfill/escalations/resume/calendar/raw) + Mark-done quick actions |
| **Raw Inbox** | Stage / heuristic classify / AI classify (metadata only) / edit / approve / batch-approve / route to vault / brain sync-raw / archive staged original |
| **Proposal Queue** | Read-only — `GET /api/proposals` normalizes Raw Inbox proposals **+ Consolidation + Research + Email Intake drafts**; filter/search/counts; actions **deep-link to the exact source item** (highlight + scroll on Inbox/Consolidate/Research/Email Intake) — no approve/apply/save in-queue |
| **Chat/AI Consolidation** | Manual paste/import — create/list/edit drafts; Save to vault writes one Markdown summary to `raw/chats/<source>/`. No AI, no brain, no browser/computer-use capture |
| **Research** | Manual capture — create/list/edit drafts; Save to vault writes one Markdown note to `raw/research/<topic>/`. No AI, no URL fetch, no web search, no browser/computer-use |
| **Email Intake** | Manual paste/import — create/list/edit drafts; Save to vault writes one Markdown summary under `raw/quercus/emails/` · `raw/business/<area>/emails/` · `raw/personal/email/` · `raw/inbox/email/`. **No Gmail connection/search/read/mutation**, no AI, no auto tasks/calendar |
| **Tasks** | Read (`ops/task-db.md` or `ops/tasks.md`), status edit, create new row — `GET /PATCH /POST /api/vault/tasks` |
| **Calendar Candidates** | Read / create file / add candidate / edit / approve / export-open manual — `ops/calendar-candidates.md` |
| **Entity creation** | Projects, Courses, Hackathons (brain CLI), Business (filesystem scaffold) |
| **Backfill** | Read / create file / add item / status edit / field edit — `ops/backfill.md` (or read-only fallback `ops/backfill-last-year.md`) |
| **Resume Pipeline** | Read / create file / add item / status edit / field edit / tailoring prompt — `ops/resume-pipeline.md` |
| **Escalation Queue** | Read / create file / add item / status edit / field edit / handoff prompt — `ops/escalation-queue.md` |
| **Tool Connections** | Read-only — `GET /api/tools/status` returns a static readiness inventory of planned tool systems (status/risk/allowed/blocked/requires). No MCP/Gmail/browser/computer-use/Google/GitHub/Drive calls; nothing reported `available`; no Connect/Enable/Test/Auth/Launch action |
| **Permission Gateway** | Classify + safe-local execute — `GET /api/permissions/policies` (19 policies) + `POST /api/permissions/evaluate` classify into denied/requires_approval/not_wired/disabled/allowed. `POST /api/permissions/execute` runs **only** `brain.status`/`brain.raw_status`/`brain.vault_path` via the safe brain wrapper; all else returns a safe non-execution response. Args untrusted (secrets redacted); no shell/arbitrary-brain/privileged execution |
| **Tool Log** | Read-only audit — `GET /api/permissions/logs` (newest first, limit/tool/decision filters). Each request writes a redacted `gateway_eval` entry; safe-local executions add a `gateway_execution` entry (`result` success/failure, exitCode, truncated stdout/stderr previews, durationMs). Backend-local (`backend/data/tool-logs/`, **not** vault; cap 500); raw args/secrets never stored; no clear/delete/replay action |
| **Local Agent** | Ollama streaming chat, conversation history, context window, `GET /api/agent/status`; **Agent modes enforced** — `GET /api/agent/modes` + backend policy gating (Locked/Observe/Computer-Use block; Draft/Assist/Research/Escalation evaluate-only; only Assist offers review handoff; Computer-Use unavailable); **Agent Tool Requests** — `POST /api/agent/tool-request` (+`mode`) + `GET /api/agent/tool-requests` evaluate a proposed tool request via the gateway and log it; **Structured Output** — assistant replies may include an optional `AGENT_STRUCTURED_OUTPUT`/fenced-JSON `tool_requests` block, parsed + (mode-permitting) evaluated on `/api/agent/chat` (+ `structured` SSE on stream). All **evaluate-only, never executes**; agent stays tool-less |
| **Settings / Config** | Vault path + brain.cmd path, env-var/file/default layering |

## Still Not Implemented

- OpenClaw / NemoClaw / OpenShell runtime wiring
- MCP gateway
- Browser harness / computer use / web search (incl. automatic ChatGPT/Claude transcript capture and automated research — Consolidation and Research are manual capture only; no URL fetching)
- Gmail intake
- Google Calendar API writes or automatic import
- Autonomous Claude Code / OpenCode launch (prompt generation only — no process launched)
- Arbitrary shell execution or file modification
- Repo scanning / automatic closeout
- Job application automation

## Safety Constraints

- No Claude Code / OpenCode process launched by Brain UI at any point.
- No shell commands beyond the strict `brain` allowlist.
- Every vault write: re-read → re-parse → conflict check → backup → write.
- `ops/backfill-last-year.md` permanently read-only.
- `POST **/create` endpoints never overwrite existing files.
- Path traversal rejected on all vault operations.
- `extra="forbid"` on all Pydantic create/update request models.
- Dashboard summary endpoint is entirely read-only — no mutations in activeWork building.
- Consolidation: transcript treated as untrusted (stored + fenced only, never executed or sent to AI); creating a draft writes no vault file; saving writes exactly one file under `raw/chats/<source>/`, never overwrites, never escapes the vault; no brain/AI/tasks/calendar/resume side effects.
- Research: pasted notes/sources treated as untrusted (stored + fenced only, URLs never fetched, never sent to AI); creating a draft writes no vault file; saving writes exactly one file under `raw/research/`, never overwrites, never escapes the vault; no web fetch/search/brain/AI/tasks/calendar/resume side effects.

## Next Recommended Sprints

1. **Capture polish** — optional opt-in local-AI summary assist for Consolidation and Research (metadata-style prompt, still preview-before-save, content still untrusted/no fetch).
2. **Open-to-edit on deep-link** — optionally auto-open the edit modal (not just highlight) for an unsaved Consolidation/Research draft arriving from the Proposal Queue, if that proves more useful than highlight-only.
3. **Filtered today view** — Tasks page "Today" filter showing only blocked/overdue/due-today items, matching the Dashboard Today's Plan logic.

## Test Plan

```bash
# Backend (includes 31 new research tests)
python -m pytest backend/tests/ -q
# Expected: 216 passed, 1 warning

# Frontend
npm run build
# Expected: 83 modules, 0 TypeScript errors, built in ~1s

# Python compile check
python -m py_compile backend\app\dashboard.py backend\app\vault.py backend\app\main.py backend\app\models.py
```
