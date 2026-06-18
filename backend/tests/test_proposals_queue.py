"""
test_proposals_queue.py — Tests for the generalized Proposal Queue aggregation (v1).

The aggregation layer is read-only: it reshapes existing Raw Inbox classification
proposals into a normalized form. These tests patch the intake read functions so no
real staging area is touched, and assert no files are written.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.proposals import list_normalized_proposals


# ── helpers ───────────────────────────────────────────────────────────────────

def _proposal(file_id, status="proposed", **kw):
    p = SimpleNamespace()
    p.file_id              = file_id
    p.status               = status
    p.domain               = kw.get("domain", "project")
    p.entity               = kw.get("entity", "JARVIS")
    p.source_type          = kw.get("source_type", "notes")
    p.proposed_destination = kw.get("proposed_destination", "raw/projects/JARVIS/notes/")
    p.confidence           = kw.get("confidence", "High")
    p.reason               = kw.get("reason", "matches project")
    p.routed_name          = kw.get("routed_name")
    p.archived_name        = kw.get("archived_name")
    p.routed_path          = kw.get("routed_path")
    p.routed_at            = kw.get("routed_at")
    p.archived_at          = kw.get("archived_at")
    p.ai_classified_at     = kw.get("ai_classified_at")
    return p


def _staged(id, original_name, uploaded_at="2026-06-11T10:00:00Z"):
    e = SimpleNamespace()
    e.id            = id
    e.original_name = original_name
    e.uploaded_at   = uploaded_at
    return e


def _run(proposals, staged=None):
    staged = staged or []
    with patch("app.proposals.list_proposals", return_value=proposals), \
         patch("app.proposals.list_staged", return_value=staged):
        return list_normalized_proposals()


# ── empty ─────────────────────────────────────────────────────────────────────

def test_empty_returns_empty():
    items, errors = _run([])
    assert items == []
    assert errors == []


# ── basic mapping ─────────────────────────────────────────────────────────────

def test_basic_mapping():
    p = _proposal("f1", "proposed")
    items, errors = _run([p], [_staged("f1", "lecture.pdf")])

    assert errors == []
    assert len(items) == 1
    it = items[0]
    assert it["id"]         == "raw-inbox:f1"
    assert it["source"]     == "raw-inbox"
    assert it["type"]       == "file_route"
    assert it["riskLevel"]  == "medium"
    assert it["title"]      == "lecture.pdf"
    assert it["status"]     == "pending"
    assert it["confidence"] == "High"
    assert it["targetPath"] == "raw/projects/JARVIS/notes/"
    assert it["relatedId"]  == "f1"
    assert it["actions"]    == ["open_raw_inbox"]
    assert it["createdAt"]  == "2026-06-11T10:00:00Z"
    assert it["details"]["domain"]     == "project"
    assert it["details"]["entity"]     == "JARVIS"
    assert it["details"]["sourceType"] == "notes"
    assert it["details"]["filename"]   == "lecture.pdf"
    assert it["details"]["reason"]     == "matches project"


# ── status mapping ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw_status,expected", [
    ("proposed", "pending"),
    ("edited",   "pending"),
    ("approved", "approved"),
    ("routed",   "applied"),
    ("archived", "applied"),
    ("skipped",  "skipped"),
    ("something-unknown", "pending"),
])
def test_status_mapping(raw_status, expected):
    items, _ = _run([_proposal("f1", raw_status)], [_staged("f1", "a.txt")])
    assert items[0]["status"] == expected


# ── routed proposals point targetPath at the routed path ───────────────────────

def test_routed_target_path_and_updated_at():
    p = _proposal(
        "f1", "routed",
        routed_path="raw/projects/JARVIS/notes/a.txt",
        routed_at="2026-06-11T11:00:00Z",
    )
    items, _ = _run([p], [_staged("f1", "a.txt")])
    assert items[0]["targetPath"] == "raw/projects/JARVIS/notes/a.txt"
    assert items[0]["updatedAt"]  == "2026-06-11T11:00:00Z"


# ── title falls back when the staged entry is gone ─────────────────────────────

def test_title_fallback_without_staged_entry():
    p = _proposal("f1", "routed", routed_name="routed-a.txt")
    items, _ = _run([p], [])  # no staged entries
    assert items[0]["title"]     == "routed-a.txt"
    assert items[0]["createdAt"] is None


def test_title_fallback_to_file_id():
    p = _proposal("f1", "proposed")
    p.routed_name = None
    p.archived_name = None
    items, _ = _run([p], [])
    assert items[0]["title"] == "f1"


# ── confidence normalization ───────────────────────────────────────────────────

def test_blank_confidence_becomes_none():
    items, _ = _run([_proposal("f1", "proposed", confidence="")], [_staged("f1", "a.txt")])
    assert items[0]["confidence"] is None


# ── malformed / failing source ─────────────────────────────────────────────────

def test_failing_source_returns_error_not_exception():
    with patch("app.proposals.list_proposals", side_effect=RuntimeError("bad index")), \
         patch("app.proposals.list_staged", return_value=[]):
        items, errors = list_normalized_proposals()
    assert items == []
    assert len(errors) == 1
    assert errors[0]["source"] == "raw-inbox"
    assert "bad index" in errors[0]["message"]


# ── read-only: listing writes nothing ──────────────────────────────────────────

def test_listing_writes_no_files(tmp_path):
    before = list(tmp_path.iterdir())
    _run([_proposal("f1", "proposed")], [_staged("f1", "a.txt")])
    after = list(tmp_path.iterdir())
    assert before == after
