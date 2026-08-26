"""
GitHub integration (D3) — READ-ONLY.

Surfaces repository activity as project evidence.

    list_repos(limit)                 -> owned/collaborating repos
    list_commits(repo, limit)         -> recent commits on the default branch
    list_issues(repo, state, limit)   -> issues and pull requests

Safety model (this module never relaxes it):
- READ-ONLY. Only HTTP GET is ever issued; a non-GET method is refused before any
  request is built. There is no create/update/delete/merge/comment path, and a
  source-guard test asserts those verbs are absent.
- THE TOKEN IS NEVER EXPOSED. It is read from the environment, sent only as an
  Authorization header to api.github.com, and never logged, echoed, returned, or
  included in an error message.
- HOST IS PINNED. Requests can only go to api.github.com over https; the caller
  supplies a path fragment, never a URL, so no request can be redirected to an
  attacker-chosen host. Redirects are disabled.
- REPO NAMES ARE VALIDATED against `owner/name` so a crafted value cannot escape
  the intended path.
- Response content (titles, commit messages, bodies) is UNTRUSTED external
  content: size-capped, stored/displayed only, never executed or followed.
- No vault write, no shell, no `brain`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

GITHUB_TOKEN_ENV = "BRAIN_UI_GITHUB_TOKEN"
API_HOST = "api.github.com"
API_BASE = f"https://{API_HOST}"

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
REQUEST_TIMEOUT_S = 15.0
MAX_TEXT_CHARS = 2_000

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}/[A-Za-z0-9._-]{1,100}$")


class GitHubError(RuntimeError):
    """Raised when a GitHub read cannot be performed safely."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A pinned-host API client must not follow redirects off that host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

def _token(env: Optional[dict] = None) -> str:
    source = os.environ if env is None else env
    return str(source.get(GITHUB_TOKEN_ENV, "") or "").strip()


def github_configured(env: Optional[dict] = None) -> bool:
    """True when a token is present. Never returns or logs the token itself."""
    return bool(_token(env))


def github_status(env: Optional[dict] = None) -> dict:
    configured = github_configured(env)
    return {
        "configured": configured,
        "readOnly": True,
        "message": (
            "GitHub read-only access is configured. Only GET requests are issued; "
            "no write, merge, or comment path exists."
            if configured else
            f"GitHub is not configured. Set {GITHUB_TOKEN_ENV} to a token with "
            f"read-only scopes."
        ),
    }


def _validate_repo(repo: str) -> str:
    value = (repo or "").strip()
    if not _REPO_RE.match(value):
        raise GitHubError(f"Invalid repository '{value}'. Expected the form owner/name.")
    return value


def _clamp(limit: Optional[int]) -> int:
    try:
        value = int(limit) if limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, value))


def _truncate(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


# ══════════════════════════════════════════════════════════════════════════════
# Transport (GET only, pinned host)
# ══════════════════════════════════════════════════════════════════════════════

def _get(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    env: Optional[dict] = None,
    opener: Optional[Callable[..., Any]] = None,
) -> Any:
    """Issue one authenticated GET against the pinned GitHub API host."""
    token = _token(env)
    if not token:
        raise GitHubError(
            f"GitHub is not configured. Set {GITHUB_TOKEN_ENV} to a read-only token."
        )

    if not path.startswith("/"):
        raise GitHubError("Internal error: GitHub path must be relative.")
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{API_BASE}{path}{query}"

    # Defence in depth: even though the base is a constant, re-verify the host.
    if urllib.parse.urlparse(url).hostname != API_HOST:
        raise GitHubError("Refusing to call a non-GitHub host.")

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "brain-ui-readonly",
        },
    )

    client = opener or urllib.request.build_opener(_NoRedirect).open
    try:
        with client(request, timeout=REQUEST_TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        # Never let the token reach an error string.
        raise GitHubError(f"GitHub request failed with HTTP {exc.code}.") from None
    except GitHubError:
        raise
    except Exception as exc:
        raise GitHubError(f"GitHub request failed: {type(exc).__name__}.") from None


# ══════════════════════════════════════════════════════════════════════════════
# Read operations
# ══════════════════════════════════════════════════════════════════════════════

def list_repos(limit: Optional[int] = None, *, env: Optional[dict] = None,
               opener: Optional[Callable[..., Any]] = None) -> List[dict]:
    """Repositories the token can see, most recently pushed first."""
    data = _get("/user/repos",
                {"per_page": _clamp(limit), "sort": "pushed", "direction": "desc"},
                env=env, opener=opener)
    repos: List[dict] = []
    for item in (data if isinstance(data, list) else [])[:_clamp(limit)]:
        if not isinstance(item, dict):
            continue
        repos.append({
            "fullName": _truncate(item.get("full_name"), 200),
            "description": _truncate(item.get("description"), 500),
            "private": bool(item.get("private")),
            "language": _truncate(item.get("language"), 60) or None,
            "pushedAt": _truncate(item.get("pushed_at"), 40) or None,
            "htmlUrl": _truncate(item.get("html_url"), 300) or None,
            "openIssues": int(item.get("open_issues_count") or 0),
        })
    return repos


def list_commits(repo: str, limit: Optional[int] = None, *, env: Optional[dict] = None,
                 opener: Optional[Callable[..., Any]] = None) -> List[dict]:
    """Recent commits. Commit messages are untrusted content."""
    name = _validate_repo(repo)
    data = _get(f"/repos/{name}/commits", {"per_page": _clamp(limit)}, env=env, opener=opener)
    commits: List[dict] = []
    for item in (data if isinstance(data, list) else [])[:_clamp(limit)]:
        if not isinstance(item, dict):
            continue
        commit = item.get("commit") or {}
        author = commit.get("author") or {}
        commits.append({
            "sha": _truncate(item.get("sha"), 40)[:12],
            "message": _truncate((commit.get("message") or "").split("\n")[0], 300),
            "author": _truncate(author.get("name"), 120) or None,
            "date": _truncate(author.get("date"), 40) or None,
            "htmlUrl": _truncate(item.get("html_url"), 300) or None,
        })
    return commits


def list_issues(repo: str, state: str = "open", limit: Optional[int] = None, *,
                env: Optional[dict] = None,
                opener: Optional[Callable[..., Any]] = None) -> List[dict]:
    """Issues and pull requests. Titles and bodies are untrusted content."""
    name = _validate_repo(repo)
    wanted = (state or "open").strip().lower()
    if wanted not in ("open", "closed", "all"):
        raise GitHubError("state must be one of: open, closed, all.")

    data = _get(f"/repos/{name}/issues", {"state": wanted, "per_page": _clamp(limit)},
                env=env, opener=opener)
    issues: List[dict] = []
    for item in (data if isinstance(data, list) else [])[:_clamp(limit)]:
        if not isinstance(item, dict):
            continue
        issues.append({
            "number": int(item.get("number") or 0),
            "title": _truncate(item.get("title"), 300),
            "state": _truncate(item.get("state"), 20),
            "isPullRequest": bool(item.get("pull_request")),
            "updatedAt": _truncate(item.get("updated_at"), 40) or None,
            "htmlUrl": _truncate(item.get("html_url"), 300) or None,
        })
    return issues
