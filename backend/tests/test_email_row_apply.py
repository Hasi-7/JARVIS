"""MVP v8: Email Intake proposed rows applied into the vault.

Uses a real temp vault so the shared safe-write adapters actually run. The user's
real vault is never touched.
"""

from pathlib import Path

import pytest

from app import proposals as pr


# ══════════════════════════════════════════════════════════════════════════════
# Row parsing
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("row,expected_due", [
    ("Submit assignment 3 by 2026-09-01", "2026-09-01"),
    ("Pay invoice on 5 Sep 2026", "2026-09-05"),
    ("Renew pass Sep 5, 2026", "2026-09-05"),
    ("Email the professor", ""),
])
def test_task_row_parsing(row, expected_due):
    parsed = pr.parse_task_row(row)
    assert parsed["title"].startswith(row.split()[0])
    assert parsed["due"] == expected_due


def test_task_row_strips_list_markers():
    assert pr.parse_task_row("- Do the thing")["title"] == "Do the thing"
    assert pr.parse_task_row("* Do the thing")["title"] == "Do the thing"


def test_blank_task_row_is_none():
    assert pr.parse_task_row("") is None
    assert pr.parse_task_row("   ") is None


def test_task_title_is_capped():
    assert len(pr.parse_task_row("x" * 5000)["title"]) <= pr._MAX_TITLE_CHARS


def test_newlines_are_flattened_out_of_titles():
    """A newline would break the Markdown table the adapter writes into."""
    parsed = pr.parse_task_row("line one\nline two")
    assert "\n" not in parsed["title"]


def test_calendar_row_requires_a_date():
    """A dateless row must NOT be scheduled on a made-up day."""
    assert pr.parse_calendar_row("Team sync sometime next week") is None
    assert pr.parse_calendar_row("Lunch") is None


def test_calendar_row_parses_date_time_duration():
    parsed = pr.parse_calendar_row("Midterm 2026-09-01 14:00 for 2h")
    assert parsed["date"] == "2026-09-01"
    assert parsed["time"] == "14:00"
    assert parsed["duration"] == "2h"


@pytest.mark.parametrize("row,expected", [
    ("Call 2026-09-01 2:30 pm", "14:30"),
    ("Call 2026-09-01 12:00 am", "00:00"),
    ("Call 2026-09-01 12:00 pm", "12:00"),
    ("Call 2026-09-01 09:15", "09:15"),
])
def test_meridiem_handling(row, expected):
    assert pr.parse_calendar_row(row)["time"] == expected


def test_calendar_rows_are_never_pre_approved():
    """An emailed suggestion is a proposal, not a decision."""
    assert pr.parse_calendar_row("Exam 2026-09-01")["approved"] == "No"


def test_ambiguous_numeric_dates_are_not_guessed():
    """03/04/2026 is either March 4 or April 3 — skipping beats guessing."""
    assert pr.parse_calendar_row("Meeting 03/04/2026") is None


# ══════════════════════════════════════════════════════════════════════════════
# Applying
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "ops").mkdir(parents=True)
    # task-db.md is deliberately NOT pre-created: vault.create_task cannot append
    # to an empty table (it needs existing rows), but it creates the file itself
    # with the canonical header when absent — which is the path worth exercising.
    (root / "ops" / "calendar-candidates.md").write_text(
        "# Calendar Candidates\n\n| Date | Time | Duration | Title | Reason | Source | Approved |\n"
        "|---|---|---|---|---|---|---|\n",
        encoding="utf-8",
    )
    return root


class _Draft:
    def __init__(self, tasks=None, cal=None):
        self.proposed_task_rows = tasks or []
        self.proposed_calendar_rows = cal or []


def _patch_draft(monkeypatch, draft):
    from app import email_intake
    monkeypatch.setattr(email_intake, "get_draft", lambda _id: draft)


def test_task_rows_create_vault_tasks(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(tasks=["Submit report by 2026-09-01", "Email prof"]))
    result = pr.apply_email_task_rows("d1", str(vault))

    assert result["ok"] is True
    assert len(result["created"]) == 2
    body = (vault / "ops" / "task-db.md").read_text(encoding="utf-8")
    assert "Submit report" in body
    assert "2026-09-01" in body


def test_calendar_rows_create_candidates_unapproved(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(cal=["Midterm 2026-09-01 14:00"]))
    result = pr.apply_email_calendar_rows("d1", str(vault))

    assert result["ok"] is True
    body = (vault / "ops" / "calendar-candidates.md").read_text(encoding="utf-8")
    row = [l for l in body.splitlines() if "Midterm" in l][0]
    assert row.rstrip().endswith("No |")     # never written pre-approved


def test_dateless_calendar_rows_are_skipped_not_invented(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(cal=["Exam 2026-09-01", "Coffee sometime"]))
    result = pr.apply_email_calendar_rows("d1", str(vault))

    assert len(result["created"]) == 1
    assert any("no date found" in s for s in result["skipped"])
    body = (vault / "ops" / "calendar-candidates.md").read_text(encoding="utf-8")
    assert "Coffee" not in body


def test_all_rows_unusable_raises_rather_than_silently_doing_nothing(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(cal=["no date here", "nor here"]))
    with pytest.raises(ValueError, match="No calendar rows could be applied"):
        pr.apply_email_calendar_rows("d1", str(vault))


def test_empty_row_lists_raise(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft())
    with pytest.raises(ValueError, match="no proposed task rows"):
        pr.apply_email_task_rows("d1", str(vault))
    with pytest.raises(ValueError, match="no proposed calendar rows"):
        pr.apply_email_calendar_rows("d1", str(vault))


def test_missing_draft_raises(vault, monkeypatch):
    from app import email_intake
    monkeypatch.setattr(email_intake, "get_draft", lambda _id: None)
    with pytest.raises(ValueError, match="not found"):
        pr.apply_email_task_rows("nope", str(vault))


def test_row_count_is_capped(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(tasks=[f"Task {i}" for i in range(200)]))
    result = pr.apply_email_task_rows("d1", str(vault))
    assert len(result["created"]) <= pr._MAX_ROWS_PER_APPLY


def test_backup_is_written_by_the_shared_adapter(vault, monkeypatch):
    """Applying reuses vault.create_task, so backup-before-write is inherited."""
    from app import vault as vault_module
    seen = {}
    real_backup = vault_module._backup_task_file
    monkeypatch.setattr(vault_module, "_backup_task_file",
                        lambda p: seen.setdefault("backed_up", True) or real_backup(p))

    _patch_draft(monkeypatch, _Draft(tasks=["Do a thing"]))
    pr.apply_email_task_rows("d1", str(vault))
    assert seen.get("backed_up") is True


def test_pipe_injection_cannot_break_the_task_table(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(tasks=["Evil | row | injection"]))
    pr.apply_email_task_rows("d1", str(vault))
    body = (vault / "ops" / "task-db.md").read_text(encoding="utf-8")
    lines = body.splitlines()
    header = [l for l in lines if l.lstrip().startswith("|") and "Status" in l][0]
    row = [l for l in lines if "Evil" in l][0]
    # The injected pipes must not add columns to the table.
    assert row.count("|") == header.count("|")


# ══════════════════════════════════════════════════════════════════════════════
# Proposal-queue dispatch
# ══════════════════════════════════════════════════════════════════════════════

def test_new_prefixes_are_known():
    assert pr._split_proposal_id("email-task:d1") == ("email-task", "d1")
    assert pr._split_proposal_id("email-calendar:d1") == ("email-calendar", "d1")


def test_apply_proposal_routes_task_rows(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(tasks=["Do a thing"]))
    result = pr.apply_proposal("email-task:d1", str(vault))
    assert result["id"] == "email-task:d1"
    assert result["targetPath"] == "ops/task-db.md"


def test_apply_proposal_routes_calendar_rows(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(cal=["Exam 2026-09-01"]))
    result = pr.apply_proposal("email-calendar:d1", str(vault))
    assert result["targetPath"] == "ops/calendar-candidates.md"


def test_unknown_prefix_still_rejected():
    with pytest.raises(ValueError, match="Unknown proposal source"):
        pr._split_proposal_id("email-danger:d1")


def test_batch_apply_collects_failures(vault, monkeypatch):
    _patch_draft(monkeypatch, _Draft(tasks=["Do a thing"]))
    results = pr.apply_batch(["email-task:d1", "email-calendar:d1"], str(vault))
    assert len(results) == 2
    assert results[0]["ok"] is True
    assert results[1]["ok"] is False      # no calendar rows on this draft


def test_actions_are_surfaced_only_when_rows_exist(monkeypatch, tmp_path):
    from app import email_intake

    class D:
        id = "d1"
        subject = "S"
        summary = "s"
        action_required = None
        confidence = None
        saved_path = None
        proposed_destination = "raw/inbox/email/x.md"
        created_at = "2026-08-24T00:00:00+00:00"
        updated_at = created_at
        status = "draft"
        domain = "unknown"
        entity = None
        proposed_task_rows = ["Do a thing"]
        proposed_calendar_rows = []

    monkeypatch.setattr(email_intake, "list_drafts", lambda: [D()])
    actions = email_intake.normalized_proposals()[0]["actions"]
    assert "apply_email_tasks" in actions
    assert "apply_email_calendar" not in actions
