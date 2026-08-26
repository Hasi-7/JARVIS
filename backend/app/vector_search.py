"""
Local semantic vault search (D3) — READ-ONLY, ON-DEVICE.

Indexes the Obsidian vault's Markdown and answers similarity queries.

    build_index(vault_path)      -> {chunks, files, embedded, degraded}
    search(query, limit)         -> [{path, heading, score, snippet}]
    index_status()               -> index freshness + backend in use

Safety model (this module never relaxes it):
- READ-ONLY ON THE VAULT. It opens Markdown files for reading and never writes,
  moves, or deletes anything there. The index lives in backend app-data.
- ON-DEVICE. Embeddings come from the already-configured local Ollama instance.
  No cloud embedding API is called, and no vault text leaves the machine.
- DEGRADES HONESTLY. If no embedding model is available, search falls back to a
  deterministic lexical score and REPORTS `degraded: true` rather than pretending
  the results are semantic.
- Vault content is treated as the user's own data, but query strings are untrusted
  input: they are never executed and never interpolated into a path.
- Indexing is bounded: file count, file size, chunk count, and chunk length are
  all capped so a huge vault cannot exhaust memory.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

INDEX_DIR: Path = Path(__file__).parent.parent / "data" / "vector-index"
INDEX_FILE: Path = INDEX_DIR / "index.json"

EMBED_MODEL_ENV = "BRAIN_UI_EMBED_MODEL"
DEFAULT_EMBED_MODEL = "nomic-embed-text"

MAX_FILES = 5_000
MAX_FILE_BYTES = 1_000_000
MAX_CHUNKS = 20_000
CHUNK_CHARS = 1_200
CHUNK_OVERLAP = 150
MAX_QUERY_CHARS = 500
DEFAULT_LIMIT = 10
MAX_LIMIT = 50
MAX_SNIPPET_CHARS = 400

_lock = threading.Lock()

_WORD_RE = re.compile(r"[a-z0-9']+")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


class VectorSearchError(ValueError):
    """Raised when indexing or searching cannot proceed."""


# ══════════════════════════════════════════════════════════════════════════════
# Chunking
# ══════════════════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def chunk_markdown(text: str, *, chunk_chars: int = CHUNK_CHARS) -> List[dict]:
    """Split Markdown into overlapping chunks, tracking the nearest heading."""
    if not (text or "").strip():
        return []

    lines = (text or "").splitlines()
    chunks: List[dict] = []
    heading = ""
    buffer: List[str] = []
    size = 0

    def flush() -> None:
        nonlocal buffer, size
        body = "\n".join(buffer).strip()
        if body:
            chunks.append({"heading": heading, "text": body[:chunk_chars * 2]})
        # Keep a tail for overlap so a match spanning a boundary is still findable.
        tail = body[-CHUNK_OVERLAP:] if len(body) > CHUNK_OVERLAP else ""
        buffer = [tail] if tail else []
        size = len(tail)

    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            flush()
            heading = match.group(2).strip()[:200]
        buffer.append(line)
        size += len(line) + 1
        if size >= chunk_chars:
            flush()

    flush()
    return chunks


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


# ══════════════════════════════════════════════════════════════════════════════
# Embeddings (local Ollama)
# ══════════════════════════════════════════════════════════════════════════════

def embed_texts(
    texts: List[str],
    *,
    env: Optional[dict] = None,
    embedder: Optional[Callable[[List[str]], List[List[float]]]] = None,
) -> Optional[List[List[float]]]:
    """Embed texts with the local model. Returns None when unavailable.

    Never raises: an unavailable embedding backend degrades to lexical search
    rather than failing the whole index.
    """
    if embedder is not None:
        try:
            return embedder(texts)
        except Exception as exc:
            logger.warning("Injected embedder failed; degrading to lexical: %s", exc)
            return None

    try:
        import json as _json
        import os as _os
        import urllib.request

        source = _os.environ if env is None else env
        base = (source.get("BRAIN_UI_OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        model = (source.get(EMBED_MODEL_ENV) or DEFAULT_EMBED_MODEL).strip()

        vectors: List[List[float]] = []
        for text in texts:
            payload = _json.dumps({"model": model, "prompt": text[:8000]}).encode("utf-8")
            request = urllib.request.Request(
                f"{base}/api/embeddings", data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                body = _json.loads(response.read().decode("utf-8"))
            vector = body.get("embedding")
            if not isinstance(vector, list) or not vector:
                return None
            vectors.append([float(v) for v in vector])
        return vectors
    except Exception as exc:
        logger.info("Local embeddings unavailable (%s); using lexical search.", type(exc).__name__)
        return None


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def lexical_score(query_tokens: List[str], chunk_tokens: Dict[str, int]) -> float:
    """Deterministic overlap score used when embeddings are unavailable."""
    if not query_tokens or not chunk_tokens:
        return 0.0
    total = sum(chunk_tokens.values()) or 1
    hits = sum(chunk_tokens.get(token, 0) for token in set(query_tokens))
    coverage = sum(1 for token in set(query_tokens) if token in chunk_tokens) / len(set(query_tokens))
    return (hits / total) * 0.5 + coverage * 0.5


# ══════════════════════════════════════════════════════════════════════════════
# Index
# ══════════════════════════════════════════════════════════════════════════════

def _read_index() -> dict:
    if not INDEX_FILE.exists():
        return {"chunks": [], "builtAt": None, "embedded": False, "vaultPath": None}
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise VectorSearchError(f"Corrupted vector index: {exc}") from exc


def _write_index(index: dict) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


def build_index(
    vault_path: str,
    *,
    env: Optional[dict] = None,
    embedder: Optional[Callable[[List[str]], List[List[float]]]] = None,
) -> dict:
    """Index the vault's Markdown. Reads only; writes nothing into the vault."""
    root = Path((vault_path or "").strip())
    if not (vault_path or "").strip():
        raise VectorSearchError("Vault path is not configured. Set it in Settings.")
    if not root.is_dir():
        raise VectorSearchError(f"Vault path does not exist: {vault_path}")

    resolved_root = root.resolve()
    chunks: List[dict] = []
    files_seen = 0

    for path in sorted(resolved_root.rglob("*.md")):
        if files_seen >= MAX_FILES or len(chunks) >= MAX_CHUNKS:
            break
        try:
            if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                continue
            # Never follow a symlink out of the vault.
            if not str(path.resolve()).startswith(str(resolved_root)):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        files_seen += 1
        relative = path.relative_to(resolved_root).as_posix()
        for chunk in chunk_markdown(text):
            if len(chunks) >= MAX_CHUNKS:
                break
            tokens = _tokenize(chunk["text"])
            counts: Dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            chunks.append({
                "path": relative,
                "heading": chunk["heading"],
                "text": chunk["text"],
                "tokens": counts,
            })

    vectors = embed_texts([c["text"] for c in chunks], env=env, embedder=embedder) if chunks else None
    embedded = vectors is not None and len(vectors) == len(chunks)
    if embedded:
        for chunk, vector in zip(chunks, vectors):
            chunk["vector"] = vector

    index = {
        "chunks": chunks,
        "builtAt": _now(),
        "embedded": embedded,
        "vaultPath": str(resolved_root),
    }
    with _lock:
        _write_index(index)

    logger.info(
        "Vault index built: %d file(s), %d chunk(s), embedded=%s (vault read-only)",
        files_seen, len(chunks), embedded,
    )
    return {
        "files": files_seen,
        "chunks": len(chunks),
        "embedded": embedded,
        "degraded": not embedded,
        "builtAt": index["builtAt"],
    }


def index_status() -> dict:
    with _lock:
        index = _read_index()
    return {
        "built": bool(index.get("builtAt")),
        "builtAt": index.get("builtAt"),
        "chunks": len(index.get("chunks") or []),
        "embedded": bool(index.get("embedded")),
        "degraded": not bool(index.get("embedded")),
        "vaultPath": index.get("vaultPath"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Search
# ══════════════════════════════════════════════════════════════════════════════

def _clamp_limit(limit: Optional[int]) -> int:
    try:
        value = int(limit) if limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, value))


def _snippet(text: str, query_tokens: List[str]) -> str:
    """Return the window around the first query hit, else the head of the chunk."""
    lowered = (text or "").lower()
    position = -1
    for token in query_tokens:
        found = lowered.find(token)
        if found >= 0 and (position < 0 or found < position):
            position = found
    if position < 0:
        return (text or "")[:MAX_SNIPPET_CHARS]
    start = max(0, position - MAX_SNIPPET_CHARS // 3)
    return ("…" if start > 0 else "") + text[start:start + MAX_SNIPPET_CHARS].strip()


def search(
    query: str,
    limit: Optional[int] = None,
    *,
    env: Optional[dict] = None,
    embedder: Optional[Callable[[List[str]], List[List[float]]]] = None,
) -> dict:
    """Search the built index. Returns {results, degraded, ...}."""
    text = (query or "").strip()
    if not text:
        raise VectorSearchError("A search query is required.")
    if len(text) > MAX_QUERY_CHARS:
        raise VectorSearchError(f"Query is too long (max {MAX_QUERY_CHARS} characters).")

    with _lock:
        index = _read_index()
    chunks = index.get("chunks") or []
    if not chunks:
        raise VectorSearchError("The vault index is empty. Build the index first.")

    top = _clamp_limit(limit)
    query_tokens = _tokenize(text)
    degraded = not index.get("embedded")

    query_vector: Optional[List[float]] = None
    if not degraded:
        vectors = embed_texts([text], env=env, embedder=embedder)
        if vectors and vectors[0]:
            query_vector = vectors[0]
        else:
            degraded = True    # index is semantic but the query could not be embedded

    scored: List[Tuple[float, dict]] = []
    for chunk in chunks:
        if query_vector is not None and chunk.get("vector"):
            score = cosine(query_vector, chunk["vector"])
        else:
            score = lexical_score(query_tokens, chunk.get("tokens") or {})
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = [{
        "path": chunk.get("path"),
        "heading": chunk.get("heading") or "",
        "score": round(float(score), 4),
        "snippet": _snippet(chunk.get("text") or "", query_tokens),
    } for score, chunk in scored[:top]]

    return {
        "query": text,
        "results": results,
        "count": len(results),
        "degraded": degraded,
        "mode": "lexical" if degraded else "semantic",
        "builtAt": index.get("builtAt"),
        "warnings": ([
            "No local embedding model was available, so results are lexical, not semantic. "
            f"Pull one with: ollama pull {DEFAULT_EMBED_MODEL}"
        ] if degraded else []),
    }
