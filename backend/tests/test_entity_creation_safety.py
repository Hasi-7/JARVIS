from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import brain
from app.entities import BusinessAreaPartialFailure, create_business_area
from app.main import brain_run
from app.models import BrainRunRequest


def _fake_brain_path(tmp_path):
    path = tmp_path / "brain.exe"
    path.write_text("fake", encoding="utf-8")
    return path


def test_unknown_argument_command_is_rejected():
    result = brain.run_brain_command_args("not-real", {})

    assert result.ok is False
    assert "allowlist" in result.stderr


def test_generic_brain_run_rejects_argument_commands():
    with pytest.raises(HTTPException) as exc:
        brain_run(BrainRunRequest(command="new-project"))

    assert exc.value.status_code == 400
    assert "entity-specific" in exc.value.detail


def test_unsafe_argument_characters_rejected():
    result = brain.run_brain_command_args("new-project", {"name": "demo&whoami", "repoPath": None})

    assert result.ok is False
    assert "unsafe shell metacharacters" in result.stderr


def test_empty_required_argument_rejected():
    result = brain.run_brain_command_args("new-course", {"code": " ", "name": None})

    assert result.ok is False
    assert "required" in result.stderr


def test_course_payload_maps_name_to_title_flag(monkeypatch, tmp_path):
    captured = {}
    fake = _fake_brain_path(tmp_path)

    def fake_run(args, shell, capture_output, text, timeout):
        captured.update({
            "args": args,
            "shell": shell,
            "capture_output": capture_output,
            "text": text,
            "timeout": timeout,
        })
        return SimpleNamespace(returncode=0, stdout="created", stderr="")

    monkeypatch.setattr(brain, "get_config", lambda: SimpleNamespace(brain_cmd=str(fake)))
    monkeypatch.setattr(brain.subprocess, "run", fake_run)

    result = brain.run_brain_command_args("new-course", {"code": "esc203", "name": "Engineering Design"})

    assert result.ok is True
    assert captured["shell"] is False
    assert captured["args"] == [str(fake), "new-course", "esc203", "--title", "Engineering Design"]


def test_unsupported_project_repo_path_rejected():
    result = brain.run_brain_command_args("new-project", {"name": "Demo", "repoPath": "D:/repo"})

    assert result.ok is False
    assert "repoPath is not supported" in result.stderr


def test_business_scaffold_creates_expected_files(tmp_path, monkeypatch):
    monkeypatch.setattr("app.entities._BACKUP_DIR", tmp_path / "backups")

    result = create_business_area(str(tmp_path), "UI Test Business", "Pipeline test")

    assert result["ok"] is True
    assert (tmp_path / "raw" / "business" / "ui-test-business").is_dir()
    assert (tmp_path / "wiki" / "business" / "ui-test-business.md").exists()
    pipeline = tmp_path / "ops" / "business-pipeline.md"
    assert pipeline.exists()
    assert "| UI Test Business | Active | Pipeline test |" in pipeline.read_text(encoding="utf-8")


def test_business_duplicate_name_rejected_before_writes(tmp_path):
    create_business_area(str(tmp_path), "Duplicate Business", None)

    with pytest.raises(ValueError, match="already exists"):
        create_business_area(str(tmp_path), "Duplicate Business", None)


def test_business_unsafe_empty_slug_rejected(tmp_path):
    with pytest.raises(ValueError, match="letter or number"):
        create_business_area(str(tmp_path), "../", None)


def test_business_pipeline_backup_created_before_existing_pipeline_update(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr("app.entities._BACKUP_DIR", backup_dir)
    pipeline = tmp_path / "ops" / "business-pipeline.md"
    pipeline.parent.mkdir(parents=True)
    pipeline.write_text("# Business Pipeline\n\n| Name | Status | Description | Created |\n|---|---|---|---|\n", encoding="utf-8")

    create_business_area(str(tmp_path), "Backed Up Business", "Existing pipeline")

    backups = list(backup_dir.glob("business-pipeline_*.md"))
    assert len(backups) == 1
    assert "Backed Up Business" in pipeline.read_text(encoding="utf-8")


def test_business_partial_failure_reports_created_paths(tmp_path, monkeypatch):
    pipeline = tmp_path / "ops" / "business-pipeline.md"
    pipeline.parent.mkdir(parents=True)
    pipeline.write_text("# Business Pipeline\n\n| Name | Status | Description | Created |\n|---|---|---|---|\n", encoding="utf-8")

    def fail_backup(path):
        raise OSError("backup failed")

    monkeypatch.setattr("app.entities._backup_pipeline", fail_backup)

    with pytest.raises(BusinessAreaPartialFailure) as exc:
        create_business_area(str(tmp_path), "Partial Business", "Failure case")

    data = exc.value.data
    assert data["ok"] is False
    assert data["paths"]["wikiPath"] == "wiki/business/partial-business.md"
    assert data["paths"]["rawPath"] == "raw/business/partial-business/"
    assert "partially failed" in data["stderr"]
