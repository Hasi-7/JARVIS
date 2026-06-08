ALLOWED_COMMANDS: frozenset[str] = frozenset({
    "doctor",
    "status",
    "vault-path",
    "today",
    "weekly",
    "raw-status",
    "sync-raw",
    "calendar-export",
    "calendar-open",
    "new-project",
    "new-course",
    "new-hackathon",
})


def is_allowed(command: str) -> bool:
    return command in ALLOWED_COMMANDS
