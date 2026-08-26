"""
Vault graph / Graphify viewer (D3d) — READ-ONLY.

    build_graph(vault_path)   -> {nodes, edges, stats}
    load_export(path)         -> a graph from an external export, if one exists

The PRD names a "Graphify viewer" (§37, MVP v10) but never defines its data
format, and `brain graphify-setup` is not in the brain allowlist, so its output
shape is unknown here. Rather than guess at that format, this module derives the
graph from a source that IS well defined: **Obsidian wikilinks**. Every `[[link]]`
between notes is an edge, which is exactly the graph an Obsidian vault already has.

If a `brain graphify-setup` export later turns out to exist, `load_export()` reads
the standard node-link JSON shape (`{"nodes": [...], "links"|"edges": [...]}`) used
by networkx / D3 / vis.js — and reports honestly when a file does not match it,
instead of silently rendering something wrong.

Safety model (this module never relaxes it):
- READ-ONLY. It opens Markdown for reading; it never writes, moves, or deletes
  anything in the vault, and runs no shell and no `brain` command.
- BOUNDED. File count, file size, node count, and edge count are all capped so a
  large vault cannot exhaust memory.
- Note titles and link text are the user's own content, but are still size-capped
  and never executed.
- An external export path is validated and size-capped before being read, and is
  never executed or imported as code.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_FILES = 5_000
MAX_FILE_BYTES = 1_000_000
MAX_NODES = 5_000
MAX_EDGES = 20_000
MAX_LABEL_CHARS = 200
MAX_EXPORT_BYTES = 8 * 1024 * 1024

# [[Note]], [[Note|alias]], [[Note#heading]] — the alias/heading are ignored for
# edge purposes, since they do not change which note is referenced.
_WIKILINK_RE = re.compile(r"\[\[([^\]\[|#]+)(?:[#|][^\]\[]*)?\]\]")
# Fenced code blocks must not contribute edges: a `[[x]]` inside a snippet is not
# a link, it is sample text.
_FENCE_RE = re.compile(r"```.*?```", re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


class GraphError(ValueError):
    """Raised when a graph cannot be built or read."""


def _truncate(value: str, limit: Optional[int] = None) -> str:
    # Resolved at call time, not bound as a default, so the cap stays configurable.
    cap = MAX_LABEL_CHARS if limit is None else limit
    text = str(value or "")
    return text if len(text) <= cap else text[:cap].rstrip() + "…"


def extract_links(text: str) -> List[str]:
    """Return wikilink targets, ignoring anything inside code fences or spans."""
    without_code = _INLINE_CODE_RE.sub(" ", _FENCE_RE.sub(" ", text or ""))
    targets: List[str] = []
    for match in _WIKILINK_RE.finditer(without_code):
        target = match.group(1).strip()
        if target:
            targets.append(target)
    return targets


def _note_key(name: str) -> str:
    """Obsidian resolves links by note name, case-insensitively."""
    return Path(str(name or "").strip()).stem.strip().lower()


# ══════════════════════════════════════════════════════════════════════════════
# Vault link graph
# ══════════════════════════════════════════════════════════════════════════════

def build_graph(vault_path: str) -> dict:
    """Derive the wikilink graph from the vault. Reads only; writes nothing."""
    if not (vault_path or "").strip():
        raise GraphError("Vault path is not configured. Set it in Settings.")
    root = Path(vault_path.strip())
    if not root.is_dir():
        raise GraphError(f"Vault path does not exist: {vault_path}")

    resolved = root.resolve()
    nodes: Dict[str, dict] = {}
    raw_edges: List[Tuple[str, str]] = []
    files_seen = 0
    truncated = False

    for path in sorted(resolved.rglob("*.md")):
        if files_seen >= MAX_FILES:
            truncated = True
            break
        try:
            if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                continue
            if not str(path.resolve()).startswith(str(resolved)):
                continue      # never follow a symlink out of the vault
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        files_seen += 1
        relative = path.relative_to(resolved).as_posix()
        key = _note_key(path.name)
        nodes.setdefault(key, {
            "id": key,
            "label": _truncate(path.stem),
            "path": relative,
            "folder": (Path(relative).parent.as_posix() if Path(relative).parent.name else ""),
            "exists": True,
            "outDegree": 0,
            "inDegree": 0,
            # Obsidian resolves wikilinks by NAME, so same-named notes in different
            # folders are one link target and therefore one node. That collapse is
            # correct for link semantics but would misrepresent the vault if hidden,
            # so the count is surfaced rather than silently dropped.
            "fileCount": 0,
        })
        nodes[key]["path"] = relative
        nodes[key]["exists"] = True
        nodes[key]["fileCount"] += 1

        for target in extract_links(text):
            if len(raw_edges) >= MAX_EDGES:
                truncated = True
                break
            target_key = _note_key(target)
            if not target_key or target_key == key:
                continue      # ignore self-links
            raw_edges.append((key, target_key))

    # Link targets that have no file of their own are real graph members: they are
    # the vault's dangling links, and hiding them would misrepresent the graph.
    for source, target in raw_edges:
        if target not in nodes:
            if len(nodes) >= MAX_NODES:
                truncated = True
                continue
            nodes[target] = {
                "id": target, "label": _truncate(target), "path": None,
                "folder": "", "exists": False, "outDegree": 0, "inDegree": 0,
                "fileCount": 0,
            }

    edges: List[dict] = []
    seen: set = set()
    for source, target in raw_edges:
        if target not in nodes or source not in nodes:
            continue
        pair = (source, target)
        if pair in seen:
            continue
        seen.add(pair)
        edges.append({"source": source, "target": target})
        nodes[source]["outDegree"] += 1
        nodes[target]["inDegree"] += 1

    node_list = sorted(nodes.values(), key=lambda n: (-n["inDegree"], n["id"]))
    dangling = sum(1 for n in node_list if not n["exists"])
    collapsed = sum(max(0, n["fileCount"] - 1) for n in node_list)
    orphans = sum(1 for n in node_list
                  if n["exists"] and n["inDegree"] == 0 and n["outDegree"] == 0)

    logger.info(
        "Vault graph built: %d node(s), %d edge(s) from %d file(s) (vault read-only)",
        len(node_list), len(edges), files_seen,
    )
    return {
        "nodes": node_list,
        "edges": edges,
        "stats": {
            "files": files_seen,
            "nodes": len(node_list),
            "edges": len(edges),
            "dangling": dangling,
            "orphans": orphans,
            "collapsed": collapsed,
            "truncated": truncated,
        },
        "source": "vault-wikilinks",
        "warnings": (
            (["Graph was truncated at the configured size limits."] if truncated else [])
            + ([
                f"{collapsed} file(s) share a note name with another file and are "
                f"merged into a single node, because Obsidian resolves wikilinks by name."
            ] if collapsed else [])
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# External export (used only if a real Graphify export turns up)
# ══════════════════════════════════════════════════════════════════════════════

def load_export(export_path: str) -> dict:
    """Read a node-link JSON graph export. Never executes or imports the file."""
    raw = (export_path or "").strip()
    if not raw:
        raise GraphError("No graph export path was provided.")
    path = Path(raw)
    if not path.is_file():
        raise GraphError(f"Graph export not found: {raw}")
    if path.stat().st_size > MAX_EXPORT_BYTES:
        raise GraphError("Graph export is too large to read.")

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        raise GraphError(f"Graph export is not valid JSON: {str(exc)[:120]}") from exc

    if not isinstance(data, dict):
        raise GraphError("Graph export root must be a JSON object.")

    raw_nodes = data.get("nodes")
    raw_edges = data.get("links") if isinstance(data.get("links"), list) else data.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise GraphError(
            "Unrecognized graph export shape. Expected a node-link object with "
            "'nodes' and 'links' (or 'edges') arrays."
        )

    nodes: List[dict] = []
    for item in raw_nodes[:MAX_NODES]:
        if isinstance(item, dict) and item.get("id") is not None:
            nodes.append({
                "id": str(item.get("id")),
                "label": _truncate(item.get("label") or item.get("name") or item.get("id")),
                "path": item.get("path"),
                "folder": "",
                "exists": True,
                "outDegree": 0,
                "inDegree": 0,
                "fileCount": 1,
            })
    known = {n["id"] for n in nodes}

    edges: List[dict] = []
    for item in raw_edges[:MAX_EDGES]:
        if not isinstance(item, dict):
            continue
        source = item.get("source") if item.get("source") is not None else item.get("from")
        target = item.get("target") if item.get("target") is not None else item.get("to")
        if source is None or target is None:
            continue
        source, target = str(source), str(target)
        if source in known and target in known:
            edges.append({"source": source, "target": target})

    by_id = {n["id"]: n for n in nodes}
    for edge in edges:
        by_id[edge["source"]]["outDegree"] += 1
        by_id[edge["target"]]["inDegree"] += 1

    return {
        "nodes": sorted(nodes, key=lambda n: (-n["inDegree"], n["id"])),
        "edges": edges,
        "stats": {
            "files": 0, "nodes": len(nodes), "edges": len(edges),
            "dangling": 0, "orphans": 0, "collapsed": 0, "truncated": False,
        },
        "source": "external-export",
        "warnings": [],
    }
