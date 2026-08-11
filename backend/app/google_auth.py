"""Local Google OAuth setup with Gmail and Calendar read-only scopes only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable


GOOGLE_DATA_DIR = Path(__file__).parent.parent / "data" / "google"
TOKEN_FILE = GOOGLE_DATA_DIR / "token.json"

GOOGLE_READONLY_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
)


class GoogleAuthSetupError(RuntimeError):
    """Raised when local Google OAuth cannot be configured safely."""


def find_client_secret(data_dir: Path = GOOGLE_DATA_DIR) -> Path:
    """Find exactly one downloaded desktop OAuth client file without reading it."""
    preferred = data_dir / "client_secret.json"
    if preferred.is_file():
        return preferred

    candidates = sorted(data_dir.glob("client_secret*.json"))
    if not candidates:
        raise GoogleAuthSetupError(
            f"No OAuth client file found in {data_dir}. Place the downloaded desktop "
            "credential JSON there."
        )
    if len(candidates) > 1:
        raise GoogleAuthSetupError(
            f"Multiple OAuth client files found in {data_dir}. Keep only the one this "
            "app should use, or rename it to client_secret.json."
        )
    return candidates[0]


def oauth_status(data_dir: Path = GOOGLE_DATA_DIR) -> dict[str, Any]:
    """Report setup-file presence only; never read credential or token contents."""
    try:
        client_file = find_client_secret(data_dir)
        client_file_name = client_file.name
        client_configured = True
        error = None
    except GoogleAuthSetupError as exc:
        client_file_name = None
        client_configured = False
        error = str(exc)

    return {
        "clientConfigured": client_configured,
        "clientFile": client_file_name,
        "tokenPresent": (data_dir / TOKEN_FILE.name).is_file(),
        "scopes": list(GOOGLE_READONLY_SCOPES),
        "error": error,
    }


def _google_dependencies() -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GoogleAuthSetupError(
            "Google OAuth dependencies are missing. Run: pip install -r requirements.txt"
        ) from exc
    return InstalledAppFlow.from_client_secrets_file, Credentials.from_authorized_user_file, Request


def _write_token(credentials: Any, token_path: Path) -> None:
    """Atomically persist the local refresh token without logging its contents."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = token_path.with_suffix(".tmp")
    temporary.write_text(credentials.to_json(), encoding="utf-8")
    temporary.replace(token_path)


def authorize_google(
    *,
    data_dir: Path = GOOGLE_DATA_DIR,
    flow_factory: Callable[..., Any] | None = None,
    credentials_loader: Callable[..., Any] | None = None,
    request_factory: Callable[..., Any] | None = None,
) -> Any:
    """Load, refresh, or interactively create local read-only Google credentials."""
    client_file = find_client_secret(data_dir)
    token_path = data_dir / TOKEN_FILE.name

    if flow_factory is None or credentials_loader is None or request_factory is None:
        default_flow, default_loader, default_request = _google_dependencies()
        flow_factory = flow_factory or default_flow
        credentials_loader = credentials_loader or default_loader
        request_factory = request_factory or default_request

    credentials = None
    if token_path.is_file():
        try:
            credentials = credentials_loader(str(token_path), list(GOOGLE_READONLY_SCOPES))
        except Exception as exc:
            raise GoogleAuthSetupError(
                f"The saved Google token is unreadable. Remove {token_path.name} and authorize again."
            ) from exc

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(request_factory())
        except Exception as exc:
            raise GoogleAuthSetupError(
                f"Google token refresh failed. Remove {token_path.name} and authorize again."
            ) from exc
    else:
        flow = flow_factory(str(client_file), list(GOOGLE_READONLY_SCOPES))
        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            open_browser=True,
            prompt="consent",
            authorization_prompt_message="Opening Google authorization in your browser...",
            success_message="Google authorization complete. You may close this tab.",
        )

    if not credentials or not credentials.valid:
        raise GoogleAuthSetupError("Google authorization did not return valid credentials.")

    _write_token(credentials, token_path)
    return credentials


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure local read-only Google OAuth.")
    parser.add_argument("command", choices=("status", "authorize"), nargs="?", default="status")
    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(oauth_status(), indent=2))
        return 0

    try:
        authorize_google()
    except GoogleAuthSetupError as exc:
        print(f"Google OAuth setup failed: {exc}")
        return 1

    print(f"Google OAuth authorized. Token saved to {TOKEN_FILE}.")
    print("Authorized scopes: Gmail readonly, Calendar readonly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
