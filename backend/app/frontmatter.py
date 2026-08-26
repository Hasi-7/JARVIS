"""YAML frontmatter for Obsidian wiki notes.

Entity metadata (repo path, GitHub URL, demo link, status) lives in the note's
own frontmatter rather than a backend database, so it stays readable and editable
from Obsidian with Brain UI closed — PRD acceptance criteria #13 and #14.

Two properties matter more than convenience here:

**Surgical writes.** This never round-trips the document through safe_load and
safe_dump. That would reformat the user's YAML, drop their comments, reorder
their keys, and rewrite quoting — destructive edits to a file they hand-maintain.
Only the leading `---` block is rewritten; the body is copied through byte for
byte, and unknown keys are preserved.

**Parsing never raises.** Obsidian frontmatter is hand-edited and frequently
malformed. A YAML error must degrade one entity card, not 500 the projects
endpoint, so read_frontmatter reports the problem instead of propagating it.
"""

import logging
import re
from datetime import date as date_type
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# A frontmatter block must open on the very first line. Obsidian requires this,
# and it means a `---` horizontal rule further down is never mistaken for one.
_OPEN_RE = re.compile(r"^---[ \t]*\r?\n")
_CLOSE_RE = re.compile(r"^(?:---|\.\.\.)[ \t]*\r?$")

MAX_FRONTMATTER_CHARS = 64_000
MAX_VALUE_CHARS = 2_000


class FrontmatterResult:
    """Parsed frontmatter plus whether reading it went wrong.

    `error` is not an exception — it is a fact about the note that the UI shows
    on that entity's card while every other card keeps working.
    """

    __slots__ = ("data", "body", "raw", "error", "had_block")

    def __init__(self, data: Dict[str, Any], body: str, raw: str,
                 error: Optional[str], had_block: bool) -> None:
        self.data = data
        self.body = body
        self.raw = raw
        self.error = error
        self.had_block = had_block

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"FrontmatterResult(keys={sorted(self.data)}, error={self.error!r})"


def _split(text: str) -> Tuple[Optional[str], str, bool]:
    """Return (raw_frontmatter, body, had_block) without parsing YAML."""
    if not _OPEN_RE.match(text):
        return None, text, False

    lines = text.splitlines(keepends=True)
    for index in range(1, len(lines)):
        if _CLOSE_RE.match(lines[index].rstrip("\r\n")):
            raw = "".join(lines[1:index])
            body = "".join(lines[index + 1:])
            return raw, body, True

    # Opened but never closed. Treat the whole file as body: rewriting on a guess
    # about where the block ends could swallow real note content.
    return None, text, False


def read_frontmatter(text: str) -> FrontmatterResult:
    """Parse a note's frontmatter. Never raises."""
    raw, body, had_block = _split(text)
    if raw is None:
        return FrontmatterResult({}, body, "", None, had_block)

    if len(raw) > MAX_FRONTMATTER_CHARS:
        return FrontmatterResult(
            {}, body, raw,
            f"Frontmatter is larger than {MAX_FRONTMATTER_CHARS} characters; ignored.",
            True,
        )

    try:
        import yaml
        parsed = yaml.safe_load(raw)
    except Exception as exc:
        # Hand-edited YAML breaks often. One bad note must not break the endpoint.
        return FrontmatterResult({}, body, raw, f"Invalid YAML frontmatter: {str(exc)[:200]}", True)

    if parsed is None:
        return FrontmatterResult({}, body, raw, None, True)
    if not isinstance(parsed, dict):
        return FrontmatterResult(
            {}, body, raw,
            f"Frontmatter must be a mapping, found {type(parsed).__name__}.",
            True,
        )

    return FrontmatterResult({str(k): v for k, v in parsed.items()}, body, raw, None, True)


def get_str(result: FrontmatterResult, *names: str) -> Optional[str]:
    """First non-empty string value among `names`, normalized and length-capped.

    Accepts several spellings because these notes are hand-written: `repo_path`,
    `repoPath` and `repo-path` all mean the same thing to a person.
    """
    for name in names:
        for key in (name, name.replace("_", "-"), _camel(name)):
            if key not in result.data:
                continue
            value = result.data[key]
            if value is None or isinstance(value, (dict, list)):
                continue
            if isinstance(value, bool):
                text = "true" if value else "false"
            elif isinstance(value, (datetime, date_type)):
                text = value.isoformat()
            else:
                text = str(value)
            text = " ".join(text.split())
            if text:
                return text[:MAX_VALUE_CHARS]
    return None


def _camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(part.title() for part in rest)


def _quote(value: str) -> str:
    """Emit a YAML scalar that round-trips, quoting only when needed."""
    if value == "":
        return '""'
    needs_quotes = (
        value[0] in "#&*!|>%@`{}[],\"'"
        or value.strip() != value
        or ": " in value
        or value.endswith(":")
        or "\n" in value
        or value.lower() in {"true", "false", "null", "yes", "no", "on", "off", "~"}
        or _looks_numeric(value)
    )
    if not needs_quotes:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def _looks_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def write_frontmatter(text: str, updates: Dict[str, Optional[str]]) -> str:
    """Return `text` with `updates` applied to its frontmatter.

    Only the keys in `updates` are touched. A value of None REMOVES that key.
    Every other line of the block — including comments, ordering, and keys this
    app knows nothing about — is preserved exactly.

    Refuses to write when the existing block is malformed: rewriting YAML we
    could not parse risks destroying data the user typed by hand.
    """
    result = read_frontmatter(text)
    if result.error:
        raise ValueError(f"Refusing to rewrite unparseable frontmatter: {result.error}")

    clean: Dict[str, Optional[str]] = {}
    for key, value in updates.items():
        key = str(key).strip()
        if not key or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key):
            raise ValueError(f"Invalid frontmatter key: {key!r}")
        if value is None:
            clean[key] = None
        else:
            flattened = " ".join(str(value).split())
            clean[key] = flattened[:MAX_VALUE_CHARS]

    raw_lines = result.raw.splitlines() if result.raw else []
    out_lines: list[str] = []
    seen: set[str] = set()

    for line in raw_lines:
        match = re.match(r"^([A-Za-z0-9_-]+)[ \t]*:", line)
        if not match:
            out_lines.append(line)          # comment, blank line, or nested value
            continue
        key = match.group(1)
        if key not in clean:
            out_lines.append(line)          # untouched key: preserve verbatim
            continue
        seen.add(key)
        if clean[key] is None:
            continue                        # removal
        out_lines.append(f"{key}: {_quote(clean[key])}")

    for key, value in clean.items():
        if key in seen or value is None:
            continue
        out_lines.append(f"{key}: {_quote(value)}")

    block = "\n".join(out_lines).rstrip("\n")
    body = result.body
    if not result.had_block and body and not body.startswith("\n"):
        # Adding a block to a note that had none: keep a blank line before the
        # body so the note still renders the way the user wrote it.
        body = "\n" + body
    return f"---\n{block}\n---\n{body}" if block else result.body
