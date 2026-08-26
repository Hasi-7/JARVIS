"""
Browser-assisted chat capture (C2) — GUARDRAILED, DENY-BY-DEFAULT.

Turns a research session's captured pages into a Chat/AI Consolidation draft
payload, so a ChatGPT / Claude / Claude Code / OpenCode conversation can be
consolidated without hand-pasting it.

    CHAT_HOSTS                                  known transcript hosts → sourceTool
    detect_source_tool(url)                     map a URL to a consolidation tool
    parse_transcript(text)                      split raw page text into turns
    build_consolidation_payload(session, ...)   PRD §13.5-shaped draft fields

Safety model (this module never relaxes it):
- IT FETCHES NOTHING. Capture happens through `browser.py`, which is itself gated
  on a healthy OpenShell sandbox and a domain allowlist. This module only reshapes
  text that has already been captured.
- TRANSCRIPTS ARE UNTRUSTED (PRD §44). Turn text is stored and surfaced for review
  only. It is never executed, never followed as instructions, and never sent to an
  LLM by this module.
- NO VAULT WRITE. It returns draft *fields*; creating the draft and saving it stay
  the user's explicit actions through the existing `consolidation.py` flow, which
  keeps every never-overwrite / stay-in-vault guarantee.
- NO CREDENTIALS, NO SESSION REUSE, NO LOGIN AUTOMATION. Capturing a logged-in
  conversation is the user's own visible browser session, never automated here.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Known transcript hosts → the `sourceTool` value consolidation.py expects.
CHAT_HOSTS: Dict[str, str] = {
    "chatgpt.com": "chatgpt",
    "chat.openai.com": "chatgpt",
    "claude.ai": "claude",
}

DEFAULT_SOURCE_TOOL = "other"

MAX_TURNS = 400
MAX_TURN_CHARS = 20_000
MAX_TRANSCRIPT_CHARS = 400_000
MAX_TITLE_CHARS = 200

# Speaker labels that commonly survive a text extraction of a chat page.
_SPEAKER_RE = re.compile(
    r"^\s*(You|User|Human|Me|ChatGPT|Claude|Assistant|AI|GPT-?\d?\S*)\s*[:—-]\s*",
    re.I,
)
_USER_LABELS = {"you", "user", "human", "me"}


class ChatCaptureError(ValueError):
    """Raised when a capture cannot be turned into a consolidation payload."""


# ══════════════════════════════════════════════════════════════════════════════
# Source detection
# ══════════════════════════════════════════════════════════════════════════════

def detect_source_tool(url: str) -> str:
    """Map a captured URL to a consolidation sourceTool. Unknown hosts → 'other'."""
    try:
        host = (urlparse(url or "").hostname or "").lower().lstrip(".")
    except Exception:
        return DEFAULT_SOURCE_TOOL
    if not host:
        return DEFAULT_SOURCE_TOOL
    for known, tool in CHAT_HOSTS.items():
        if host == known or host.endswith("." + known):
            return tool
    return DEFAULT_SOURCE_TOOL


def is_chat_url(url: str) -> bool:
    return detect_source_tool(url) != DEFAULT_SOURCE_TOOL


# ══════════════════════════════════════════════════════════════════════════════
# Transcript parsing (untrusted text in, untrusted text out)
# ══════════════════════════════════════════════════════════════════════════════

def _truncate(value: str, limit: int) -> str:
    text = value or ""
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def parse_transcript(text: str) -> List[dict]:
    """Split extracted page text into {role, text} turns.

    Best-effort only: chat pages vary and extraction is lossy. When no speaker
    labels are found the whole text is returned as ONE unknown-role turn rather
    than inventing structure that is not there.
    """
    raw = (text or "").strip()
    if not raw:
        return []

    lines = [ln.strip() for ln in re.split(r"[\r\n]+", raw) if ln.strip()]
    turns: List[dict] = []
    role: Optional[str] = None
    buffer: List[str] = []

    def flush() -> None:
        if role is None or not buffer:
            return
        if len(turns) >= MAX_TURNS:
            return
        turns.append({"role": role, "text": _truncate(" ".join(buffer).strip(), MAX_TURN_CHARS)})

    for line in lines:
        match = _SPEAKER_RE.match(line)
        if match:
            flush()
            label = match.group(1).lower()
            role = "user" if label in _USER_LABELS else "assistant"
            buffer = [line[match.end():].strip()]
        elif role is not None:
            buffer.append(line)

    flush()

    if not turns:
        return [{"role": "unknown", "text": _truncate(raw, MAX_TURN_CHARS)}]
    return turns


def render_transcript(turns: List[dict]) -> str:
    """Render turns back to a readable transcript for the consolidation draft."""
    lines: List[str] = []
    for turn in turns or []:
        role = str(turn.get("role") or "unknown")
        label = {"user": "You", "assistant": "Assistant"}.get(role, "Transcript")
        lines.append(f"{label}: {turn.get('text') or ''}")
    return _truncate("\n\n".join(lines), MAX_TRANSCRIPT_CHARS)


# ══════════════════════════════════════════════════════════════════════════════
# Consolidation payload
# ══════════════════════════════════════════════════════════════════════════════

def build_consolidation_payload(
    session: dict,
    *,
    domain: str = "unknown",
    entity: Optional[str] = None,
    capture_index: Optional[int] = None,
) -> dict:
    """Shape a captured chat page into consolidation draft fields.

    Creates NO draft and writes NO vault file — the caller passes these fields to
    the existing `consolidation.create_draft` flow, which the user then reviews
    and saves.
    """
    captures = list((session or {}).get("captures") or [])
    if not captures:
        raise ChatCaptureError("This research session has no captured pages yet.")

    if capture_index is None:
        chat_captures = [c for c in captures if is_chat_url(str(c.get("url") or ""))]
        capture = chat_captures[-1] if chat_captures else captures[-1]
    else:
        try:
            capture = captures[capture_index]
        except (IndexError, TypeError):
            raise ChatCaptureError(f"No capture at index {capture_index}.")

    url = str(capture.get("url") or "")
    source_tool = detect_source_tool(url)
    turns = parse_transcript(str(capture.get("snippet") or ""))

    title = _truncate(
        str(capture.get("title") or "").strip() or session.get("topic") or "Captured conversation",
        MAX_TITLE_CHARS,
    )

    warnings: List[str] = [
        "Transcript text is untrusted captured content. Review it before saving.",
        "Page-text extraction is lossy — turn boundaries may be imperfect.",
    ]
    if source_tool == DEFAULT_SOURCE_TOOL:
        warnings.append(
            f"'{urlparse(url).hostname or url}' is not a known chat host; "
            f"sourceTool defaults to 'other'."
        )
    if len(turns) == 1 and turns[0].get("role") == "unknown":
        warnings.append("No speaker labels were detected; the transcript is stored as one block.")

    return {
        "sourceTool": source_tool,
        "conversationTitle": title,
        "domain": domain,
        "entity": entity,
        "transcript": render_transcript(turns),
        "turnCount": len(turns),
        "sourceUrl": url,
        "capturedAt": capture.get("timestamp"),
        "warnings": warnings,
    }
