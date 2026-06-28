# Session Summary: Email Intake manual v0 (paste/import only)

Date: 2026-06-24
Tool: Claude Code
Project: Brain UI (JARVIS)

---

## Goal

Implement the PRD's **manual fallback** for Gmail/email intake (§33) while Gmail stays disconnected. The user pastes raw email content, reviews/edits extracted fields, and explicitly saves one Markdown summary into the vault. **No Gmail integration** of any kind in this sprint.

```text
paste email content → create structured draft → review/edit fields → Save to vault → one Markdown file under an allowed raw email path
```

This follows the exact pattern of Chat/AI Consolidation v1 and Research v1.

---

## Backend files changed

| File | Role |
|---|---|
| `backend/app/email_intake.py` | **New.** Draft CRUD + save-to-vault with destination rules + `normalized_proposals()`. Storage at `backend/data/email-intake/drafts.json`. |
| `backend/app/models.py` | **New models** `EmailIntakeDraftResponse`, `EmailIntakeDraftsResponse`, `CreateEmailIntakeDraftRequest` (`extra="forbid"`), `UpdateEmailIntakeDraftRequest` (`extra="forbid"`), `SaveEmailIntakeDraftResponse`. |
| `backend/app/main.py` | **New endpoints** POST/GET `/api/email-intake/drafts`, GET/PATCH `/api/email-intake/drafts/{id}`, POST `/api/email-intake/drafts/{id}/save`. |
| `backend/app/proposals.py` | Aggregate `email_intake.normalized_proposals()` into the Proposal Queue (independent, error-isolated source). |
| `backend/tests/test_email_intake.py` | **New.** 30 tests. |

### Draft lifecycle

- **Create** (`POST`): requires non-empty `subject` + `rawEmail`; validates `domain` (`course|business|personal|unknown`) and `confidence` (`High|Medium|Low`); missing summary → deterministic fallback (subject + body preview, **no AI**). Stores backend JSON only — **no vault write**.
- **List/Get** (`GET`): newest first / by id.
- **Update** (`PATCH`): editable = `subject/sender/receivedAt/domain/entity/summary/actionRequired/dueDate/confidence/proposedTaskRows/proposedCalendarRows`. Locked = `id/createdAt/updatedAt/status/savedPath/rawEmail`. Re-derives `proposedDestination` while unsaved.
- **Save** (`POST .../save`): writes one Markdown file, marks `saved`, stores `savedPath`.

### Vault save behavior

Destination by domain/entity:

| Domain (+entity) | Path |
|---|---|
| `course` (±entity) | `raw/quercus/emails/` |
| `business` + entity | `raw/business/<slug-entity>/emails/` |
| `business` no entity | `raw/business/unknown/emails/` |
| `personal` | `raw/personal/email/` |
| `unknown` | `raw/inbox/email/` |

Filename `<date>-<slug-subject>.md`. Never overwrites (UUID suffix on collision). Resolved dir + file are both verified to stay under the vault root; the only variable path component (business entity) is slugified, so traversal is impossible. Email body is embedded in a widened fenced code block.

### Proposal Queue integration

Unsaved drafts → `email-intake` / `email_summary` proposals (riskLevel `medium`, status `pending`); saved → `applied`. Action `open_email_intake`. Read-only — no apply/save from the queue.

---

## Frontend files changed

| File | Role |
|---|---|
| `src/lib/api.ts` | Types `EmailIntakeDomain`, `EmailIntakeStatus`, `EmailConfidence`, `EmailIntakeDraft`, `CreateEmailIntakeDraftRequest`, `UpdateEmailIntakeDraftRequest`, `SaveEmailIntakeDraftResponse`; functions `createEmailIntakeDraft`, `listEmailIntakeDrafts`, `getEmailIntakeDraft`, `updateEmailIntakeDraft`, `saveEmailIntakeDraft`. Extended proposal unions with `email-intake` / `email_summary` / `open_email_intake`. |
| `src/pages/EmailIntakePage.tsx` | **New.** Gmail-not-wired banner, new-draft form, draft list with cards, edit modal (raw email locked), save-to-vault confirmation, Proposal-Queue deep-link highlight, safety notice. |
| `src/App.tsx`, `src/types/index.ts`, `src/data/mock.ts` | Route `email` + nav item under Intake. |
| `src/store/useAppStore.ts` | `ProposalTargetSource` += `email-intake`. |
| `src/pages/ProposalsPage.tsx` | **Open in Email Intake** action + deep-link navigation. |

---

## Safety constraints (this sprint)

- No Gmail API/MCP/auth, no email search/read, **no Gmail mutation** (send/delete/archive/labels), no browser/computer-use, no MCP, no AI, no `brain`.
- Email content treated as **untrusted**: stored + fenced only; never executed, sent to an LLM, or followed as instructions.
- Create writes no vault file; save writes exactly one file under an allowlisted raw email path, never overwrites, never escapes the vault, and **never creates tasks/calendar rows**. Proposed task/calendar rows are informational only in v0.
- Proposal Queue stays read-only (navigate-only).

---

## Tests run

- `python -m pytest backend/tests` → **287 passed** (30 new): create/validation, destination mapping (all 6 cases), list/get, editable-field update + locked-field protection + redirect-on-edit, save under allowed paths, no-overwrite, save-twice rejected, traversal entity stays in vault, untrusted-email fenced, proposal aggregation (pending/applied) + read-only.
- `npm run build` → clean, **85 modules**.

---

## What remains not implemented

Gmail MCP/API/auth, email search/read, Gmail send/delete/archive/labels, email forwarding, AI summarization, automatic task/calendar/resume rows, Proposal Queue apply/save, browser/computer-use, MCP, OpenClaw/NemoClaw runtime, tool logs, Google Calendar API, `brain sync-raw`. Local Agent remains tool-less.

---

## Recommended next sprint

1. **Quercus/Canvas course-email quick template** — a one-click "course notification" preset on the Email Intake form (course domain + entity picker from existing vault courses) to speed the most common manual path, still paste-only and no Gmail.
2. **Optional opt-in local-AI summary assist** (shared with Consolidation/Research) — a preview-before-save local summarization that keeps email content untrusted and never auto-creates tasks/calendar.
