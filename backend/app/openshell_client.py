"""
NVIDIA OpenShell gateway client (C0) — READ-ONLY.

The OpenShell gateway speaks **gRPC over HTTP/2 with mutual TLS**. There is no
REST API: every plain HTTP path returns 404, and server reflection is
UNIMPLEMENTED, so the vendored protos in `backend/proto/openshell/` (pinned to the
installed gateway version) are the only contract. See
`backend/proto/openshell/REGENERATE.md`.

This module exposes ONLY read-only RPCs:

    health()          → liveness + version        (openshell.v1.OpenShell/Health)
    gateway_info()    → version + compute drivers
    list_sandboxes()  → existing sandboxes
    current_user()    → authenticated identity

Safety model (this module never relaxes it):
- PRIVILEGED RPCs ARE UNREACHABLE HERE. It never calls CreateSandbox,
  DeleteSandbox, StopSandbox, StartSandbox, ExecSandbox, ExecSandboxInteractive,
  CreateSshSession, ForwardTcp, or UpdateConfig. A source-guard test asserts this.
  Sandbox creation and command execution are privileged actions that must go
  through the Permission Gateway approval queue (C1), not through this module.
- Connecting proves nothing is unlocked: browser/computer-use stay disabled until
  the bridge is implemented and explicitly enabled.
- mTLS material is read from a configured directory and NEVER logged, echoed, or
  returned. Only non-secret metadata (version, status, counts) is surfaced.
- Gateway responses are treated as untrusted display data.
- Import of `grpc` is optional: when grpcio is absent every call fails cleanly
  with OpenShellError instead of breaking app startup.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Optional grpc import. grpcio IS in requirements, but the app must still boot if
# the environment is incomplete — mirrors the optional-PyYAML pattern.
try:  # pragma: no cover - exercised via monkeypatch in tests
    import grpc as _grpc
except Exception:  # pragma: no cover
    _grpc = None

try:  # pragma: no cover
    from app.openshell_pb import openshell_pb2 as _pb
    from app.openshell_pb import openshell_pb2_grpc as _pb_grpc
except Exception:  # pragma: no cover
    _pb = None
    _pb_grpc = None


GATEWAY_URL_ENV = "NEMOCLAW_RUNTIME_URL"
MTLS_DIR_ENV = "NEMOCLAW_MTLS_DIR"
TARGET_OVERRIDE_ENV = "NEMOCLAW_TLS_SERVER_NAME"

# The gateway's server certificate SANs include this name.
DEFAULT_TARGET_NAME = "host.openshell.internal"
DEFAULT_TIMEOUT_S = 5.0
MAX_TIMEOUT_S = 15.0

_MTLS_FILES = ("ca.crt", "tls.crt", "tls.key")

# Health probe pseudo-status codes, so callers that think in HTTP terms (the
# runtime probe) keep working unchanged.
HEALTH_OK = 200
HEALTH_UNAVAILABLE = 503


class OpenShellError(RuntimeError):
    """Raised when the OpenShell gateway cannot be reached or read safely."""


# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

def _env(source: Optional[dict]) -> dict:
    return os.environ if source is None else source


def gateway_target(url: Optional[str]) -> str:
    """Normalize a configured URL into a gRPC `host:port` target."""
    raw = (url or "").strip()
    if not raw:
        raise OpenShellError(
            f"{GATEWAY_URL_ENV} is not configured. Set it to the OpenShell gateway "
            f"endpoint, e.g. https://localhost:17670"
        )

    parsed = urlparse(raw if "//" in raw else f"//{raw}")
    if parsed.username or parsed.password:
        raise OpenShellError("Credentials embedded in the gateway URL are not accepted.")
    if parsed.scheme and parsed.scheme not in ("http", "https", "grpc", "grpcs"):
        raise OpenShellError(f"Unsupported gateway URL scheme '{parsed.scheme}'.")

    host = parsed.hostname
    port = parsed.port
    if not host:
        raise OpenShellError(f"Could not read a host from {GATEWAY_URL_ENV}.")
    if not port:
        raise OpenShellError(
            f"{GATEWAY_URL_ENV} must include a port (the gateway default is 17670)."
        )
    return f"{host}:{port}"


def load_mtls_material(mtls_dir: Optional[str]) -> Tuple[bytes, bytes, bytes]:
    """Read (ca, cert, key) bytes. Contents are never logged or returned upward."""
    raw = (mtls_dir or "").strip()
    if not raw:
        raise OpenShellError(
            f"{MTLS_DIR_ENV} is not configured. Point it at the gateway's mTLS "
            f"directory containing {', '.join(_MTLS_FILES)}."
        )

    base = Path(raw)
    if not base.is_dir():
        raise OpenShellError(f"mTLS directory does not exist: {_shorten(base)}")

    material: List[bytes] = []
    for name in _MTLS_FILES:
        path = base / name
        if not path.is_file():
            raise OpenShellError(f"Missing {name} in the configured mTLS directory.")
        try:
            material.append(path.read_bytes())
        except OSError as exc:
            raise OpenShellError(f"Could not read {name}: {exc.strerror or 'unreadable'}") from exc

    ca, cert, key = material
    if not (ca and cert and key):
        raise OpenShellError("One or more mTLS files are empty.")
    return ca, cert, key


def _shorten(path: Path) -> str:
    """Display form of a path — never reveals full user directories in errors."""
    parts = path.parts
    return str(path) if len(parts) <= 3 else str(Path(*parts[:1]) / "…" / path.parent.name / path.name)


def _clamp_timeout(timeout_s: Optional[float]) -> float:
    try:
        value = float(timeout_s) if timeout_s is not None else DEFAULT_TIMEOUT_S
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_S
    return max(0.1, min(MAX_TIMEOUT_S, value))


# ══════════════════════════════════════════════════════════════════════════════
# Channel
# ══════════════════════════════════════════════════════════════════════════════

def build_channel(env: Optional[dict] = None, *, grpc_module: Any = None) -> Any:
    """Build an mTLS gRPC channel to the configured gateway."""
    source = _env(env)
    grpc = grpc_module or _grpc
    if grpc is None:
        raise OpenShellError("grpcio is not installed. Run: pip install -r requirements.txt")

    target = gateway_target(source.get(GATEWAY_URL_ENV))
    ca, cert, key = load_mtls_material(source.get(MTLS_DIR_ENV))

    credentials = grpc.ssl_channel_credentials(
        root_certificates=ca, private_key=key, certificate_chain=cert
    )
    server_name = (source.get(TARGET_OVERRIDE_ENV) or DEFAULT_TARGET_NAME).strip()
    options = (("grpc.ssl_target_name_override", server_name),)
    return grpc.secure_channel(target, credentials, options=options)


def _stub(channel: Any, stub_factory: Any = None) -> Any:
    factory = stub_factory or (_pb_grpc.OpenShellStub if _pb_grpc else None)
    if factory is None:
        raise OpenShellError(
            "OpenShell gRPC stubs are missing. See backend/proto/openshell/REGENERATE.md"
        )
    return factory(channel)


def _call(rpc: Callable[[], Any], what: str) -> Any:
    """Invoke one RPC, converting transport failures into OpenShellError."""
    try:
        return rpc()
    except OpenShellError:
        raise
    except Exception as exc:
        detail = getattr(exc, "details", None)
        message = detail() if callable(detail) else str(exc)
        raise OpenShellError(f"OpenShell {what} failed: {str(message)[:200]}") from exc


# ══════════════════════════════════════════════════════════════════════════════
# Read-only RPCs
# ══════════════════════════════════════════════════════════════════════════════

def health(
    env: Optional[dict] = None,
    timeout_s: Optional[float] = None,
    *,
    channel: Any = None,
    stub_factory: Any = None,
    messages: Any = None,
) -> dict:
    """Gateway liveness. Returns {healthy, status, statusName, version}."""
    pb = messages or _pb
    if pb is None:
        raise OpenShellError(
            "OpenShell gRPC stubs are missing. See backend/proto/openshell/REGENERATE.md"
        )

    timeout = _clamp_timeout(timeout_s)
    chan = channel or build_channel(env)
    stub = _stub(chan, stub_factory)

    response = _call(lambda: stub.Health(pb.HealthRequest(), timeout=timeout), "health check")
    status = int(getattr(response, "status", 0))
    try:
        status_name = pb.ServiceStatus.Name(status)
    except Exception:
        status_name = "SERVICE_STATUS_UNSPECIFIED"

    return {
        "healthy": status_name == "SERVICE_STATUS_HEALTHY",
        "status": status,
        "statusName": status_name,
        "version": str(getattr(response, "version", "") or ""),
    }


def gateway_info(
    env: Optional[dict] = None,
    timeout_s: Optional[float] = None,
    *,
    channel: Any = None,
    stub_factory: Any = None,
    messages: Any = None,
) -> dict:
    """Gateway version + configured compute drivers (non-secret metadata only)."""
    pb = messages or _pb
    if pb is None:
        raise OpenShellError("OpenShell gRPC stubs are missing.")

    timeout = _clamp_timeout(timeout_s)
    stub = _stub(channel or build_channel(env), stub_factory)
    response = _call(
        lambda: stub.GetGatewayInfo(pb.GetGatewayInfoRequest(), timeout=timeout), "gateway info"
    )

    drivers: List[dict] = []
    for driver in list(getattr(response, "compute_drivers", []) or [])[:20]:
        capabilities = getattr(driver, "capabilities", None)
        drivers.append({
            "name": str(getattr(driver, "name", "") or ""),
            "version": str(getattr(capabilities, "driver_version", "") or "") if capabilities else "",
        })

    return {
        "version": str(getattr(response, "gateway_version", "") or ""),
        "computeDrivers": drivers,
    }


def list_sandboxes(
    env: Optional[dict] = None,
    timeout_s: Optional[float] = None,
    *,
    channel: Any = None,
    stub_factory: Any = None,
    messages: Any = None,
) -> List[dict]:
    """Enumerate sandboxes. Creates and destroys nothing."""
    pb = messages or _pb
    if pb is None:
        raise OpenShellError("OpenShell gRPC stubs are missing.")

    timeout = _clamp_timeout(timeout_s)
    stub = _stub(channel or build_channel(env), stub_factory)
    response = _call(
        lambda: stub.ListSandboxes(pb.ListSandboxesRequest(), timeout=timeout), "sandbox list"
    )

    out: List[dict] = []
    for sandbox in list(getattr(response, "sandboxes", []) or [])[:100]:
        out.append({
            "id": str(getattr(sandbox, "id", "") or ""),
            "name": str(getattr(sandbox, "name", "") or ""),
            "status": str(getattr(sandbox, "status", "") or ""),
        })
    return out


def current_user(
    env: Optional[dict] = None,
    timeout_s: Optional[float] = None,
    *,
    channel: Any = None,
    stub_factory: Any = None,
    messages: Any = None,
) -> dict:
    """Authenticated identity. Returns non-secret identity metadata only."""
    pb = messages or _pb
    if pb is None:
        raise OpenShellError("OpenShell gRPC stubs are missing.")

    timeout = _clamp_timeout(timeout_s)
    stub = _stub(channel or build_channel(env), stub_factory)
    response = _call(
        lambda: stub.GetCurrentUser(pb.GetCurrentUserRequest(), timeout=timeout), "current user"
    )
    return {
        "subject": str(getattr(response, "subject", "") or ""),
        "displayName": str(getattr(response, "display_name", "") or ""),
        "roles": [str(r) for r in list(getattr(response, "roles", []) or [])[:20]],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Runtime-probe transport
# ══════════════════════════════════════════════════════════════════════════════

def health_status_code(url: str, timeout_s: float, env: Optional[dict] = None) -> int:
    """Health check shaped like an HTTP status, for `runtime_probe`.

    The probe was written against plain HTTP, which cannot work here: the gateway
    is gRPC-only and answers every REST path with 404. This adapter keeps the
    probe's existing classification, timeout clamping, loopback enforcement and
    redaction intact while swapping only the transport.

    Returns 200 when the gateway reports healthy, 503 otherwise. Never raises.
    """
    source = dict(_env(env))
    if url:
        source[GATEWAY_URL_ENV] = url
    try:
        return HEALTH_OK if health(source, timeout_s).get("healthy") else HEALTH_UNAVAILABLE
    except OpenShellError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise OpenShellError(f"OpenShell health probe failed: {str(exc)[:200]}") from exc
