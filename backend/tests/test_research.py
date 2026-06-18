"""
test_research.py — Research v1 (manual capture).

Covers draft create/validation, destination mapping, list/get, editable-field updates,
vault save (write-once under raw/research/, no overwrite, traversal rejected), and
Proposal Queue aggregation. Storage paths are redirected into tmp_path so no real
backend data or vault is touched.
"""

import json

import pytest

from app import research
from app.proposals import list_normalized_proposals


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    rdir = tmp_path / "research"
    monkeypatch.setattr(research, "RESEARCH_DIR", rdir)
    monkeypatch.setattr(research, "DRAFTS_FILE", rdir / "drafts.json")
    yield


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    v.mkdir()
    return v


def _mk(**kw):
    base = dict(
        title="Vector DB Comparison",
        topic="Vector Databases",
        domain="technical",
        entity="JARVIS",
        research_question="Which vector DB fits local-first RAG?",
        summary=None,
        key_findings=["pgvector is simplest to operate"],
        sources=[{"title": "pgvector", "url": "https://github.com/pgvector/pgvector", "notes": "extension"}],
        open_questions=["What about hybrid search?"],
        recommended_next_actions=["Prototype pgvector"],
        raw_notes="raw pasted notes here",
    )
    base.update(kw)
    return research.create_draft(**base)


# ── create / validation ─────────────────────────────────────────────────────────

def test_create_basic_no_vault_write(vault):
    d = _mk()
    assert d.status == "draft"
    assert d.saved_path is None
    assert list(vault.rglob("*")) == []


def test_create_requires_title():
    with pytest.raises(ValueError):
        _mk(title="   ")


def test_create_requires_some_content():
    # No raw notes, no summary, no findings → rejected.
    with pytest.raises(ValueError):
        _mk(raw_notes="", summary=None, key_findings=None)


def test_create_accepts_summary_only():
    d = _mk(raw_notes="", summary="Just a summary.", key_findings=None)
    assert d.summary == "Just a summary."


def test_create_accepts_finding_only():
    d = _mk(raw_notes="", summary=None, key_findings=["one finding"])
    assert d.key_findings == ["one finding"]


def test_create_rejects_bad_domain():
    with pytest.raises(ValueError):
        _mk(domain="astrology")


@pytest.mark.parametrize("field", ["title", "topic", "entity"])
def test_create_rejects_traversal(field):
    with pytest.raises(ValueError):
        _mk(**{field: "../etc/passwd"})


def test_sources_cleaned():
    d = _mk(sources=[
        {"title": "A", "url": "", "notes": None},
        {"title": "", "url": "", "notes": ""},   # all empty → dropped
        {"url": "https://x.test"},
    ])
    assert len(d.sources) == 2
    assert d.sources[0] == {"title": "A", "url": None, "notes": None}


# ── destination mapping ─────────────────────────────────────────────────────────

def test_destination_uses_topic_slug():
    d = _mk(title="Vector DB Comparison", topic="Vector Databases")
    assert d.proposed_destination.startswith("raw/research/vector-databases/")
    assert d.proposed_destination.endswith("-vector-db-comparison.md")


def test_destination_falls_back_to_title_slug():
    d = _mk(title="Edge Caching", topic=None)
    assert d.proposed_destination.startswith("raw/research/edge-caching/")


# ── list / get ──────────────────────────────────────────────────────────────────

def test_list_and_get():
    a = _mk(title="First")
    b = _mk(title="Second")
    ids = {x.id for x in research.list_drafts()}
    assert ids == {a.id, b.id}
    assert research.get_draft(a.id).title == "First"
    assert research.get_draft("nope") is None


# ── update editable fields ──────────────────────────────────────────────────────

def test_update_editable_fields():
    d = _mk()
    updated = research.update_draft(d.id, {
        "summary": "edited summary",
        "key_findings": ["a", "  ", "b"],
        "domain": "market",
        "sources": [{"title": "S", "url": "https://s.test", "notes": "n"}],
    })
    assert updated.summary == "edited summary"
    assert updated.key_findings == ["a", "b"]
    assert updated.domain == "market"
    assert updated.sources[0]["title"] == "S"


def test_update_title_resyncs_destination():
    d = _mk(title="Old", topic=None)
    updated = research.update_draft(d.id, {"title": "Brand New Title"})
    assert updated.proposed_destination.startswith("raw/research/brand-new-title/")


def test_update_rejects_bad_domain():
    d = _mk()
    with pytest.raises(ValueError):
        research.update_draft(d.id, {"domain": "astrology"})


def test_update_ignores_locked_fields():
    d = _mk()
    created = d.created_at
    updated = research.update_draft(d.id, {
        "status": "saved",
        "saved_path": "raw/evil.md",
        "created_at": "1999",
        "summary": "ok",
    })
    assert updated.status == "draft"
    assert updated.saved_path is None
    assert updated.created_at == created
    assert updated.summary == "ok"


def test_update_missing_returns_none():
    assert research.update_draft("nope", {"summary": "x"}) is None


# ── save to vault ───────────────────────────────────────────────────────────────

def test_save_writes_markdown_under_raw_research(vault):
    d = _mk(title="My Study", topic="Caching", summary="Key summary.")
    saved, info = research.save_draft(d.id, str(vault))

    assert saved.status == "saved"
    assert saved.saved_path.startswith("raw/research/caching/")
    written = vault / saved.saved_path
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert "# My Study" in text
    assert "- Domain: technical" in text
    assert "## Research Question" in text
    assert "## Key Findings" in text
    assert "## Sources" in text
    assert "## Raw Notes" in text
    assert "raw pasted notes here" in text


def test_save_renders_source_link(vault):
    d = _mk(sources=[{"title": "pgvector", "url": "https://pgv.test", "notes": "ext"}])
    saved, _ = research.save_draft(d.id, str(vault))
    text = (vault / saved.saved_path).read_text(encoding="utf-8")
    assert "[pgvector](https://pgv.test) — ext" in text


def test_save_marks_draft_saved_in_store(vault):
    d = _mk()
    research.save_draft(d.id, str(vault))
    assert research.get_draft(d.id).status == "saved"


def test_save_twice_rejected(vault):
    d = _mk()
    research.save_draft(d.id, str(vault))
    with pytest.raises(ValueError):
        research.save_draft(d.id, str(vault))


def test_save_never_overwrites(vault):
    d = _mk(title="Dup", topic="Dup")
    target = vault / d.proposed_destination
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("SENTINEL", encoding="utf-8")

    saved, _ = research.save_draft(d.id, str(vault))
    assert (vault / saved.saved_path) != target
    assert target.read_text(encoding="utf-8") == "SENTINEL"


def test_save_rejects_tampered_destination(vault):
    d = _mk()
    raw = json.loads(research.DRAFTS_FILE.read_text(encoding="utf-8"))
    raw[0]["proposedDestination"] = "raw/research/../../evil.md"
    research.DRAFTS_FILE.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        research.save_draft(d.id, str(vault))
    assert not (vault.parent / "evil.md").exists()


def test_save_rejects_destination_outside_raw_research(vault):
    d = _mk()
    raw = json.loads(research.DRAFTS_FILE.read_text(encoding="utf-8"))
    raw[0]["proposedDestination"] = "raw/chats/evil.md"
    research.DRAFTS_FILE.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        research.save_draft(d.id, str(vault))


def test_save_missing_vault_rejected(tmp_path):
    d = _mk()
    with pytest.raises(ValueError):
        research.save_draft(d.id, str(tmp_path / "does-not-exist"))


def test_save_raw_notes_with_backticks_fenced(vault):
    d = _mk(raw_notes="```js\nconsole.log(1)\n```")
    saved, _ = research.save_draft(d.id, str(vault))
    text = (vault / saved.saved_path).read_text(encoding="utf-8")
    assert "````text" in text


# ── Proposal Queue integration ──────────────────────────────────────────────────

def test_proposals_include_unsaved_draft():
    d = _mk(title="Aggregate Me", summary="my summary")
    items, errors = list_normalized_proposals()
    mine = [i for i in items if i["relatedId"] == d.id]
    assert errors == []
    assert len(mine) == 1
    it = mine[0]
    assert it["source"] == "research"
    assert it["type"] == "research_note"
    assert it["riskLevel"] == "medium"
    assert it["status"] == "pending"
    assert it["title"] == "Aggregate Me"
    assert it["summary"] == "my summary"
    assert it["actions"] == ["open_research"]
    assert it["targetPath"].startswith("raw/research/")


def test_proposals_summary_falls_back_to_finding():
    d = _mk(summary=None, raw_notes="", key_findings=["only finding"])
    items, _ = list_normalized_proposals()
    it = next(i for i in items if i["relatedId"] == d.id)
    assert it["summary"] == "only finding"


def test_proposals_saved_draft_is_applied(vault):
    d = _mk()
    research.save_draft(d.id, str(vault))
    items, _ = list_normalized_proposals()
    it = next(i for i in items if i["relatedId"] == d.id)
    assert it["status"] == "applied"


def test_listing_proposals_writes_nothing(vault):
    _mk()
    before = sorted(p.name for p in vault.rglob("*"))
    list_normalized_proposals()
    after = sorted(p.name for p in vault.rglob("*"))
    assert before == after == []
