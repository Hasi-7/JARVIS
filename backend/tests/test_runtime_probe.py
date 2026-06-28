"""
test_runtime_probe.py — NemoClaw/OpenShell Health Probe v0 (explicit, opt-in).

The probe performs a single bounded GET to a CONFIGURED LOCAL runtime URL only when
asked. It unlocks nothing, starts no process, runs no shell/`brain`, writes no vault,
and never probes non-local hosts (unless explicitly allowed) or sends credentials.

Tests inject a fake HTTP client (no real network) and isolate the last-probe cache.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from app import runtime_probe as rp
from app.runtime_probe import probe_nemoclaw, read_last_probe
from app.runtime_status import list_runtime_status


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    import tempfile, shutil
    d = Path(tempfile.mkdtemp())
    monkeypatch.setattr(rp, "LAST_PROBE_DIR", d / "runtime")
    monkeypatch.setattr(rp, "LAST_PROBE_FILE", d / "runtime" / "last-probe.json")
    yield
    shutil.rmtree(d, ignore_errors=True)


class Spy:
    """Fake HTTP client. Records calls; returns a status code or raises."""
    def __init__(self, result=200, exc=None):
        self.calls = []
        self.result = result
        self.exc = exc

    def __call__(self, url, timeout_s):
        self.calls.append((url, timeout_s))
        if self.exc is not None:
            raise self.exc
        return self.result


# ── not configured / not enabled → no network call ──────────────────────────────

def test_no_url_not_configured_no_network():
    spy = Spy()
    r = probe_nemoclaw(env={}, http_get=spy)
    assert r["status"] == "not_configured"
    assert r["configured"] is False
    assert r["reachable"] is False
    assert spy.calls == []                       # no network call
    assert r["details"]["urlConfigured"] is False


def test_disabled_flag_no_network():
    spy = Spy()
    env = {"NEMOCLAW_ENABLED": "false", "NEMOCLAW_RUNTIME_URL": "http://localhost:9000"}
    r = probe_nemoclaw(env=env, http_get=spy)
    assert r["status"] == "not_configured"
    assert r["reachable"] is False
    assert spy.calls == []


def test_enabled_flag_missing_no_network():
    spy = Spy()
    env = {"NEMOCLAW_RUNTIME_URL": "http://localhost:9000"}   # url but no enabled flag
    r = probe_nemoclaw(env=env, http_get=spy)
    assert r["status"] == "not_configured"
    assert spy.calls == []


# ── local success / failure ─────────────────────────────────────────────────────

def _enabled_env(url):
    return {"NEMOCLAW_ENABLED": "true", "NEMOCLAW_RUNTIME_URL": url}


def test_localhost_success_reachable():
    spy = Spy(result=200)
    r = probe_nemoclaw(env=_enabled_env("http://localhost:9000/health"), http_get=spy)
    assert r["status"] == "reachable"
    assert r["reachable"] is True
    assert r["configured"] is True
    assert len(spy.calls) == 1
    assert spy.calls[0][0] == "http://localhost:9000/health"


def test_127_success_reachable():
    spy = Spy(result=204)
    r = probe_nemoclaw(env=_enabled_env("http://127.0.0.1:9000"), http_get=spy)
    assert r["status"] == "reachable"
    assert r["reachable"] is True


def test_localhost_timeout_unavailable():
    spy = Spy(exc=TimeoutError("timed out"))
    r = probe_nemoclaw(env=_enabled_env("http://localhost:9000"), http_get=spy)
    assert r["status"] == "unavailable"
    assert r["reachable"] is False
    assert "did not respond" in r["message"]


def test_localhost_non_2xx_unavailable():
    spy = Spy(result=500)
    r = probe_nemoclaw(env=_enabled_env("http://localhost:9000"), http_get=spy)
    assert r["status"] == "unavailable"
    assert r["reachable"] is False


# ── URL safety ──────────────────────────────────────────────────────────────────

def test_non_local_rejected_by_default():
    spy = Spy()
    r = probe_nemoclaw(env=_enabled_env("http://10.0.0.5/health"), http_get=spy)
    assert r["status"] == "error"
    assert r["reachable"] is False
    assert spy.calls == []                       # rejected before any network call
    assert "Remote runtime probing is blocked" in r["message"]


def test_public_host_rejected_by_default():
    spy = Spy()
    r = probe_nemoclaw(env=_enabled_env("http://example.com/health"), http_get=spy)
    assert r["status"] == "error"
    assert spy.calls == []


def test_remote_allowed_with_flag():
    spy = Spy(result=200)
    env = _enabled_env("http://10.0.0.5/health")
    env["NEMOCLAW_ALLOW_REMOTE_PROBE"] = "true"
    r = probe_nemoclaw(env=env, http_get=spy)
    assert len(spy.calls) == 1                    # now allowed
    assert r["details"]["remoteProbeAllowed"] is True


def test_credentials_in_url_rejected():
    spy = Spy()
    r = probe_nemoclaw(env=_enabled_env("http://user:pass@localhost:9000"), http_get=spy)
    assert r["status"] == "error"
    assert spy.calls == []
    assert "Credentials" in r["message"]


def test_non_http_scheme_rejected():
    spy = Spy()
    r = probe_nemoclaw(env=_enabled_env("ftp://localhost:9000"), http_get=spy)
    assert r["status"] == "error"
    assert spy.calls == []


def test_host_redacted_excludes_path_and_query():
    spy = Spy(result=200)
    r = probe_nemoclaw(env=_enabled_env("http://localhost:9000/health?token=SECRET"), http_get=spy)
    assert r["details"]["hostRedacted"] == "http://localhost:9000"
    assert "SECRET" not in (r["details"]["hostRedacted"] or "")


# ── timeout clamp ───────────────────────────────────────────────────────────────

def test_timeout_clamped_max():
    spy = Spy(result=200)
    probe_nemoclaw(timeout_ms=999999, env=_enabled_env("http://localhost:9000"), http_get=spy)
    # http_get receives seconds; clamp is 3000ms = 3.0s
    assert spy.calls[0][1] == 3.0


def test_timeout_clamped_min():
    spy = Spy(result=200)
    probe_nemoclaw(timeout_ms=-50, env=_enabled_env("http://localhost:9000"), http_get=spy)
    assert spy.calls[0][1] == 0.001              # 1ms floor


def test_timeout_default_when_none():
    spy = Spy(result=200)
    probe_nemoclaw(timeout_ms=None, env=_enabled_env("http://localhost:9000"), http_get=spy)
    assert spy.calls[0][1] == 1.5                # default 1500ms


# ── no execution side effects ───────────────────────────────────────────────────

def test_no_shell_brain_or_subprocess():
    spy = Spy(result=200)
    with patch("app.brain.run_brain_command") as mbrain, patch("subprocess.run") as msub:
        probe_nemoclaw(env={}, http_get=spy)
        probe_nemoclaw(env=_enabled_env("http://localhost:9000"), http_get=spy)
    mbrain.assert_not_called()
    msub.assert_not_called()


def test_probe_does_not_enable_browser_or_computer_use():
    # A reachable probe must NOT flip browser/computer-use on in runtime status.
    spy = Spy(result=200)
    env = _enabled_env("http://localhost:9000")
    probe_nemoclaw(env=env, http_get=spy)
    by = {i["id"]: i for i in list_runtime_status(env=env)}
    assert by["browser_harness"]["status"] == "disabled"
    assert by["browser_harness"]["available"] is False
    assert by["computer_use"]["status"] == "disabled"
    assert by["computer_use"]["available"] is False


# ── last-probe cache ────────────────────────────────────────────────────────────

def test_last_probe_cached_and_readable():
    spy = Spy(result=200)
    probe_nemoclaw(env=_enabled_env("http://localhost:9000"), http_get=spy)
    last = read_last_probe()
    assert last is not None
    assert last["status"] == "reachable"


def test_read_last_probe_none_when_absent():
    assert read_last_probe() is None


# ── endpoint ────────────────────────────────────────────────────────────────────

def test_endpoint_not_configured(monkeypatch):
    from app.main import runtime_probe_nemoclaw
    from app.models import NemoclawProbeRequest
    # Force an empty env so the real os.environ doesn't carry config.
    monkeypatch.setattr(rp.os, "environ", {})
    res = runtime_probe_nemoclaw(NemoclawProbeRequest())
    assert res.status == "not_configured"
    assert res.reachable is False


def test_last_endpoint(monkeypatch):
    from app.main import runtime_probe_nemoclaw_last
    spy = Spy(result=200)
    probe_nemoclaw(env=_enabled_env("http://localhost:9000"), http_get=spy)
    res = runtime_probe_nemoclaw_last()
    assert res.lastProbe is not None
    assert res.lastProbe.status == "reachable"
