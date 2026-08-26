"""Frontmatter read/write for Obsidian wiki notes.

Two properties carry the weight here: parsing must never raise (these notes are
hand-edited and break often), and writing must be surgical (a safe_load/safe_dump
round-trip would silently reformat a file the user maintains by hand).
"""

import pytest

from app.frontmatter import read_frontmatter, write_frontmatter, get_str


NOTE_WITH_FM = """---
domain: project
status: active
repo_path: D:\\Hasnain\\dev\\JARVIS
---

# Brain UI

Body text.
"""

NOTE_WITHOUT_FM = """# Brain UI

Body text stays exactly here.
"""


# ── reading ───────────────────────────────────────────────────────────────────

def test_reads_keys_and_body():
    r = read_frontmatter(NOTE_WITH_FM)
    assert r.error is None
    assert r.had_block is True
    assert r.data["domain"] == "project"
    assert r.body.startswith("\n# Brain UI")


def test_note_without_frontmatter_is_all_body():
    r = read_frontmatter(NOTE_WITHOUT_FM)
    assert r.data == {}
    assert r.had_block is False
    assert r.body == NOTE_WITHOUT_FM


@pytest.mark.parametrize("text", [
    "---\nkey: [unclosed\n---\nbody",          # malformed YAML
    "---\n\tkey: value\n---\nbody",            # tab indentation
    "---\na: 1\n b: 2\n---\nbody",             # bad indentation
])
def test_malformed_yaml_never_raises(text):
    """One bad note must degrade one entity card, not 500 the endpoint."""
    r = read_frontmatter(text)
    assert r.error is not None
    assert r.data == {}


def test_a_scalar_document_is_reported_not_guessed():
    r = read_frontmatter("---\njust a string\n---\nbody")
    assert r.error is not None
    assert "mapping" in r.error


def test_unclosed_block_is_treated_as_body():
    """Guessing where an unterminated block ends could swallow note content."""
    text = "---\ndomain: project\n\n# Heading\n"
    r = read_frontmatter(text)
    assert r.had_block is False
    assert r.body == text


def test_a_horizontal_rule_is_not_frontmatter():
    text = "# Title\n\n---\n\nMore text.\n"
    r = read_frontmatter(text)
    assert r.had_block is False
    assert r.body == text


def test_oversized_frontmatter_is_refused():
    r = read_frontmatter("---\n" + ("k: v\n" * 40_000) + "---\nbody")
    assert r.error is not None


# ── get_str ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", ["repo_path", "repo-path", "repoPath"])
def test_accepts_the_spellings_a_human_would_write(key):
    r = read_frontmatter(f"---\n{key}: D:/x\n---\nbody")
    assert get_str(r, "repo_path") == "D:/x"


def test_ignores_structured_values_rather_than_stringifying_them():
    r = read_frontmatter("---\nstatus:\n  - a\n  - b\n---\nbody")
    assert get_str(r, "status") is None


def test_renders_dates_and_bools_readably():
    r = read_frontmatter("---\ncreated: 2026-08-26\narchived: true\n---\nbody")
    assert get_str(r, "created") == "2026-08-26"
    assert get_str(r, "archived") == "true"


# ── writing ───────────────────────────────────────────────────────────────────

def test_updates_only_the_named_key():
    out = write_frontmatter(NOTE_WITH_FM, {"status": "archived"})
    r = read_frontmatter(out)
    assert r.data["status"] == "archived"
    assert r.data["domain"] == "project"          # untouched
    assert r.data["repo_path"] == "D:\\Hasnain\\dev\\JARVIS"
    assert "Body text." in out


def test_preserves_comments_key_order_and_unknown_keys():
    """The whole point of a surgical write: this file is hand-maintained."""
    note = (
        "---\n"
        "# a comment the user wrote\n"
        "zzz_last: keep\n"
        "domain: project\n"
        "some_unknown_plugin_key: 42\n"
        "---\n"
        "body\n"
    )
    out = write_frontmatter(note, {"domain": "course"})
    assert "# a comment the user wrote" in out
    assert "some_unknown_plugin_key: 42" in out
    # Order preserved: zzz_last still precedes domain.
    assert out.index("zzz_last") < out.index("domain")


def test_adds_a_block_to_a_note_that_had_none_without_eating_the_body():
    out = write_frontmatter(NOTE_WITHOUT_FM, {"domain": "project"})
    assert out.startswith("---\ndomain: project\n---\n")
    assert "Body text stays exactly here." in out
    assert read_frontmatter(out).data["domain"] == "project"


def test_none_removes_a_key():
    out = write_frontmatter(NOTE_WITH_FM, {"status": None})
    r = read_frontmatter(out)
    assert "status" not in r.data
    assert r.data["domain"] == "project"


def test_refuses_to_rewrite_unparseable_frontmatter():
    """Rewriting YAML we could not parse risks destroying hand-typed data."""
    with pytest.raises(ValueError, match="Refusing to rewrite"):
        write_frontmatter("---\nkey: [unclosed\n---\nbody", {"status": "active"})


@pytest.mark.parametrize("value", [
    "true", "false", "null", "yes", "no", "123", "1.5",
    "value: with colon", "#hash", "*star", "  padded  ", "a\nb",
])
def test_values_that_would_change_meaning_are_quoted(value):
    out = write_frontmatter(NOTE_WITHOUT_FM, {"field": value})
    r = read_frontmatter(out)
    assert r.error is None, out
    # Newlines are flattened; everything else must round-trip as a string.
    expected = " ".join(value.split()) if "\n" in value else value.strip() if value.strip() != value else value
    assert str(r.data["field"]) == expected, out


def test_a_value_cannot_inject_extra_keys():
    out = write_frontmatter(NOTE_WITHOUT_FM, {"field": "x\ninjected: pwned"})
    r = read_frontmatter(out)
    assert "injected" not in r.data
    assert r.error is None


@pytest.mark.parametrize("key", ["bad key", "key:", "", "a" * 100, "../etc"])
def test_invalid_keys_are_refused(key):
    with pytest.raises(ValueError, match="Invalid frontmatter key"):
        write_frontmatter(NOTE_WITHOUT_FM, {key: "v"})


def test_round_trip_is_stable():
    once = write_frontmatter(NOTE_WITH_FM, {"status": "active"})
    twice = write_frontmatter(once, {"status": "active"})
    assert once == twice
