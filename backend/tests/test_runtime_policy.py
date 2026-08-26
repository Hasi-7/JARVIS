"""
test_runtime_policy.py — NemoClaw/OpenShell Policy Inspection v0.

Inspection is read-only: it reads ONLY the configured NEMOCLAW_POLICY_PATH, parses it
defensively, and summarizes declared scopes. It never enforces the policy, starts the
runtime, makes a network call, executes/imports the policy file, runs shell/`brain`,
writes the vault, or unlocks any capability.

Tests use real temp files and set NEMOCLAW_POLICY_PATH via the injected env dict, so no
process/network/shell/vault side effect is possible.
"""

import json
from pathlib import Path

import pytest

from app import runtime_policy as rpol
from app.runtime_policy import inspect_nemoclaw_policy, MAX_POLICY_BYTES


@pytest.fixture()
def tmp_policy(tmp_path):
    def _write(name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p
    return _write


# ── not configured ───────────────────────────────────────────────────────────────

def test_no_path_configured():
    r = inspect_nemoclaw_policy(env={})
    assert r["status"] == "not_configured"
    assert r["configured"] is False
    assert r["pathConfigured"] is False
    assert r["pathExists"] is False
    assert r["readable"] is False
    assert r["valid"] is False
    assert r["summary"] is None
    assert r["policyPathDisplay"] is None


def test_blank_path_configured():
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": "   "})
    assert r["status"] == "not_configured"
    assert r["pathConfigured"] is False


# ── missing file ─────────────────────────────────────────────────────────────────

def test_missing_file(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(missing)})
    assert r["status"] == "missing"
    assert r["configured"] is True
    assert r["pathConfigured"] is True
    assert r["pathExists"] is False
    assert r["readable"] is False
    assert r["errors"]


def test_directory_is_unreadable_not_listed(tmp_path):
    d = tmp_path / "policydir"
    d.mkdir()
    (d / "secret.txt").write_text("should not be listed", encoding="utf-8")
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(d)})
    assert r["status"] == "unreadable"
    assert r["pathExists"] is True
    assert r["readable"] is False
    assert r["summary"] is None
    # nothing from inside the directory leaks
    assert "secret" not in json.dumps(r)


# ── valid JSON policy ────────────────────────────────────────────────────────────

def test_valid_json_policy_summarized(tmp_policy):
    p = tmp_policy("policy.json", json.dumps({
        "modes": ["observe", "draft", "assist"],
        "network_policy": "restricted",
        "filesystem_scopes": ["vault_read_only"],
        "browser": False,
        "computer_use": False,
        "mcp": False,
        "credentials": "blocked",
    }))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "loaded"
    assert r["valid"] is True
    assert r["readable"] is True
    assert r["format"] == "json"
    # This module inspects; OpenShell enforces. The message must not imply the
    # policy is inert -- it is what openshell_exec checks before executing.
    assert "never enforces it" in r["message"]
    s = r["summary"]
    assert s["declaredModes"] == ["observe", "draft", "assist"]
    assert s["networkPolicy"] == "restricted"
    assert s["filesystemScopes"] == ["vault_read_only"]
    assert s["browserAllowed"] is False
    assert s["computerUseAllowed"] is False
    assert s["mcpAllowed"] is False
    assert s["credentialAccess"] == "blocked"
    assert s["unknownKeys"] == []


def test_browser_allowed_only_when_clearly_declared(tmp_policy):
    p = tmp_policy("policy.json", json.dumps({"browser": True, "computer_use": "allowed"}))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["summary"]["browserAllowed"] is True
    assert r["summary"]["computerUseAllowed"] is True


def test_capabilities_default_to_unknown_when_absent(tmp_policy):
    p = tmp_policy("policy.json", json.dumps({"modes": ["observe"]}))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    s = r["summary"]
    assert s["browserAllowed"] is None
    assert s["computerUseAllowed"] is None
    assert s["mcpAllowed"] is None
    assert s["credentialAccess"] == "unknown"


def test_ambiguous_capability_is_unknown_not_allowed(tmp_policy):
    p = tmp_policy("policy.json", json.dumps({"browser": "maybe"}))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["summary"]["browserAllowed"] is None


def test_nested_capability_object(tmp_policy):
    p = tmp_policy("policy.json", json.dumps({
        "browser": {"allowed": False},
        "filesystem": {"scopes": ["vault_read_only", "downloads"]},
        "network": {"policy": "restricted"},
        "credentials": {"access": "blocked"},
    }))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    s = r["summary"]
    assert s["browserAllowed"] is False
    assert s["filesystemScopes"] == ["vault_read_only", "downloads"]
    assert s["networkPolicy"] == "restricted"
    assert s["credentialAccess"] == "blocked"


# ── unknown keys surfaced ────────────────────────────────────────────────────────

def test_unknown_keys_surfaced(tmp_policy):
    p = tmp_policy("policy.json", json.dumps({
        "modes": ["observe"],
        "some_future_scope": {"x": 1},
        "another_unknown": True,
    }))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "loaded"
    assert r["summary"]["unknownKeys"] == ["another_unknown", "some_future_scope"]
    assert any("not recognized" in w for w in r["warnings"])


def test_unknown_but_valid_policy_has_warning(tmp_policy):
    p = tmp_policy("policy.json", json.dumps({"totally": "unrecognized"}))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "loaded"
    assert r["valid"] is True
    assert any("unknown-but-valid" in w for w in r["warnings"])


# ── invalid JSON ─────────────────────────────────────────────────────────────────

def test_invalid_json_reported(tmp_policy):
    p = tmp_policy("policy.json", "{ this is: not json ]")
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "invalid"
    assert r["valid"] is False
    assert r["readable"] is True
    assert r["summary"] is None
    assert r["errors"]


def test_json_non_object_root_is_invalid(tmp_policy):
    p = tmp_policy("policy.json", json.dumps(["observe", "draft"]))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "invalid"
    assert r["summary"] is None


# ── oversized file rejected ──────────────────────────────────────────────────────

def test_oversized_file_rejected(tmp_path):
    p = tmp_path / "huge.json"
    p.write_text("{" + ("\"k\":\"" + "x" * 1000 + "\"," ) * (MAX_POLICY_BYTES // 900) + "\"end\":1}", encoding="utf-8")
    assert p.stat().st_size > MAX_POLICY_BYTES
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "invalid"
    assert r["valid"] is False
    assert any("too large" in e.lower() or "limit" in e.lower() for e in r["errors"])


# ── UTF-8 only ───────────────────────────────────────────────────────────────────

def test_non_utf8_file_unreadable(tmp_path):
    p = tmp_path / "policy.json"
    p.write_bytes(b"\xff\xfe\x00\x01 not utf8")
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "unreadable"
    assert r["readable"] is False


# ── YAML behaviour ───────────────────────────────────────────────────────────────

def test_yaml_policy_when_supported(tmp_policy):
    if rpol._yaml is None:
        pytest.skip("PyYAML not installed in this environment")
    p = tmp_policy("policy.yaml", "modes:\n  - observe\n  - draft\nnetwork_policy: restricted\nbrowser: false\n")
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "loaded"
    assert r["format"] == "yaml"
    assert r["summary"]["declaredModes"] == ["observe", "draft"]
    assert r["summary"]["networkPolicy"] == "restricted"
    assert r["summary"]["browserAllowed"] is False


def test_yaml_reported_honestly_when_unsupported(tmp_policy, monkeypatch):
    monkeypatch.setattr(rpol, "_yaml", None)
    p = tmp_policy("policy.yaml", "modes:\n  - observe\n")
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "invalid"
    assert r["format"] == "yaml"
    assert any("not supported" in e.lower() for e in r["errors"])


def test_uses_yaml_safe_load_not_load(monkeypatch, tmp_policy):
    """Guard: the module calls yaml.safe_load (SafeLoader), never the unsafe yaml.load."""
    import inspect as _inspect
    # source guard: the module must not call the unsafe full loader directly.
    src = _inspect.getsource(rpol)
    assert "_yaml.load(" not in src
    assert "yaml.load(" not in src
    assert "safe_load" in src

    if rpol._yaml is None:
        pytest.skip("PyYAML not installed in this environment")
    # runtime guard: safe_load is the parse entry point that actually runs.
    calls = {"safe": 0}
    real_safe = rpol._yaml.safe_load

    def _spy(text):
        calls["safe"] += 1
        return real_safe(text)

    monkeypatch.setattr(rpol._yaml, "safe_load", _spy)
    p = tmp_policy("policy.yaml", "modes: [observe]\n")
    inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert calls["safe"] == 1


# ── safety: no frontend path, no side effects ────────────────────────────────────

def test_only_env_path_is_read_no_argument_for_frontend_path(tmp_policy):
    """inspect_nemoclaw_policy takes no file-path argument — only env is honored."""
    import inspect
    sig = inspect.signature(inspect_nemoclaw_policy)
    assert list(sig.parameters) == ["env"]
    # and a stray env key that looks like a frontend path is ignored
    p = tmp_policy("real.json", json.dumps({"modes": ["observe"]}))
    r = inspect_nemoclaw_policy(env={
        "NEMOCLAW_POLICY_PATH": str(p),
        "path": "C:/Windows/System32/drivers/etc/hosts",
        "file": "/etc/passwd",
    })
    assert r["status"] == "loaded"
    assert "System32" not in json.dumps(r)
    assert "passwd" not in json.dumps(r)


def test_no_subprocess_or_network(monkeypatch, tmp_policy):
    """The inspector must not spawn a process or open a socket."""
    import subprocess
    import socket

    def _boom_popen(*a, **k):
        raise AssertionError("policy inspection must not launch a subprocess")

    def _boom_socket(*a, **k):
        raise AssertionError("policy inspection must not open a socket")

    monkeypatch.setattr(subprocess, "Popen", _boom_popen)
    monkeypatch.setattr(subprocess, "run", _boom_popen)
    monkeypatch.setattr(socket, "socket", _boom_socket)

    p = tmp_policy("policy.json", json.dumps({"modes": ["observe"], "browser": True}))
    r = inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    assert r["status"] == "loaded"


def test_inspection_never_writes_next_to_policy(tmp_path, tmp_policy):
    p = tmp_policy("policy.json", json.dumps({"modes": ["observe"]}))
    before = set(x.name for x in tmp_path.iterdir())
    inspect_nemoclaw_policy(env={"NEMOCLAW_POLICY_PATH": str(p)})
    after = set(x.name for x in tmp_path.iterdir())
    assert before == after   # no files created/removed by inspection


# ── endpoint smoke (read-only) ───────────────────────────────────────────────────

def test_endpoint_returns_not_configured(monkeypatch):
    from app.main import runtime_policy_nemoclaw
    monkeypatch.delenv("NEMOCLAW_POLICY_PATH", raising=False)
    res = runtime_policy_nemoclaw()
    assert res.status == "not_configured"
    assert res.summary is None


def test_endpoint_summarizes_configured_policy(monkeypatch, tmp_policy):
    from app.main import runtime_policy_nemoclaw
    p = tmp_policy("policy.json", json.dumps({"modes": ["observe"], "browser": False}))
    monkeypatch.setenv("NEMOCLAW_POLICY_PATH", str(p))
    res = runtime_policy_nemoclaw()
    assert res.status == "loaded"
    assert res.summary.declaredModes == ["observe"]
    assert res.summary.browserAllowed is False


# ══════════════════════════════════════════════════════════════════════════════
# Real NVIDIA OpenShell SandboxPolicy schema (proto/openshell/sandbox.proto)
# ══════════════════════════════════════════════════════════════════════════════

_OPENSHELL_POLICY = """version: 1

filesystem_policy:
  include_workdir: true
  read_only:
    - /usr
    - /etc
  read_write:
    - /sandbox
    - /tmp

landlock:
  compatibility: best_effort
"""


def _inspect_yaml(tmp_path, text, name="policy.yaml"):
    from app.runtime_policy import inspect_nemoclaw_policy
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return inspect_nemoclaw_policy({"NEMOCLAW_POLICY_PATH": str(path)})


def test_official_openshell_keys_are_recognized(tmp_path):
    result = _inspect_yaml(tmp_path, _OPENSHELL_POLICY)
    assert result["status"] == "loaded"
    # Regression: these were reported as unknown before the real schema was known.
    assert result["summary"]["unknownKeys"] == []


def test_filesystem_policy_scopes_are_surfaced(tmp_path):
    scopes = _inspect_yaml(tmp_path, _OPENSHELL_POLICY)["summary"]["filesystemScopes"]
    assert "ro: /usr" in scopes
    assert "rw: /sandbox" in scopes
    assert any("include_workdir" in s for s in scopes)


def test_absent_network_policies_reads_as_deny(tmp_path):
    net = _inspect_yaml(tmp_path, _OPENSHELL_POLICY)["summary"]["networkPolicy"]
    assert net == "deny (no network_policies declared)"


def test_declared_network_policies_are_named(tmp_path):
    text = _OPENSHELL_POLICY + "\nnetwork_policies:\n  gitlab:\n    allow: true\n"
    net = _inspect_yaml(tmp_path, text)["summary"]["networkPolicy"]
    assert net.startswith("allow (")
    assert "gitlab" in net


def test_foreign_document_does_not_infer_deny(tmp_path):
    """A non-OpenShell document missing the key means unknown, not deny."""
    result = _inspect_yaml(tmp_path, "some_other_tool:\n  enabled: true\n")
    assert result["summary"]["networkPolicy"] is None


def test_best_effort_landlock_raises_fail_open_warning(tmp_path):
    warnings = _inspect_yaml(tmp_path, _OPENSHELL_POLICY)["warnings"]
    joined = " ".join(warnings).lower()
    assert "fails open" in joined
    assert "hard_requirement" in joined


def test_hard_requirement_landlock_has_no_fail_open_warning(tmp_path):
    text = _OPENSHELL_POLICY.replace("best_effort", "hard_requirement")
    warnings = _inspect_yaml(tmp_path, text)["warnings"]
    assert not any("fails open" in w.lower() for w in warnings)


def test_recognized_policy_does_not_warn_about_missing_scopes(tmp_path):
    warnings = _inspect_yaml(tmp_path, _OPENSHELL_POLICY)["warnings"]
    assert not any("No recognized policy scopes" in w for w in warnings)


def test_inspection_still_enables_nothing(tmp_path):
    """Reading a permissive policy must not flip any capability on."""
    text = _OPENSHELL_POLICY + "\nnetwork_policies:\n  everything:\n    allow: true\n"
    summary = _inspect_yaml(tmp_path, text)["summary"]
    assert summary["browserAllowed"] is None
    assert summary["computerUseAllowed"] is None
    assert summary["mcpAllowed"] is None
    assert summary["credentialAccess"] == "unknown"


# ── the policy this repo actually ships ───────────────────────────────────────
# MVP v4 browsing was broken twice, independently: openshell_exec refuses to run
# under best_effort Landlock, AND no network_policies were declared, so curl had
# no egress even once Landlock was fixed. These pin both halves.

_SHIPPED_POLICY = Path(__file__).parent.parent / "policies" / "jarvis-deny-by-default.yaml"


def test_shipped_policy_exists_and_parses():
    assert _SHIPPED_POLICY.exists(), "the sandbox policy this repo ships is missing"
    result = inspect_nemoclaw_policy({"NEMOCLAW_POLICY_PATH": str(_SHIPPED_POLICY)})
    assert result["status"] == "loaded", result
    assert result["errors"] == []
    # An unrecognized key is a typo or a schema drift; either way we want to know.
    assert result["summary"]["unknownKeys"] == []


def test_shipped_policy_does_not_fail_open():
    """best_effort applies what the host supports and otherwise only warns, so
    isolation can silently not apply. hard_requirement aborts startup instead."""
    result = inspect_nemoclaw_policy({"NEMOCLAW_POLICY_PATH": str(_SHIPPED_POLICY)})
    assert not any("fails open" in w.lower() for w in result["warnings"]), result["warnings"]

    from app.openshell_exec import assert_policy_enforces
    verdict = assert_policy_enforces({"NEMOCLAW_POLICY_PATH": str(_SHIPPED_POLICY)})
    assert verdict["enforced"] is True
    assert verdict["overridden"] is False


def test_shipped_policy_declares_egress_for_the_pinned_search_host():
    """Without this, the sandbox denies all outbound traffic and browser.search
    fails with a connection error rather than a policy one."""
    import yaml
    from app.browser import SEARCH_PROVIDER_HOST

    data = yaml.safe_load(_SHIPPED_POLICY.read_text(encoding="utf-8"))
    rules = data.get("network_policies") or {}
    assert rules, "no network_policies declared: outbound access is denied"

    hosts = {
        str(endpoint.get("host", ""))
        for rule in rules.values()
        for endpoint in (rule.get("endpoints") or [])
    }
    assert SEARCH_PROVIDER_HOST in hosts, (
        f"the pinned search provider {SEARCH_PROVIDER_HOST} has no egress rule; "
        f"declared hosts: {sorted(hosts)}"
    )


def test_shipped_policy_permits_tls_only():
    """Plaintext egress from the sandbox would leak page contents on the wire."""
    import yaml
    data = yaml.safe_load(_SHIPPED_POLICY.read_text(encoding="utf-8"))
    for name, rule in (data.get("network_policies") or {}).items():
        for endpoint in rule.get("endpoints") or []:
            assert endpoint.get("port") == 443, f"{name} permits non-TLS port {endpoint.get('port')}"
