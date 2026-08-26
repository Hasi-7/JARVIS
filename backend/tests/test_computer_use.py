"""MVP v7 computer-use harness tests (PRD §13.3 / §13.4).

Every action driver is injected. Nothing here moves a real mouse, types on a real
keyboard, or captures a real screen.
"""

import json
from pathlib import Path

import pytest

from app import computer_use as cu


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(cu, "SESSIONS_DIR", tmp_path / "cu")
    monkeypatch.setattr(cu, "SESSIONS_FILE", tmp_path / "cu" / "sessions.json")
    monkeypatch.setattr(cu, "SHOTS_DIR", tmp_path / "cu" / "shots")
    monkeypatch.setenv(cu.ENABLED_ENV, "true")


ENV = None       # inherits the monkeypatched os.environ


def _session(**kw):
    params = {"task_description": "tidy the notes window",
              "allowed_windows": ["Obsidian"]}
    params.update(kw)
    return cu.start_session(**params)


def _fg(title="Obsidian - vault"):
    return lambda: title


class _Img:
    size = (2560, 1440)

    def resize(self, size):
        img = _Img()
        img.size = size
        return img

    def save(self, buffer, format=None):
        buffer.write(b"\x89PNG\r\n\x1a\n" + b"0" * 64)


# ══════════════════════════════════════════════════════════════════════════════
# Gate 3 — kill switch, OFF by default
# ══════════════════════════════════════════════════════════════════════════════

def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv(cu.ENABLED_ENV, raising=False)
    assert cu.computer_use_enabled() is False
    with pytest.raises(cu.ComputerUseDisabled, match="disabled"):
        _session()


@pytest.mark.parametrize("value,expected", [
    ("true", True), ("1", True), ("yes", True), ("on", True),
    ("false", False), ("0", False), ("", False), ("maybe", False),
])
def test_kill_switch_parsing(value, expected):
    assert cu.computer_use_enabled({cu.ENABLED_ENV: value}) is expected


def test_actions_refused_when_switch_flipped_off_mid_session(monkeypatch):
    session = _session()
    monkeypatch.delenv(cu.ENABLED_ENV, raising=False)
    clicks = []
    with pytest.raises(cu.ComputerUseDisabled):
        cu.click(session["id"], 10, 10, foreground_fn=_fg(),
                 click_fn=lambda x, y: clicks.append((x, y)))
    assert clicks == []


# ══════════════════════════════════════════════════════════════════════════════
# Gate 5 — foreground window must match; NEVER retarget
# ══════════════════════════════════════════════════════════════════════════════

def test_action_refused_when_focus_moved_elsewhere():
    """The load-bearing guard: a mis-aimed action must not land in another app."""
    session = _session()
    clicks = []
    with pytest.raises(cu.WindowNotAllowed, match="not in this session"):
        cu.click(session["id"], 10, 10, foreground_fn=_fg("Online Banking - Chrome"),
                 click_fn=lambda x, y: clicks.append((x, y)))
    assert clicks == []          # nothing was clicked anywhere


def test_refusal_says_it_did_not_retarget():
    session = _session()
    try:
        cu.click(session["id"], 1, 1, foreground_fn=_fg("Other App"),
                 click_fn=lambda x, y: None)
    except cu.WindowNotAllowed as exc:
        assert "not retargeted" in str(exc)


def test_matching_window_allows_the_action():
    session = _session()
    clicks = []
    result = cu.click(session["id"], 10, 20, foreground_fn=_fg("Obsidian - vault"),
                      click_fn=lambda x, y: clicks.append((x, y)))
    assert result["ok"] is True
    assert clicks == [(10, 20)]


def test_window_matching_is_case_insensitive_substring():
    assert cu.window_matches("My OBSIDIAN vault", ["obsidian"]) is True
    assert cu.window_matches("Notepad", ["obsidian"]) is False


def test_empty_allowlist_matches_nothing():
    assert cu.window_matches("anything", []) is False
    assert cu.window_matches("", ["obsidian"]) is False


def test_empty_allowlist_rejected_at_session_start():
    with pytest.raises(cu.ComputerUseError, match="At least one allowed window"):
        _session(allowed_windows=[])


def test_unknown_foreground_is_refused():
    """A window we cannot identify is not an allowlisted window."""
    session = _session()
    with pytest.raises(cu.WindowNotAllowed):
        cu.click(session["id"], 1, 1, foreground_fn=lambda: "", click_fn=lambda x, y: None)


def test_refusals_are_recorded():
    session = _session()
    with pytest.raises(cu.WindowNotAllowed):
        cu.click(session["id"], 1, 1, foreground_fn=_fg("Other"), click_fn=lambda x, y: None)
    actions = cu.get_session(session["id"])["actions"]
    assert actions[-1]["refused"] == "window_not_allowed"
    assert actions[-1]["ok"] is False


# ══════════════════════════════════════════════════════════════════════════════
# PRD §13.4 — risky categories need per-action confirmation
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("title,category", [
    ("Checkout - Amazon", "purchase"),
    ("Authorize application access", "permissions"),
    ("Settings", "settings"),
    ("Delete 40 items?", "delete"),
    ("Compose - Gmail", "send_message"),
    ("Upload file", "upload"),
])
def test_risky_windows_require_confirmation(title, category):
    session = _session(allowed_windows=[title.split()[0]])
    with pytest.raises(cu.RiskyActionRequiresConfirmation, match=category):
        cu.click(session["id"], 1, 1, foreground_fn=_fg(title), click_fn=lambda x, y: None)


def test_confirmation_allows_the_risky_action():
    session = _session(allowed_windows=["Checkout"])
    clicks = []
    result = cu.click(session["id"], 5, 5, confirm_risk="purchase",
                      foreground_fn=_fg("Checkout - Store"),
                      click_fn=lambda x, y: clicks.append((x, y)))
    assert result["ok"] is True
    assert clicks == [(5, 5)]


def test_wrong_confirmation_category_does_not_unlock():
    session = _session(allowed_windows=["Checkout"])
    with pytest.raises(cu.RiskyActionRequiresConfirmation):
        cu.click(session["id"], 1, 1, confirm_risk="settings",
                 foreground_fn=_fg("Checkout - Store"), click_fn=lambda x, y: None)


def test_confirmation_is_per_action_not_sticky():
    """A confirmed action must not leave the session unlocked for the next one."""
    session = _session(allowed_windows=["Checkout"])
    cu.click(session["id"], 1, 1, confirm_risk="purchase",
             foreground_fn=_fg("Checkout - Store"), click_fn=lambda x, y: None)
    with pytest.raises(cu.RiskyActionRequiresConfirmation):
        cu.click(session["id"], 2, 2, foreground_fn=_fg("Checkout - Store"),
                 click_fn=lambda x, y: None)


def test_ordinary_action_needs_no_confirmation():
    session = _session()
    assert cu.click(session["id"], 1, 1, foreground_fn=_fg("Obsidian - notes"),
                    click_fn=lambda x, y: None)["ok"] is True


# ══════════════════════════════════════════════════════════════════════════════
# Credential surfaces — refused outright, never confirmable
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("title", [
    "Sign in - Google", "Login | Bank", "Password Manager",
    "1Password", "Two-Factor Authentication", "Bitwarden",
])
def test_typing_into_credential_windows_is_refused_outright(title):
    session = _session(allowed_windows=[title.split()[0]])
    typed = []
    with pytest.raises(cu.ComputerUseError, match="password or credential"):
        cu.type_text(session["id"], "hunter2", foreground_fn=_fg(title),
                     type_fn=lambda t: typed.append(t))
    assert typed == []


def test_credential_typing_cannot_be_confirmed_away():
    """Unlike other risky categories, this one has no confirmation escape."""
    session = _session(allowed_windows=["Sign"])
    typed = []
    with pytest.raises(cu.ComputerUseError, match="never confirmable"):
        cu.type_text(session["id"], "hunter2", confirm_risk="credentials",
                     foreground_fn=_fg("Sign in - Google"),
                     type_fn=lambda t: typed.append(t))
    assert typed == []


def test_clicking_a_credential_window_is_confirmable_but_typing_is_not():
    """Clicking Cancel on a login dialog is legitimate; typing a password is not."""
    session = _session(allowed_windows=["Sign"])
    assert cu.click(session["id"], 1, 1, confirm_risk="credentials",
                    foreground_fn=_fg("Sign in - Google"),
                    click_fn=lambda x, y: None)["ok"] is True


# ══════════════════════════════════════════════════════════════════════════════
# Typed-text limits
# ══════════════════════════════════════════════════════════════════════════════

def test_empty_text_rejected():
    session = _session()
    with pytest.raises(cu.ComputerUseError, match="required"):
        cu.type_text(session["id"], "", foreground_fn=_fg(), type_fn=lambda t: None)


def test_overlong_text_rejected():
    session = _session()
    with pytest.raises(cu.ComputerUseError, match="too long"):
        cu.type_text(session["id"], "x" * 99999, foreground_fn=_fg(), type_fn=lambda t: None)


@pytest.mark.parametrize("bad", ["a\x00b", "a\x1bb", "a\x07b"])
def test_control_characters_rejected(bad):
    session = _session()
    with pytest.raises(cu.ComputerUseError, match="Control characters"):
        cu.type_text(session["id"], bad, foreground_fn=_fg(), type_fn=lambda t: None)


def test_tab_and_newline_are_allowed():
    session = _session()
    typed = []
    cu.type_text(session["id"], "line\tone\n", foreground_fn=_fg(),
                 type_fn=lambda t: typed.append(t))
    assert typed == ["line\tone\n"]


@pytest.mark.parametrize("combo", ["ctrl+alt+delete", "win+r", "alt+f4", "WIN+L"])
def test_system_hotkeys_rejected(combo):
    session = _session()
    with pytest.raises(cu.ComputerUseError, match="System key combinations"):
        cu.type_text(session["id"], combo, foreground_fn=_fg(), type_fn=lambda t: None)


def test_typed_content_is_never_logged():
    """Typed text may be personal; only its length belongs in the log."""
    session = _session()
    secret = "my private note contents"
    cu.type_text(session["id"], secret, foreground_fn=_fg(), type_fn=lambda t: None)
    body = str(cu.get_session(session["id"])["actions"])
    assert secret not in body
    assert "chars" in body


# ══════════════════════════════════════════════════════════════════════════════
# Click validation
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("x,y", [(-1, 0), (0, -5)])
def test_negative_coordinates_rejected(x, y):
    session = _session()
    with pytest.raises(cu.ComputerUseError, match="non-negative"):
        cu.click(session["id"], x, y, foreground_fn=_fg(), click_fn=lambda a, b: None)


def test_non_integer_coordinates_rejected():
    session = _session()
    with pytest.raises(cu.ComputerUseError, match="integers"):
        cu.click(session["id"], "left", 5, foreground_fn=_fg(), click_fn=lambda a, b: None)


# ══════════════════════════════════════════════════════════════════════════════
# Budget, limits, stop
# ══════════════════════════════════════════════════════════════════════════════

def test_budget_is_clamped():
    assert cu._clamp_budget(1) == cu.MIN_BUDGET_SECONDS
    assert cu._clamp_budget(999999) == cu.MAX_BUDGET_SECONDS
    assert cu._clamp_budget(None) == cu.DEFAULT_BUDGET_SECONDS
    assert cu._clamp_budget("nonsense") == cu.DEFAULT_BUDGET_SECONDS


def test_actions_refused_after_budget_expiry():
    clock = {"t": 1000.0}
    session = _session(budget_seconds=30, now_fn=lambda: clock["t"])
    clock["t"] += 31
    clicks = []
    with pytest.raises(cu.ComputerUseError, match="budget is exhausted"):
        cu.click(session["id"], 1, 1, now_fn=lambda: clock["t"], foreground_fn=_fg(),
                 click_fn=lambda x, y: clicks.append(1))
    assert clicks == []


def test_action_count_is_capped(monkeypatch):
    monkeypatch.setattr(cu, "MAX_ACTIONS_PER_SESSION", 2)
    session = _session()
    for _ in range(2):
        cu.click(session["id"], 1, 1, foreground_fn=_fg(), click_fn=lambda x, y: None)
    with pytest.raises(cu.ComputerUseError, match="Action limit reached"):
        cu.click(session["id"], 1, 1, foreground_fn=_fg(), click_fn=lambda x, y: None)


def test_stop_is_immediate_and_blocks_actions():
    session = _session()
    assert cu.stop_session(session["id"])["status"] == cu.STATUS_STOPPED
    clicks = []
    with pytest.raises(cu.ComputerUseError, match="was stopped"):
        cu.click(session["id"], 1, 1, foreground_fn=_fg(),
                 click_fn=lambda x, y: clicks.append(1))
    assert clicks == []


def test_stop_is_idempotent():
    session = _session()
    first = cu.stop_session(session["id"])
    assert cu.stop_session(session["id"])["endedAt"] == first["endedAt"]


def test_stop_works_even_when_kill_switch_is_off(monkeypatch):
    """Stopping must never be gated — it is the emergency control."""
    session = _session()
    monkeypatch.delenv(cu.ENABLED_ENV, raising=False)
    assert cu.stop_session(session["id"])["status"] == cu.STATUS_STOPPED


def test_task_description_required_and_bounded():
    with pytest.raises(cu.ComputerUseError, match="task description is required"):
        _session(task_description="   ")
    with pytest.raises(cu.ComputerUseError, match="too long"):
        _session(task_description="x" * 5000)


def test_too_many_windows_rejected():
    with pytest.raises(cu.ComputerUseError, match="Too many allowed windows"):
        _session(allowed_windows=[f"W{i}" for i in range(50)])


def test_starting_a_session_performs_no_action():
    session = _session()
    assert session["actions"] == []
    assert session["status"] == cu.STATUS_ACTIVE


def test_active_session_is_discoverable_for_the_indicator():
    session = _session()
    assert cu.active_session()["id"] == session["id"]
    cu.stop_session(session["id"])
    assert cu.active_session() is None


# ══════════════════════════════════════════════════════════════════════════════
# Observation / screenshots
# ══════════════════════════════════════════════════════════════════════════════

def test_observe_returns_a_downscaled_screenshot():
    session = _session()
    result = cu.observe(session["id"], foreground_fn=_fg(), screenshot_fn=lambda: _Img())
    assert result["width"] <= cu.SCREENSHOT_MAX_WIDTH
    assert result["screenshotBase64"]
    assert any("untrusted" in w.lower() for w in result["warnings"])


def test_observe_obeys_the_window_gate():
    session = _session()
    with pytest.raises(cu.WindowNotAllowed):
        cu.observe(session["id"], foreground_fn=_fg("Other App"),
                   screenshot_fn=lambda: _Img())


def test_screenshots_are_stored_backend_local_never_in_a_vault(tmp_path):
    session = _session()
    result = cu.observe(session["id"], foreground_fn=_fg(), screenshot_fn=lambda: _Img())
    assert result["screenshotPath"] is not None
    assert str(cu.SHOTS_DIR) in result["screenshotPath"]
    assert "vault" not in result["screenshotPath"].lower()


def test_old_screenshots_are_pruned(monkeypatch):
    monkeypatch.setattr(cu, "MAX_STORED_SHOTS", 2)
    session = _session()
    for _ in range(5):
        cu.observe(session["id"], foreground_fn=_fg(), screenshot_fn=lambda: _Img())
    assert len(list(cu.SHOTS_DIR.glob("*.png"))) <= 2


# ══════════════════════════════════════════════════════════════════════════════
# Module-level guarantees
# ══════════════════════════════════════════════════════════════════════════════

def test_failsafe_is_enabled_before_every_real_action():
    source = Path(cu.__file__).read_text(encoding="utf-8")
    assert source.count("pyautogui.FAILSAFE = True") >= 2


def test_no_vault_write_or_shell():
    source = Path(cu.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "run_brain_command", "save_draft", "os.system"):
        assert forbidden not in source


def test_no_hotkey_or_keydown_primitive_is_exposed():
    """Only literal typing and clicking — no key-combination primitive exists."""
    source = Path(cu.__file__).read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]
    for primitive in ("pyautogui.hotkey", "pyautogui.keyDown", "pyautogui.press"):
        assert primitive not in body


def test_summary_shape():
    session = _session(budget_seconds=120)
    summary = cu.session_summary(session)
    assert summary["actionCount"] == 0
    assert summary["remainingSeconds"] <= 120
    assert summary["allowedWindows"] == ["Obsidian"]


def test_obsidian_vault_is_not_a_credential_surface():
    """This app is built around an Obsidian *vault* — matching that word would
    flag every ordinary window and make the tool unusable."""
    assert cu.classify_risk("Obsidian - my vault", "type", "notes") != "credentials"
    assert cu.classify_risk("vault/wiki/rust.md - Obsidian", "click") != "credentials"


def test_real_credential_surfaces_are_still_caught():
    for title in ("Sign in - Google", "Password Manager", "Bitwarden",
                  "Password Vault", "Two-Factor Authentication"):
        assert cu.classify_risk(title, "type", "x") == "credentials", title


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints — gate 2 (operator token) and the ungated emergency stop
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def token(monkeypatch):
    from app import tool_approvals
    monkeypatch.setenv(tool_approvals.APPROVAL_TOKEN_ENV, "ZZ-operator-token")
    return "ZZ-operator-token"


def test_start_requires_the_operator_token(token):
    from fastapi import HTTPException
    import app.main as m
    from app.models import StartComputerUseSessionRequest

    req = StartComputerUseSessionRequest(task="t", allowedWindows=["Obsidian"])
    with pytest.raises(HTTPException) as exc:
        m.computer_use_start(req, x_brain_approval_token=None)
    assert exc.value.status_code in (401, 403)


def test_start_rejects_a_wrong_token(token):
    from fastapi import HTTPException
    import app.main as m
    from app.models import StartComputerUseSessionRequest

    req = StartComputerUseSessionRequest(task="t", allowedWindows=["Obsidian"])
    with pytest.raises(HTTPException) as exc:
        m.computer_use_start(req, x_brain_approval_token="wrong")
    assert exc.value.status_code in (401, 403)


def test_direct_start_is_refused_and_points_at_the_approval_queue(token):
    """Session start must go through the gateway, not around it.

    A valid operator token used to be enough to open a desktop-control session,
    which meant the most privileged capability was the one that skipped the
    stack PRD §32 defines — and the documented Assist-mode requirement was
    never actually checked anywhere.
    """
    from fastapi import HTTPException
    import app.main as m
    from app.models import StartComputerUseSessionRequest

    req = StartComputerUseSessionRequest(task="tidy notes", allowedWindows=["Obsidian"])
    with pytest.raises(HTTPException) as exc:
        m.computer_use_start(req, x_brain_approval_token=token)
    assert exc.value.status_code == 410
    assert "computer.start_session" in exc.value.detail
    # And nothing was started as a side effect of the refusal.
    assert cu.active_session() is None


def test_start_session_through_the_approval_queue(token, monkeypatch):
    """The supported path: Assist-mode request -> approve -> execute."""
    from app import permission_gateway as pg
    from app.agent_tool_requests import create_request
    from app.main import tool_approval_approve, tool_approval_execute
    from app.models import ApproveToolApprovalRequest, ExecuteToolApprovalRequest

    monkeypatch.setenv(pg.PRIVILEGED_EXECUTION_ENV, "true")
    request = create_request(
        tool="computer.start_session",
        args={"task": "tidy notes", "allowedWindows": ["Obsidian"], "budgetSeconds": 120},
        reason="Repetitive UI tidy-up", requested_by="local-agent",
        conversation_id="conv-1", mode="assist",
    )
    assert request["status"] == "pending_approval"

    tool_approval_approve(request["id"], ApproveToolApprovalRequest(approvedBy="owner"), token)
    executed = tool_approval_execute(request["approvalId"], ExecuteToolApprovalRequest(), token)
    assert executed.status == "executed"
    assert executed.result.resultType == "computer_session_started"

    live = cu.active_session()
    assert live is not None
    assert live["task"] == "tidy notes"
    assert live["allowedWindows"] == ["Obsidian"]


def test_a_session_cannot_be_queued_outside_assist_mode(token, monkeypatch):
    """This is where the Assist-mode guard actually lives now."""
    from app.agent_tool_requests import create_request

    for mode in ("locked", "observe", "draft", "research", "escalation"):
        record = create_request(
            tool="computer.start_session",
            args={"task": "t", "allowedWindows": ["X"]},
            reason="r", requested_by="local-agent", conversation_id="c", mode=mode,
        )
        assert record["status"] == "evaluated_only", mode
        assert record["approvalId"] is None, mode
    assert cu.active_session() is None


def test_an_empty_window_allowlist_is_refused_before_it_reaches_the_queue():
    """An unscoped session would let the agent act on whatever is focused."""
    from app import tool_approvals as ta

    with pytest.raises(Exception) as exc:
        ta.validate_canonical_args("computer.start_session", {"task": "t", "allowedWindows": []})
    assert "allowed window" in str(exc.value).lower() or "at least" in str(exc.value).lower()


def test_click_requires_the_token(token):
    from fastapi import HTTPException
    import app.main as m
    from app.models import ComputerUseClickRequest

    session = _session()
    with pytest.raises(HTTPException) as exc:
        m.computer_use_click(session["id"], ComputerUseClickRequest(x=1, y=1),
                             x_brain_approval_token=None)
    assert exc.value.status_code in (401, 403)


def test_stop_is_never_token_gated(token):
    """The emergency stop must work even without a token."""
    import app.main as m

    session = _session()
    res = m.computer_use_stop(session["id"])
    assert res.session.status == cu.STATUS_STOPPED


def test_status_is_unauthenticated_so_the_indicator_always_renders():
    import app.main as m

    session = _session()
    res = m.computer_use_status()
    assert res.enabled is True
    assert res.active is not None
    assert res.active.id == session["id"]
    assert "ACTIVE" in res.message


def test_status_when_disabled(monkeypatch):
    import app.main as m
    monkeypatch.delenv(cu.ENABLED_ENV, raising=False)
    res = m.computer_use_status()
    assert res.enabled is False
    assert res.active is None


def test_risky_action_maps_to_428(token, monkeypatch):
    from fastapi import HTTPException
    import app.main as m
    from app.models import ComputerUseClickRequest

    session = _session(allowed_windows=["Checkout"])
    # main.py binds `cu_click` at import time, so patching cu.click would not
    # affect the endpoint — patch the binding the endpoint actually calls.
    monkeypatch.setattr(m, "cu_click", lambda *a, **k: (_ for _ in ()).throw(
        cu.RiskyActionRequiresConfirmation("needs confirmation")))
    with pytest.raises(HTTPException) as exc:
        m.computer_use_click(session["id"], ComputerUseClickRequest(x=1, y=1),
                             x_brain_approval_token=token)
    assert exc.value.status_code == 428     # Precondition Required


def test_window_mismatch_maps_to_409(token, monkeypatch):
    from fastapi import HTTPException
    import app.main as m
    from app.models import ComputerUseClickRequest

    session = _session()
    monkeypatch.setattr(m, "cu_click", lambda *a, **k: (_ for _ in ()).throw(
        cu.WindowNotAllowed("focus moved")))
    with pytest.raises(HTTPException) as exc:
        m.computer_use_click(session["id"], ComputerUseClickRequest(x=1, y=1),
                             x_brain_approval_token=token)
    assert exc.value.status_code == 409


def test_disabled_maps_to_503(token, monkeypatch):
    from fastapi import HTTPException
    import app.main as m
    from app.models import StartComputerUseSessionRequest

    monkeypatch.delenv(cu.ENABLED_ENV, raising=False)
    # Start is gateway-only now, so the kill switch is exercised on an action.
    with pytest.raises(HTTPException) as exc:
        m.computer_use_observe(
            "no-such-session", x_brain_approval_token=token,
        )
    assert exc.value.status_code == 503


def test_request_models_forbid_extra_fields():
    from pydantic import ValidationError
    from app.models import ComputerUseClickRequest, StartComputerUseSessionRequest

    with pytest.raises(ValidationError):
        ComputerUseClickRequest(x=1, y=1, button="right")
    with pytest.raises(ValidationError):
        StartComputerUseSessionRequest(task="t", allowedWindows=["X"], sneaky=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tool inventory reflects the real kill-switch state
# ══════════════════════════════════════════════════════════════════════════════

def test_inventory_reports_disabled_while_the_switch_is_off(monkeypatch):
    from app import tools
    monkeypatch.setattr(tools, "_computer_use_ready", lambda: False)
    entry = {t["id"]: t for t in tools.list_tool_connections()}["computer-use"]
    assert entry["status"] == "disabled"
    assert entry["allowedNow"] == []
    assert "click" in entry["blockedNow"]


def test_inventory_reports_available_once_enabled(monkeypatch):
    from app import tools
    monkeypatch.setattr(tools, "_computer_use_ready", lambda: True)
    entry = {t["id"]: t for t in tools.list_tool_connections()}["computer-use"]
    assert entry["status"] == "available"
    assert entry["enabled"] is True
    assert set(entry["allowedNow"]) == {"screenshot", "click", "type"}
    # Even when fully enabled, credential typing stays blocked.
    assert "credential_typing" in entry["blockedNow"]


def test_inventory_never_claims_a_sandbox_protects_desktop_control(monkeypatch):
    """Full desktop control has no sandbox boundary; saying otherwise would
    misrepresent what is actually protecting the user."""
    from app import tools
    monkeypatch.setattr(tools, "_computer_use_ready", lambda: True)
    entry = {t["id"]: t for t in tools.list_tool_connections()}["computer-use"]
    assert not any("NemoClaw" in r or "OpenShell" in r for r in entry["requires"])


# ── audit trail (PRD §13.3, §32, acceptance criterion #19) ────────────────────
# Computer-use actions previously reached only a backend session file and a
# Python log line, so the one capability that can click and type on the real
# desktop was the one absent from the audit log.

def _gateway_logs(monkeypatch, tmp_path):
    from app import permission_gateway as pg
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", tmp_path / "tool-logs")
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", tmp_path / "tool-logs" / "evaluations.json")
    return pg


def test_a_click_reaches_the_gateway_audit_log(tmp_path, monkeypatch):
    pg = _gateway_logs(monkeypatch, tmp_path)
    session = _session()
    cu.click(session["id"], 10, 20, foreground_fn=_fg(), click_fn=lambda x, y: None)

    entries = [e for e in pg.list_logs(limit=50) if e["source"] == "computer_use_action"]
    assert len(entries) == 1
    assert entries[0]["tool"] == "computer.click"
    assert entries[0]["result"] == "success"
    assert entries[0]["riskLevel"] == "high"
    assert session["id"] in entries[0]["requestId"]


def test_a_refusal_reaches_the_audit_log(tmp_path, monkeypatch):
    """The most audit-relevant event: the agent tried to act out of scope."""
    pg = _gateway_logs(monkeypatch, tmp_path)
    session = _session()
    with pytest.raises(cu.WindowNotAllowed):
        cu.click(session["id"], 10, 20, foreground_fn=_fg("Online Banking - Chrome"),
                 click_fn=lambda x, y: None)

    entries = [e for e in pg.list_logs(limit=50) if e["source"] == "computer_use_action"]
    assert len(entries) == 1
    assert entries[0]["result"] == "failure"
    assert entries[0]["allowed"] is False
    assert "window_not_allowed" in entries[0]["policyNotes"]


def test_typed_content_never_reaches_the_audit_log(tmp_path, monkeypatch):
    pg = _gateway_logs(monkeypatch, tmp_path)
    session = _session(allowed_windows=["Notepad"])
    secret = "hunter2-do-not-log-me"
    cu.type_text(session["id"], secret, foreground_fn=_fg("Notepad"),
                 type_fn=lambda text: None)

    blob = json.dumps(pg.list_logs(limit=50))
    assert secret not in blob
    entries = [e for e in pg.list_logs(limit=50) if e["source"] == "computer_use_action"]
    assert len(entries) == 1
    assert entries[0]["tool"] == "computer.type"


def test_audit_failure_never_breaks_the_action(monkeypatch):
    """A broken audit write must not turn a completed click into an error."""
    from app import permission_gateway as pg

    def boom(**kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(pg, "log_computer_use_action", boom)
    session = _session()
    clicks = []
    result = cu.click(session["id"], 5, 5, foreground_fn=_fg(),
                      click_fn=lambda x, y: clicks.append((x, y)))
    assert result["x"] == 5
    assert clicks == [(5, 5)]
