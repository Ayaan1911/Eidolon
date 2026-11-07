"""GitHub API auth headers and rate-limit messaging.

Run from backend/:  python -m pytest test_github_scanner.py
No real GitHub calls - httpx.MockTransport stands in for the network.
"""

import asyncio

import httpx

from services import github_scanner
from services.github_scanner import _headers, _rate_limit_reason, scan_user_repos


def _mock_github(monkeypatch, handler):
    real_client = github_scanner.httpx.AsyncClient
    monkeypatch.setattr(
        github_scanner.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )


def test_no_token_sends_no_authorization_header():
    assert "Authorization" not in _headers()


def test_token_sends_classic_scheme_not_bearer(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_examplenotarealtoken")
    assert _headers()["Authorization"] == "token ghp_examplenotarealtoken"


def test_rate_limit_reason_says_unconfigured_when_no_token():
    reason = _rate_limit_reason(mid_scan=False)
    assert "no github_token is configured" in reason.lower()
    assert "60 requests/hour" in reason


def test_rate_limit_reason_says_authenticated_when_token_present(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_examplenotarealtoken")
    reason = _rate_limit_reason(mid_scan=True)
    assert "despite an authenticated github_token" in reason.lower()
    assert "no github_token" not in reason.lower()


def _rate_limited_transport(request: httpx.Request) -> httpx.Response:
    return httpx.Response(403, headers={"X-RateLimit-Remaining": "0"}, json={"message": "rate limited"})


def test_scan_reports_unconfigured_token_when_rate_limited(monkeypatch):
    _mock_github(monkeypatch, _rate_limited_transport)
    result = asyncio.run(scan_user_repos("octocat"))

    assert result["incomplete"] is True
    assert result["repos_scanned"] == 0
    assert "no github_token is configured" in result["incomplete_reason"].lower()


def test_scan_reports_authenticated_rate_limit_when_token_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_examplenotarealtoken")
    _mock_github(monkeypatch, _rate_limited_transport)
    result = asyncio.run(scan_user_repos("octocat"))

    assert result["incomplete"] is True
    assert "despite an authenticated github_token" in result["incomplete_reason"].lower()


def test_raw_content_fetch_never_carries_the_github_token(monkeypatch):
    """The actual bug: sending Authorization to raw.githubusercontent.com got a
    separately-cached (and observed to be staler) response than an unauthenticated
    fetch of the identical URL - a rescan right after a push could see stale content."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_examplenotarealtoken")
    seen = {"api": [], "raw": []}

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("authorization")
        if request.url.host == "api.github.com":
            seen["api"].append(auth)
            if request.url.path.endswith("/repos"):
                return httpx.Response(200, json=[{"name": "r", "owner": {"login": "octocat"}, "fork": False}])
            return httpx.Response(
                200, json={"tree": [{"path": "README.md", "type": "blob", "size": 10}]}
            )
        seen["raw"].append(auth)
        return httpx.Response(200, text="nothing interesting here")

    _mock_github(monkeypatch, handler)
    asyncio.run(scan_user_repos("octocat"))

    assert seen["api"] and all(a == "token ghp_examplenotarealtoken" for a in seen["api"])
    assert seen["raw"] == [None]  # the raw-content fetch happened, carrying no auth at all


def test_test_files_are_not_scan_candidates():
    from services.github_scanner import _is_candidate

    for path in (
        "backend/test_secret_scanner.py",  # Eidolon's own fixture-heavy tests
        "tests/fixtures/config.yml",
        "src/__tests__/auth.js",
        "pkg/client_test.go",
        "app/conftest.py",
        "web/login.test.tsx",
        "web/api.spec.js",
        "src/main/AuthServiceTest.java",
    ):
        assert not _is_candidate(path, 100), path


def test_lookalike_names_are_still_scanned():
    from services.github_scanner import _is_candidate

    for path in (
        "backend/services/secret_scanner.py",
        "contest.py",
        "latest.py",
        "testimonials/index.html",
        ".env.example",
        "src/Contest.java",
    ):
        assert _is_candidate(path, 100), path

