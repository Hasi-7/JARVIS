import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _unauthorized_external_reads(monkeypatch):
    """Pin external-read readiness to False for the whole suite.

    `permission_gateway.external_read_ready_fn` otherwise inspects the real
    `backend/data/google/` directory, so Gmail policy decisions would silently
    depend on whether the developer's machine happens to be authorized — the same
    test would pass before `authorize` and fail after it.

    Tests that exercise the authorized path opt in explicitly by rebinding
    `permission_gateway.external_read_ready_fn` themselves.
    """
    from app import permission_gateway, tools

    monkeypatch.setattr(permission_gateway, "external_read_ready_fn", lambda: False)
    monkeypatch.setattr(tools, "_gmail_reads_ready", lambda: False)
    monkeypatch.setattr(tools, "_computer_use_ready", lambda: False)
    monkeypatch.setattr(permission_gateway, "github_read_ready_fn", lambda: False)

    # The vault tool-log mirror resolves the REAL vault path from config, so any
    # test that logs a gateway evaluation would append to the user's actual
    # Obsidian vault. Disabled by default; the mirror's own tests re-enable it
    # against a tmp_path vault.
    monkeypatch.setenv(permission_gateway.VAULT_LOG_MIRROR_ENV, "false")
