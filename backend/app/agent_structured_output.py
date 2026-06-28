"""
Local Agent Structured Output v0 — defensive parser for the optional structured
JSON block an assistant response may include.

The Local Agent may append a small structured block proposing tool requests. This
module extracts and validates the `tool_requests` from that block, then (via
evaluate_structured_output) routes each one through the evaluate-only Agent Tool
Request path. NOTHING is executed here.

Safety model:
- Parsed content is UNTRUSTED: it is only validated/summarized, never executed.
- Malformed JSON never breaks the chat — it yields a parse error, not an exception.
- Tool-request count is capped; reasons truncated; args must be a JSON object.
- This module never calls /execute, the brain wrapper, a subprocess, or any tool;
  evaluation/execution happens (or is blocked) downstream in the Permission Gateway.
"""

import json
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

LABEL = "AGENT_STRUCTURED_OUTPUT:"

MAX_REQUESTS = 5
MAX_REASON_LEN = 300

# Fenced code block: ```json ... ``` or ``` ... ``` (DOTALL, non-greedy).
_FENCE_RE = re.compile(r"```[ \t]*(?:json)?[ \t]*\r?\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def _load_obj(candidate: str) -> Optional[dict]:
    """Try to parse a JSON object from a candidate string. Returns dict or None."""
    candidate = (candidate or "").strip()
    if not candidate:
        return None
    # 1. whole-string parse
    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # 2. first balanced object via raw_decode from the first '{'
    i = candidate.find("{")
    if i != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(candidate[i:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None


def _validate_entry(entry: object, index: int) -> Tuple[Optional[dict], Optional[str]]:
    """Validate one tool_requests entry → (spec, error). Untrusted input."""
    if not isinstance(entry, dict):
        return None, f"tool_requests[{index}] is not an object; ignored."

    tool = entry.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        return None, f"tool_requests[{index}] missing a non-empty 'tool'; ignored."

    args = entry.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return None, f"tool_requests[{index}] 'args' must be a JSON object; ignored."

    reason = entry.get("reason")
    if not isinstance(reason, str):
        reason = ""
    reason = reason.strip()
    if len(reason) > MAX_REASON_LEN:
        reason = reason[:MAX_REASON_LEN] + "…"
    if not reason:
        reason = "(no reason provided)"

    return {"tool": tool.strip(), "args": args, "reason": reason}, None


def parse_structured_output(text: Optional[str]) -> dict:
    """
    Extract validated tool-request specs from an assistant response.

    Returns { "requests": [ {tool, args, reason} ], "parseErrors": [str] }.
    Never raises. If no structured block is present, returns empty with no errors.
    """
    if not text or not isinstance(text, str):
        return {"requests": [], "parseErrors": []}

    errors: list = []
    candidates: list = []
    found_marker = False

    for m in _FENCE_RE.finditer(text):
        content = m.group(1).strip()
        if content:
            candidates.append(content)
            found_marker = True

    li = text.find(LABEL)
    if li != -1:
        found_marker = True
        candidates.append(text[li + len(LABEL):])

    # Prefer a parsed object that actually carries tool_requests.
    parsed: Optional[dict] = None
    for cand in candidates:
        obj = _load_obj(cand)
        if isinstance(obj, dict) and "tool_requests" in obj:
            parsed = obj
            break
    if parsed is None:
        for cand in candidates:
            obj = _load_obj(cand)
            if isinstance(obj, dict):
                parsed = obj
                break

    if parsed is None:
        if found_marker:
            errors.append("Structured output block found but could not be parsed as JSON.")
        return {"requests": [], "parseErrors": errors}

    tr = parsed.get("tool_requests")
    if tr is None:
        return {"requests": [], "parseErrors": errors}
    if not isinstance(tr, list):
        errors.append("tool_requests must be a list; ignored.")
        return {"requests": [], "parseErrors": errors}

    requests: list = []
    for i, entry in enumerate(tr):
        if len(requests) >= MAX_REQUESTS:
            errors.append(f"tool_requests capped at {MAX_REQUESTS}; extra entries ignored.")
            break
        spec, err = _validate_entry(entry, i)
        if err:
            errors.append(err)
        if spec:
            requests.append(spec)

    return {"requests": requests, "parseErrors": errors}


def evaluate_structured_output(text: Optional[str], conversation_id: Optional[str]) -> dict:
    """
    Parse structured output and route each valid tool request through the
    evaluate-only Agent Tool Request path. NOTHING is executed.

    Returns { "toolRequests": [ <agent tool request record> ], "parseErrors": [str] }.
    Never raises.
    """
    # Imported here to avoid any import-time coupling; this module is also used by tests.
    from app.agent_tool_requests import create_request

    parsed = parse_structured_output(text)
    errors = list(parsed["parseErrors"])
    records: list = []

    for spec in parsed["requests"]:
        try:
            record = create_request(
                tool=spec["tool"],
                args=spec["args"],
                reason=spec["reason"],
                requested_by="local-agent",
                conversation_id=conversation_id,
            )
            records.append(record)
        except ValueError as exc:
            errors.append(f"{spec['tool']}: {exc}")

    if records:
        logger.info(
            "Structured output: evaluated %d agent tool request(s) (NOT executed)", len(records)
        )
    return {"toolRequests": records, "parseErrors": errors}
