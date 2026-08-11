from pathlib import Path

import pytest

from app import google_auth as ga


class FakeCredentials:
    def __init__(self, *, valid=True, expired=False, refresh_token=None):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refresh_calls = 0

    def refresh(self, request):
        self.refresh_calls += 1
        self.valid = True

    def to_json(self):
        return '{"refresh_token":"not-a-real-token"}'


def _client_file(data_dir: Path, name: str = "client_secret_downloaded.json") -> Path:
    path = data_dir / name
    path.write_text("{}", encoding="utf-8")
    return path


def test_readonly_scopes_are_exact():
    assert ga.GOOGLE_READONLY_SCOPES == (
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
    )


def test_find_client_secret_accepts_google_download_name(tmp_path):
    expected = _client_file(tmp_path, "client_secret_123.apps.googleusercontent.com.json")
    assert ga.find_client_secret(tmp_path) == expected


def test_find_client_secret_rejects_missing_or_ambiguous(tmp_path):
    with pytest.raises(ga.GoogleAuthSetupError, match="No OAuth client"):
        ga.find_client_secret(tmp_path)

    _client_file(tmp_path, "client_secret_one.json")
    _client_file(tmp_path, "client_secret_two.json")
    with pytest.raises(ga.GoogleAuthSetupError, match="Multiple OAuth client"):
        ga.find_client_secret(tmp_path)


def test_status_does_not_read_files(tmp_path, monkeypatch):
    _client_file(tmp_path)
    (tmp_path / "token.json").write_text("secret", encoding="utf-8")

    def fail_read(*args, **kwargs):
        raise AssertionError("status must not read credential files")

    monkeypatch.setattr(Path, "read_text", fail_read)
    status = ga.oauth_status(tmp_path)
    assert status["clientConfigured"] is True
    assert status["tokenPresent"] is True
    assert status["scopes"] == list(ga.GOOGLE_READONLY_SCOPES)


def test_authorize_runs_local_consent_with_readonly_scopes(tmp_path):
    client_file = _client_file(tmp_path)
    credentials = FakeCredentials()
    calls = {}

    class Flow:
        def run_local_server(self, **kwargs):
            calls["server"] = kwargs
            return credentials

    def flow_factory(path, scopes):
        calls["flow"] = (path, scopes)
        return Flow()

    result = ga.authorize_google(
        data_dir=tmp_path,
        flow_factory=flow_factory,
        credentials_loader=lambda *args: None,
        request_factory=lambda: object(),
    )

    assert result is credentials
    assert calls["flow"] == (str(client_file), list(ga.GOOGLE_READONLY_SCOPES))
    assert calls["server"]["host"] == "localhost"
    assert calls["server"]["port"] == 0
    assert calls["server"]["open_browser"] is True
    assert (tmp_path / "token.json").is_file()


def test_valid_saved_token_skips_consent_and_rewrite(tmp_path):
    _client_file(tmp_path)
    token = tmp_path / "token.json"
    token.write_text("existing", encoding="utf-8")
    credentials = FakeCredentials(valid=True)

    result = ga.authorize_google(
        data_dir=tmp_path,
        flow_factory=lambda *args: pytest.fail("consent flow should not run"),
        credentials_loader=lambda path, scopes: credentials,
        request_factory=lambda: object(),
    )

    assert result is credentials
    assert token.read_text(encoding="utf-8") == "existing"


def test_expired_token_refreshes_and_is_saved(tmp_path):
    _client_file(tmp_path)
    (tmp_path / "token.json").write_text("expired", encoding="utf-8")
    credentials = FakeCredentials(valid=False, expired=True, refresh_token="refresh")

    ga.authorize_google(
        data_dir=tmp_path,
        flow_factory=lambda *args: pytest.fail("consent flow should not run"),
        credentials_loader=lambda path, scopes: credentials,
        request_factory=lambda: "request",
    )

    assert credentials.refresh_calls == 1
    assert "not-a-real-token" in (tmp_path / "token.json").read_text(encoding="utf-8")


def test_invalid_authorization_is_not_saved(tmp_path):
    _client_file(tmp_path)
    credentials = FakeCredentials(valid=False)

    class Flow:
        def run_local_server(self, **kwargs):
            return credentials

    with pytest.raises(ga.GoogleAuthSetupError, match="did not return valid"):
        ga.authorize_google(
            data_dir=tmp_path,
            flow_factory=lambda *args: Flow(),
            credentials_loader=lambda *args: None,
            request_factory=lambda: object(),
        )
    assert not (tmp_path / "token.json").exists()
