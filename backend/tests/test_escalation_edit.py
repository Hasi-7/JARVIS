"""
Tests for update_escalation_item() — Sprint 25.

Each test uses a tmp_path vault so no real vault is touched.
"""

import pytest
from pathlib import Path

from app.escalations import (
    add_escalation_item,
    create_escalation_queue_file,
    get_escalations,
    update_escalation_item,
    update_escalation_status,
    _BACKUP_DIR,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_vault(tmp_path: Path) -> str:
    vault = tmp_path / "vault"
    vault.mkdir()
    return str(vault)


def _seeded_vault(tmp_path: Path) -> tuple[str, str]:
    """Return (vault_path, item_id) after adding one item."""
    vault = _make_vault(tmp_path)
    create_escalation_queue_file(vault)
    result = add_escalation_item(
        vault_path=vault,
        task="Fix the login bug",
        target="claude-code",
        priority="high",
        source="brain-ui",
        path="src/auth.ts",
        notes="Reported by QA",
    )
    return vault, result["items"][0]["id"]


# ── basic edit ────────────────────────────────────────────────────────────────

def test_edit_returns_ok(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    result = update_escalation_item(
        vault_path=vault,
        item_id=item_id,
        task="Fix the login bug — revised",
        target="opencode",
    )
    assert result["ok"] is True
    assert result["item"]["task"] == "Fix the login bug — revised"
    assert result["item"]["target"] == "opencode"


def test_edit_preserves_status(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    # First bump status to 'ready'
    update_escalation_status(vault, item_id, "ready")
    # Now edit the fields
    result = update_escalation_item(
        vault_path=vault,
        item_id=item_id,
        task="New task title",
        target="manual",
    )
    assert result["item"]["status"] == "ready"


def test_edit_preserves_created(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    original_created = get_escalations(vault)["items"][0]["created"]
    result = update_escalation_item(
        vault_path=vault,
        item_id=item_id,
        task="Different task",
        target="claude-code",
    )
    assert result["item"]["created"] == original_created


def test_edit_clears_optional_fields_when_omitted(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    result = update_escalation_item(
        vault_path=vault,
        item_id=item_id,
        task="Simplified task",
        target="manual",
        # priority, source, path, notes intentionally omitted
    )
    assert result["item"]["priority"] is None
    assert result["item"]["source"]   is None
    assert result["item"]["path"]     is None
    assert result["item"]["notes"]    is None


def test_edit_updates_all_editable_fields(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    result = update_escalation_item(
        vault_path=vault,
        item_id=item_id,
        task="Updated task",
        target="opencode",
        priority="low",
        source="new-source",
        path="backend/app/new.py",
        notes="Updated notes",
    )
    item = result["item"]
    assert item["task"]     == "Updated task"
    assert item["target"]   == "opencode"
    assert item["priority"] == "low"
    assert item["source"]   == "new-source"
    assert item["path"]     == "backend/app/new.py"
    assert item["notes"]    == "Updated notes"


# ── validation ────────────────────────────────────────────────────────────────

def test_invalid_target_rejected(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    with pytest.raises(ValueError, match="Invalid target"):
        update_escalation_item(
            vault_path=vault,
            item_id=item_id,
            task="Some task",
            target="github-copilot",
        )


def test_invalid_priority_rejected(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    with pytest.raises(ValueError, match="Invalid priority"):
        update_escalation_item(
            vault_path=vault,
            item_id=item_id,
            task="Some task",
            target="manual",
            priority="critical",
        )


def test_empty_task_rejected(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    with pytest.raises(ValueError, match="task is required"):
        update_escalation_item(
            vault_path=vault,
            item_id=item_id,
            task="   ",
            target="manual",
        )


def test_newline_in_task_rejected(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    with pytest.raises(ValueError, match="newline"):
        update_escalation_item(
            vault_path=vault,
            item_id=item_id,
            task="Task\nwith newline",
            target="manual",
        )


def test_invalid_item_id_rejected(tmp_path):
    vault, _ = _seeded_vault(tmp_path)
    with pytest.raises(ValueError, match="Invalid item id"):
        update_escalation_item(
            vault_path=vault,
            item_id="x99",
            task="Some task",
            target="manual",
        )


def test_out_of_range_item_id_rejected(tmp_path):
    vault, _ = _seeded_vault(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        update_escalation_item(
            vault_path=vault,
            item_id="e99",
            task="Some task",
            target="manual",
        )


# ── backup behavior ───────────────────────────────────────────────────────────

def test_backup_created_before_edit(tmp_path, monkeypatch):
    """A backup file is created in _BACKUP_DIR before the write."""
    vault, item_id = _seeded_vault(tmp_path)

    backup_dir = tmp_path / "bak"
    backup_dir.mkdir()
    monkeypatch.setattr("app.escalations._BACKUP_DIR", backup_dir)

    assert list(backup_dir.iterdir()) == []
    update_escalation_item(
        vault_path=vault,
        item_id=item_id,
        task="Backed-up task",
        target="manual",
    )
    backups = list(backup_dir.iterdir())
    assert len(backups) == 1
    assert backups[0].suffix == ".md"


# ── file integrity ────────────────────────────────────────────────────────────

def test_edit_does_not_modify_other_rows(tmp_path):
    """Adding a second item and editing the first must not corrupt the second."""
    vault, item_id = _seeded_vault(tmp_path)
    add_escalation_item(
        vault_path=vault,
        task="Second task",
        target="opencode",
    )

    update_escalation_item(
        vault_path=vault,
        item_id=item_id,
        task="First task — edited",
        target="claude-code",
    )

    items = get_escalations(vault)["items"]
    assert len(items) == 2
    assert items[0]["task"] == "First task — edited"
    assert items[1]["task"] == "Second task"


def test_pipe_char_sanitized_in_task(tmp_path):
    vault, item_id = _seeded_vault(tmp_path)
    result = update_escalation_item(
        vault_path=vault,
        item_id=item_id,
        task="Task | with pipe",
        target="manual",
    )
    assert "|" not in result["item"]["task"]
    assert "∣" in result["item"]["task"]
