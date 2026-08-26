"""
NemoClaw/OpenShell Policy Inspection v0 — safe, read-only policy file inspection.

The PRD requires NemoClaw/OpenShell as the runtime guardrail for privileged agent
actions (§4.3.1, §31). Before any privileged bridge is built, this module makes the
FUTURE guardrail *inspectable*: it reads a configured policy file, parses it
defensively, and reports a safe summarized view of the declared scopes.

It inspects ONLY. It does NOT:
  * enforce the policy,
  * start or reach NemoClaw/OpenShell (no network call),
  * execute any tool, run shell / `brain`, or write the vault,
  * enable browser / computer-use / MCP / OpenClaw,
  * execute or import the policy file as code (text parse only),
  * accept a file path from the frontend (only NEMOCLAW_POLICY_PATH is read).

Path safety (enforced here):
  * only the configured NEMOCLAW_POLICY_PATH is read — never a frontend-supplied path;
  * the path is resolved; a non-file target (missing / directory) is reported honestly;
  * the file is read as UTF-8 text only, capped at MAX_POLICY_BYTES (256 KB);
  * no directory listing, no symlink chasing beyond the OS resolve, no code execution.

Format support:
  * JSON via the stdlib `json` (always available);
  * YAML via `yaml.safe_load` IF PyYAML is importable (it is optional — not a hard
    dependency). When PyYAML is absent, YAML is reported as unsupported, honestly,
    rather than failing or pretending to parse.

Summary behaviour (defensive):
  * an unrecognized-but-parseable object is "loaded" with its unknown keys surfaced;
  * capabilities default to unknown (null) and are only reported allowed when the
    policy clearly declares them so — we never imply a capability is allowed;
  * nothing here changes what the app can do — capabilities stay disabled regardless.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

RUNTIME_ID = "nemoclaw_openshell"

# Read the policy file as text only, capped so a huge/hostile file can't be slurped.
MAX_POLICY_BYTES = 256 * 1024  # 256 KB

# Status vocabulary (explicit; mirrors the spec).
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_MISSING = "missing"
STATUS_UNREADABLE = "unreadable"
STATUS_INVALID = "invalid"
STATUS_LOADED = "loaded"
STATUS_ERROR = "error"

# Optional YAML support. PyYAML is NOT a hard dependency — when it is missing we report
# YAML honestly as unsupported instead of adding a required dependency.
try:  # pragma: no cover - import guard
    import yaml as _yaml  # type: ignore
except Exception:  # pragma: no cover - PyYAML absent
    _yaml = None

# Top-level policy keys we recognize; everything else is surfaced as an unknown key.
# Real NVIDIA OpenShell `SandboxPolicy` keys, taken from the vendored
# proto/openshell/sandbox.proto (the YAML uses `filesystem_policy` where the proto
# field is `filesystem` — serde renaming, both are accepted here).
OPENSHELL_KEYS = {
    "version",
    "filesystem_policy", "filesystem",
    "landlock",
    "process", "process_policy",
    "network_policies", "network_middlewares",
}

# Speculative keys kept from before the real schema was known, so a hand-written
# or non-OpenShell policy still summarizes rather than reading as all-unknown.
LEGACY_KEYS = {
    "modes", "declaredModes", "declared_modes",
    "network", "network_policy", "networkPolicy",
    "filesystem_scopes", "filesystemScopes",
    "browser", "browser_harness", "browserAllowed",
    "computer_use", "computerUse", "computerUseAllowed",
    "mcp", "mcpAllowed",
    "credentials", "credential_access", "credentialAccess",
    "allow", "deny", "blocked",
}

KNOWN_KEYS = OPENSHELL_KEYS | LEGACY_KEYS

# Landlock compatibility modes. `best_effort` fails OPEN: it applies what the host
# supports and only warns otherwise, so filesystem isolation can silently not take
# effect. `hard_requirement` fails CLOSED by aborting sandbox startup.
LANDLOCK_FAIL_OPEN = "best_effort"
LANDLOCK_FAIL_CLOSED = "hard_requirement"

_TRUTHY = {"allow", "allowed", "true", "enabled", "enable", "on", "yes"}
_FALSY = {
    "block", "blocked", "deny", "denied", "false", "disabled", "disable",
    "off", "no", "none", "restricted",
}


# ── coercion helpers (defensive; never raise) ───────────────────────────────────

def _as_str_list(val) -> List[str]:
    """Coerce a value into a list of non-empty strings. Unknown shapes → []."""
    if val is None:
        return []
    if isinstance(val, str):
        s = val.strip()
        return [s] if s else []
    if isinstance(val, (list, tuple)):
        out: List[str] = []
        for x in val:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
            elif isinstance(x, (int, float, bool)):
                out.append(str(x))
        return out
    return []


def _as_str(val) -> Optional[str]:
    """Coerce a scalar into a trimmed string, or None."""
    if isinstance(val, str) and val.strip():
        return val.strip()
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return str(val)
    return None


def _cap_allowed(val) -> Optional[bool]:
    """
    Interpret a capability declaration into allowed(True)/blocked(False)/unknown(None).

    Conservative: only a clearly-affirmative declaration yields True. Anything
    ambiguous or absent yields None (unknown) — we never imply a capability is allowed.
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, dict):
        for key in ("allowed", "enabled", "allow", "enable"):
            if key in val:
                return _cap_allowed(val[key])
        return None
    if isinstance(val, str):
        v = val.strip().lower()
        if v in _TRUTHY:
            return True
        if v in _FALSY:
            return False
        return None
    return None


def _first(data: dict, *keys):
    """Return the first present key's value from a dict."""
    for k in keys:
        if k in data:
            return data[k]
    return None


# ── summary builder ─────────────────────────────────────────────────────────────

def _summarize(data: dict) -> dict:
    """Extract only obvious, recognized fields. Unknown keys are surfaced, not trusted."""
    modes = _as_str_list(_first(data, "modes", "declaredModes", "declared_modes"))

    # network policy may be a bare string or a nested {policy: ...} object.
    net_raw = _first(data, "network_policy", "networkPolicy", "network")
    if isinstance(net_raw, dict):
        network_policy = _as_str(_first(net_raw, "policy", "mode", "level"))
    else:
        network_policy = _as_str(net_raw)

    # OpenShell declares outbound access via `network_policies` (a map keyed by
    # name). Absent or empty means DENY — surface that instead of reporting null,
    # which reads as "no policy" when the truth is "nothing is permitted".
    # Only infer for documents that actually look like OpenShell policies — a
    # foreign document missing this key means "unknown", not "deny".
    looks_like_openshell = any(k in data for k in OPENSHELL_KEYS)
    if network_policy is None and looks_like_openshell:
        rules = data.get("network_policies")
        names = sorted(rules.keys()) if isinstance(rules, dict) else []
        network_policy = (
            f"allow ({', '.join(names)})" if names
            else "deny (no network_policies declared)"
        )

    # filesystem scopes may be a list, or nested {scopes: [...]}.
    fs_raw = _first(data, "filesystem_scopes", "filesystemScopes", "filesystem_policy", "filesystem")
    if isinstance(fs_raw, dict):
        fs_scopes = _as_str_list(_first(fs_raw, "scopes", "paths", "allow", "read"))
        # OpenShell FilesystemPolicy: include_workdir + read_only[] + read_write[].
        if not fs_scopes:
            for field, label in (("read_only", "ro"), ("read_write", "rw")):
                fs_scopes.extend(f"{label}: {p}" for p in _as_str_list(fs_raw.get(field)))
            if fs_raw.get("include_workdir") is True:
                fs_scopes.append("rw: <workdir> (include_workdir)")
    else:
        fs_scopes = _as_str_list(fs_raw)

    browser = _cap_allowed(_first(data, "browser", "browser_harness", "browserAllowed"))
    computer_use = _cap_allowed(_first(data, "computer_use", "computerUse", "computerUseAllowed"))
    mcp = _cap_allowed(_first(data, "mcp", "mcpAllowed"))

    cred_raw = _first(data, "credentials", "credential_access", "credentialAccess")
    if isinstance(cred_raw, dict):
        cred = _as_str(_first(cred_raw, "access", "policy", "mode"))
    else:
        cred = _as_str(cred_raw)
    # Default unknown credential access to the safe reading: unknown.
    credential_access = cred if cred else "unknown"

    unknown_keys = sorted(k for k in data.keys() if k not in KNOWN_KEYS)

    return {
        "declaredModes": modes,
        "networkPolicy": network_policy,
        "filesystemScopes": fs_scopes,
        "browserAllowed": browser,
        "computerUseAllowed": computer_use,
        "mcpAllowed": mcp,
        "credentialAccess": credential_access,
        "unknownKeys": unknown_keys,
    }


# ── format detection + parsing (text only; never executes/imports) ──────────────

def _detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".json":
        return "json"
    if ext in (".yaml", ".yml"):
        return "yaml"
    return "unknown"


def _parse_text(text: str, fmt: str) -> Tuple[Optional[object], Optional[str], str]:
    """
    Parse policy text WITHOUT executing/importing it.

    Returns (data, error, actual_format). `data` is None on failure. For `unknown`
    format we try JSON first, then YAML (if available).
    """
    if fmt == "json":
        try:
            return json.loads(text), None, "json"
        except Exception as exc:
            return None, f"Policy is not valid JSON: {exc}", "json"

    if fmt == "yaml":
        if _yaml is None:
            return None, "YAML policy files are not supported in this build (PyYAML is not installed).", "yaml"
        try:
            return _yaml.safe_load(text), None, "yaml"
        except Exception as exc:
            return None, f"Policy is not valid YAML: {exc}", "yaml"

    # Unknown extension → try JSON, then YAML.
    try:
        return json.loads(text), None, "json"
    except Exception:
        pass
    if _yaml is not None:
        try:
            return _yaml.safe_load(text), None, "yaml"
        except Exception as exc:
            return None, f"Policy could not be parsed as JSON or YAML: {exc}", "unknown"
    return None, "Policy could not be parsed as JSON (YAML is unsupported in this build).", "unknown"


# ── result builder ──────────────────────────────────────────────────────────────

def _result(
    *,
    status: str,
    configured: bool,
    path_configured: bool,
    path_exists: bool,
    readable: bool,
    valid: bool,
    message: str,
    path_display: Optional[str],
    fmt: Optional[str],
    summary: Optional[dict],
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
) -> dict:
    return {
        "id": RUNTIME_ID,
        "configured": bool(configured),
        "pathConfigured": bool(path_configured),
        "pathExists": bool(path_exists),
        "readable": bool(readable),
        "valid": bool(valid),
        "status": status,
        "message": message,
        "policyPathDisplay": path_display,
        "format": fmt,
        "summary": summary,
        "warnings": warnings or [],
        "errors": errors or [],
    }


def _shorten_path(p: Path) -> str:
    """A readable, shortened display of the resolved path (kept local, not a secret)."""
    parts = p.parts
    if len(parts) <= 3:
        return str(p)
    return os.path.join(parts[0], "…", parts[-2], parts[-1])


# ── public API ──────────────────────────────────────────────────────────────────

def inspect_nemoclaw_policy(env: Optional[dict] = None) -> dict:
    """
    Inspect the configured NemoClaw/OpenShell policy file (read-only). Never raises.

    Reads ONLY the path in NEMOCLAW_POLICY_PATH. Does not enforce the policy, start the
    runtime, make a network call, execute/import the file, run shell/`brain`, write the
    vault, or unlock any capability.
    """
    env = os.environ if env is None else env
    raw_path = str(env.get("NEMOCLAW_POLICY_PATH", "") or "").strip()

    inspection_note = (
        "Policy file read for inspection. This module never enforces it — "
        "OpenShell does, when a sandbox runs under it."
    )

    # No configured path → not_configured. NO file read attempted.
    if not raw_path:
        return _result(
            status=STATUS_NOT_CONFIGURED,
            configured=False, path_configured=False, path_exists=False,
            readable=False, valid=False,
            message="No NemoClaw/OpenShell policy path is configured (NEMOCLAW_POLICY_PATH).",
            path_display=None, fmt=None, summary=None,
        )

    try:
        path = Path(raw_path).expanduser().resolve()
    except Exception:
        return _result(
            status=STATUS_ERROR,
            configured=True, path_configured=True, path_exists=False,
            readable=False, valid=False,
            message="Configured policy path could not be resolved.",
            path_display=None, fmt=None, summary=None,
            errors=["NEMOCLAW_POLICY_PATH could not be resolved to a filesystem path."],
        )

    path_display = _shorten_path(path)

    # Path missing → honest, no read.
    if not path.exists():
        return _result(
            status=STATUS_MISSING,
            configured=True, path_configured=True, path_exists=False,
            readable=False, valid=False,
            message="Configured policy file does not exist.",
            path_display=path_display, fmt=None, summary=None,
            errors=["Policy file not found at the configured path."],
        )

    # Exists but is not a regular file (e.g. a directory) → unreadable. No listing.
    if not path.is_file():
        return _result(
            status=STATUS_UNREADABLE,
            configured=True, path_configured=True, path_exists=True,
            readable=False, valid=False,
            message="Configured policy path is not a regular file.",
            path_display=path_display, fmt=None, summary=None,
            errors=["Policy path exists but is not a file (directories are not inspected)."],
        )

    fmt = _detect_format(path)

    # Enforce the size cap BEFORE reading contents.
    try:
        size = path.stat().st_size
    except OSError as exc:
        return _result(
            status=STATUS_UNREADABLE,
            configured=True, path_configured=True, path_exists=True,
            readable=False, valid=False,
            message="Configured policy file could not be inspected.",
            path_display=path_display, fmt=fmt, summary=None,
            errors=[f"Could not stat the policy file: {exc}"],
        )

    if size > MAX_POLICY_BYTES:
        return _result(
            status=STATUS_INVALID,
            configured=True, path_configured=True, path_exists=True,
            readable=True, valid=False,
            message=f"Policy file is too large to inspect safely (max {MAX_POLICY_BYTES // 1024} KB).",
            path_display=path_display, fmt=fmt, summary=None,
            errors=[f"Policy file is {size} bytes; the inspection limit is {MAX_POLICY_BYTES} bytes."],
        )

    # Read as UTF-8 text only. Never executed or imported.
    try:
        raw_bytes = path.read_bytes()[:MAX_POLICY_BYTES]
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return _result(
            status=STATUS_UNREADABLE,
            configured=True, path_configured=True, path_exists=True,
            readable=False, valid=False,
            message="Policy file is not valid UTF-8 text.",
            path_display=path_display, fmt=fmt, summary=None,
            errors=["Policy file could not be decoded as UTF-8 text."],
        )
    except OSError as exc:
        return _result(
            status=STATUS_UNREADABLE,
            configured=True, path_configured=True, path_exists=True,
            readable=False, valid=False,
            message="Policy file could not be read.",
            path_display=path_display, fmt=fmt, summary=None,
            errors=[f"Could not read the policy file: {exc}"],
        )

    data, parse_err, actual_fmt = _parse_text(text, fmt)

    if parse_err is not None:
        return _result(
            status=STATUS_INVALID,
            configured=True, path_configured=True, path_exists=True,
            readable=True, valid=False,
            message="Policy file could not be parsed.",
            path_display=path_display, fmt=actual_fmt, summary=None,
            errors=[parse_err],
        )

    # Parsed, but the root is not a policy object (e.g. a list/scalar) → structurally invalid.
    if not isinstance(data, dict):
        return _result(
            status=STATUS_INVALID,
            configured=True, path_configured=True, path_exists=True,
            readable=True, valid=False,
            message="Policy file parsed but its top level is not an object.",
            path_display=path_display, fmt=actual_fmt, summary=None,
            errors=["Expected the policy root to be a mapping/object of scopes."],
        )

    summary = _summarize(data)

    warnings: List[str] = []
    if summary["unknownKeys"]:
        warnings.append(
            "Some policy keys were not recognized and are shown as-is: "
            + ", ".join(summary["unknownKeys"])
        )

    # Landlock fail-open advisory. `best_effort` applies whatever the host supports
    # and only warns otherwise, so filesystem isolation can silently not take effect
    # — notably under container runtimes whose seccomp profile blocks the Landlock
    # syscalls. A deny-by-default policy should fail closed instead.
    landlock = data.get("landlock")
    if isinstance(landlock, dict):
        compatibility = _as_str(landlock.get("compatibility")) or ""
        if compatibility.strip().lower() == LANDLOCK_FAIL_OPEN:
            warnings.append(
                f"landlock.compatibility is '{LANDLOCK_FAIL_OPEN}', which fails OPEN: "
                f"if the host or container runtime cannot apply Landlock, the sandbox "
                f"still starts with filesystem isolation silently reduced or absent. "
                f"Use '{LANDLOCK_FAIL_CLOSED}' to abort startup instead."
            )
    recognized = (
        summary["declaredModes"] or summary["networkPolicy"] or summary["filesystemScopes"]
        or summary["browserAllowed"] is not None or summary["computerUseAllowed"] is not None
        or summary["mcpAllowed"] is not None or summary["credentialAccess"] != "unknown"
    )
    if not recognized:
        warnings.append("No recognized policy scopes were found; showing an unknown-but-valid policy.")

    return _result(
        status=STATUS_LOADED,
        configured=True, path_configured=True, path_exists=True,
        readable=True, valid=True,
        message=inspection_note,
        path_display=path_display, fmt=actual_fmt, summary=summary,
        warnings=warnings,
    )
