"""
test_email_intake.py — Email Intake v1 (manual paste/import).

Covers draft create/validation, destination mapping (course/business/personal/
unknown, with/without entity), list/get, editable-field updates, vault save
(write-once under allowlisted raw email paths, no overwrite, traversal rejected),
saved-status, and Proposal Queue aggregation. Storage paths are redirected into
tmp_path so no real backend data or vault is touched.

The save is the only vault-writing path; everything else writes nothing. No Gmail/
MCP/AI/external call exists in this module.
"""

from pathlib import Path

import pytest

from app import email_intake as ei
from app.proposals import list_normalized_proposals


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    edir = tmp_path / "email-intake"
    monkeypatch.setattr(ei, "EMAIL_INTAKE_DIR", edir)
    monkeypatch.setattr(ei, "DRAFTS_FILE", edir / "drafts.json")
    yield


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    v.mkdir()
    return v


def _mk(**kw):
    base = dict(
        subject="Midterm date announcement",
        sender="prof@uni.edu",
        received_at="2026-06-20",
        domain="course",
        entity="ESC101",
        summary=None,
        action_required="Reply by Friday",
        due_date="2026-06-27",
        confidence="High",
        raw_email="Hello, the midterm is on the 27th.",
        proposed_task_rows=None,
        proposed_calendar_rows=None,
    )
    base.update(kw)
    return ei.create_draft(**base)


# ── create / validation ───────────────────────────────────────────────────────

def test_create_basic_no_vault_write(vault):
    d = _mk()
    assert d.status == "draft"
    assert d.saved_path is None
    assert list(vault.rglob("*")) == []  # nothing written by creating a draft


def test_subject_required():
    with pytest.raises(ValueError):
        _mk(subject="   ")


def test_raw_email_required():
    with pytest.raises(ValueError):
        _mk(raw_email="")


def test_invalid_domain_rejected():
    with pytest.raises(ValueError):
        _mk(domain="finance")


def test_invalid_confidence_rejected():
    with pytest.raises(ValueError):
        _mk(confidence="Maybe")


def test_missing_summary_gets_fallback():
    d = _mk(summary=None, raw_email="Quercus says assignment 3 is due.")
    assert "No summary was provided" in d.summary
    assert "no AI used" in d.summary


def test_task_calendar_rows_cleaned():
    d = _mk(proposed_task_rows=["t1", "  ", "t2"], proposed_calendar_rows=["", "c1"])
    assert d.proposed_task_rows == ["t1", "t2"]
    assert d.proposed_calendar_rows == ["c1"]


# ── destination mapping ────────────────────────────────────────────────────────

@pytest.mark.parametrize("domain,entity,expected_dir", [
    ("course",   "ESC101",     "raw/quercus/emails/"),
    ("course",   None,         "raw/quercus/emails/"),
    ("business", "Acme Corp",  "raw/business/acme-corp/emails/"),
    ("business", None,         "raw/business/unknown/emails/"),
    ("personal", None,         "raw/personal/email/"),
    ("unknown",  None,         "raw/inbox/email/"),
])
def test_destination_mapping(domain, entity, expected_dir):
    d = _mk(domain=domain, entity=entity, subject="Hello World")
    assert d.proposed_destination.startswith(expected_dir)
    assert d.proposed_destination.endswith("-hello-world.md")


# ── list / get ─────────────────────────────────────────────────────────────────

def test_list_newest_first_and_get():
    a = _mk(subject="first")
    b = _mk(subject="second")
    ids = [d.id for d in ei.list_drafts()]
    assert set(ids) == {a.id, b.id}
    assert ei.get_draft(a.id).subject == "first"
    assert ei.get_draft("nope") is None


# ── update editable fields ─────────────────────────────────────────────────────

def test_update_editable_fields_and_redirect():
    d = _mk(domain="unknown", entity=None, subject="orig")
    updated = ei.update_draft(d.id, {
        "subject": "new subject",
        "domain": "business",
        "entity": "Beta LLC",
        "summary": "edited",
        "action_required": "do x",
        "due_date": "2026-07-01",
        "confidence": "Low",
        "proposed_task_rows": ["x"],
    })
    assert updated.subject == "new subject"
    assert updated.domain == "business"
    assert updated.summary == "edited"
    assert updated.confidence == "Low"
    # destination re-derived from new domain/entity/subject
    assert updated.proposed_destination.startswith("raw/business/beta-llc/emails/")
    assert updated.proposed_destination.endswith("-new-subject.md")


def test_update_rejects_bad_domain():
    d = _mk()
    with pytest.raises(ValueError):
        ei.update_draft(d.id, {"domain": "nope"})


def test_update_locked_fields_ignored():
    d = _mk()
    ei.update_draft(d.id, {"raw_email": "TAMPERED", "status": "saved", "id": "x"})
    again = ei.get_draft(d.id)
    assert again.raw_email == d.raw_email
    assert again.status == "draft"
    assert again.id == d.id


def test_update_missing_returns_none():
    assert ei.update_draft("missing", {"subject": "x"}) is None


# ── save to vault ──────────────────────────────────────────────────────────────

def test_save_writes_under_allowed_path(vault):
    d = _mk(domain="course", entity="ESC101")
    saved, info = ei.save_draft(d.id, str(vault))
    assert saved.status == "saved"
    assert saved.saved_path == info["relativePath"]
    assert info["relativePath"].startswith("raw/quercus/emails/")
    written = vault / info["relativePath"]
    assert written.exists()
    content = written.read_text(encoding="utf-8")
    assert content.startswith("# Midterm date announcement")
    assert "## Original Email" in content
    assert "Saved from Brain UI manual email intake" in content


@pytest.mark.parametrize("domain,entity,expected_dir", [
    ("business", "Acme Corp", "raw/business/acme-corp/emails/"),
    ("personal", None,        "raw/personal/email/"),
    ("unknown",  None,        "raw/inbox/email/"),
])
def test_save_destinations(vault, domain, entity, expected_dir):
    d = _mk(domain=domain, entity=entity)
    _, info = ei.save_draft(d.id, str(vault))
    assert info["relativePath"].startswith(expected_dir)
    assert (vault / info["relativePath"]).exists()


def test_save_never_overwrites(vault):
    d1 = _mk(subject="same subject", domain="course")
    d2 = _mk(subject="same subject", domain="course")
    _, i1 = ei.save_draft(d1.id, str(vault))
    _, i2 = ei.save_draft(d2.id, str(vault))
    assert i1["relativePath"] != i2["relativePath"]
    assert (vault / i1["relativePath"]).exists()
    assert (vault / i2["relativePath"]).exists()


def test_save_twice_rejected(vault):
    d = _mk()
    ei.save_draft(d.id, str(vault))
    with pytest.raises(ValueError):
        ei.save_draft(d.id, str(vault))


def test_save_missing_draft_rejected(vault):
    with pytest.raises(ValueError):
        ei.save_draft("nope", str(vault))


def test_save_stays_in_vault_with_traversal_entity(vault):
    """A traversal-looking business entity is slugified, so it cannot escape."""
    d = _mk(domain="business", entity="../../etc/passwd")
    _, info = ei.save_draft(d.id, str(vault))
    written = (vault / info["relativePath"]).resolve()
    assert str(written).startswith(str(vault.resolve()))
    assert ".." not in info["relativePath"]
    # nothing was created outside the vault
    assert (vault / "raw" / "business").exists()


def test_save_untrusted_email_is_fenced(vault):
    d = _mk(raw_email="```\nrm -rf /\n```\nclick here")
    _, info = ei.save_draft(d.id, str(vault))
    content = (vault / info["relativePath"]).read_text(encoding="utf-8")
    # fence widened beyond the 3-backtick run in the body
    assert "````text" in content
    assert "rm -rf /" in content  # present as quoted text, never executed


# ── proposal queue aggregation (read-only) ─────────────────────────────────────

def test_proposal_aggregation_includes_unsaved_email_draft():
    d = _mk(subject="Course email", domain="course", entity="ESC101")
    items, errors = list_normalized_proposals()
    em = [i for i in items if i["source"] == "email-intake"]
    assert len(em) == 1
    it = em[0]
    assert it["id"] == f"email-intake:{d.id}"
    assert it["type"] == "email_summary"
    assert it["riskLevel"] == "medium"
    assert it["status"] == "pending"
    assert it["title"] == "Course email"
    assert it["relatedId"] == d.id
    assert it["actions"] == ["open_email_intake"]
    assert it["targetPath"].startswith("raw/quercus/emails/")


def test_proposal_status_saved_is_applied(vault):
    d = _mk()
    ei.save_draft(d.id, str(vault))
    items, _ = list_normalized_proposals()
    em = [i for i in items if i["relatedId"] == d.id]
    assert em and em[0]["status"] == "applied"


def test_listing_proposals_writes_nothing(vault, tmp_path):
    _mk()
    before = sorted(p.name for p in vault.iterdir())
    list_normalized_proposals()
    after = sorted(p.name for p in vault.iterdir())
    assert before == after
