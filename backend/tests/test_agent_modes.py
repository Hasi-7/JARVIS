"""
test_agent_modes.py — Agent Mode Enforcement v0.

Agent modes are enforced by backend policy, not just frontend labels:
  * locked / observe / computer_use BLOCK structured tool-request evaluation,
  * draft / assist / research / escalation allow EVALUATE-ONLY,
  * computer_use is recognized but unavailable,
  * NOTHING executes from any mode.

These tests isolate the agent-tool-request store + the gateway log path and patch
the brain wrapper / subprocess to assert they are never called and that blocked
modes write no records and no logs.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from app import agent_modes as am
from app import agent_tool_requests as atr
from app import permission_gateway as pg
from app.agent_modes import (
    normalize_mode,
    can_evaluate_tool_requests,
    can_offer_review_handoff,
    is_mode_available,
    list_modes,
)
from app.models import AgentChatRequest, AgentModeBlockedResponse, CreateAgentToolRequestRequest


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


# ── policy table ──────────────────────────────────────────────────────────────

# (mode, available, evaluate, review)
_EXPECTED = [
    ("locked",       True,  False, False),
    ("observe",      True,  False, False),
    ("draft",        True,  True,  False),
    ("assist",       True,  True,  True),
    ("research",     True,  True,  False),
    ("escalation",   True,  True,  False),
    ("computer_use", False, False, False),
]


@pytest.mark.parametrize("mode,available,evaluate,review", _EXPECTED)
def test_policy_table(mode, available, evaluate, review):
    assert is_mode_available(mode) is available
    assert can_evaluate_tool_requests(mode) is evaluate
    assert can_offer_review_handoff(mode) is review


def test_only_assist_offers_review():
    offering = [m for m, *_ in _EXPECTED if can_offer_review_handoff(m)]
    assert offering == ["assist"]


def test_computer_use_unavailable_enables_nothing():
    assert is_mode_available("computer_use") is False
    assert can_evaluate_tool_requests("computer_use") is False
    assert can_offer_review_handoff("computer_use") is False


# ── normalization ─────────────────────────────────────────────────────────────

def test_normalize_known_modes():
    for mode, *_ in _EXPECTED:
        assert normalize_mode(mode) == mode


def test_normalize_aliases():
    assert normalize_mode("computer") == "computer_use"
    assert normalize_mode("computer-use") == "computer_use"
    assert normalize_mode("Computer Use") == "computer_use"
    assert normalize_mode("manual") == "locked"


@pytest.mark.parametrize("bad", [None, "", "  ", "nonsense", "DELETE", 123, [], {}])
def test_normalize_unknown_falls_back_to_locked(bad):
    assert normalize_mode(bad) == "locked"
    # And the safest mode cannot evaluate.
    assert can_evaluate_tool_requests(bad) is False


def test_normalize_case_insensitive():
    assert normalize_mode("DRAFT") == "draft"
    assert normalize_mode(" Assist ") == "assist"


# ── list_modes / endpoint ─────────────────────────────────────────────────────

def test_list_modes_shape():
    modes = list_modes()
    ids = [m["id"] for m in modes]
    assert ids == ["locked", "observe", "draft", "assist", "research", "escalation", "computer_use"]
    for m in modes:
        assert set(m) == {
            "id", "label", "available",
            "canEvaluateToolRequests", "canOfferReviewHandoff", "notes",
        }
    by_id = {m["id"]: m for m in modes}
    assert by_id["assist"]["canOfferReviewHandoff"] is True
    assert by_id["computer_use"]["available"] is False


def test_modes_endpoint():
    from app.main import agent_modes_list
    res = agent_modes_list()
    assert [m.id for m in res.modes] == [
        "locked", "observe", "draft", "assist", "research", "escalation", "computer_use",
    ]
    by_id = {m.id: m for m in res.modes}
    assert by_id["observe"].canEvaluateToolRequests is False
    assert by_id["draft"].canEvaluateToolRequests is True
    assert by_id["assist"].canOfferReviewHandoff is True


# ── manual tool request: blocked modes ────────────────────────────────────────

def _create(mode, tool="brain.status"):
    from app.main import agent_tool_request_create
    return agent_tool_request_create(
        CreateAgentToolRequestRequest(tool=tool, args={}, reason="r", mode=mode)
    )


@pytest.mark.parametrize("mode", ["locked", "observe", "computer_use", "manual", "nonsense"])
def test_manual_request_blocked_modes(mode):
    with patch("app.brain.run_brain_command") as mbrain, patch("subprocess.run") as msub:
        res = _create(mode)
    assert isinstance(res, AgentModeBlockedResponse)
    assert res.status == "blocked_by_mode"
    assert res.mode == normalize_mode(mode)
    assert res.message
    # Nothing was evaluated, stored, or logged.
    assert atr.list_requests(limit=200) == []
    assert pg.list_logs(limit=200) == []
    mbrain.assert_not_called()
    msub.assert_not_called()


# ── manual tool request: evaluate-only modes ──────────────────────────────────

@pytest.mark.parametrize("mode", ["draft", "assist", "research", "escalation"])
def test_manual_request_evaluate_only_modes(mode):
    from app.models import AgentToolRequestResponse
    with patch("app.brain.run_brain_command") as mbrain, patch("subprocess.run") as msub:
        res = _create(mode)
    assert isinstance(res, AgentToolRequestResponse)
    assert res.status == "evaluated_only"
    assert res.tool == "brain.status"
    # Exactly one gateway_eval log, never an execution log.
    logs = pg.list_logs(limit=200)
    assert len(logs) == 1
    assert logs[0]["source"] == "gateway_eval"
    assert all(l["source"] != "gateway_execution" for l in logs)
    mbrain.assert_not_called()
    msub.assert_not_called()


def test_manual_request_default_mode_blocks():
    """Missing mode normalizes to the safest mode (locked) → blocked."""
    from app.main import agent_tool_request_create
    res = agent_tool_request_create(CreateAgentToolRequestRequest(tool="brain.status"))
    assert isinstance(res, AgentModeBlockedResponse)
    assert res.mode == "locked"
    assert atr.list_requests(limit=200) == []


# ── chat structured output gated by mode ──────────────────────────────────────

_REPLY = 'Checking.\n```json\n{"tool_requests":[{"tool":"brain.status","reason":"check"}]}\n```'


def _patch_chat(monkeypatch, reply=_REPLY):
    import app.main as m
    monkeypatch.setattr(m, "chat_with_agent", lambda **kw: {
        "ok": True, "provider": "ollama", "model": "test", "message": reply, "durationMs": 1.0,
    })
    monkeypatch.setattr(m, "get_conversation", lambda cid: {"id": cid})
    monkeypatch.setattr(m, "_prior_messages", lambda cid: ([], 0))
    monkeypatch.setattr(m, "save_chat_turn", lambda **kw: None)
    return m


@pytest.mark.parametrize("mode", ["observe", "locked", "computer_use"])
def test_chat_structured_blocked_in_non_evaluating_modes(monkeypatch, mode):
    m = _patch_chat(monkeypatch)
    with patch("app.brain.run_brain_command") as mbrain, patch("subprocess.run") as msub:
        res = m.agent_chat(AgentChatRequest(message="check", conversationId="c1", mode=mode))
    assert res.structured is not None
    assert res.structured.blockedByMode is True
    assert res.structured.toolRequests == []
    assert res.structured.message
    # Blocked: nothing evaluated, stored, or logged; no execution.
    assert atr.list_requests(limit=200) == []
    assert pg.list_logs(limit=200) == []
    mbrain.assert_not_called()
    msub.assert_not_called()


@pytest.mark.parametrize("mode", ["draft", "assist"])
def test_chat_structured_evaluated_in_evaluating_modes(monkeypatch, mode):
    m = _patch_chat(monkeypatch)
    with patch("app.brain.run_brain_command") as mbrain, patch("subprocess.run") as msub:
        res = m.agent_chat(AgentChatRequest(message="check", conversationId="c1", mode=mode))
    assert res.structured is not None
    assert res.structured.blockedByMode is False
    assert len(res.structured.toolRequests) == 1
    assert res.structured.toolRequests[0].evaluation.decision == "allowed"
    assert res.structured.toolRequests[0].status == "evaluated_only"
    # Evaluate-only: one gateway_eval log, never an execution log.
    logs = pg.list_logs(limit=200)
    assert len(logs) == 1
    assert logs[0]["source"] == "gateway_eval"
    assert all(l["source"] != "gateway_execution" for l in logs)
    mbrain.assert_not_called()
    msub.assert_not_called()


def test_chat_no_structured_block_when_reply_has_none(monkeypatch):
    m = _patch_chat(monkeypatch, reply="Just a plain answer, no tools.")
    res = m.agent_chat(AgentChatRequest(message="hi", conversationId="c1", mode="draft"))
    assert res.structured is None
    assert pg.list_logs(limit=200) == []
