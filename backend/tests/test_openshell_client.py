"""C0 OpenShell gRPC client tests.

Every test injects a fake channel/stub. Nothing here opens a socket, reads real
mTLS material, or requires a running gateway.
"""

from pathlib import Path

import pytest

from app import openshell_client as osc


# ══════════════════════════════════════════════════════════════════════════════
# Fakes
# ══════════════════════════════════════════════════════════════════════════════

class FakeServiceStatus:
    @staticmethod
    def Name(value):
        return {0: "SERVICE_STATUS_UNSPECIFIED", 1: "SERVICE_STATUS_HEALTHY",
                2: "SERVICE_STATUS_DEGRADED"}[value]


class _Msg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakePb:
    ServiceStatus = FakeServiceStatus

    @staticmethod
    def HealthRequest():
        return _Msg()

    @staticmethod
    def GetGatewayInfoRequest():
        return _Msg()

    @staticmethod
    def ListSandboxesRequest():
        return _Msg()

    @staticmethod
    def GetCurrentUserRequest():
        return _Msg()


class FakeStub:
    """Records which RPCs were invoked; privileged ones raise if ever touched."""

    def __init__(self, channel=None, *, health_status=1, raise_on=None):
        self.channel = channel
        self.calls = []
        self._health_status = health_status
        self._raise_on = raise_on or {}

    def _record(self, name):
        self.calls.append(name)
        if name in self._raise_on:
            raise self._raise_on[name]

    def Health(self, req, timeout=None):
        self._record("Health")
        return _Msg(status=self._health_status, version="0.0.111")

    def GetGatewayInfo(self, req, timeout=None):
        self._record("GetGatewayInfo")
        return _Msg(
            gateway_version="0.0.111",
            compute_drivers=[_Msg(name="docker", capabilities=_Msg(driver_version="29.7.2"))],
        )

    def ListSandboxes(self, req, timeout=None):
        self._record("ListSandboxes")
        return _Msg(sandboxes=[_Msg(id="sb1", name="research", status="RUNNING")])

    def GetCurrentUser(self, req, timeout=None):
        self._record("GetCurrentUser")
        return _Msg(subject="user-1", display_name="Hasnain", roles=["openshell-user"])

    # Privileged RPCs must never be reached from this module.
    def __getattr__(self, name):
        raise AssertionError(f"Privileged or unexpected RPC invoked: {name}")


def _stub_factory(stub):
    return lambda channel: stub


# ══════════════════════════════════════════════════════════════════════════════
# Privileged RPCs are unreachable (load-bearing guarantee)
# ══════════════════════════════════════════════════════════════════════════════

_FORBIDDEN_RPCS = (
    "CreateSandbox", "DeleteSandbox", "StopSandbox", "StartSandbox",
    "ExecSandbox", "ExecSandboxInteractive", "CreateSshSession",
    "ForwardTcp", "UpdateConfig", "ExposeService", "IssueSandboxToken",
)


def test_module_never_calls_privileged_rpcs():
    source = Path(osc.__file__).read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]   # strip the docstring that names them
    for rpc in _FORBIDDEN_RPCS:
        assert f".{rpc}(" not in body, f"openshell_client must never call {rpc}"


def test_read_only_calls_touch_only_read_rpcs():
    stub = FakeStub()
    env = {}
    osc.health(env, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    osc.gateway_info(env, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    osc.list_sandboxes(env, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    osc.current_user(env, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    assert set(stub.calls) == {"Health", "GetGatewayInfo", "ListSandboxes", "GetCurrentUser"}


def test_no_subprocess_or_shell_in_module():
    source = Path(osc.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "run_brain_command", "popen"):
        assert forbidden not in source.lower()


# ══════════════════════════════════════════════════════════════════════════════
# URL normalization
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("url,expected", [
    ("https://localhost:17670", "localhost:17670"),
    ("http://127.0.0.1:17670", "127.0.0.1:17670"),
    ("localhost:17670", "localhost:17670"),
    ("grpcs://gw.internal:9999", "gw.internal:9999"),
])
def test_gateway_target_normalizes(url, expected):
    assert osc.gateway_target(url) == expected


@pytest.mark.parametrize("bad,match", [
    ("", "not configured"),
    ("   ", "not configured"),
    ("localhost", "must include a port"),
    ("https://user:pw@localhost:17670", "Credentials embedded"),
    ("ftp://localhost:17670", "Unsupported gateway URL scheme"),
])
def test_gateway_target_rejects(bad, match):
    with pytest.raises(osc.OpenShellError, match=match):
        osc.gateway_target(bad)


# ══════════════════════════════════════════════════════════════════════════════
# mTLS material
# ══════════════════════════════════════════════════════════════════════════════

def _write_mtls(tmp_path, ca=b"CA", cert=b"CERT", key=b"KEY"):
    for name, blob in (("ca.crt", ca), ("tls.crt", cert), ("tls.key", key)):
        (tmp_path / name).write_bytes(blob)
    return tmp_path


def test_load_mtls_material_reads_all_three(tmp_path):
    _write_mtls(tmp_path)
    ca, cert, key = osc.load_mtls_material(str(tmp_path))
    assert (ca, cert, key) == (b"CA", b"CERT", b"KEY")


def test_load_mtls_material_requires_configuration():
    with pytest.raises(osc.OpenShellError, match="not configured"):
        osc.load_mtls_material("")


def test_load_mtls_material_rejects_missing_dir(tmp_path):
    with pytest.raises(osc.OpenShellError, match="does not exist"):
        osc.load_mtls_material(str(tmp_path / "nope"))


@pytest.mark.parametrize("missing", ["ca.crt", "tls.crt", "tls.key"])
def test_load_mtls_material_rejects_incomplete(tmp_path, missing):
    _write_mtls(tmp_path)
    (tmp_path / missing).unlink()
    with pytest.raises(osc.OpenShellError, match=f"Missing {missing}"):
        osc.load_mtls_material(str(tmp_path))


def test_load_mtls_material_rejects_empty_file(tmp_path):
    _write_mtls(tmp_path, key=b"")
    with pytest.raises(osc.OpenShellError, match="empty"):
        osc.load_mtls_material(str(tmp_path))


def test_mtls_contents_never_appear_in_errors(tmp_path):
    secret = b"SUPER_SECRET_KEY_MATERIAL"
    _write_mtls(tmp_path, key=secret)
    (tmp_path / "ca.crt").unlink()
    try:
        osc.load_mtls_material(str(tmp_path))
    except osc.OpenShellError as exc:
        assert secret.decode() not in str(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Read-only RPC behaviour
# ══════════════════════════════════════════════════════════════════════════════

def test_health_reports_healthy():
    stub = FakeStub(health_status=1)
    result = osc.health({}, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    assert result == {
        "healthy": True, "status": 1,
        "statusName": "SERVICE_STATUS_HEALTHY", "version": "0.0.111",
    }


def test_health_reports_unhealthy_status_honestly():
    stub = FakeStub(health_status=2)
    result = osc.health({}, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    assert result["healthy"] is False
    assert result["statusName"] == "SERVICE_STATUS_DEGRADED"


def test_gateway_info_surfaces_drivers():
    stub = FakeStub()
    info = osc.gateway_info({}, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    assert info["version"] == "0.0.111"
    assert info["computeDrivers"] == [{"name": "docker", "version": "29.7.2"}]


def test_list_sandboxes_shape():
    stub = FakeStub()
    boxes = osc.list_sandboxes({}, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    assert boxes == [{"id": "sb1", "name": "research", "status": "RUNNING"}]


def test_current_user_returns_identity_metadata_only():
    stub = FakeStub()
    user = osc.current_user({}, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)
    assert user == {"subject": "user-1", "displayName": "Hasnain", "roles": ["openshell-user"]}


def test_rpc_failure_becomes_openshell_error():
    stub = FakeStub(raise_on={"Health": RuntimeError("transport error")})
    with pytest.raises(osc.OpenShellError, match="health check failed"):
        osc.health({}, channel=object(), stub_factory=_stub_factory(stub), messages=FakePb)


def test_missing_message_module_fails_cleanly(monkeypatch):
    monkeypatch.setattr(osc, "_pb", None)
    with pytest.raises(osc.OpenShellError, match="stubs are missing"):
        osc.health({}, channel=object(), stub_factory=None, messages=None)


def test_missing_grpc_stub_module_fails_cleanly(monkeypatch):
    monkeypatch.setattr(osc, "_pb_grpc", None)
    with pytest.raises(osc.OpenShellError, match="stubs are missing"):
        osc.health({}, channel=object(), stub_factory=None, messages=FakePb)


@pytest.mark.parametrize("given,expected", [
    (None, osc.DEFAULT_TIMEOUT_S), (0, 0.1), (-5, 0.1),
    (999, osc.MAX_TIMEOUT_S), ("bad", osc.DEFAULT_TIMEOUT_S), (3.5, 3.5),
])
def test_timeout_is_clamped(given, expected):
    assert osc._clamp_timeout(given) == expected


# ══════════════════════════════════════════════════════════════════════════════
# Channel construction
# ══════════════════════════════════════════════════════════════════════════════

class FakeGrpc:
    def __init__(self):
        self.creds_args = None
        self.channel_args = None

    def ssl_channel_credentials(self, root_certificates=None, private_key=None,
                                certificate_chain=None):
        self.creds_args = (root_certificates, private_key, certificate_chain)
        return "CREDS"

    def secure_channel(self, target, credentials, options=None):
        self.channel_args = (target, credentials, options)
        return "CHANNEL"


def test_build_channel_uses_mtls_and_target_override(tmp_path):
    _write_mtls(tmp_path)
    fake = FakeGrpc()
    env = {
        osc.GATEWAY_URL_ENV: "https://localhost:17670",
        osc.MTLS_DIR_ENV: str(tmp_path),
    }
    channel = osc.build_channel(env, grpc_module=fake)

    assert channel == "CHANNEL"
    assert fake.creds_args == (b"CA", b"KEY", b"CERT")   # ca, key, cert ordering
    target, creds, options = fake.channel_args
    assert target == "localhost:17670"
    assert creds == "CREDS"
    assert ("grpc.ssl_target_name_override", osc.DEFAULT_TARGET_NAME) in options


def test_build_channel_honours_server_name_override(tmp_path):
    _write_mtls(tmp_path)
    fake = FakeGrpc()
    env = {
        osc.GATEWAY_URL_ENV: "https://localhost:17670",
        osc.MTLS_DIR_ENV: str(tmp_path),
        osc.TARGET_OVERRIDE_ENV: "custom.internal",
    }
    osc.build_channel(env, grpc_module=fake)
    assert ("grpc.ssl_target_name_override", "custom.internal") in fake.channel_args[2]


def test_build_channel_without_grpc_fails_cleanly(tmp_path, monkeypatch):
    _write_mtls(tmp_path)
    monkeypatch.setattr(osc, "_grpc", None)
    env = {osc.GATEWAY_URL_ENV: "https://localhost:17670", osc.MTLS_DIR_ENV: str(tmp_path)}
    with pytest.raises(osc.OpenShellError, match="grpcio is not installed"):
        osc.build_channel(env)


# ══════════════════════════════════════════════════════════════════════════════
# Runtime-probe adapter
# ══════════════════════════════════════════════════════════════════════════════

def test_health_status_code_maps_healthy_to_200(monkeypatch):
    monkeypatch.setattr(osc, "health", lambda env, t: {"healthy": True})
    assert osc.health_status_code("https://localhost:17670", 2.0, {}) == osc.HEALTH_OK


def test_health_status_code_maps_unhealthy_to_503(monkeypatch):
    monkeypatch.setattr(osc, "health", lambda env, t: {"healthy": False})
    assert osc.health_status_code("https://localhost:17670", 2.0, {}) == osc.HEALTH_UNAVAILABLE


def test_health_status_code_propagates_configuration_error():
    with pytest.raises(osc.OpenShellError):
        osc.health_status_code("", 2.0, {})


def test_probe_falls_back_to_plain_http_when_grpc_unusable(monkeypatch):
    """The probe must still work for a non-gRPC runtime configured at this URL."""
    from app import runtime_probe

    calls = []
    monkeypatch.setattr(runtime_probe, "_plain_http_get",
                        lambda url, t: calls.append(url) or 200)
    monkeypatch.setattr(osc, "health",
                        lambda env, t: (_ for _ in ()).throw(osc.OpenShellError("no stubs")))

    assert runtime_probe._default_http_get("http://localhost:9999/health", 1.0) == 200
    assert calls == ["http://localhost:9999/health"]


def test_probe_uses_grpc_health_when_available(monkeypatch):
    from app import runtime_probe

    monkeypatch.setattr(runtime_probe, "_plain_http_get",
                        lambda url, t: pytest.fail("plain HTTP must not be used"))
    monkeypatch.setattr(osc, "health", lambda env, t: {"healthy": True})
    assert runtime_probe._default_http_get("https://localhost:17670", 1.0) == 200
