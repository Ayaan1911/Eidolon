"""GitHub API auth headers and rate-limit messaging.

Run from backend/:  python -m pytest test_github_scanner.py
No real GitHub calls - httpx.MockTransport stands in for the network.
"""

import asyncio

import httpx
import pytest

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


def test_rate_limit_reason_is_generic_with_or_without_a_token(monkeypatch):
    without = _rate_limit_reason(mid_scan=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_examplenotarealtoken")
    with_token = _rate_limit_reason(mid_scan=False)
    assert without == with_token  # nothing public tells the two setups apart
    assert "token" not in with_token.lower()


def _rate_limited_transport(request: httpx.Request) -> httpx.Response:
    return httpx.Response(403, headers={"X-RateLimit-Remaining": "0"}, json={"message": "rate limited"})


def test_scan_reports_unconfigured_token_when_rate_limited(monkeypatch):
    _mock_github(monkeypatch, _rate_limited_transport)
    result = asyncio.run(scan_user_repos("octocat"))

    assert result["incomplete"] is True
    assert result["repos_scanned"] == 0
    assert "rate limit" in result["incomplete_reason"].lower()


def test_scan_reports_authenticated_rate_limit_when_token_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_examplenotarealtoken")
    _mock_github(monkeypatch, _rate_limited_transport)
    result = asyncio.run(scan_user_repos("octocat"))

    assert result["incomplete"] is True
    assert "token" not in result["incomplete_reason"].lower()


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



def _boom(request):
    raise httpx.ConnectError("no route to api.github.com/users/octocat")


@pytest.mark.parametrize(
    "handler",
    [lambda r: httpx.Response(401, json={"message": "Bad credentials"}), lambda r: httpx.Response(500, text="boom"), _boom],
    ids=["token-rejected", "server-error", "network"],
)
def test_github_errors_are_generic(monkeypatch, handler):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_examplenotarealtoken")
    _mock_github(monkeypatch, handler)
    with pytest.raises(github_scanner.GitHubScanError) as e:
        asyncio.run(scan_user_repos("octocat"))
    assert str(e.value) == github_scanner.PUBLIC_ERROR


def test_unknown_user_message_does_not_echo_the_name(monkeypatch):
    _mock_github(monkeypatch, lambda r: httpx.Response(404, json={}))
    with pytest.raises(github_scanner.GitHubScanError) as e:
        asyncio.run(scan_user_repos("octocat"))
    assert e.value.status_code == 404 and "octocat" not in str(e.value)
