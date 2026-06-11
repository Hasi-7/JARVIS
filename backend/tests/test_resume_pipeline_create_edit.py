"""
Tests for create_resume_pipeline_file(), create_resume_pipeline_item(),
and update_resume_pipeline_item() — Sprint 3.

Each test uses a tmp_path vault so no real vault is touched.
"""

import pytest
from pathlib import Path

from app.vault import (
    create_resume_pipeline_file,
    create_resume_pipeline_item,
    get_resume_pipeline,
    update_resume_pipeline_item,
    update_resume_pipeline_status,
    _RESUME_FILE,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_vault(tmp_path: Path) -> str:
    vault = tmp_path / "vault"
    vault.mkdir()
    return str(vault)


def _rp_path(vault: str) -> Path:
    return Path(vault) / _RESUME_FILE


def _seed_file(vault: str) -> dict:
    return create_resume_pipeline_file(vault)


def _seed_item(vault: str, target: str = "Senior SWE", **kwargs) -> dict:
    _seed_file(vault)
    return create_resume_pipeline_item(vault_path=vault, target=target, **kwargs)


# ── create_resume_pipeline_file ───────────────────────────────────────────────

def test_create_file_returns_ok(tmp_path):
    vault = _make_vault(tmp_path)
    result = create_resume_pipeline_file(vault)
    assert result["exists"] is True
    assert result["parseMode"] == "markdown-table"


def test_create_file_writes_table_header(tmp_path):
    vault = _make_vault(tmp_path)
    create_resume_pipeline_file(vault)
    content = _rp_path(vault).read_text(encoding="utf-8")
    assert "| Target |" in content
    assert "| Status |" in content


def test_create_file_does_not_overwrite_existing(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    rp = _rp_path(vault)
    original = "# Custom file\n\n| Target | Status |\n|---|---|\n| Existing | new |\n"
    rp.write_text(original, encoding="utf-8")
    create_resume_pipeline_file(vault)
    assert rp.read_text(encoding="utf-8") == original


def test_create_file_idempotent_returns_existing_items(tmp_path):
    vault = _make_vault(tmp_path)
    create_resume_pipeline_file(vault)
    create_resume_pipeline_item(vault_path=vault, target="Item A")
    result = create_resume_pipeline_file(vault)
    assert len(result["items"]) == 1
    assert result["items"][0]["target"] == "Item A"


def test_create_file_creates_ops_dir(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    assert not ops.exists()
    create_resume_pipeline_file(vault)
    assert ops.is_dir()


# ── create_resume_pipeline_item ───────────────────────────────────────────────

def test_create_item_returns_ok(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    result = create_resume_pipeline_item(vault_path=vault, target="SWE Intern")
    assert result["ok"] is True
    assert result["item"]["target"] == "SWE Intern"
    assert result["path"] == _RESUME_FILE


def test_create_item_defaults_status_to_new(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    result = create_resume_pipeline_item(vault_path=vault, target="Test target")
    assert result["item"]["status"] == "new"


def test_create_item_all_fields(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    result = create_resume_pipeline_item(
        vault_path=vault,
        target="Frontend SWE",
        company="Acme Corp",
        role="Software Engineer",
        status="tailoring",
        priority="high",
        deadline="2026-09-01",
        link="https://acme.com/careers",
        notes="Apply via portal",
    )
    it = result["item"]
    assert it["target"]   == "Frontend SWE"
    assert it["company"]  == "Acme Corp"
    assert it["role"]     == "Software Engineer"
    assert it["status"]   == "tailoring"
    assert it["priority"] == "high"
    assert it["deadline"] == "2026-09-01"
    assert it["link"]     == "https://acme.com/careers"
    assert it["notes"]    == "Apply via portal"


def test_create_item_visible_via_get(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    create_resume_pipeline_item(vault_path=vault, target="FAANG Intern")
    data = get_resume_pipeline(vault)
    assert len(data["items"]) == 1
    assert data["items"][0]["target"] == "FAANG Intern"


def test_create_item_sequential_ids(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    r1 = create_resume_pipeline_item(vault_path=vault, target="Job A")
    r2 = create_resume_pipeline_item(vault_path=vault, target="Job B")
    r3 = create_resume_pipeline_item(vault_path=vault, target="Job C")
    assert r1["item"]["id"] == "r1"
    assert r2["item"]["id"] == "r2"
    assert r3["item"]["id"] == "r3"


def test_create_item_appends_to_existing_rows(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    create_resume_pipeline_item(vault_path=vault, target="Existing")
    create_resume_pipeline_item(vault_path=vault, target="Appended")
    data = get_resume_pipeline(vault)
    assert len(data["items"]) == 2
    assert data["items"][0]["target"] == "Existing"
    assert data["items"][1]["target"] == "Appended"


def test_create_item_rejects_empty_target(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="target is required"):
        create_resume_pipeline_item(vault_path=vault, target="")


def test_create_item_rejects_whitespace_target(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="target is required"):
        create_resume_pipeline_item(vault_path=vault, target="   ")


def test_create_item_rejects_newline_in_target(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="newlines"):
        create_resume_pipeline_item(vault_path=vault, target="Bad\ntarget")


def test_create_item_rejects_newline_in_notes(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="newlines"):
        create_resume_pipeline_item(vault_path=vault, target="Good", notes="bad\nnotes")


def test_create_item_rejects_invalid_status(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="Invalid status"):
        create_resume_pipeline_item(vault_path=vault, target="Good", status="unknown")


def test_create_item_rejects_invalid_priority(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    with pytest.raises(ValueError, match="Invalid priority"):
        create_resume_pipeline_item(vault_path=vault, target="Good", priority="urgent")


def test_create_item_rejects_missing_file(tmp_path):
    vault = _make_vault(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        create_resume_pipeline_item(vault_path=vault, target="Good")


def test_create_item_rejects_malformed_file(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    _rp_path(vault).write_text("# No table here\n\nJust prose.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Markdown table"):
        create_resume_pipeline_item(vault_path=vault, target="Good")


def test_create_item_pipe_sanitized(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    create_resume_pipeline_item(vault_path=vault, target="Acme | Corp Role")
    content = _rp_path(vault).read_text(encoding="utf-8")
    assert "Acme ∣ Corp Role" in content


def test_create_item_backup_created(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups" / "resume"
    monkeypatch.setattr("app.vault._RESUME_BACKUP_DIR", backup_dir)
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    pre_count = len(list(backup_dir.glob("*.md"))) if backup_dir.exists() else 0
    create_resume_pipeline_item(vault_path=vault, target="Backed up")
    post_count = len(list(backup_dir.glob("*.md")))
    assert post_count > pre_count


# ── update_resume_pipeline_item ───────────────────────────────────────────────

def test_edit_returns_ok(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, target="Old target")
    result = update_resume_pipeline_item(vault_path=vault, item_id="r1", target="New target")
    assert result["ok"] is True
    assert result["item"]["target"] == "New target"
    assert result["path"] == _RESUME_FILE


def test_edit_updates_all_editable_fields(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, target="Original", company="OldCo", role="Dev")
    result = update_resume_pipeline_item(
        vault_path=vault, item_id="r1",
        target="Renamed",
        company="NewCo",
        role="Senior Dev",
        priority="medium",
        deadline="2027-01-01",
        link="https://example.com",
        notes="Updated notes",
    )
    it = result["item"]
    assert it["target"]   == "Renamed"
    assert it["company"]  == "NewCo"
    assert it["role"]     == "Senior Dev"
    assert it["priority"] == "medium"
    assert it["deadline"] == "2027-01-01"
    assert it["link"]     == "https://example.com"
    assert it["notes"]    == "Updated notes"


def test_edit_visible_via_get(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, target="Before")
    update_resume_pipeline_item(vault_path=vault, item_id="r1", target="After")
    data = get_resume_pipeline(vault)
    assert data["items"][0]["target"] == "After"


def test_edit_preserves_status(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, target="Tracked", status="applied")
    result = update_resume_pipeline_item(
        vault_path=vault, item_id="r1",
        target="Tracked Renamed", company="Acme",
    )
    assert result["item"]["status"] == "applied"


def test_edit_preserves_status_after_status_update(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, target="Track me", status="new")
    update_resume_pipeline_status(vault_path=vault, item_id="r1", new_status="interview")
    result = update_resume_pipeline_item(
        vault_path=vault, item_id="r1",
        target="Track me edited",
    )
    assert result["item"]["status"] == "interview"


def test_edit_preserves_unknown_columns(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    p = _rp_path(vault)
    p.write_text(
        "# Resume\n\n"
        "| Target | Status | CustomField |\n"
        "|---|---|---|\n"
        "| Old target | new | secret-value |\n",
        encoding="utf-8",
    )
    update_resume_pipeline_item(vault_path=vault, item_id="r1", target="New target")
    content = p.read_text(encoding="utf-8")
    assert "secret-value" in content
    assert "New target" in content


def test_edit_does_not_modify_other_rows(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_file(vault)
    create_resume_pipeline_item(vault_path=vault, target="Job A")
    create_resume_pipeline_item(vault_path=vault, target="Job B")
    create_resume_pipeline_item(vault_path=vault, target="Job C")
    update_resume_pipeline_item(vault_path=vault, item_id="r2", target="Job B edited")
    data = get_resume_pipeline(vault)
    items = data["items"]
    assert len(items) == 3
    assert items[0]["target"] == "Job A"
    assert items[1]["target"] == "Job B edited"
    assert items[2]["target"] == "Job C"


def test_edit_rejects_missing_file(tmp_path):
    vault = _make_vault(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        update_resume_pipeline_item(vault_path=vault, item_id="r1", target="Test")


def test_edit_rejects_malformed_file(tmp_path):
    vault = _make_vault(tmp_path)
    ops = Path(vault) / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    p = _rp_path(vault)
    p.write_text("# No table\n\nJust prose.\n", encoding="utf-8")
    original = p.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="Markdown table"):
        update_resume_pipeline_item(vault_path=vault, item_id="r1", target="Test")
    assert p.read_text(encoding="utf-8") == original


def test_edit_backup_created(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups" / "resume"
    monkeypatch.setattr("app.vault._RESUME_BACKUP_DIR", backup_dir)
    vault = _make_vault(tmp_path)
    _seed_item(vault, target="Backup test")
    pre_count = len(list(backup_dir.glob("*.md"))) if backup_dir.exists() else 0
    update_resume_pipeline_item(vault_path=vault, item_id="r1", target="Edited")
    post_count = len(list(backup_dir.glob("*.md")))
    assert post_count > pre_count


def test_edit_rejects_empty_target(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="target is required"):
        update_resume_pipeline_item(vault_path=vault, item_id="r1", target="")


def test_edit_rejects_whitespace_target(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="target is required"):
        update_resume_pipeline_item(vault_path=vault, item_id="r1", target="   ")


def test_edit_rejects_newline_in_target(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="newlines"):
        update_resume_pipeline_item(vault_path=vault, item_id="r1", target="Bad\nline")


def test_edit_rejects_newline_in_notes(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="newlines"):
        update_resume_pipeline_item(vault_path=vault, item_id="r1", target="Good", notes="bad\nnotes")


def test_edit_rejects_invalid_priority(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="Invalid priority"):
        update_resume_pipeline_item(vault_path=vault, item_id="r1", target="Good", priority="critical")


def test_edit_rejects_invalid_item_id(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    with pytest.raises(ValueError, match="Invalid item id"):
        update_resume_pipeline_item(vault_path=vault, item_id="x99", target="Test")


def test_edit_rejects_out_of_range_id(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, target="Only item")
    with pytest.raises(ValueError, match="not found"):
        update_resume_pipeline_item(vault_path=vault, item_id="r99", target="Ghost")


def test_edit_pipe_sanitized(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault)
    update_resume_pipeline_item(vault_path=vault, item_id="r1", target="Acme | Corp")
    content = _rp_path(vault).read_text(encoding="utf-8")
    assert "Acme ∣ Corp" in content


def test_edit_appears_in_markdown(tmp_path):
    vault = _make_vault(tmp_path)
    _seed_item(vault, target="Old title")
    update_resume_pipeline_item(vault_path=vault, item_id="r1", target="New title")
    content = _rp_path(vault).read_text(encoding="utf-8")
    assert "New title" in content
    assert "Old title" not in content
