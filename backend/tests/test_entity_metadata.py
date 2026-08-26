"""Entity frontmatter writes (PRD §35.1 Work Item).

The load-bearing test here is the lost-update guard. Every other vault writer in
this app targets ops/*.md tables the user rarely edits mid-session; these are
wiki notes the user has open in Obsidian, and Obsidian autosaves. Without a
precondition the failure mode is silent: read note -> user types in Obsidian ->
write back stale content -> their paragraph is gone.
"""

import time
from pathlib import Path

import pytest

from app import vault
from app.vault import (
    EntityVersionConflict,
    ALLOWED_ENTITY_DOMAINS,
    ALLOWED_BACKFILL_TYPES,
    get_projects,
    update_entity_metadata,
)
from app.vault_paths import precondition_token


@pytest.fixture
def note(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, "_ENTITY_BACKUP_DIR", tmp_path / "backups" / "entities")
    (tmp_path / "wiki" / "projects").mkdir(parents=True)
    (tmp_path / "raw" / "projects").mkdir(parents=True)
    path = tmp_path / "wiki" / "projects" / "Brain UI.md"
    path.write_text("# Brain UI\n\nOriginal prose the user wrote.\n", encoding="utf-8")
    return tmp_path, path


def _update(root, **kw):
    args = {"status": None, "domain": None, "repo_path": None,
            "github_url": None, "demo_url": None}
    args.update(kw)
    args = {k: v for k, v in args.items() if v is not None}
    return update_entity_metadata(
        str(root), "project", "wiki/projects/Brain UI.md", args,
        expected_version=kw.pop("expected_version", None),
    )


# ── the enum stays in lockstep ────────────────────────────────────────────────

def test_entity_domains_match_backfill_types():
    """Spelled out separately only because of module ordering; they must agree."""
    assert ALLOWED_ENTITY_DOMAINS == ALLOWED_BACKFILL_TYPES


# ── happy path ────────────────────────────────────────────────────────────────

def test_writes_frontmatter_without_touching_the_body(note):
    root, path = note
    result = update_entity_metadata(
        str(root), "project", "wiki/projects/Brain UI.md",
        {"status": "active", "repo_path": "D:/dev/JARVIS"},
    )
    assert result["ok"] is True and result["changed"] is True
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "Original prose the user wrote." in text

    projects = {p["name"]: p for p in get_projects(str(root))}
    assert projects["Brain UI"]["status"] == "active"
    assert projects["Brain UI"]["repoPath"] == "D:/dev/JARVIS"
    # The preview must show prose, not the YAML we just added.
    assert not projects["Brain UI"]["preview"].startswith("---")


def test_a_backup_is_written_before_the_change(note, tmp_path):
    root, _ = note
    _update(root, status="active")
    backups = list((tmp_path / "backups" / "entities").glob("*.md"))
    assert len(backups) == 1
    assert "Original prose" in backups[0].read_text(encoding="utf-8")
    assert "---" not in backups[0].read_text(encoding="utf-8").split("\n")[0]


def test_a_no_op_write_reports_unchanged_and_makes_no_backup(note, tmp_path):
    root, _ = note
    _update(root, status="active")
    before = len(list((tmp_path / "backups" / "entities").glob("*.md")))
    result = _update(root, status="active")
    assert result["changed"] is False
    assert len(list((tmp_path / "backups" / "entities").glob("*.md"))) == before


# ── the lost-update guard ─────────────────────────────────────────────────────

def test_refuses_when_the_note_changed_since_it_was_read(note):
    """This is the Obsidian-autosave case."""
    root, path = note
    stale = precondition_token(path)

    time.sleep(0.01)
    path.write_text(
        "# Brain UI\n\nOriginal prose the user wrote.\n\nA paragraph typed in Obsidian.\n",
        encoding="utf-8",
    )

    with pytest.raises(EntityVersionConflict, match="changed on disk"):
        update_entity_metadata(
            str(root), "project", "wiki/projects/Brain UI.md",
            {"status": "active"}, expected_version=stale,
        )
    # And their paragraph is still there.
    assert "A paragraph typed in Obsidian." in path.read_text(encoding="utf-8")


def test_a_current_version_is_accepted(note):
    root, path = note
    result = update_entity_metadata(
        str(root), "project", "wiki/projects/Brain UI.md",
        {"status": "active"}, expected_version=precondition_token(path),
    )
    assert result["changed"] is True


def test_the_returned_version_can_be_used_for_the_next_write(note):
    root, _ = note
    first = _update(root, status="active")
    second = update_entity_metadata(
        str(root), "project", "wiki/projects/Brain UI.md",
        {"status": "archived"}, expected_version=first["version"],
    )
    assert second["changed"] is True


# ── validation ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["deleted", "in-flight", "ACTIVE-ish", "done"])
def test_rejects_unknown_statuses(note, bad):
    root, _ = note
    with pytest.raises(ValueError, match="Invalid status"):
        _update(root, status=bad)


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "file:///etc/passwd", "ftp://x", "example.com"])
def test_rejects_non_http_links(note, bad):
    root, _ = note
    with pytest.raises(ValueError, match="http"):
        _update(root, github_url=bad)


@pytest.mark.parametrize("rel", [
    "../../../etc/passwd.md",
    "wiki/projects/../../secrets.md",
    "ops/task-db.md",
    "wiki/courses/Other.md",     # right vault, wrong folder for this entity type
])
def test_rejects_notes_outside_the_entity_folder(note, rel):
    root, _ = note
    with pytest.raises(ValueError):
        update_entity_metadata(str(root), "project", rel, {"status": "active"})


def test_rejects_an_unknown_entity_type(note):
    root, _ = note
    with pytest.raises(ValueError, match="Unknown entity type"):
        update_entity_metadata(str(root), "spaceship", "wiki/projects/Brain UI.md",
                               {"status": "active"})


def test_rejects_a_missing_note(note):
    root, _ = note
    with pytest.raises(ValueError, match="not found"):
        update_entity_metadata(str(root), "project", "wiki/projects/Nope.md",
                               {"status": "active"})


def test_rejects_an_empty_update(note):
    root, _ = note
    with pytest.raises(ValueError, match="No editable fields"):
        update_entity_metadata(str(root), "project", "wiki/projects/Brain UI.md", {})


def test_refuses_to_touch_a_note_with_broken_frontmatter(note):
    """Rewriting YAML we could not parse risks destroying hand-typed data."""
    root, path = note
    path.write_text("---\nkey: [unclosed\n---\n\n# Brain UI\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Refusing to rewrite"):
        _update(root, status="active")


def test_a_broken_note_degrades_only_its_own_card(note):
    """One unparseable note must not fail the projects endpoint."""
    root, _ = note
    (root / "wiki" / "projects" / "Broken.md").write_text(
        "---\nkey: [unclosed\n---\n\n# Broken\n", encoding="utf-8")
    projects = {p["name"]: p for p in get_projects(str(root))}
    assert projects["Broken"]["frontmatterError"]
    assert projects["Brain UI"]["frontmatterError"] is None


def test_the_write_is_atomic(note, monkeypatch):
    """A crash mid-write must leave the note old, never truncated."""
    root, path = note
    original = path.read_text(encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(vault, "write_text_atomic", boom)
    with pytest.raises(OSError):
        _update(root, status="active")
    assert path.read_text(encoding="utf-8") == original


# ── PRD §34.1 brain allowlist ─────────────────────────────────────────────────

def test_allowlist_covers_every_command_the_prd_names():
    """§34.1 lists these as allowed; five were missing, which is what blocked
    §20's closeout/scaffold actions and §21's archive."""
    from app.security import ALLOWED_COMMANDS
    for command in (
        "status", "today", "weekly", "raw-status", "sync-raw",
        "calendar-export", "calendar-open", "new-project", "project-closeout",
        "new-repo-scaffold", "new-hackathon", "archive-hackathon", "new-course",
        "vault-path", "backup", "lint",
    ):
        assert command in ALLOWED_COMMANDS, f"PRD §34.1 names {command!r} but it is not allowed"


def test_allowlist_contains_no_command_the_cli_lacks():
    """An allowlist entry for a nonexistent command fails confusingly at runtime
    and overstates what this app can do. Pinned against the real CLI's parser."""
    from app.security import ALLOWED_COMMANDS
    real_cli_commands = {
        "add-resume-row", "add-task", "archive-hackathon", "backup",
        "calendar-export", "calendar-open", "closeout", "doctor",
        "graphify-setup", "ingest", "lint", "mark-ingested", "new-course",
        "new-hackathon", "new-project", "new-repo-scaffold", "open",
        "project-closeout", "raw-status", "schedule-candidates", "setup-future",
        "status", "sync-raw", "today", "vault-path", "weekly",
    }
    unknown = ALLOWED_COMMANDS - real_cli_commands
    assert unknown == set(), f"allowlisted but not implemented by the CLI: {sorted(unknown)}"


def test_commands_taking_a_name_declare_an_arg_schema():
    from app.brain import _ARG_SCHEMAS, _REQUIRED_ARGS, supports_args
    for command in ("project-closeout", "new-repo-scaffold", "archive-hackathon"):
        assert supports_args(command), command
        assert command in _ARG_SCHEMAS and command in _REQUIRED_ARGS, command
    # Commands that take no arguments must not silently accept them.
    for command in ("status", "today", "backup", "lint"):
        assert not supports_args(command), command
