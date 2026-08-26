"""D2 approved Google Calendar event creation tests.

The only external write in this app. Every test injects a fake Calendar service;
nothing here reaches Google or creates a real event.
"""

from datetime import datetime
from pathlib import Path

import pytest

from app import gcal_write as gw
from app import permission_gateway as pg
from app.google_auth import CALENDAR_WRITE_SCOPE, GOOGLE_READONLY_SCOPES


class _Insert:
    def __init__(self, service, kwargs):
        self._service, self._kwargs = service, kwargs

    def execute(self):
        self._service.calls.append(self._kwargs)
        if isinstance(self._service.result, Exception):
            raise self._service.result
        return self._service.result


class FakeEvents:
    def __init__(self, service):
        self._service = service

    def insert(self, **kwargs):
        return _Insert(self._service, kwargs)

    def __getattr__(self, name):
        raise AssertionError(f"Forbidden Calendar write method called: {name}")


class FakeWriteService:
    def __init__(self, result=None):
        self.result = result if result is not None else {
            "id": "evt-1",
            "htmlLink": "https://calendar.google.com/evt-1",
            "summary": "Dentist",
            "start": {"dateTime": "2026-09-01T14:00:00"},
            "end": {"dateTime": "2026-09-01T15:00:00"},
        }
        self.calls = []

    def events(self):
        return FakeEvents(self)


NOW = datetime(2026, 8, 23, 12, 0, 0)


def _spec(**kw):
    base = {"title": "Dentist", "date": "2026-09-01", "time": "14:00", "duration": "1h"}
    base.update(kw)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# Create-only: no update / delete / move, ever
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("method", ["update", "patch", "delete", "move", "import_"])
def test_module_never_references_other_mutations(method):
    source = Path(gw.__file__).read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]      # docstring names them as absent
    assert f".{method}(" not in body


def test_read_module_stays_write_free():
    """gcal.py must remain provably read-only — writes live only in gcal_write.py."""
    from app import gcal
    source = Path(gcal.__file__).read_text(encoding="utf-8")
    assert ".insert(" not in source.split('"""', 2)[-1]


def test_only_insert_is_called():
    service = FakeWriteService()
    gw.create_event(_spec(), service=service, now=NOW)
    assert len(service.calls) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Never notifies anyone
# ══════════════════════════════════════════════════════════════════════════════

def test_send_updates_is_always_none():
    service = FakeWriteService()
    gw.create_event(_spec(), service=service, now=NOW)
    assert service.calls[0]["sendUpdates"] == "none"


def test_attendees_are_never_forwarded():
    """A candidate row must not be able to turn event creation into sending invites."""
    service = FakeWriteService()
    gw.create_event(
        _spec(attendees=[{"email": "someone@example.com"}]), service=service, now=NOW
    )
    assert "attendees" not in service.calls[0]["body"]


def test_arbitrary_api_fields_are_not_smuggled_through():
    service = FakeWriteService()
    gw.create_event(
        _spec(conferenceData={"x": 1}, reminders={"useDefault": False}, guestsCanModify=True),
        service=service, now=NOW,
    )
    body = service.calls[0]["body"]
    assert set(body).issubset({"summary", "description", "location", "start", "end"})


# ══════════════════════════════════════════════════════════════════════════════
# Scope enforcement
# ══════════════════════════════════════════════════════════════════════════════

def test_write_refused_without_events_scope():
    class Creds:
        scopes = list(GOOGLE_READONLY_SCOPES)

    with pytest.raises(gw.CalendarWriteError, match="do not include the Calendar events scope"):
        gw.build_write_service(credentials_factory=Creds, service_builder=lambda *a, **k: None)


def test_write_service_builds_with_events_scope():
    class Creds:
        scopes = list(GOOGLE_READONLY_SCOPES) + [CALENDAR_WRITE_SCOPE]

    built = gw.build_write_service(
        credentials_factory=Creds, service_builder=lambda *a, **k: FakeWriteService()
    )
    assert built is not None


def test_write_scope_granted_helper():
    class Yes:
        scopes = [CALENDAR_WRITE_SCOPE]

    class No:
        scopes = list(GOOGLE_READONLY_SCOPES)

    assert gw.write_scope_granted(Yes()) is True
    assert gw.write_scope_granted(No()) is False


# ══════════════════════════════════════════════════════════════════════════════
# Body construction / validation
# ══════════════════════════════════════════════════════════════════════════════

def test_timed_event_body():
    body = gw.build_event_body(_spec(), now=NOW)
    assert body["summary"] == "Dentist"
    assert body["start"]["dateTime"].startswith("2026-09-01T14:00")
    assert body["end"]["dateTime"].startswith("2026-09-01T15:00")


def test_all_day_event_uses_exclusive_end_date():
    body = gw.build_event_body(_spec(time=None, duration=None), now=NOW)
    assert body["start"]["date"] == "2026-09-01"
    assert body["end"]["date"] == "2026-09-02"      # Calendar end.date is exclusive


def test_title_is_required():
    with pytest.raises(gw.CalendarWriteError, match="title is required"):
        gw.build_event_body(_spec(title=""), now=NOW)


def test_date_is_required():
    with pytest.raises(gw.CalendarWriteError, match="date is required"):
        gw.build_event_body(_spec(date=""), now=NOW)


def test_unparseable_date_is_rejected():
    with pytest.raises(gw.CalendarWriteError, match="Could not parse"):
        gw.build_event_body(_spec(date="whenever"), now=NOW)


def test_far_future_event_is_refused():
    with pytest.raises(gw.CalendarWriteError, match="years in the future"):
        gw.build_event_body(_spec(date="2099-01-01"), now=NOW)


def test_overlong_fields_are_rejected():
    with pytest.raises(gw.CalendarWriteError, match="Title is too long"):
        gw.build_event_body(_spec(title="x" * 5000), now=NOW)
    with pytest.raises(gw.CalendarWriteError, match="Description is too long"):
        gw.build_event_body(_spec(reason="y" * 99999), now=NOW)


def test_invalid_timezone_rejected():
    with pytest.raises(gw.CalendarWriteError, match="Invalid time zone"):
        gw.build_event_body(_spec(timeZone="'; DROP TABLE"), now=NOW)


def test_valid_timezone_is_applied():
    body = gw.build_event_body(_spec(timeZone="America/Toronto"), now=NOW)
    assert body["start"]["timeZone"] == "America/Toronto"


def test_non_dict_spec_rejected():
    with pytest.raises(gw.CalendarWriteError):
        gw.build_event_body("not-a-dict", now=NOW)


def test_reason_becomes_description():
    body = gw.build_event_body(_spec(reason="from calendar candidate"), now=NOW)
    assert body["description"] == "from calendar candidate"


# ══════════════════════════════════════════════════════════════════════════════
# Result / failure handling
# ══════════════════════════════════════════════════════════════════════════════

def test_create_returns_normalized_result():
    result = gw.create_event(_spec(), service=FakeWriteService(), now=NOW)
    assert result["eventId"] == "evt-1"
    assert result["summary"] == "Dentist"
    assert result["htmlLink"].endswith("evt-1")


def test_api_failure_becomes_calendar_write_error():
    service = FakeWriteService(result=RuntimeError("quota exceeded"))
    with pytest.raises(gw.CalendarWriteError, match="creation failed"):
        gw.create_event(_spec(), service=service, now=NOW)


def test_missing_id_in_response_is_an_error():
    with pytest.raises(gw.CalendarWriteError, match="did not return a created event"):
        gw.create_event(_spec(), service=FakeWriteService(result={}), now=NOW)


def test_validation_happens_before_any_api_call():
    service = FakeWriteService()
    with pytest.raises(gw.CalendarWriteError):
        gw.create_event(_spec(title=""), service=service, now=NOW)
    assert service.calls == []


# ══════════════════════════════════════════════════════════════════════════════
# Approval-queue gating
# ══════════════════════════════════════════════════════════════════════════════

def test_create_event_is_approval_required_not_directly_executable():
    assert pg.is_approval_required_tool("calendar.create_event") is True
    assert pg.is_executable("calendar.create_event") is False


def test_evaluate_requires_approval_and_is_high_risk():
    result = pg.evaluate_tool_request("calendar.create_event", {"title": "x"})
    assert result["allowed"] is False
    assert result["decision"] == "requires_approval"
    assert result["riskLevel"] == "high"
    assert result["executionEnabled"] is False


def test_dispatcher_routes_create_event(monkeypatch):
    """The approval dispatcher must reach gcal_write, not gcal."""
    from app import tool_approvals

    captured = {}

    def fake_create(args):
        captured["args"] = args
        return {"eventId": "e1"}

    monkeypatch.setattr(gw, "create_event", fake_create)

    result = tool_approvals._dispatch("calendar.create_event", {"title": "T", "date": "2026-09-01"})
    assert result["eventId"] == "e1"
    assert captured["args"]["title"] == "T"


def test_execution_summary_reports_event_created():
    from app import tool_approvals

    summary = tool_approvals._execution_summary(
        "calendar.create_event", {"eventId": "evt-9"}, True
    )
    assert summary["resultType"] == "calendar_event_created"
    assert summary["ok"] is True


def test_no_shell_or_vault_write_in_module():
    source = Path(gw.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "run_brain_command", "save_draft", "os.system"):
        assert forbidden not in source
