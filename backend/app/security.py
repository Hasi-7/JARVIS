"""Allowlist of `brain` subcommands the backend may run (PRD §34.1).

Every entry has been verified to exist in the real CLI at
D:\Hasnain\Personal\dev\ai-command-tools\brain.py. An allowlist entry for a
command the CLI does not implement would fail confusingly at runtime and would
overstate what this app can do.

Deliberately absent: `ingest`, `mark-ingested`, `graphify-setup`, `setup-future`,
`schedule-candidates`, `add-task`, `add-resume-row`. The first two mutate raw
sync state the CLI owns; the rest are either superseded by richer in-app flows
(tasks, resume rows and calendar candidates are written through the validated,
backup-before-write vault adapters) or have no UI that needs them.
"""

ALLOWED_COMMANDS: frozenset[str] = frozenset({
    # Read-only status
    "doctor",
    "status",
    "vault-path",
    "raw-status",
    # Planning
    "today",
    "weekly",
    # Raw intake
    "sync-raw",
    # Calendar (.ics export/open only; real Calendar writes go through the
    # approval queue, never through here)
    "calendar-export",
    "calendar-open",
    # Entity scaffolding
    "new-project",
    "new-course",
    "new-hackathon",
    "new-repo-scaffold",
    # Closeout / archive
    "project-closeout",
    "archive-hackathon",
    # Maintenance
    "backup",
    "lint",
})


def is_allowed(command: str) -> bool:
    return command in ALLOWED_COMMANDS
