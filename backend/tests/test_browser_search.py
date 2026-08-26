"""C1 / PRD §13.2 browser search tests.

The fetch driver is injected. Nothing here reaches a search provider.
"""

from pathlib import Path

import pytest

from app import browser


@pytest.fixture(autouse=True)
def _isolate_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(browser, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(browser, "SESSIONS_FILE", tmp_path / "sessions" / "sessions.json")


RESULTS_HTML = """
<html><body>
  <a class="result__a" href="https://doc.rust-lang.org/book/ch04.html">Ownership &amp; Borrowing</a>
  <a class="result__a" href="https://evil.example.com/malware">Totally Safe</a>
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdoc.rust-lang.org%2Fstd%2F">Std docs</a>
  <a href="https://duckduckgo.com/settings">Settings</a>
</body></html>
"""


def _fetch(html=RESULTS_HTML):
    calls = []

    def fetch(url, timeout):
        calls.append((url, timeout))
        return {"html": html, "status": 200}

    fetch.calls = calls
    return fetch


def _session(**kw):
    params = {"topic": "rust", "allowed_domains": ["doc.rust-lang.org"]}
    params.update(kw)
    return browser.start_session(**params)


# ══════════════════════════════════════════════════════════════════════════════
# Result parsing
# ══════════════════════════════════════════════════════════════════════════════

def test_results_are_extracted_with_titles():
    results = browser.parse_search_results(RESULTS_HTML)
    urls = [r["url"] for r in results]
    assert "https://doc.rust-lang.org/book/ch04.html" in urls
    assert results[0]["title"] == "Ownership & Borrowing"


def test_provider_redirect_wrappers_are_unwrapped():
    urls = [r["url"] for r in browser.parse_search_results(RESULTS_HTML)]
    assert "https://doc.rust-lang.org/std/" in urls


def test_provider_own_links_are_not_results():
    urls = [r["url"] for r in browser.parse_search_results(RESULTS_HTML)]
    assert not any("duckduckgo.com" in u for u in urls)


def test_duplicate_urls_collapse():
    html = '<a class="result__a" href="https://a.com/x">A</a>' * 5
    assert len(browser.parse_search_results(html)) == 1


def test_result_count_is_capped():
    html = "".join(
        f'<a class="result__a" href="https://a.com/{i}">R{i}</a>' for i in range(100)
    )
    assert len(browser.parse_search_results(html, limit=5)) == 5


def test_non_http_hrefs_are_dropped():
    html = '<a class="result__a" href="javascript:alert(1)">Bad</a>'
    assert browser.parse_search_results(html) == []


def test_malformed_html_yields_no_results():
    assert browser.parse_search_results("") == []
    assert browser.parse_search_results("<html>no links") == []


def test_titles_are_tag_stripped_and_capped(monkeypatch):
    monkeypatch.setattr(browser, "MAX_TITLE_CHARS", 20)
    html = f'<a class="result__a" href="https://a.com/x"><b>{"T" * 500}</b></a>'
    assert len(browser.parse_search_results(html)[0]["title"]) <= 21


# ══════════════════════════════════════════════════════════════════════════════
# The allowlist still governs what may be opened
# ══════════════════════════════════════════════════════════════════════════════

def test_offsite_results_are_returned_but_not_openable():
    """Appearing in search results grants a URL nothing."""
    session = _session()
    result = browser.search(session["id"], "rust ownership", fetch=_fetch())

    by_url = {r["url"]: r for r in result["results"]}
    assert by_url["https://doc.rust-lang.org/book/ch04.html"]["openable"] is True
    evil = by_url["https://evil.example.com/malware"]
    assert evil["openable"] is False
    assert "not in this session" in evil["blockedReason"]


def test_openable_count_is_reported():
    session = _session()
    result = browser.search(session["id"], "rust", fetch=_fetch())
    assert result["openableCount"] < result["count"]


def test_a_blocked_result_still_cannot_be_opened():
    session = _session()
    browser.search(session["id"], "rust", fetch=_fetch())
    with pytest.raises(browser.BrowserError, match="not in this session"):
        browser.open_page(session["id"], "https://evil.example.com/malware", fetch=_fetch())


def test_untrusted_warning_is_always_present():
    session = _session()
    result = browser.search(session["id"], "rust", fetch=_fetch())
    assert any("untrusted" in w.lower() for w in result["warnings"])


# ══════════════════════════════════════════════════════════════════════════════
# Provider is fixed, never caller-supplied
# ══════════════════════════════════════════════════════════════════════════════

def test_query_goes_only_to_the_fixed_provider():
    session = _session()
    fetch = _fetch()
    browser.search(session["id"], "rust ownership", fetch=fetch)
    called = fetch.calls[0][0]
    assert called.startswith(browser.SEARCH_PROVIDER_URL)
    assert "q=rust+ownership" in called


def test_query_is_url_encoded_not_interpolated():
    session = _session()
    fetch = _fetch()
    browser.search(session["id"], "a&b=c d", fetch=fetch)
    called = fetch.calls[0][0]
    assert called.count("?") == 1          # no injected extra query separator
    assert "a%26b%3Dc+d" in called


def test_module_pins_the_provider_host():
    source = Path(browser.__file__).read_text(encoding="utf-8")
    assert 'SEARCH_PROVIDER_HOST = "html.duckduckgo.com"' in source


# ══════════════════════════════════════════════════════════════════════════════
# Session rules apply to search too
# ══════════════════════════════════════════════════════════════════════════════

def test_search_refused_on_a_stopped_session():
    session = _session()
    browser.stop_session(session["id"])
    fetch = _fetch()
    with pytest.raises(browser.BrowserError, match="was stopped"):
        browser.search(session["id"], "rust", fetch=fetch)
    assert fetch.calls == []


def test_search_refused_after_budget_exhausted():
    clock = {"t": 1000.0}
    session = _session(budget_seconds=30, now_fn=lambda: clock["t"])
    fetch = _fetch()
    clock["t"] += 31
    with pytest.raises(browser.BrowserError, match="budget is exhausted"):
        browser.search(session["id"], "rust", fetch=fetch, now_fn=lambda: clock["t"])
    assert fetch.calls == []


def test_search_timeout_respects_remaining_budget():
    clock = {"t": 1000.0}
    session = _session(budget_seconds=15, now_fn=lambda: clock["t"])
    fetch = _fetch()
    clock["t"] += 10
    browser.search(session["id"], "rust", fetch=fetch, now_fn=lambda: clock["t"])
    assert fetch.calls[0][1] <= 5.0


def test_unknown_session_raises():
    with pytest.raises(browser.BrowserError, match="not found"):
        browser.search("nope", "rust", fetch=_fetch())


def test_empty_and_overlong_queries_rejected():
    session = _session()
    fetch = _fetch()
    for bad in ("", "   "):
        with pytest.raises(browser.BrowserError, match="query is required"):
            browser.search(session["id"], bad, fetch=fetch)
    with pytest.raises(browser.BrowserError, match="too long"):
        browser.search(session["id"], "x" * 5000, fetch=fetch)
    assert fetch.calls == []


def test_search_fails_closed_without_the_guardrail(monkeypatch):
    """The default driver still refuses when the sandbox is unavailable."""
    session = _session()
    monkeypatch.setattr(browser, "guardrail_healthy", lambda env=None: False)
    with pytest.raises(browser.GuardrailUnavailableError):
        browser.search(session["id"], "rust")


def test_fetch_failure_becomes_browser_error():
    session = _session()

    def boom(url, timeout):
        raise RuntimeError("provider down")

    with pytest.raises(browser.BrowserError, match="Search failed"):
        browser.search(session["id"], "rust", fetch=boom)


# ══════════════════════════════════════════════════════════════════════════════
# Approval gating
# ══════════════════════════════════════════════════════════════════════════════

def test_search_is_approval_gated_not_directly_executable():
    from app import permission_gateway as pg
    assert pg.is_approval_required_tool("browser.search") is True
    assert pg.is_executable("browser.search") is False

    result = pg.evaluate_tool_request("browser.search", {"query": "x"})
    assert result["allowed"] is False
    assert result["decision"] == "requires_approval"


def test_dispatcher_routes_search(monkeypatch):
    from app import tool_approvals

    seen = {}

    def fake_search(session_id, query, limit=None):
        seen["args"] = (session_id, query)
        return {"query": query, "results": [], "count": 0, "openableCount": 0, "warnings": []}

    monkeypatch.setattr(browser, "search", fake_search)
    result = tool_approvals._dispatch(
        "browser.search", {"sessionId": "s1", "query": "rust ownership"}
    )
    assert seen["args"] == ("s1", "rust ownership")
    assert result["count"] == 0


def test_execution_summary_reports_search():
    from app import tool_approvals
    summary = tool_approvals._execution_summary("browser.search", {"count": 3}, True)
    assert summary["resultType"] == "sandboxed_search"
