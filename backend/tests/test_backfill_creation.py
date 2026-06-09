"""
Tests for create_backfill_file() and create_backfill_item() — Sprint 26.

Each test uses a tmp_path vault so no real vault is touched.
"""

import pytest
from pathlib import Path

from app.vault import (
    create_backfill_file,
    create_backfill_item,
    get_backfill,
    _BACKFILL_PRIMARY,
    _BACKFILL_CANDIDATES,
    _BACKFILL_BACKUP_DIR,
    ALLOWED_BACKFILL_STATUSES,
    ALLOWED_BACKFILL_TYPES,
    ALLOWED_BACKFILL_VALUES,
    ALLOWED_BACKFILL_AGENTS,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_vault(tmp_path: Path) -> str:
    vault = tmp_path / "vault"
    vault.mkdir()
    return str(vault)


def _primary_path(vault: str) -> Path:
    return Path(vault) / _BACKFILL_PRIMARY


def _seed_file(vault: str) -> None:
    """Create a valid ops/backfill.md starter file."""
    create_backfill_file(vault)


def _seed_item(vault: str, item: str = "Old repo", **kwargs) -> dict:
    """Ensure file exists and add one item. Returns the create result."""
    _seed_file(vault)
    return create_backfill_item(vault_path=vault, item=item, **kwargs)


# ── starter file creation ─────────────────────────────────────────────────────

def test_create_file_creates_backfill_md(tmp_path):
    vault = _make_vault(tmp_path)
    result = create_backfill_file(vault)
    p = _primary_path(vault)
    assert p.is_file()
    assert result["exists"] is True
    assert result["path"] == _BACKFILL_PRIMARY


def test_create_file_contains_table_header(tmp_path):
    vault = _make_vault(tmp_path)
    create_backfill_file(vault)
    content = _primary_path(vault).read_text(encoding="utf-8")
    assert "| Item |" in content
    assert "|---|" in content


def test_create_file_does_not_overwrite_existing(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    # Write a custom line to existing file
    p = _primary_path(vault)
    original = p.read_text(encoding="utf-8")
    p.write_text(original + "| My item | other | new |  |  |  |  |\n", encoding="utf-8")
    modified = p.read_text(encoding="utf-8")

    # Call again — must not overwrite
    create_backfill_file(vault)
    assert p.read_text(encoding="utf-8") == modified


def test_create_file_returns_backfill_response_shape(tmp_path):
    vault = _make_vault(tmp_path)
    result = create_backfill_file(vault)
    for key in ("path", "exists", "lastModified", "preview", "parseMode", "items"):
        assert key in result


def test_create_file_does_not_create_last_year_file(tmp_path):
    vault = _make_vault(tmp_path)
    create_backfill_file(vault)
    fallback = Path(vault) / _BACKFILL_CANDIDATES[1]
    assert not fallback.exists()


# ── append item ───────────────────────────────────────────────────────────────

def test_append_valid_item_returns_ok(tmp_path):
    vault = _make_vault(tmp_path)
    result = _seed_item(vault, item="Legacy payments repo")
    assert result["ok"] is True
    assert result["item"]["item"] == "Legacy payments repo"
    assert result["path"] == _BACKFILL_PRIMARY


def test_append_item_appears_in_file(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="Old course notes")
    content = _primary_path(vault).read_text(encoding="utf-8")
    assert "Old course notes" in content


def test_append_item_readable_via_get_backfill(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="My hackathon", item_type="hackathon", status="triaged", value="high")
    data = get_backfill(vault)
    assert data["parseMode"] == "markdown-table"
    assert len(data["items"]) == 1
    it = data["items"][0]
    assert it["item"] == "My hackathon"
    assert it["type"] == "hackathon"
    assert it["status"] == "triaged"
    assert it["value"] == "high"


def test_append_multiple_items(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    for i in range(3):
        create_backfill_item(vault_path=vault, item=f"Item {i}")
    data = get_backfill(vault)
    assert len(data["items"]) == 3


def test_append_defaults_status_to_new(tmp_path):
    vault = _make_vault(tmp_path)
    result = _seed_item(vault, item="No status given")
    assert result["item"]["status"] == "new"


def test_append_defaults_type_to_other(tmp_path):
    vault = _make_vault(tmp_path)
    result = _seed_item(vault, item="No type given")
    assert result["item"]["type"] == "other"


def test_append_optional_fields_stored(tmp_path):
    vault = _make_vault(tmp_path)
    result = _seed_item(
        vault,
        item="Repo X",
        item_type="repo",
        value="medium",
        agent="opencode",
        path="/home/user/repo-x",
        notes="Needs review",
    )
    it = result["item"]
    assert it["value"] == "medium"
    assert it["agent"] == "opencode"
    assert it["path"] == "/home/user/repo-x"
    assert it["notes"] == "Needs review"


# ── reject if primary file missing ────────────────────────────────────────────

def test_append_rejects_if_no_file(tmp_path):
    vault = _make_vault(tmp_path)
    with pytest.raises(ValueError, match="Create it first"):
        create_backfill_item(vault_path=vault, item="Test item")


def test_append_rejects_with_fallback_only_message(tmp_path):
    vault = _make_vault(tmp_path)
    # Create only the fallback file
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    fallback = ops / "backfill-last-year.md"
    fallback.write_text(
        "# Backfill\n\n| Item | Type | Status |\n|---|---|---|\n| Old thing | repo | done |\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Create ops/backfill.md before adding"):
        create_backfill_item(vault_path=vault, item="New item")


# ── reject malformed file ─────────────────────────────────────────────────────

def test_append_rejects_malformed_file(tmp_path):
    vault = _make_vault(tmp_path)
    p = _primary_path(vault)
    (Path(vault) / "ops").mkdir(parents=True, exist_ok=True)
    p.write_text("# Backfill\n\nJust some prose, no table.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Markdown table"):
        create_backfill_item(vault_path=vault, item="Test item")


# ── backup before append ──────────────────────────────────────────────────────

def test_backup_created_before_append(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.vault._BACKFILL_BACKUP_DIR",
        tmp_path / "backups" / "backfill",
    )
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    backup_dir = tmp_path / "backups" / "backfill"
    assert not any(backup_dir.glob("*.md")) if not backup_dir.exists() else not any(backup_dir.glob("*.md"))
    create_backfill_item(vault_path=vault, item="First item")
    backups = list(backup_dir.glob("*.md"))
    assert len(backups) >= 1


# ── validation: empty item ────────────────────────────────────────────────────

def test_empty_item_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="item is required"):
        create_backfill_item(vault_path=vault, item="")


def test_whitespace_item_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="item is required"):
        create_backfill_item(vault_path=vault, item="   ")


# ── validation: invalid enum values ──────────────────────────────────────────

def test_invalid_status_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="Invalid status"):
        create_backfill_item(vault_path=vault, item="X", status="pending")


def test_invalid_type_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="Invalid type"):
        create_backfill_item(vault_path=vault, item="X", item_type="unknown-type")


def test_invalid_value_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="Invalid value"):
        create_backfill_item(vault_path=vault, item="X", value="urgent")


def test_invalid_agent_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="Invalid agent"):
        create_backfill_item(vault_path=vault, item="X", agent="gpt")


# ── validation: raw newlines ──────────────────────────────────────────────────

def test_newline_in_item_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="newlines"):
        create_backfill_item(vault_path=vault, item="Bad\nitem")


def test_newline_in_path_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="newlines"):
        create_backfill_item(vault_path=vault, item="Good", path="/bad\npath")


def test_newline_in_notes_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="newlines"):
        create_backfill_item(vault_path=vault, item="Good", notes="note\r\nwith newlines")


# ── pipe sanitization ─────────────────────────────────────────────────────────

def test_pipe_in_item_sanitized(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    result = create_backfill_item(vault_path=vault, item="Repo | Legacy")
    content = _primary_path(vault).read_text(encoding="utf-8")
    # Pipe replaced with Unicode divides character
    assert "Repo ∣ Legacy" in content
    # No raw pipe in the item cell that would break the table
    assert result["ok"] is True


def test_pipe_in_notes_sanitized(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    create_backfill_item(vault_path=vault, item="Repo", notes="see also: a | b")
    content = _primary_path(vault).read_text(encoding="utf-8")
    assert "see also: a ∣ b" in content


# ── no modification of fallback file ─────────────────────────────────────────

def test_fallback_file_not_modified_after_append(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    fallback = ops / "backfill-last-year.md"
    fallback_content = "# Last Year\n\n| Item | Status |\n|---|---|\n| old | done |\n"
    fallback.write_text(fallback_content, encoding="utf-8")

    # Create primary and append
    _seed_file(vault)
    create_backfill_item(vault_path=vault, item="New item")

    # Fallback unchanged
    assert fallback.read_text(encoding="utf-8") == fallback_content
