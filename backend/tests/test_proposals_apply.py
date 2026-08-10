"""
test_proposals_apply.py — Tests for the generalized Proposal apply/reject spine (A1).

The apply spine adds no new write primitive: it dispatches a normalized proposal id
to the SAME save/route function the source page already uses. These tests patch those
source functions so no real vault/staging is touched, and verify dispatch, safety,
idempotency, and batch behavior.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.proposals import (
    _split_proposal_id,
    apply_batch,
    apply_proposal,
    reject_proposal,
)


# ── id parsing ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pid,prefix,related", [
    ("raw-inbox:f1", "raw-inbox", "f1"),
    ("consolidation:abc-123", "consolidation", "abc-123"),
    ("research:xyz", "research", "xyz"),
    ("email-intake:e9", "email-intake", "e9"),
])
def test_split_valid(pid, prefix, related):
    assert _split_proposal_id(pid) == (prefix, related)


@pytest.mark.parametrize("bad", ["", "nocolon", "raw-inbox:", ":f1", "unknown:f1"])
def test_split_invalid(bad):
    with pytest.raises(ValueError):
        _split_proposal_id(bad)


# ── draft dispatch (consolidation / research / email-intake) ────────────────────

@pytest.mark.parametrize("prefix,module", [
    ("consolidation", "app.consolidation"),
    ("research", "app.research"),
    ("email-intake", "app.email_intake"),
])
def test_apply_draft_dispatches_to_save(prefix, module):
    info = {"relativePath": "raw/x/y.md", "absolutePath": "/vault/raw/x/y.md"}
    with patch(f"{module}.save_draft", return_value=(SimpleNamespace(), info)) as m:
        result = apply_proposal(f"{prefix}:d1", "/vault")
    m.assert_called_once_with("d1", "/vault")
    assert result["ok"] is True
    assert result["status"] == "applied"
    assert result["targetPath"] == "raw/x/y.md"
    assert result["id"] == f"{prefix}:d1"


def test_apply_draft_already_saved_raises():
    with patch("app.consolidation.save_draft", side_effect=ValueError("Draft is already saved.")):
        with pytest.raises(ValueError, match="already saved"):
            apply_proposal("consolidation:d1", "/vault")


# ── raw-inbox dispatch ──────────────────────────────────────────────────────────

def _raw(status, **kw):
    p = SimpleNamespace(file_id="f1", status=status)
    p.routed_path = kw.get("routed_path")
    return p


def test_apply_raw_inbox_approves_then_routes():
    info = {"relativePath": "raw/projects/JARVIS/notes/a.txt"}
    with patch("app.intake.list_proposals", return_value=[_raw("proposed")]), \
         patch("app.intake.approve_proposal") as approve, \
         patch("app.intake.route_proposal", return_value=(SimpleNamespace(), info)) as route:
        result = apply_proposal("raw-inbox:f1", "/vault")
    approve.assert_called_once_with("f1")
    route.assert_called_once_with("f1", "/vault")
    assert result["ok"] is True
    assert result["status"] == "applied"
    assert result["alreadyApplied"] is False
    assert result["targetPath"] == "raw/projects/JARVIS/notes/a.txt"


@pytest.mark.parametrize("status", ["routed", "archived"])
def test_apply_raw_inbox_already_applied_is_idempotent(status):
    with patch("app.intake.list_proposals",
               return_value=[_raw(status, routed_path="raw/x/a.txt")]), \
         patch("app.intake.approve_proposal") as approve, \
         patch("app.intake.route_proposal") as route:
        result = apply_proposal("raw-inbox:f1", "/vault")
    approve.assert_not_called()
    route.assert_not_called()
    assert result["ok"] is True
    assert result["alreadyApplied"] is True
    assert result["targetPath"] == "raw/x/a.txt"


def test_apply_raw_inbox_skipped_raises():
    with patch("app.intake.list_proposals", return_value=[_raw("skipped")]):
        with pytest.raises(ValueError, match="Skipped"):
            apply_proposal("raw-inbox:f1", "/vault")


def test_apply_raw_inbox_not_found_raises():
    with patch("app.intake.list_proposals", return_value=[]):
        with pytest.raises(ValueError, match="not found"):
            apply_proposal("raw-inbox:missing", "/vault")


# ── batch ────────────────────────────────────────────────────────────────────────

def test_apply_batch_collects_results_and_never_raises():
    info = {"relativePath": "raw/x/y.md"}
    with patch("app.research.save_draft", return_value=(SimpleNamespace(), info)), \
         patch("app.consolidation.save_draft", side_effect=ValueError("boom")):
        results = apply_batch(["research:ok", "consolidation:bad", "unknown:z"], "/vault")
    assert len(results) == 3
    ok = {r["id"]: r for r in results}
    assert ok["research:ok"]["ok"] is True
    assert ok["consolidation:bad"]["ok"] is False
    assert ok["consolidation:bad"]["status"] == "error"
    assert "boom" in ok["consolidation:bad"]["message"]
    assert ok["unknown:z"]["ok"] is False  # malformed/unknown prefix → error, not exception


# ── reject ───────────────────────────────────────────────────────────────────────

def test_reject_raw_inbox_skips():
    with patch("app.intake.skip_proposal", return_value=SimpleNamespace()) as skip:
        result = reject_proposal("raw-inbox:f1")
    skip.assert_called_once_with("f1")
    assert result["ok"] is True
    assert result["status"] == "skipped"


def test_reject_raw_inbox_not_found_raises():
    with patch("app.intake.skip_proposal", return_value=None):
        with pytest.raises(ValueError, match="not found"):
            reject_proposal("raw-inbox:missing")


@pytest.mark.parametrize("prefix", ["consolidation", "research", "email-intake"])
def test_reject_draft_not_supported(prefix):
    with pytest.raises(ValueError, match="not supported"):
        reject_proposal(f"{prefix}:d1")


# ── endpoint smoke (call route fns directly; no httpx in this repo) ─────────────

def test_endpoint_apply_smoke():
    from app.main import proposals_apply
    from app.models import ApplyProposalRequest

    info = {"relativePath": "raw/x/y.md"}
    with patch("app.main.get_config", return_value=SimpleNamespace(vault_path="/vault")), \
         patch("app.research.save_draft", return_value=(SimpleNamespace(), info)):
        resp = proposals_apply(ApplyProposalRequest(id="research:d1"))
    assert resp.ok is True
    assert resp.targetPath == "raw/x/y.md"


def test_endpoint_apply_batch_counts():
    from app.main import proposals_apply_batch
    from app.models import ApplyBatchRequest

    info = {"relativePath": "raw/x/y.md"}
    with patch("app.main.get_config", return_value=SimpleNamespace(vault_path="/vault")), \
         patch("app.research.save_draft", return_value=(SimpleNamespace(), info)), \
         patch("app.consolidation.save_draft", side_effect=ValueError("boom")):
        resp = proposals_apply_batch(ApplyBatchRequest(ids=["research:a", "consolidation:b"]))
    assert resp.appliedCount == 1
    assert resp.failedCount == 1


def test_endpoint_apply_bad_id_400():
    from fastapi import HTTPException
    from app.main import proposals_apply
    from app.models import ApplyProposalRequest

    with patch("app.main.get_config", return_value=SimpleNamespace(vault_path="/vault")):
        with pytest.raises(HTTPException) as ei:
            proposals_apply(ApplyProposalRequest(id="garbage"))
    assert ei.value.status_code == 400
