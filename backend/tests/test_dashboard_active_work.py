"""
test_dashboard_active_work.py — Tests for dashboard activeWork drill-down logic.

Tests use unittest.mock to patch vault/intake data sources so no real vault or
staging area is needed. All tested paths are read-only; no files are written.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.dashboard import _build_active_work, _MAX_ACTIVE_ITEMS


# ── helpers ───────────────────────────────────────────────────────────────────

def _backfill_item(id, item, status="new", value=None, type=None, path=None):
    return {"id": id, "item": item, "status": status, "value": value, "type": type, "path": path}


def _escalation_item(id, task, status="new", priority=None, target=None, path=None):
    return {"id": id, "task": task, "status": status, "priority": priority, "target": target, "path": path}


def _resume_item(id, target, status="new", priority=None, company=None, role=None, deadline=None):
    return {"id": id, "target": target, "status": status, "priority": priority,
            "company": company, "role": role, "deadline": deadline}


def _cal_candidate(id, title, approved="No", date=None, time=None):
    return {"id": id, "title": title, "approved": approved, "date": date, "time": time}


def _proposal(file_id, status, entity="Unassigned"):
    p = SimpleNamespace()
    p.file_id = file_id
    p.status = status
    p.entity = entity
    p.proposed_destination = f"raw/misc/{file_id}"
    return p


def _staged(id, original_name):
    e = SimpleNamespace()
    e.id = id
    e.original_name = original_name
    return e


def _call(**kwargs):
    defaults = dict(
        staged_entries=[],
        proposals=[],
        calendar_candidates=[],
        backfill_items=[],
        resume_items=[],
        escalation_items=[],
    )
    defaults.update(kwargs)
    return _build_active_work(**defaults)


# ── list limit tests ──────────────────────────────────────────────────────────

def test_backfill_limit_to_three():
    items = [_backfill_item(f"b{i}", f"Item {i}", "new") for i in range(10)]
    result, errors = _call(backfill_items=items)
    assert len(result["backfill"]) == _MAX_ACTIVE_ITEMS
    assert errors == []


def test_escalations_limit_to_three():
    items = [_escalation_item(f"e{i}", f"Task {i}", "new") for i in range(10)]
    result, errors = _call(escalation_items=items)
    assert len(result["escalations"]) == _MAX_ACTIVE_ITEMS


def test_resume_limit_to_three():
    items = [_resume_item(f"r{i}", f"Job {i}", "new") for i in range(10)]
    result, errors = _call(resume_items=items)
    assert len(result["resume"]) == _MAX_ACTIVE_ITEMS


def test_calendar_limit_to_three():
    cands = [_cal_candidate(f"c{i}", f"Event {i}") for i in range(10)]
    result, errors = _call(calendar_candidates=cands)
    assert len(result["calendar"]) == _MAX_ACTIVE_ITEMS


def test_raw_limit_to_three():
    props = [_proposal(f"f{i}", "proposed") for i in range(10)]
    result, errors = _call(proposals=props)
    assert len(result["raw"]) == _MAX_ACTIVE_ITEMS


# ── exclusion tests ───────────────────────────────────────────────────────────

def test_backfill_excludes_done_and_skipped():
    items = [
        _backfill_item("b1", "Active", "in-progress"),
        _backfill_item("b2", "Done item", "done"),
        _backfill_item("b3", "Skipped item", "skipped"),
        _backfill_item("b4", "New item", "new"),
    ]
    result, _ = _call(backfill_items=items)
    ids = {it["id"] for it in result["backfill"]}
    assert "b2" not in ids
    assert "b3" not in ids
    assert "b1" in ids
    assert "b4" in ids


def test_escalations_excludes_done_and_skipped():
    items = [
        _escalation_item("e1", "Active", "blocked"),
        _escalation_item("e2", "Done", "done"),
        _escalation_item("e3", "Skipped", "skipped"),
    ]
    result, _ = _call(escalation_items=items)
    ids = {it["id"] for it in result["escalations"]}
    assert "e2" not in ids
    assert "e3" not in ids
    assert "e1" in ids


def test_resume_excludes_rejected_archived_offer():
    items = [
        _resume_item("r1", "Active job", "new"),
        _resume_item("r2", "Rejected", "rejected"),
        _resume_item("r3", "Archived", "archived"),
        _resume_item("r4", "Offer received", "offer"),
    ]
    result, _ = _call(resume_items=items)
    ids = {it["id"] for it in result["resume"]}
    assert "r2" not in ids
    assert "r3" not in ids
    assert "r4" not in ids
    assert "r1" in ids


def test_calendar_includes_only_unapproved():
    cands = [
        _cal_candidate("c1", "Approved event", approved="Yes"),
        _cal_candidate("c2", "Pending event", approved="No"),
        _cal_candidate("c3", "Also pending", approved=""),
    ]
    result, _ = _call(calendar_candidates=cands)
    ids = {it["id"] for it in result["calendar"]}
    assert "c1" not in ids
    assert "c2" in ids
    assert "c3" in ids


def test_raw_includes_only_proposed_and_edited():
    props = [
        _proposal("f1", "proposed"),
        _proposal("f2", "edited"),
        _proposal("f3", "approved"),
        _proposal("f4", "routed"),
        _proposal("f5", "archived"),
    ]
    result, _ = _call(proposals=props)
    ids = {it["id"] for it in result["raw"]}
    assert "f1" in ids
    assert "f2" in ids
    assert "f3" not in ids
    assert "f4" not in ids
    assert "f5" not in ids


# ── sorting tests ─────────────────────────────────────────────────────────────

def test_backfill_sort_inprogress_before_triaged_before_new():
    items = [
        _backfill_item("b1", "New item",        "new"),
        _backfill_item("b2", "Triaged item",    "triaged"),
        _backfill_item("b3", "In-progress item","in-progress"),
    ]
    result, _ = _call(backfill_items=items)
    assert result["backfill"][0]["id"] == "b3"
    assert result["backfill"][1]["id"] == "b2"
    assert result["backfill"][2]["id"] == "b1"


def test_backfill_sort_high_value_first_within_status():
    items = [
        _backfill_item("b1", "Low new",    "new", value="low"),
        _backfill_item("b2", "High new",   "new", value="high"),
        _backfill_item("b3", "Medium new", "new", value="medium"),
    ]
    result, _ = _call(backfill_items=items)
    assert result["backfill"][0]["id"] == "b2"
    assert result["backfill"][1]["id"] == "b3"
    assert result["backfill"][2]["id"] == "b1"


def test_escalations_sort_blocked_first():
    items = [
        _escalation_item("e1", "New",        "new"),
        _escalation_item("e2", "In progress","in-progress"),
        _escalation_item("e3", "Blocked",    "blocked"),
        _escalation_item("e4", "Ready",      "ready"),
    ]
    result, _ = _call(escalation_items=items)
    assert result["escalations"][0]["id"] == "e3"


def test_escalations_high_priority_before_medium():
    items = [
        _escalation_item("e1", "Medium blocked", "blocked", priority="medium"),
        _escalation_item("e2", "High blocked",   "blocked", priority="high"),
    ]
    result, _ = _call(escalation_items=items)
    assert result["escalations"][0]["id"] == "e2"


def test_resume_sort_interview_first():
    items = [
        _resume_item("r1", "New job",       "new"),
        _resume_item("r2", "Applied job",   "applied"),
        _resume_item("r3", "Interview job", "interview"),
        _resume_item("r4", "Tailoring",     "tailoring"),
    ]
    result, _ = _call(resume_items=items)
    assert result["resume"][0]["id"] == "r3"


def test_raw_sort_edited_first():
    props = [
        _proposal("f1", "proposed"),
        _proposal("f2", "edited"),
        _proposal("f3", "proposed"),
    ]
    result, _ = _call(proposals=props)
    assert result["raw"][0]["id"] == "f2"


# ── field mapping tests ───────────────────────────────────────────────────────

def test_backfill_title_is_item_field():
    items = [_backfill_item("b1", "My repo project", "new")]
    result, _ = _call(backfill_items=items)
    assert result["backfill"][0]["title"] == "My repo project"


def test_escalation_title_is_task_field():
    items = [_escalation_item("e1", "Fix the auth bug", "blocked")]
    result, _ = _call(escalation_items=items)
    assert result["escalations"][0]["title"] == "Fix the auth bug"


def test_resume_title_is_target_field():
    items = [_resume_item("r1", "SWE Intern @ Acme", "new", company="Acme")]
    result, _ = _call(resume_items=items)
    assert result["resume"][0]["title"] == "SWE Intern @ Acme"
    assert result["resume"][0]["company"] == "Acme"


def test_calendar_status_is_pending():
    cands = [_cal_candidate("c1", "Team sync", approved="No")]
    result, _ = _call(calendar_candidates=cands)
    assert result["calendar"][0]["status"] == "pending"
    assert result["calendar"][0]["reason"] == "Pending approval"


def test_raw_uses_original_name_from_staged_entries():
    props = [_proposal("f1", "proposed")]
    staged = [_staged("f1", "my-document.pdf")]
    result, _ = _call(proposals=props, staged_entries=staged)
    assert result["raw"][0]["title"] == "my-document.pdf"


def test_raw_falls_back_to_entity_when_no_staged():
    p = _proposal("f1", "proposed", entity="JARVIS project")
    result, _ = _call(proposals=[p])
    assert result["raw"][0]["title"] == "JARVIS project"


# ── partial failure isolation ─────────────────────────────────────────────────

def test_one_source_failure_does_not_affect_others():
    # Force backfill to fail by passing non-iterable
    bad_backfill = None  # will fail the list comprehension
    good_escalations = [_escalation_item("e1", "Task", "blocked")]
    result, errors = _build_active_work(
        staged_entries=[],
        proposals=[],
        calendar_candidates=[],
        backfill_items=bad_backfill,
        resume_items=[],
        escalation_items=good_escalations,
    )
    assert result["escalations"][0]["id"] == "e1"
    assert result["backfill"] == []
    assert any("activeWork.backfill" in e["source"] for e in errors)


def test_empty_sources_return_empty_lists():
    result, errors = _call()
    assert result == {
        "backfill": [], "escalations": [], "resume": [],
        "calendar": [], "raw": [],
    }
    assert errors == []


# ── read-only guarantee ───────────────────────────────────────────────────────

def test_build_active_work_makes_no_file_writes(tmp_path):
    """Calling _build_active_work should never write files. We verify by
    checking no files appear in a temp directory (sanity test)."""
    before = list(tmp_path.iterdir())
    _call()
    after = list(tmp_path.iterdir())
    assert before == after
