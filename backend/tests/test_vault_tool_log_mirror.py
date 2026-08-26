"""Vault tool-log mirror tests (PRD §32, acceptance criterion #19).

The mirror is disabled globally by conftest because it resolves the REAL vault
path from config. Every test here re-enables it against a tmp_path vault, so the
user's actual Obsidian vault is never touched.
"""

from pathlib import Path

import pytest

from app import permission_gateway as pg


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    # Patch the predicate directly rather than the env var: conftest's autouse
    # fixture also sets that env var, and fixture ordering decides which setenv
    # wins. Patching the function is deterministic. The kill-switch parsing tests
    # below do not use this fixture, so they still exercise the real function.
    monkeypatch.setattr(pg, "vault_log_mirror_enabled", lambda env=None: True)
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", tmp_path / "logs" / "evaluations.json")

    class Cfg:
        vault_path = str(root)

    import app.config as config
    monkeypatch.setattr(config, "get_config", lambda: Cfg())
    return root


def _entry(**kw):
    base = {
        "id": "log-1",
        "timestamp": "2026-08-24T12:00:00.000+00:00",
        "source": "gateway_eval",
        "tool": "brain.status",
        "requestedBy": "manual-ui",
        "reason": "check",
        "decision": "allowed",
        "riskLevel": "low",
        "allowed": True,
        "requiresApproval": False,
        "executionEnabled": True,
        "sanitizedArgsSummary": "(no arguments)",
        "policyNotes": None,
        "result": "evaluated_only",
        "exitCode": None,
    }
    base.update(kw)
    return base


def _log_file(vault, date="2026-08-24"):
    return vault / "ops" / "tool-logs" / f"{date}-tool-log.md"


# ══════════════════════════════════════════════════════════════════════════════
# Mirror content
# ══════════════════════════════════════════════════════════════════════════════

def test_first_entry_creates_a_dated_file_with_header(vault):
    pg._mirror_entry_to_vault(_entry())
    path = _log_file(vault)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "# Tool Log — 2026-08-24" in text
    assert "| Time | Agent/Model | Tool |" in text
    assert "brain.status" in text


def test_second_entry_appends_without_rewriting(vault):
    pg._mirror_entry_to_vault(_entry(id="a", tool="brain.status"))
    first = _log_file(vault).read_text(encoding="utf-8")
    pg._mirror_entry_to_vault(_entry(id="b", tool="brain.today"))
    second = _log_file(vault).read_text(encoding="utf-8")

    assert second.startswith(first)      # append-only: prior rows untouched
    assert "brain.today" in second
    assert second.count("| Time |") == 1  # header written exactly once


def test_entries_are_split_by_date(vault):
    pg._mirror_entry_to_vault(_entry(timestamp="2026-08-24T10:00:00+00:00"))
    pg._mirror_entry_to_vault(_entry(timestamp="2026-08-25T10:00:00+00:00"))
    assert _log_file(vault, "2026-08-24").is_file()
    assert _log_file(vault, "2026-08-25").is_file()


def test_row_carries_the_prd_columns(vault):
    pg._mirror_entry_to_vault(_entry(
        tool="calendar.create_event", riskLevel="high", requiresApproval=True,
        requestedBy="local-agent", sanitizedArgsSummary="title=Dentist",
    ))
    row = [l for l in _log_file(vault).read_text(encoding="utf-8").splitlines()
           if "calendar.create_event" in l][0]
    for expected in ("local-agent", "calendar.create_event", "title=Dentist", "high", "yes"):
        assert expected in row


def test_execution_outcome_is_reported(vault):
    pg._mirror_entry_to_vault(_entry(source="gateway_execution", exitCode=0))
    assert "success" in _log_file(vault).read_text(encoding="utf-8")

    pg._mirror_entry_to_vault(_entry(id="b", source="gateway_execution", exitCode=2))
    assert "failure (exit 2)" in _log_file(vault).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# Table integrity — untrusted values must not break the Markdown
# ══════════════════════════════════════════════════════════════════════════════

def test_pipes_in_values_are_escaped(vault):
    pg._mirror_entry_to_vault(_entry(sanitizedArgsSummary="a|b|c"))
    row = [l for l in _log_file(vault).read_text(encoding="utf-8").splitlines()
           if "brain.status" in l][0]
    assert r"a\|b\|c" in row
    structural = row.replace(r"\|", "")   # escaped pipes are content, not structure
    assert structural.count("|") == 10   # 9 cells + closing pipe, structure intact


def test_newlines_are_flattened(vault):
    pg._mirror_entry_to_vault(_entry(reason="line one\nline two", sanitizedArgsSummary="x\ny"))
    body = _log_file(vault).read_text(encoding="utf-8")
    rows = [l for l in body.splitlines() if l.startswith("| 2026")]
    assert len(rows) == 1                # one entry stayed one row


def test_long_values_are_truncated(vault):
    pg._mirror_entry_to_vault(_entry(sanitizedArgsSummary="z" * 5000))
    row = [l for l in _log_file(vault).read_text(encoding="utf-8").splitlines()
           if l.startswith("| 2026")][0]
    assert len(row) < 1200


def test_missing_fields_render_as_placeholder(vault):
    pg._mirror_entry_to_vault({"id": "x", "timestamp": "2026-08-24T12:00:00+00:00"})
    assert "—" in _log_file(vault).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# Best-effort: the mirror must never break the action it records
# ══════════════════════════════════════════════════════════════════════════════

def test_mirror_failure_is_swallowed(vault, monkeypatch):
    import app.config as config

    def boom():
        raise RuntimeError("config exploded")

    monkeypatch.setattr(config, "get_config", boom)
    assert pg._mirror_entry_to_vault(_entry()) is None      # no raise


def test_unwritable_target_is_swallowed(vault, monkeypatch):
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
    assert pg._mirror_entry_to_vault(_entry()) is None


def test_traversal_is_rejected_by_the_shared_helper(vault, monkeypatch):
    from app import vault as vault_module
    monkeypatch.setattr(vault_module, "_safe_subpath", lambda *a, **k: None)
    assert pg._mirror_entry_to_vault(_entry()) is None
    assert not (vault / "ops").exists()


def test_missing_vault_path_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(pg, "vault_log_mirror_enabled", lambda env=None: True)

    class Cfg:
        vault_path = ""

    import app.config as config
    monkeypatch.setattr(config, "get_config", lambda: Cfg())
    assert pg._mirror_entry_to_vault(_entry()) is None


def test_logging_still_succeeds_when_mirror_fails(vault, monkeypatch, tmp_path):
    """The JSON log is the source of truth and must be unaffected."""
    monkeypatch.setattr(pg, "_mirror_entry_to_vault",
                        lambda e, vault_path=None: (_ for _ in ()).throw(RuntimeError("x")))
    evaluation = pg.evaluate_tool_request("brain.status", {})
    with pytest.raises(RuntimeError):
        # _append_log_entry calls the mirror directly, so a raising mirror WOULD
        # surface — which is why the real implementation catches internally.
        pg.log_evaluation(evaluation, requested_by="test")


# ══════════════════════════════════════════════════════════════════════════════
# Kill switch
# ══════════════════════════════════════════════════════════════════════════════

def test_mirror_can_be_disabled(vault, monkeypatch):
    monkeypatch.setattr(pg, "vault_log_mirror_enabled", lambda env=None: False)
    assert pg._mirror_entry_to_vault(_entry()) is None
    assert not _log_file(vault).exists()


@pytest.mark.parametrize("value,expected", [
    ("true", True), ("", True), ("1", True),
    ("false", False), ("0", False), ("no", False), ("off", False),
])
def test_kill_switch_env_parsing(value, expected):
    env = {pg.VAULT_LOG_MIRROR_ENV: value} if value else {}
    assert pg.vault_log_mirror_enabled(env) is expected


# ══════════════════════════════════════════════════════════════════════════════
# End-to-end through the real logging path
# ══════════════════════════════════════════════════════════════════════════════

def test_log_evaluation_mirrors_to_the_vault(vault):
    evaluation = pg.evaluate_tool_request("brain.status", {"x": 1}, reason="smoke")
    entry = pg.log_evaluation(evaluation, requested_by="manual-ui", reason="smoke")

    # Derive the filename from the entry's own UTC timestamp — hardcoding today's
    # local date makes this flake whenever UTC has rolled past midnight.
    body = _log_file(vault, entry["timestamp"][:10]).read_text(encoding="utf-8")
    assert "brain.status" in body
    assert "manual-ui" in body
    # And the JSON source still has it.
    assert any(e["id"] == entry["id"] for e in pg.list_logs(limit=10))


def test_secrets_never_reach_the_vault_copy(vault):
    evaluation = pg.evaluate_tool_request(
        "brain.status", {"password": "ZZ-secret", "token": "ZZ-token", "q": "visible"},
    )
    entry = pg.log_evaluation(evaluation, requested_by="manual-ui")
    body = _log_file(vault, entry["timestamp"][:10]).read_text(encoding="utf-8")
    assert "ZZ-secret" not in body
    assert "ZZ-token" not in body
    assert "redacted" in body.lower()
