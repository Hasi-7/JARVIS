"""
test_agent_structured_output.py — Local Agent Structured Output v0.

The parser extracts validated tool-request specs from an assistant reply;
evaluate_structured_output routes each through the evaluate-only Agent Tool Request
path. NOTHING is executed. Tests isolate the request store + gateway log path and
assert the brain wrapper / subprocess are never touched and only gateway_eval logs
are written.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from app import agent_structured_output as aso
from app import agent_tool_requests as atr
from app import permission_gateway as pg
from app.agent_structured_output import parse_structured_output, evaluate_structured_output


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    import tempfile, shutil
    d = Path(tempfile.mkdtemp())
    monkeypatch.setattr(atr, "AGENT_REQUESTS_DIR", d / "atr")
    monkeypatch.setattr(atr, "REQUESTS_FILE", d / "atr" / "requests.json")
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", d / "logs")
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", d / "logs" / "evaluations.json")
    yield
    shutil.rmtree(d, ignore_errors=True)


# ── parsing ─────────────────────────────────────────────────────────────────────

def test_parse_fenced_json():
    text = (
        "Sure.\n```json\n"
        '{"tool_requests":[{"tool":"brain.status","args":{},"reason":"check"}],'
        '"confidence":"Medium","needs_user_decision":true}\n```\nDone.'
    )
    p = parse_structured_output(text)
    assert p["parseErrors"] == []
    assert len(p["requests"]) == 1
    assert p["requests"][0]["tool"] == "brain.status"
    assert p["requests"][0]["args"] == {}
    assert p["requests"][0]["reason"] == "check"


def test_parse_labelled_block():
    text = 'Here.\nAGENT_STRUCTURED_OUTPUT:\n{"tool_requests":[{"tool":"brain.raw_status","reason":"raw"}]}\ntrailing'
    p = parse_structured_output(text)
    assert [r["tool"] for r in p["requests"]] == ["brain.raw_status"]
    assert p["parseErrors"] == []


def test_parse_no_block_returns_empty():
    p = parse_structured_output("A normal reply with no structured output.")
    assert p["requests"] == []
    assert p["parseErrors"] == []


def test_parse_malformed_returns_error_not_exception():
    p = parse_structured_output("```json\n{not valid json,,,}\n```")
    assert p["requests"] == []
    assert len(p["parseErrors"]) == 1


def test_parse_caps_request_count():
    entries = ",".join('{"tool":"brain.status","reason":"r%d"}' % i for i in range(8))
    p = parse_structured_output("```json\n{\"tool_requests\":[" + entries + "]}\n```")
    assert len(p["requests"]) == aso.MAX_REQUESTS
    assert any("capped" in e for e in p["parseErrors"])


def test_parse_invalid_entries_reported_and_skipped():
    text = (
        '```json\n{"tool_requests":['
        '{"tool":"brain.status","reason":"ok"},'      # valid
        '{"tool":"","reason":"empty tool"},'           # invalid: empty tool
        '{"reason":"no tool"},'                         # invalid: missing tool
        '{"tool":"gmail.search","args":"notobj","reason":"bad args"},'  # invalid args
        '"notanobject"'                                # invalid entry type
        ']}\n```'
    )
    p = parse_structured_output(text)
    assert [r["tool"] for r in p["requests"]] == ["brain.status"]
    assert len(p["parseErrors"]) == 4


def test_parse_reason_truncated():
    long = "x" * 500
    p = parse_structured_output('```json\n{"tool_requests":[{"tool":"brain.status","reason":"' + long + '"}]}\n```')
    assert p["requests"][0]["reason"].endswith("…")
    assert len(p["requests"][0]["reason"]) < 400


def test_parse_missing_reason_fallback():
    p = parse_structured_output('```json\n{"tool_requests":[{"tool":"brain.status"}]}\n```')
    assert p["requests"][0]["reason"] == "(no reason provided)"


def test_parse_tool_requests_not_list():
    p = parse_structured_output('```json\n{"tool_requests":"nope"}\n```')
    assert p["requests"] == []
    assert any("must be a list" in e for e in p["parseErrors"])


# ── evaluation (evaluate-only) ──────────────────────────────────────────────────

def test_evaluate_creates_evaluated_only_requests():
    text = '```json\n{"tool_requests":[{"tool":"brain.status","reason":"check"}]}\n```'
    with patch("app.brain.run_brain_command") as mbrain, patch("subprocess.run") as msub:
        res = evaluate_structured_output(text, "conv1")
    mbrain.assert_not_called()
    msub.assert_not_called()
    assert len(res["toolRequests"]) == 1
    r = res["toolRequests"][0]
    assert r["status"] == "evaluated_only"
    ev = r["evaluation"]
    assert ev["decision"] == "allowed"
    assert ev["executionEnabled"] is True   # executable, but NOT executed here
    assert ev["logId"]


def test_evaluate_gmail_not_wired():
    text = '```json\n{"tool_requests":[{"tool":"gmail.search","args":{"q":"x"},"reason":"find"}]}\n```'
    with patch("app.brain.run_brain_command") as mbrain:
        res = evaluate_structured_output(text, None)
    mbrain.assert_not_called()
    assert res["toolRequests"][0]["evaluation"]["decision"] == "not_wired"
    assert res["toolRequests"][0]["evaluation"]["allowed"] is False


def test_evaluate_no_block_is_empty():
    res = evaluate_structured_output("plain reply", "c1")
    assert res["toolRequests"] == []
    assert res["parseErrors"] == []


def test_evaluate_secrets_redacted_in_store():
    text = '```json\n{"tool_requests":[{"tool":"gmail.search","args":{"token":"ZZsecret","q":"v"},"reason":"r"}]}\n```'
    evaluate_structured_output(text, "c1")
    raw = atr.REQUESTS_FILE.read_text(encoding="utf-8")
    assert "ZZsecret" not in raw
    assert "[redacted]" in raw


def test_evaluate_writes_eval_logs_not_execution_logs():
    text = '```json\n{"tool_requests":[{"tool":"brain.status","reason":"a"},{"tool":"gmail.send","reason":"b"}]}\n```'
    evaluate_structured_output(text, "c1")
    logs = pg.list_logs(limit=100)
    assert sum(1 for l in logs if l["source"] == "gateway_eval") == 2
    assert all(l["source"] != "gateway_execution" for l in logs)


def test_evaluate_no_subprocess():
    text = '```json\n{"tool_requests":[{"tool":"brain.status","reason":"a"},{"tool":"shell.run","reason":"b"}]}\n```'
    with patch("app.brain.run_brain_command") as mbrain, \
         patch("subprocess.run") as msub, patch("subprocess.Popen") as mpop:
        evaluate_structured_output(text, "c1")
    mbrain.assert_not_called()
    msub.assert_not_called()
    mpop.assert_not_called()


# ── chat endpoint integration ───────────────────────────────────────────────────

def test_chat_endpoint_attaches_evaluated_structured(monkeypatch):
    """agent_chat parses the assistant reply and attaches evaluated-only requests."""
    import app.main as m
    reply = 'Checking.\n```json\n{"tool_requests":[{"tool":"brain.status","reason":"check"}]}\n```'

    monkeypatch.setattr(m, "chat_with_agent", lambda **kw: {
        "ok": True, "provider": "ollama", "model": "test", "message": reply, "durationMs": 1.0,
    })
    monkeypatch.setattr(m, "get_conversation", lambda cid: {"id": cid})
    monkeypatch.setattr(m, "_prior_messages", lambda cid: ([], 0))
    saved = {}
    monkeypatch.setattr(m, "save_chat_turn", lambda **kw: saved.update(kw))

    from app.models import AgentChatRequest
    with patch("app.brain.run_brain_command") as mbrain:
        res = m.agent_chat(AgentChatRequest(message="check brain", conversationId="c1"))
    mbrain.assert_not_called()
    assert res.structured is not None
    assert len(res.structured.toolRequests) == 1
    assert res.structured.toolRequests[0].evaluation.decision == "allowed"
    assert res.structured.toolRequests[0].status == "evaluated_only"
