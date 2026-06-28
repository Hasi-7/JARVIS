"""
test_tool_execution.py — Safe-local Tool Execution v0 (Permission Gateway).

The /execute endpoint evaluates + logs every request and executes ONLY the three
allowlisted low-risk brain status tools, via the existing safe brain wrapper. These
tests mock `app.main.run_brain_command` so no real subprocess runs, isolate the log
path, and assert non-executable tools never reach the wrapper.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import permission_gateway as pg
from app.permission_gateway import list_logs, is_executable, brain_command_for
import app.main as m
from app.models import ToolRequestEvaluationRequest


@pytest.fixture(autouse=True)
def _isolate_log(monkeypatch):
    import tempfile, shutil
    d = Path(tempfile.mkdtemp())
    monkeypatch.setattr(pg, "TOOL_LOGS_DIR", d)
    monkeypatch.setattr(pg, "EVALUATIONS_FILE", d / "evaluations.json")
    yield
    shutil.rmtree(d, ignore_errors=True)


def _fake_result(command="status", ok=True, exit_code=0, stdout="vault OK", stderr="", duration=12.3):
    return SimpleNamespace(command=command, ok=ok, exitCode=exit_code,
                           stdout=stdout, stderr=stderr, durationMs=duration)


def _execute(tool, args=None, reason="r", requested_by="manual-ui"):
    return m.permissions_execute(ToolRequestEvaluationRequest(
        tool=tool, args=args, reason=reason, requestedBy=requested_by,
    ))


# ── executable safe-local tools ─────────────────────────────────────────────────

@pytest.mark.parametrize("tool,cmd", [
    ("brain.status", "status"),
    ("brain.raw_status", "raw-status"),
    ("brain.vault_path", "vault-path"),
])
def test_execute_safe_brain_tools(tool, cmd):
    with patch("app.main.run_brain_command", return_value=_fake_result(cmd)) as mrun:
        res = _execute(tool)
    mrun.assert_called_once_with(cmd)           # mapped to the right safe brain subcommand
    assert res.decision == "executed"
    assert res.allowed is True
    assert res.executionEnabled is True
    assert res.ok is True
    assert res.exitCode == 0
    assert res.stdout == "vault OK"
    assert res.evaluationLogId
    assert res.executionLogId


def test_is_executable_and_mapping():
    assert is_executable("brain.status")
    assert not is_executable("gmail.search")
    assert brain_command_for("brain.raw_status") == "raw-status"
    assert brain_command_for("gmail.search") is None


# ── non-executable tools never reach the wrapper ────────────────────────────────

@pytest.mark.parametrize("tool,expected_decision", [
    ("gmail.search", "not_wired"),
    ("gmail.send", "disabled"),
    ("shell.run", "disabled"),
    ("frobnicate.thing", "denied"),
    ("brain.sync_raw", "requires_approval"),
    ("filesystem.write_vault", "requires_approval"),
])
def test_non_executable_tools_do_not_execute(tool, expected_decision):
    with patch("app.main.run_brain_command") as mrun:
        res = _execute(tool, args={"x": 1})
    mrun.assert_not_called()                     # the safe wrapper is never touched
    assert res.allowed is False
    assert res.decision == expected_decision
    assert res.executionLogId is None
    assert res.ok is False
    assert res.error == "Tool is not executable in this build."


def test_execute_empty_tool_rejected():
    from fastapi import HTTPException
    with patch("app.main.run_brain_command") as mrun:
        with pytest.raises(HTTPException) as ei:
            _execute("   ")
    assert ei.value.status_code == 400
    mrun.assert_not_called()


# ── logging behaviour ───────────────────────────────────────────────────────────

def test_evaluation_log_created_for_every_execute():
    with patch("app.main.run_brain_command", return_value=_fake_result()):
        _execute("brain.status")
    with patch("app.main.run_brain_command") as mrun:
        _execute("gmail.search")
        mrun.assert_not_called()
    sources = [l["source"] for l in list_logs(limit=100)]
    # both requests produced a gateway_eval; only the executed one produced gateway_execution
    assert sources.count("gateway_eval") == 2
    assert sources.count("gateway_execution") == 1


def test_execution_log_only_for_executed_tools():
    with patch("app.main.run_brain_command", return_value=_fake_result()):
        _execute("brain.status")
    with patch("app.main.run_brain_command") as mrun:
        _execute("shell.run")
        _execute("gmail.send")
        mrun.assert_not_called()
    execs = [l for l in list_logs(limit=100) if l["source"] == "gateway_execution"]
    assert len(execs) == 1
    e = execs[0]
    assert e["tool"] == "brain.status"
    assert e["decision"] == "executed"
    assert e["result"] == "success"
    assert e["exitCode"] == 0


def test_execution_failure_logged_as_failure():
    with patch("app.main.run_brain_command", return_value=_fake_result(ok=False, exit_code=2, stderr="boom")):
        res = _execute("brain.status")
    assert res.ok is False
    e = [l for l in list_logs() if l["source"] == "gateway_execution"][0]
    assert e["result"] == "failure"
    assert e["exitCode"] == 2
    assert "boom" in (e["stderrPreview"] or "")


def test_stdout_stderr_previews_truncated():
    big = "A" * 5000
    with patch("app.main.run_brain_command", return_value=_fake_result(stdout=big, stderr=big)):
        _execute("brain.status")
    e = [l for l in list_logs() if l["source"] == "gateway_execution"][0]
    assert len(e["stdoutPreview"]) < len(big)
    assert "[truncated]" in e["stdoutPreview"]
    assert "[truncated]" in e["stderrPreview"]


def test_execution_log_redacts_secret_args():
    with patch("app.main.run_brain_command", return_value=_fake_result()):
        _execute("brain.status", args={"token": "ZZsecret", "note": "ok"})
    raw = pg.EVALUATIONS_FILE.read_text(encoding="utf-8")
    assert "ZZsecret" not in raw
    assert "[redacted]" in raw


# ── no shell / no real subprocess path used directly ────────────────────────────

def test_execute_uses_wrapper_not_raw_subprocess():
    """The endpoint must go through app.main.run_brain_command, never subprocess directly."""
    with patch("app.main.run_brain_command", return_value=_fake_result()) as mrun, \
         patch("subprocess.run") as m_sub, patch("subprocess.Popen") as m_pop:
        _execute("brain.status")
    mrun.assert_called_once()
    m_sub.assert_not_called()
    m_pop.assert_not_called()


def test_execute_writes_no_vault_files(tmp_path):
    before = list(tmp_path.iterdir())
    with patch("app.main.run_brain_command", return_value=_fake_result()):
        _execute("brain.status")
    with patch("app.main.run_brain_command") as mrun:
        _execute("gmail.search")
    assert list(tmp_path.iterdir()) == before
