"""backend/.env loading.

`.env` was documented throughout .env.example and read by nothing — every module
calls os.environ.get directly and nothing populated it. A correct .env on disk
did absolutely nothing, which is a bad way to discover your kill switch was never
enabled.
"""

import os

import pytest

from app.env_file import load_env_file


def test_missing_file_is_not_an_error(tmp_path):
    result = load_env_file(tmp_path / "nope.env")
    assert result["exists"] is False
    assert result["loaded"] == 0


def test_values_are_loaded(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("BRAIN_UI_TEST_ALPHA=hello\nBRAIN_UI_TEST_BETA=world\n", encoding="utf-8")
    monkeypatch.delenv("BRAIN_UI_TEST_ALPHA", raising=False)
    monkeypatch.delenv("BRAIN_UI_TEST_BETA", raising=False)

    result = load_env_file(env)
    assert result["loaded"] == 2
    assert os.environ["BRAIN_UI_TEST_ALPHA"] == "hello"
    monkeypatch.delenv("BRAIN_UI_TEST_ALPHA")
    monkeypatch.delenv("BRAIN_UI_TEST_BETA")


def test_a_real_environment_variable_wins(tmp_path, monkeypatch):
    """Documented precedence is env > .env > config file > defaults, and a
    one-off `set X=...` must still work for a single run."""
    env = tmp_path / ".env"
    env.write_text("BRAIN_UI_TEST_GAMMA=from-file\n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_UI_TEST_GAMMA", "from-shell")

    result = load_env_file(env)
    assert result["skipped"] == 1
    assert os.environ["BRAIN_UI_TEST_GAMMA"] == "from-shell"


def test_windows_paths_survive_intact(tmp_path, monkeypatch):
    """Backslashes and spaces are the norm here — a hand-rolled parser would
    mangle them, which is why this uses python-dotenv."""
    env = tmp_path / ".env"
    env.write_text(
        'BRAIN_UI_TEST_PATH=D:\\Hasnain\\Personal\\OneDrive - University of Toronto\\AI-Command-Center\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("BRAIN_UI_TEST_PATH", raising=False)
    load_env_file(env)
    assert os.environ["BRAIN_UI_TEST_PATH"] == (
        "D:\\Hasnain\\Personal\\OneDrive - University of Toronto\\AI-Command-Center"
    )
    monkeypatch.delenv("BRAIN_UI_TEST_PATH")


def test_a_malformed_file_never_stops_the_backend(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(b"\xff\xfe\x00 not valid utf-8 \x00\xff")
    result = load_env_file(env)          # must not raise
    assert result["exists"] is True


def test_the_summary_never_contains_values(tmp_path, monkeypatch):
    """This file holds the operator token and API tokens; the diagnostic summary
    is logged, so it must carry counts only."""
    env = tmp_path / ".env"
    secret = "super-secret-operator-token"
    env.write_text(f"BRAIN_UI_TEST_SECRET={secret}\n", encoding="utf-8")
    monkeypatch.delenv("BRAIN_UI_TEST_SECRET", raising=False)

    result = load_env_file(env)
    assert secret not in repr(result)
    monkeypatch.delenv("BRAIN_UI_TEST_SECRET")


def test_the_real_env_file_is_gitignored():
    """It holds tokens. Committing it would publish them."""
    from pathlib import Path
    ignore = (Path(__file__).parent.parent.parent / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignore
