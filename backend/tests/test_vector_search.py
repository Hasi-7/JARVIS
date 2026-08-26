"""D3 local vault semantic search tests.

Embeddings are injected. Nothing here calls Ollama, reaches the network, or
writes to the vault.
"""

from pathlib import Path

import pytest

from app import vector_search as vs


@pytest.fixture(autouse=True)
def _isolate_index(tmp_path, monkeypatch):
    monkeypatch.setattr(vs, "INDEX_DIR", tmp_path / "idx")
    monkeypatch.setattr(vs, "INDEX_FILE", tmp_path / "idx" / "index.json")

    # embed_texts() otherwise falls through to a live Ollama HTTP call, which would
    # make these tests depend on whether Ollama happens to be running (and slow).
    # Passing embedder=None in a test means "no embeddings available".
    real_embed = vs.embed_texts

    def hermetic_embed(texts, *, env=None, embedder=None):
        if embedder is None:
            return None
        return real_embed(texts, env=env, embedder=embedder)

    monkeypatch.setattr(vs, "embed_texts", hermetic_embed)


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "wiki").mkdir(parents=True)
    (root / "wiki" / "rust.md").write_text(
        "# Rust\n\nOwnership means each value has a single owner.\n\n"
        "## Borrowing\n\nBorrowing lends a reference without moving ownership.\n",
        encoding="utf-8",
    )
    (root / "wiki" / "python.md").write_text(
        "# Python\n\nGarbage collection reclaims unused objects automatically.\n",
        encoding="utf-8",
    )
    (root / "notes.txt").write_text("not markdown, must be ignored", encoding="utf-8")
    return root


def _fake_embedder(dim=8):
    """Deterministic hash embedding — good enough to test the plumbing."""
    def embed(texts):
        vectors = []
        for text in texts:
            vector = [0.0] * dim
            for token in vs._tokenize(text):
                vector[hash(token) % dim] += 1.0
            vectors.append(vector)
        return vectors
    return embed


# ══════════════════════════════════════════════════════════════════════════════
# Vault safety: read-only
# ══════════════════════════════════════════════════════════════════════════════

def test_indexing_writes_nothing_into_the_vault(vault):
    before = {p: p.stat().st_mtime for p in vault.rglob("*")}
    vs.build_index(str(vault), embedder=_fake_embedder())
    after = {p: p.stat().st_mtime for p in vault.rglob("*")}
    assert before.keys() == after.keys()
    assert list(vault.rglob("index.json")) == []


def test_module_never_writes_or_shells():
    source = Path(vs.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "shutil.rmtree", "unlink("):
        assert forbidden not in source


def test_only_markdown_is_indexed(vault):
    vs.build_index(str(vault), embedder=_fake_embedder())
    result = vs.search("markdown ignored", embedder=_fake_embedder())
    assert all(r["path"].endswith(".md") for r in result["results"])


def test_missing_vault_path_rejected():
    with pytest.raises(vs.VectorSearchError, match="not configured"):
        vs.build_index("")


def test_nonexistent_vault_rejected(tmp_path):
    with pytest.raises(vs.VectorSearchError, match="does not exist"):
        vs.build_index(str(tmp_path / "nope"))


# ══════════════════════════════════════════════════════════════════════════════
# Chunking
# ══════════════════════════════════════════════════════════════════════════════

def test_chunking_tracks_headings():
    chunks = vs.chunk_markdown("# Top\n\nalpha\n\n## Sub\n\nbeta\n")
    headings = [c["heading"] for c in chunks]
    assert "Top" in headings or "Sub" in headings


def test_chunking_handles_empty_text():
    assert vs.chunk_markdown("") == []
    assert vs.chunk_markdown("   \n  ") == []


def test_long_document_produces_multiple_chunks():
    text = "\n".join(f"line {i} with some filler words" for i in range(500))
    assert len(vs.chunk_markdown(text, chunk_chars=400)) > 1


def test_chunk_count_is_capped(vault, monkeypatch):
    monkeypatch.setattr(vs, "MAX_CHUNKS", 2)
    stats = vs.build_index(str(vault), embedder=_fake_embedder())
    assert stats["chunks"] <= 2


def test_oversized_files_are_skipped(vault, monkeypatch):
    monkeypatch.setattr(vs, "MAX_FILE_BYTES", 10)
    stats = vs.build_index(str(vault), embedder=_fake_embedder())
    assert stats["files"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# Semantic path
# ══════════════════════════════════════════════════════════════════════════════

def test_index_reports_embedded_when_embeddings_available(vault):
    stats = vs.build_index(str(vault), embedder=_fake_embedder())
    assert stats["embedded"] is True
    assert stats["degraded"] is False


def test_search_is_semantic_when_embedded(vault):
    vs.build_index(str(vault), embedder=_fake_embedder())
    result = vs.search("ownership", embedder=_fake_embedder())
    assert result["mode"] == "semantic"
    assert result["degraded"] is False
    assert result["count"] > 0


def test_search_finds_the_relevant_file(vault):
    vs.build_index(str(vault), embedder=None)     # lexical, deterministic
    result = vs.search("borrowing reference", embedder=None)
    assert result["results"][0]["path"].endswith("rust.md")


def test_cosine_basics():
    assert vs.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert vs.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert vs.cosine([], [1]) == 0.0
    assert vs.cosine([0, 0], [0, 0]) == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Honest degradation
# ══════════════════════════════════════════════════════════════════════════════

def test_index_degrades_when_no_embedder(vault):
    stats = vs.build_index(str(vault), embedder=None)
    assert stats["embedded"] is False
    assert stats["degraded"] is True


def test_search_reports_lexical_mode_honestly(vault):
    vs.build_index(str(vault), embedder=None)
    result = vs.search("ownership", embedder=None)
    assert result["mode"] == "lexical"
    assert result["degraded"] is True
    assert any("lexical, not semantic" in w for w in result["warnings"])


def test_failing_embedder_degrades_instead_of_raising(vault):
    def boom(texts):
        raise RuntimeError("ollama down")

    stats = vs.build_index(str(vault), embedder=boom)
    assert stats["degraded"] is True


def test_embed_texts_returns_none_on_failure():
    def boom(texts):
        raise RuntimeError("nope")

    assert vs.embed_texts(["x"], embedder=boom) is None


def test_semantic_index_with_unembeddable_query_degrades(vault):
    vs.build_index(str(vault), embedder=_fake_embedder())

    def boom(texts):
        raise RuntimeError("embedding died")

    result = vs.search("ownership", embedder=boom)
    assert result["degraded"] is True
    assert result["mode"] == "lexical"


# ══════════════════════════════════════════════════════════════════════════════
# Query handling
# ══════════════════════════════════════════════════════════════════════════════

def test_empty_query_rejected(vault):
    vs.build_index(str(vault), embedder=None)
    with pytest.raises(vs.VectorSearchError, match="query is required"):
        vs.search("  ", embedder=None)


def test_overlong_query_rejected(vault):
    vs.build_index(str(vault), embedder=None)
    with pytest.raises(vs.VectorSearchError, match="too long"):
        vs.search("x" * 5000, embedder=None)


def test_search_without_index_raises():
    with pytest.raises(vs.VectorSearchError, match="index is empty"):
        vs.search("anything", embedder=None)


def test_limit_is_clamped(vault):
    vs.build_index(str(vault), embedder=None)
    assert len(vs.search("the", 9999, embedder=None)["results"]) <= vs.MAX_LIMIT
    assert len(vs.search("the", 0, embedder=None)["results"]) <= 1


def test_query_is_never_used_as_a_path(vault):
    """A path-shaped query must be treated as text, not a filesystem reference."""
    vs.build_index(str(vault), embedder=None)
    result = vs.search("../../../etc/passwd", embedder=None)
    assert isinstance(result["results"], list)      # no traversal, no crash


def test_snippet_is_bounded(vault):
    vs.build_index(str(vault), embedder=None)
    for hit in vs.search("ownership", embedder=None)["results"]:
        assert len(hit["snippet"]) <= vs.MAX_SNIPPET_CHARS + 2


# ══════════════════════════════════════════════════════════════════════════════
# Status
# ══════════════════════════════════════════════════════════════════════════════

def test_status_before_and_after_build(vault):
    assert vs.index_status()["built"] is False
    vs.build_index(str(vault), embedder=_fake_embedder())
    status = vs.index_status()
    assert status["built"] is True
    assert status["chunks"] > 0
    assert status["embedded"] is True


def test_corrupted_index_raises_clearly(vault):
    vs.build_index(str(vault), embedder=None)
    vs.INDEX_FILE.write_text("{not json", encoding="utf-8")
    with pytest.raises(vs.VectorSearchError, match="Corrupted"):
        vs.index_status()
