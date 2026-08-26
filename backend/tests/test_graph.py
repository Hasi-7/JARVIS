"""D3d vault graph / Graphify viewer tests.

Graphs are derived from temp vaults. Nothing here writes to a vault, runs a
shell, or calls the brain CLI.
"""

import json
from pathlib import Path

import pytest

from app import graph as g


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "wiki").mkdir(parents=True)
    (root / "wiki" / "rust.md").write_text(
        "# Rust\n\nSee [[ownership]] and [[borrowing|the borrow checker]].\n",
        encoding="utf-8",
    )
    (root / "wiki" / "ownership.md").write_text(
        "# Ownership\n\nRelated: [[rust]].\n", encoding="utf-8",
    )
    (root / "wiki" / "orphan.md").write_text("# Orphan\n\nNo links here.\n", encoding="utf-8")
    return root


# ══════════════════════════════════════════════════════════════════════════════
# Read-only guarantee
# ══════════════════════════════════════════════════════════════════════════════

def test_building_writes_nothing_into_the_vault(vault):
    before = {p: p.stat().st_mtime for p in vault.rglob("*")}
    g.build_graph(str(vault))
    after = {p: p.stat().st_mtime for p in vault.rglob("*")}
    assert before.keys() == after.keys()
    assert list(vault.rglob("*.json")) == []


def test_module_runs_no_shell_or_brain():
    source = Path(g.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "run_brain_command", "os.system", "eval(", "exec("):
        assert forbidden not in source


def test_missing_vault_path_rejected():
    with pytest.raises(g.GraphError, match="not configured"):
        g.build_graph("")


def test_nonexistent_vault_rejected(tmp_path):
    with pytest.raises(g.GraphError, match="does not exist"):
        g.build_graph(str(tmp_path / "nope"))


# ══════════════════════════════════════════════════════════════════════════════
# Wikilink extraction
# ══════════════════════════════════════════════════════════════════════════════

def test_extracts_plain_alias_and_heading_links():
    links = g.extract_links("[[one]] [[two|alias]] [[three#section]]")
    assert links == ["one", "two", "three"]


def test_ignores_links_inside_code_fences():
    """A wikilink in a code sample is sample text, not a link."""
    text = "real [[yes]]\n\n```\nnot a link [[no]]\n```\n"
    assert g.extract_links(text) == ["yes"]


def test_ignores_links_inside_inline_code():
    assert g.extract_links("`[[no]]` but [[yes]]") == ["yes"]


def test_empty_and_malformed_links_ignored():
    assert g.extract_links("[[]] [[   ]] [not a link] [[ok]]") == ["ok"]


# ══════════════════════════════════════════════════════════════════════════════
# Graph shape
# ══════════════════════════════════════════════════════════════════════════════

def test_nodes_and_edges_are_built(vault):
    result = g.build_graph(str(vault))
    ids = {n["id"] for n in result["nodes"]}
    assert {"rust", "ownership", "borrowing", "orphan"} <= ids
    pairs = {(e["source"], e["target"]) for e in result["edges"]}
    assert ("rust", "ownership") in pairs
    assert ("ownership", "rust") in pairs


def test_dangling_links_become_nodes(vault):
    """`borrowing` has no file; hiding it would misrepresent the graph."""
    result = g.build_graph(str(vault))
    borrowing = {n["id"]: n for n in result["nodes"]}["borrowing"]
    assert borrowing["exists"] is False
    assert borrowing["path"] is None
    assert result["stats"]["dangling"] == 1


def test_orphans_are_counted(vault):
    result = g.build_graph(str(vault))
    assert result["stats"]["orphans"] == 1        # orphan.md


def test_degrees_are_computed(vault):
    nodes = {n["id"]: n for n in g.build_graph(str(vault))["nodes"]}
    assert nodes["rust"]["outDegree"] == 2
    assert nodes["rust"]["inDegree"] == 1
    assert nodes["borrowing"]["inDegree"] == 1


def test_self_links_are_ignored(tmp_path):
    root = tmp_path / "v"
    root.mkdir()
    (root / "a.md").write_text("[[a]] [[b]]", encoding="utf-8")
    edges = g.build_graph(str(root))["edges"]
    assert all(e["source"] != e["target"] for e in edges)


def test_duplicate_links_produce_one_edge(tmp_path):
    root = tmp_path / "v"
    root.mkdir()
    (root / "a.md").write_text("[[b]] [[b]] [[b]]", encoding="utf-8")
    assert len(g.build_graph(str(root))["edges"]) == 1


def test_link_resolution_is_case_insensitive(tmp_path):
    root = tmp_path / "v"
    root.mkdir()
    (root / "Note.md").write_text("x", encoding="utf-8")
    (root / "other.md").write_text("[[note]]", encoding="utf-8")
    result = g.build_graph(str(root))
    note = {n["id"]: n for n in result["nodes"]}["note"]
    assert note["exists"] is True          # resolved to Note.md, not a dangling link


def test_empty_vault_yields_empty_graph(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    result = g.build_graph(str(root))
    assert result["nodes"] == []
    assert result["edges"] == []


def test_source_is_reported(vault):
    assert g.build_graph(str(vault))["source"] == "vault-wikilinks"


# ══════════════════════════════════════════════════════════════════════════════
# Bounds
# ══════════════════════════════════════════════════════════════════════════════

def test_file_cap_truncates_honestly(vault, monkeypatch):
    monkeypatch.setattr(g, "MAX_FILES", 1)
    result = g.build_graph(str(vault))
    assert result["stats"]["truncated"] is True
    assert any("truncated" in w.lower() for w in result["warnings"])


def test_edge_cap_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "MAX_EDGES", 2)
    root = tmp_path / "v"
    root.mkdir()
    (root / "a.md").write_text(" ".join(f"[[n{i}]]" for i in range(50)), encoding="utf-8")
    assert len(g.build_graph(str(root))["edges"]) <= 2


def test_oversized_files_skipped(vault, monkeypatch):
    monkeypatch.setattr(g, "MAX_FILE_BYTES", 5)
    assert g.build_graph(str(vault))["stats"]["files"] == 0


def test_labels_are_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "MAX_LABEL_CHARS", 10)
    root = tmp_path / "v"
    root.mkdir()
    (root / "a.md").write_text("[[" + "x" * 500 + "]]", encoding="utf-8")
    assert all(len(n["label"]) <= 11 for n in g.build_graph(str(root))["nodes"])


# ══════════════════════════════════════════════════════════════════════════════
# External export
# ══════════════════════════════════════════════════════════════════════════════

def _export(tmp_path, payload, name="graph.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_node_link_export_is_read(tmp_path):
    path = _export(tmp_path, {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b"}],
        "links": [{"source": "a", "target": "b"}],
    })
    result = g.load_export(path)
    assert {n["id"] for n in result["nodes"]} == {"a", "b"}
    assert result["edges"] == [{"source": "a", "target": "b"}]
    assert result["source"] == "external-export"


def test_edges_key_is_also_accepted(tmp_path):
    path = _export(tmp_path, {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"from": "a", "to": "b"}],
    })
    assert g.load_export(path)["edges"] == [{"source": "a", "target": "b"}]


def test_edges_to_unknown_nodes_are_dropped(tmp_path):
    path = _export(tmp_path, {
        "nodes": [{"id": "a"}],
        "links": [{"source": "a", "target": "ghost"}],
    })
    assert g.load_export(path)["edges"] == []


def test_unrecognized_shape_is_reported_not_guessed(tmp_path):
    """Rendering an unknown format as if it were understood would be worse."""
    path = _export(tmp_path, {"something": "else"})
    with pytest.raises(g.GraphError, match="Unrecognized graph export shape"):
        g.load_export(path)


def test_invalid_json_is_reported(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(g.GraphError, match="not valid JSON"):
        g.load_export(str(path))


def test_missing_export_is_reported(tmp_path):
    with pytest.raises(g.GraphError, match="not found"):
        g.load_export(str(tmp_path / "nope.json"))


def test_empty_export_path_rejected():
    with pytest.raises(g.GraphError, match="No graph export path"):
        g.load_export("")


def test_oversized_export_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "MAX_EXPORT_BYTES", 10)
    path = _export(tmp_path, {"nodes": [{"id": "a"}], "links": []})
    with pytest.raises(g.GraphError, match="too large"):
        g.load_export(path)


def test_non_object_root_rejected(tmp_path):
    path = _export(tmp_path, [1, 2, 3])
    with pytest.raises(g.GraphError, match="must be a JSON object"):
        g.load_export(path)


# ══════════════════════════════════════════════════════════════════════════════
# Endpoint
# ══════════════════════════════════════════════════════════════════════════════

def test_graph_endpoint_builds_from_vault(vault, monkeypatch):
    import app.main as m

    class Cfg:
        vault_path = str(vault)      # matches RuntimeConfig

    monkeypatch.setattr(m, "get_config", lambda: Cfg())
    res = m.vault_graph()
    assert res.source == "vault-wikilinks"
    assert res.stats.nodes > 0
    assert any(n.exists is False for n in res.nodes)     # dangling link surfaced


def test_graph_endpoint_reads_an_export(tmp_path, monkeypatch):
    import app.main as m

    path = _export(tmp_path, {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "links": [{"source": "a", "target": "b"}],
    })
    res = m.vault_graph(exportPath=path)
    assert res.source == "external-export"
    assert len(res.edges) == 1


def test_graph_endpoint_reports_bad_export(tmp_path):
    from fastapi import HTTPException
    import app.main as m

    path = _export(tmp_path, {"something": "else"})
    with pytest.raises(HTTPException) as exc:
        m.vault_graph(exportPath=path)
    assert exc.value.status_code == 400


def test_same_named_notes_collapse_and_are_reported(tmp_path):
    """Obsidian resolves links by name, so same-named notes are one node —
    but the collapse must be visible, not silent."""
    root = tmp_path / "v"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir(parents=True)
    (root / "a" / "index.md").write_text("one", encoding="utf-8")
    (root / "b" / "index.md").write_text("two", encoding="utf-8")

    result = g.build_graph(str(root))
    index = {n["id"]: n for n in result["nodes"]}["index"]
    assert index["fileCount"] == 2
    assert result["stats"]["collapsed"] == 1
    assert any("share a note name" in w for w in result["warnings"])


def test_no_collapse_reported_when_names_are_unique(vault):
    result = g.build_graph(str(vault))
    assert result["stats"]["collapsed"] == 0
    assert not any("share a note name" in w for w in result["warnings"])
