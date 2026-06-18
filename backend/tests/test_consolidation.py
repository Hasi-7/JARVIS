"""
test_consolidation.py — Chat/AI Consolidation v1 (manual paste/import).

Covers draft create/validation, destination mapping, list/get, editable-field
updates, vault save (write-once under raw/chats/<source>/, no overwrite, traversal
rejected), and Proposal Queue aggregation. Storage paths are redirected into tmp_path
so no real backend data or vault is touched.
"""

import json
from pathlib import Path

import pytest

from app import consolidation
from app.proposals import list_normalized_proposals


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    """Point the drafts store at a temp dir for every test."""
    cdir = tmp_path / "consolidation"
    monkeypatch.setattr(consolidation, "CONSOLIDATION_DIR", cdir)
    monkeypatch.setattr(consolidation, "DRAFTS_FILE", cdir / "drafts.json")
    yield


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    v.mkdir()
    return v


def _mk(**kw):
    base = dict(
        source_tool="chatgpt",
        conversation_title="My Conversation Title",
        domain="project",
        entity="JARVIS",
        transcript="user: hi\nassistant: hello",
        summary=None,
        decisions=None,
        action_items=None,
        code_or_files_referenced=None,
    )
    base.update(kw)
    return consolidation.create_draft(**base)


# ── create / validation ─────────────────────────────────────────────────────────

def test_create_basic_no_vault_write(vault):
    d = _mk()
    assert d.status == "draft"
    assert d.saved_path is None
    # No file written anywhere under the vault by creating a draft.
    assert list(vault.rglob("*")) == []


def test_create_requires_transcript():
    with pytest.raises(ValueError):
        _mk(transcript="   ")


def test_create_requires_title():
    with pytest.raises(ValueError):
        _mk(conversation_title="")


def test_create_rejects_bad_tool():
    with pytest.raises(ValueError):
        _mk(source_tool="grok")


def test_create_rejects_bad_domain():
    with pytest.raises(ValueError):
        _mk(domain="space")


def test_fallback_summary_when_missing():
    d = _mk(summary=None)
    assert "No summary was provided" in d.summary
    assert "no AI used" in d.summary


def test_user_summary_preserved():
    d = _mk(summary="A concise human summary.")
    assert d.summary == "A concise human summary."


# ── destination mapping ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("tool,sub", [
    ("chatgpt",     "raw/chats/chatgpt/"),
    ("claude",      "raw/chats/claude/"),
    ("claude-code", "raw/chats/claude-code/"),
    ("opencode",    "raw/chats/opencode/"),
    ("other",       "raw/chats/other/"),
])
def test_destination_mapping(tool, sub):
    d = _mk(source_tool=tool, conversation_title="Hello World")
    assert d.proposed_destination.startswith(sub)
    assert d.proposed_destination.endswith("-hello-world.md")


# ── list / get ──────────────────────────────────────────────────────────────────

def test_list_newest_first_and_get():
    a = _mk(conversation_title="First")
    b = _mk(conversation_title="Second")
    drafts = consolidation.list_drafts()
    assert {x.id for x in drafts} == {a.id, b.id}
    assert consolidation.get_draft(a.id).conversation_title == "First"
    assert consolidation.get_draft("nope") is None


# ── update editable fields ──────────────────────────────────────────────────────

def test_update_editable_fields():
    d = _mk()
    updated = consolidation.update_draft(d.id, {
        "summary": "edited summary",
        "decisions": ["use FastAPI", "  ", "skip MCP"],
        "domain": "research",
        "entity": "  Brain UI  ",
    })
    assert updated.summary == "edited summary"
    assert updated.decisions == ["use FastAPI", "skip MCP"]  # blank dropped, trimmed
    assert updated.domain == "research"
    assert updated.entity == "Brain UI"


def test_update_rejects_bad_domain():
    d = _mk()
    with pytest.raises(ValueError):
        consolidation.update_draft(d.id, {"domain": "space"})


def test_update_ignores_locked_fields():
    d = _mk()
    original_tool = d.source_tool
    original_transcript = d.transcript
    updated = consolidation.update_draft(d.id, {
        "source_tool": "opencode",
        "transcript": "tampered",
        "status": "saved",
        "summary": "ok",
    })
    assert updated.source_tool == original_tool
    assert updated.transcript == original_transcript
    assert updated.status == "draft"
    assert updated.summary == "ok"


def test_update_missing_returns_none():
    assert consolidation.update_draft("nope", {"summary": "x"}) is None


# ── save to vault ───────────────────────────────────────────────────────────────

def test_save_writes_markdown_under_raw_chats(vault):
    d = _mk(source_tool="chatgpt", conversation_title="My Notes",
            summary="Key summary.", decisions=None, action_items=None)
    saved, info = consolidation.save_draft(d.id, str(vault))

    assert saved.status == "saved"
    assert saved.saved_path.startswith("raw/chats/chatgpt/")
    written = vault / saved.saved_path
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert "# My Notes" in text
    assert "- Source tool: ChatGPT" in text
    assert "## Summary" in text
    assert "Key summary." in text
    assert "## Original Transcript" in text
    assert "user: hi" in text


def test_save_marks_draft_saved_in_store(vault):
    d = _mk()
    consolidation.save_draft(d.id, str(vault))
    assert consolidation.get_draft(d.id).status == "saved"


def test_save_twice_rejected(vault):
    d = _mk()
    consolidation.save_draft(d.id, str(vault))
    with pytest.raises(ValueError):
        consolidation.save_draft(d.id, str(vault))


def test_save_never_overwrites(vault):
    d = _mk(source_tool="chatgpt", conversation_title="Dup Title")
    # Pre-create the exact proposed file with sentinel content.
    target = vault / d.proposed_destination
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("SENTINEL", encoding="utf-8")

    saved, _ = consolidation.save_draft(d.id, str(vault))
    assert (vault / saved.saved_path) != target          # got a suffixed name
    assert target.read_text(encoding="utf-8") == "SENTINEL"  # original untouched


def test_save_rejects_tampered_source_tool(vault):
    d = _mk()
    # Tamper the stored source tool to attempt traversal; save must reject it.
    raw = json.loads(consolidation.DRAFTS_FILE.read_text(encoding="utf-8"))
    raw[0]["sourceTool"] = "../../evil"
    consolidation.DRAFTS_FILE.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        consolidation.save_draft(d.id, str(vault))


def test_save_missing_vault_rejected(tmp_path):
    d = _mk()
    with pytest.raises(ValueError):
        consolidation.save_draft(d.id, str(tmp_path / "does-not-exist"))


def test_save_transcript_with_backticks_is_fenced(vault):
    d = _mk(transcript="```python\nprint('hi')\n```")
    saved, _ = consolidation.save_draft(d.id, str(vault))
    text = (vault / saved.saved_path).read_text(encoding="utf-8")
    # A fence longer than the inner triple-backtick run is used so it stays one block.
    assert "````text" in text


# ── Proposal Queue integration ──────────────────────────────────────────────────

def test_proposals_include_unsaved_draft():
    d = _mk(conversation_title="Aggregate Me")
    items, errors = list_normalized_proposals()
    mine = [i for i in items if i["relatedId"] == d.id]
    assert errors == []
    assert len(mine) == 1
    it = mine[0]
    assert it["source"] == "chat-consolidation"
    assert it["type"] == "chat_consolidation"
    assert it["riskLevel"] == "medium"
    assert it["status"] == "pending"
    assert it["title"] == "Aggregate Me"
    assert it["actions"] == ["open_consolidation"]
    assert it["targetPath"].startswith("raw/chats/chatgpt/")


def test_proposals_saved_draft_is_applied(vault):
    d = _mk()
    consolidation.save_draft(d.id, str(vault))
    items, _ = list_normalized_proposals()
    it = next(i for i in items if i["relatedId"] == d.id)
    assert it["status"] == "applied"
    assert it["targetPath"].startswith("raw/chats/")


def test_listing_proposals_writes_nothing(vault):
    _mk()
    before = sorted(p.name for p in vault.rglob("*"))
    list_normalized_proposals()
    after = sorted(p.name for p in vault.rglob("*"))
    assert before == after == []
