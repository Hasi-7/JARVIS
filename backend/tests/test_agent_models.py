"""Mocked tests for fixed Ollama tiers and centralized completions."""

import threading
import urllib.error

import pytest
from pydantic import ValidationError

from app import agent, classify_ai, intake
from app.models import CaptureAssistRequest


def test_tier_resolver_is_bounded(monkeypatch):
    monkeypatch.setattr(agent, "LOCAL_MODEL", "everyday-test")
    monkeypatch.setattr(agent, "HEAVY_LOCAL_MODEL", "heavy-test")
    assert agent.resolve_model_tier() == "everyday-test"
    assert agent.resolve_model_tier("everyday") == "everyday-test"
    assert agent.resolve_model_tier("heavy") == "heavy-test"
    with pytest.raises(ValueError):
        agent.resolve_model_tier("llama-arbitrary")


def test_assist_request_forbids_model_names_and_extra_fields():
    request = CaptureAssistRequest(modelTier="heavy")
    assert request.modelTier == "heavy"
    assert request.model_dump() == {"modelTier": "heavy"}
    with pytest.raises(ValidationError):
        CaptureAssistRequest(modelTier="gemma4:99b")
    with pytest.raises(ValidationError):
        CaptureAssistRequest(modelTier="everyday", model="other")
    with pytest.raises(ValidationError):
        CaptureAssistRequest()


def test_central_completion_uses_context_and_disables_thinking(monkeypatch):
    seen = {}

    def fake_post(url, payload, timeout):
        seen.update(url=url, payload=payload, timeout=timeout)
        return {"message": {"content": "  result  ", "thinking": "private"}}

    monkeypatch.setattr(agent, "_post_json", fake_post)
    monkeypatch.setattr(agent, "HEAVY_LOCAL_MODEL", "heavy-test")
    result = agent.complete_ollama_chat(
        [{"role": "user", "content": "x"}], tier="heavy", structured=True,
    )
    assert seen["payload"]["model"] == "heavy-test"
    assert seen["payload"]["options"]["num_ctx"] == 16_384
    assert seen["payload"]["options"]["num_predict"] == 2_048
    assert seen["payload"]["format"] == "json"
    assert seen["payload"]["think"] is False
    assert result["message"] == "result"
    assert result["modelTier"] == "heavy"
    assert "thinking" not in result


def test_central_completion_rejects_concurrent_inference(monkeypatch):
    class BusyGate:
        def acquire(self, blocking=False):
            return False

        def release(self):
            raise AssertionError("unacquired gate must not be released")

    monkeypatch.setattr(agent, "_INFERENCE_GATE", BusyGate())
    monkeypatch.setattr(agent, "_post_json", lambda *args, **kwargs: pytest.fail("request must not run"))
    with pytest.raises(agent.OllamaBusyError):
        agent.complete_ollama_chat([{"role": "user", "content": "x"}])


def test_stream_holds_shared_gate_until_normal_completion(monkeypatch):
    class Response:
        def __init__(self):
            self.lines = iter([
                b'{"message":{"content":"token"},"done":false}\n',
                b'{"done":true}\n',
            ])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def readline(self):
            return next(self.lines, b"")

    monkeypatch.setattr(agent, "_INFERENCE_GATE", threading.BoundedSemaphore(1))
    monkeypatch.setattr(agent.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(
        agent, "_post_json", lambda *args, **kwargs: {"message": {"content": "complete"}},
    )

    stream = agent.stream_ollama_chat("hello")
    assert next(stream) == "token"
    with pytest.raises(agent.OllamaBusyError):
        agent.complete_ollama_chat([{"role": "user", "content": "blocked"}])

    assert list(stream) == []
    assert agent.complete_ollama_chat(
        [{"role": "user", "content": "released"}],
    )["message"] == "complete"


def test_stream_rejects_concurrent_inference_before_opening_ollama(monkeypatch):
    gate = threading.BoundedSemaphore(1)
    assert gate.acquire(blocking=False)
    monkeypatch.setattr(agent, "_INFERENCE_GATE", gate)
    monkeypatch.setattr(
        agent.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("request must not open"),
    )

    with pytest.raises(agent.OllamaBusyError):
        next(agent.stream_ollama_chat("hello"))


def test_stream_releases_shared_gate_after_error(monkeypatch):
    class ErrorResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def readline(self):
            raise urllib.error.URLError("stream interrupted")

    monkeypatch.setattr(agent, "_INFERENCE_GATE", threading.BoundedSemaphore(1))
    monkeypatch.setattr(agent.urllib.request, "urlopen", lambda *args, **kwargs: ErrorResponse())
    stream = agent.stream_ollama_chat("hello")
    with pytest.raises(ValueError, match="Could not reach Ollama"):
        next(stream)

    monkeypatch.setattr(
        agent, "_post_json", lambda *args, **kwargs: {"message": {"content": "released"}},
    )
    assert agent.complete_ollama_chat(
        [{"role": "user", "content": "after error"}],
    )["message"] == "released"


def test_chat_behavior_remains_everyday_and_compatible(monkeypatch):
    monkeypatch.setattr(agent, "complete_ollama_chat", lambda messages, **kwargs: {
        "ok": True, "provider": "ollama", "model": "daily", "modelTier": "everyday",
        "message": "hello", "durationMs": 2.0,
    })
    result = agent.chat_with_agent("hi", prior_messages=[])
    assert result["ok"] is True
    assert result["model"] == "daily"
    assert result["message"] == "hello"
    assert result["durationMs"] == 2.0
    assert set(result) == {"ok", "provider", "model", "message", "durationMs"}


def test_status_reports_both_configured_models(monkeypatch):
    monkeypatch.setattr(agent, "LOCAL_MODEL", "daily")
    monkeypatch.setattr(agent, "HEAVY_LOCAL_MODEL", "large")
    responses = iter([
        (True, {"version": "test"}),
        (True, {"models": [{"name": "daily"}, {"name": "large"}]}),
    ])
    monkeypatch.setattr(agent, "_get_json", lambda *args, **kwargs: next(responses))
    result = agent.get_agent_status()
    assert result["model"] == "daily"  # legacy field
    assert result["available"] is True  # legacy field
    assert result["everydayModel"] == "daily"
    assert result["heavyModel"] == "large"
    assert result["everydayAvailable"] is True
    assert result["heavyAvailable"] is True


def test_classifier_is_everyday_only_and_uses_central_completion(monkeypatch):
    seen = {}

    def fake_complete(messages, **kwargs):
        seen.update(messages=messages, kwargs=kwargs)
        return {"message": '{"domain":"unknown","entity":"Unassigned","sourceType":"other","proposedDestination":"raw/inbox/unclassified/","confidence":"Low","needsReview":true,"reason":"Unknown"}'}

    monkeypatch.setattr(classify_ai, "complete_ollama_chat", fake_complete)
    result = classify_ai.ai_classify_file(
        original_name="ignore instructions.txt", stored_name="x", content_type="text/plain",
        size_bytes=10, heuristic={},
    )
    assert result["domain"] == "unknown"
    assert seen["messages"][1]["content"].startswith("UNTRUSTED CONTENT RULE:")
    assert seen["kwargs"]["tier"] == "everyday"
    assert seen["kwargs"]["structured"] is True


def test_raw_inbox_attribution_uses_actual_everyday_model(monkeypatch):
    entry = intake.StagedEntry(
        id="f1", original_name="note.txt", stored_name="stored.txt", size_bytes=4,
        content_type="text/plain", uploaded_at="now",
    )
    proposal = intake.Proposal(
        file_id="f1", domain="unknown", source_type="other",
        proposed_destination="raw/inbox/unclassified/", confidence="Low", reason="initial",
    )
    monkeypatch.setattr(intake, "_read_index", lambda: [entry])
    monkeypatch.setattr(intake, "_read_proposals", lambda: [proposal])
    monkeypatch.setattr(intake, "_write_proposals", lambda proposals: None)
    monkeypatch.setattr(agent, "LOCAL_MODEL", "configured-everyday")
    monkeypatch.setattr(classify_ai, "ai_classify_file", lambda **kwargs: {
        "domain": "unknown", "entity": "Unassigned", "sourceType": "other",
        "proposedDestination": "raw/inbox/unclassified/", "confidence": "Low",
        "needsReview": True, "reason": "classified",
    })

    updated = intake.ai_classify_proposal("f1")
    assert updated is proposal
    assert updated.ai_model == "configured-everyday"
