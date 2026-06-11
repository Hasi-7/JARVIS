"""
Tests for update_backfill_item() — Sprint 27.

Each test uses a tmp_path vault so no real vault is touched.
"""

import pytest
from pathlib import Path

from app.vault import (
    create_backfill_file,
    create_backfill_item,
    update_backfill_item,
    update_backfill_status,
    get_backfill,
    _BACKFILL_PRIMARY,
    _BACKFILL_CANDIDATES,
    _BACKFILL_BACKUP_DIR,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_vault(tmp_path: Path) -> str:
    vault = tmp_path / "vault"
    vault.mkdir()
    return str(vault)


def _primary_path(vault: str) -> Path:
    return Path(vault) / _BACKFILL_PRIMARY


def _seed_item(vault: str, item: str = "Old repo", **kwargs) -> dict:
    create_backfill_file(vault)
    return create_backfill_item(vault_path=vault, item=item, **kwargs)


def _seed_and_edit(vault: str, item_id: str, **kwargs) -> dict:
    return update_backfill_item(vault_path=vault, item_id=item_id, **kwargs)


# ── basic edit ────────────────────────────────────────────────────────────────

def test_edit_returns_ok(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="My project", item_type="project")
    result = update_backfill_item(vault_path=vault, item_id="b1", item="Updated project")
    assert result["ok"] is True
    assert result["item"]["item"] == "Updated project"
    assert result["path"] == _BACKFILL_PRIMARY


def test_edit_updates_all_editable_fields(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="Original", item_type="repo", value="low", agent="manual")
    result = update_backfill_item(
        vault_path=vault, item_id="b1",
        item="Renamed",
        item_type="course",
        value="high",
        agent="claude-code",
        path="/new/path",
        notes="Updated notes",
    )
    it = result["item"]
    assert it["item"]  == "Renamed"
    assert it["type"]  == "course"
    assert it["value"] == "high"
    assert it["agent"] == "claude-code"
    assert it["path"]  == "/new/path"
    assert it["notes"] == "Updated notes"


def test_edit_visible_via_get_backfill(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="Before")
    update_backfill_item(vault_path=vault, item_id="b1", item="After", item_type="hackathon")
    data = get_backfill(vault)
    assert len(data["items"]) == 1
    assert data["items"][0]["item"] == "After"
    assert data["items"][0]["type"] == "hackathon"


def test_edit_appears_in_markdown(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="Legacy thing")
    update_backfill_item(vault_path=vault, item_id="b1", item="Modernized thing")
    content = _primary_path(vault).read_text(encoding="utf-8")
    assert "Modernized thing" in content
    assert "Legacy thing" not in content


# ── status preservation ───────────────────────────────────────────────────────

def test_edit_preserves_status(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="Project X", status="triaged")
    result = update_backfill_item(
        vault_path=vault, item_id="b1",
        item="Project X Renamed", item_type="project",
    )
    assert result["item"]["status"] == "triaged"


def test_edit_after_status_update_preserves_new_status(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="Workflow test", status="new")
    update_backfill_status(vault_path=vault, item_id="b1", new_status="done")
    result = update_backfill_item(
        vault_path=vault, item_id="b1",
        item="Workflow test edited", item_type="other",
    )
    assert result["item"]["status"] == "done"


# ── unknown columns preserved ─────────────────────────────────────────────────

def test_edit_preserves_unknown_columns(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    p = Path(vault) / _BACKFILL_PRIMARY
    p.write_text(
        "# Backfill\n\n"
        "| Item | Type | Status | Value | Path | Agent | Notes | CustomCol |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| Old item | repo | new |  |  |  |  | secret-data |\n",
        encoding="utf-8",
    )
    update_backfill_item(vault_path=vault, item_id="b1", item="New item", item_type="project")
    content = p.read_text(encoding="utf-8")
    assert "secret-data" in content
    assert "New item" in content


# ── reject missing / fallback file ───────────────────────────────────────────

def test_edit_rejects_if_no_file(tmp_path):
    vault = _make_vault(tmp_path)
    with pytest.raises(ValueError, match="Create it first"):
        update_backfill_item(vault_path=vault, item_id="b1", item="Test")


def test_edit_rejects_with_fallback_only_message(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    fallback = ops / "backfill-last-year.md"
    fallback.write_text(
        "# Backfill\n\n| Item | Type | Status |\n|---|---|---|\n| Old thing | repo | done |\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Backfill edits require ops/backfill.md"):
        update_backfill_item(vault_path=vault, item_id="b1", item="New")


def test_edit_fallback_file_not_modified(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    fallback = ops / "backfill-last-year.md"
    fallback_content = "# Last Year\n\n| Item | Status |\n|---|---|\n| old | done |\n"
    fallback.write_text(fallback_content, encoding="utf-8")

    create_backfill_file(vault)
    create_backfill_item(vault_path=vault, item="Primary item")
    update_backfill_item(vault_path=vault, item_id="b1", item="Edited item")

    assert fallback.read_text(encoding="utf-8") == fallback_content


# ── reject malformed file ─────────────────────────────────────────────────────

def test_edit_rejects_malformed_file(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    p = Path(vault) / _BACKFILL_PRIMARY
    p.write_text("# Backfill\n\nJust prose, no table.\n", encoding="utf-8")
    original = p.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="Markdown table"):
        update_backfill_item(vault_path=vault, item_id="b1", item="Test")
    assert p.read_text(encoding="utf-8") == original


# ── backup before edit ────────────────────────────────────────────────────────

def test_backup_created_before_edit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.vault._BACKFILL_BACKUP_DIR",
        tmp_path / "backups" / "backfill",
    )
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="To be edited")
    backup_dir = tmp_path / "backups" / "backfill"
    # Clear any backups from seeding
    pre_count = len(list(backup_dir.glob("*.md"))) if backup_dir.exists() else 0
    update_backfill_item(vault_path=vault, item_id="b1", item="Edited")
    post_count = len(list(backup_dir.glob("*.md")))
    assert post_count > pre_count


# ── validation: empty item ────────────────────────────────────────────────────

def test_empty_item_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="item is required"):
        update_backfill_item(vault_path=vault, item_id="b1", item="")


def test_whitespace_item_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="item is required"):
        update_backfill_item(vault_path=vault, item_id="b1", item="   ")


# ── validation: invalid enums ─────────────────────────────────────────────────

def test_invalid_type_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="Invalid type"):
        update_backfill_item(vault_path=vault, item_id="b1", item="X", item_type="unknown")


def test_invalid_value_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="Invalid value"):
        update_backfill_item(vault_path=vault, item_id="b1", item="X", value="urgent")


def test_invalid_agent_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="Invalid agent"):
        update_backfill_item(vault_path=vault, item_id="b1", item="X", agent="gpt")


def test_invalid_item_id_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="Invalid item id"):
        update_backfill_item(vault_path=vault, item_id="x99", item="X")


# ── validation: raw newlines ──────────────────────────────────────────────────

def test_newline_in_item_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="newlines"):
        update_backfill_item(vault_path=vault, item_id="b1", item="Bad\nitem")


def test_newline_in_path_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="newlines"):
        update_backfill_item(vault_path=vault, item_id="b1", item="Good", path="/bad\npath")


def test_newline_in_notes_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="newlines"):
        update_backfill_item(vault_path=vault, item_id="b1", item="Good", notes="multi\r\nline")


# ── pipe sanitization ─────────────────────────────────────────────────────────

def test_pipe_in_item_sanitized(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    update_backfill_item(vault_path=vault, item_id="b1", item="Repo | Legacy")
    content = _primary_path(vault).read_text(encoding="utf-8")
    assert "Repo ∣ Legacy" in content


def test_pipe_in_notes_sanitized(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    update_backfill_item(vault_path=vault, item_id="b1", item="Repo", notes="a | b")
    content = _primary_path(vault).read_text(encoding="utf-8")
    assert "a ∣ b" in content


# ── out of range ──────────────────────────────────────────────────────────────

def test_out_of_range_item_id_rejected(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, item="Only item")
    with pytest.raises(ValueError, match="not found"):
        update_backfill_item(vault_path=vault, item_id="b99", item="Ghost")


# ── does not modify other rows ────────────────────────────────────────────────

def test_edit_does_not_modify_other_rows(tmp_path):
    vault = _make_vault(tmp_path)
    create_backfill_file(vault)
    create_backfill_item(vault_path=vault, item="Item A", item_type="repo")
    create_backfill_item(vault_path=vault, item="Item B", item_type="project")
    create_backfill_item(vault_path=vault, item="Item C", item_type="course")

    update_backfill_item(vault_path=vault, item_id="b2", item="Item B edited")

    data = get_backfill(vault)
    items = data["items"]
    assert len(items) == 3
    assert items[0]["item"] == "Item A"
    assert items[1]["item"] == "Item B edited"
    assert items[2]["item"] == "Item C"
