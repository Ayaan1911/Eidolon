"""GitHub API auth headers and rate-limit messaging.

Run from backend/:  python test_github_scanner.py  (also collected by pytest)
No real GitHub calls - httpx.MockTransport stands in for the network.
"""

import asyncio
import os

import httpx

from services import github_scanner
from services.github_scanner import _headers, _rate_limit_reason, scan_user_repos


def test_no_token_sends_no_authorization_header():
    os.environ.pop("GITHUB_TOKEN", None)
    assert "Authorization" not in _headers()


def test_token_sends_classic_scheme_not_bearer():
    os.environ["GITHUB_TOKEN"] = "ghp_examplenotarealtoken"
    try:
        assert _headers()["Authorization"] == "token ghp_examplenotarealtoken"
    finally:
        os.environ.pop("GITHUB_TOKEN", None)


def test_rate_limit_reason_says_unconfigured_when_no_token():
    os.environ.pop("GITHUB_TOKEN", None)
    reason = _rate_limit_reason(mid_scan=False)
    assert "no github_token is configured" in reason.lower()
    assert "60 requests/hour" in reason


def test_rate_limit_reason_says_authenticated_when_token_present():
    os.environ["GITHUB_TOKEN"] = "ghp_examplenotarealtoken"
    try:
        reason = _rate_limit_reason(mid_scan=True)
        assert "despite an authenticated github_token" in reason.lower()
        assert "no github_token" not in reason.lower()
    finally:
        os.environ.pop("GITHUB_TOKEN", None)


def _rate_limited_transport(request: httpx.Request) -> httpx.Response:
    return httpx.Response(403, headers={"X-RateLimit-Remaining": "0"}, json={"message": "rate limited"})


def test_scan_reports_unconfigured_token_when_rate_limited():
    os.environ.pop("GITHUB_TOKEN", None)
    real_client = github_scanner.httpx.AsyncClient
    github_scanner.httpx.AsyncClient = lambda **kw: real_client(
        transport=httpx.MockTransport(_rate_limited_transport), **kw
    )
    try:
        result = asyncio.run(scan_user_repos("octocat"))
    finally:
        github_scanner.httpx.AsyncClient = real_client

    assert result["incomplete"] is True
    assert result["repos_scanned"] == 0
    assert "no github_token is configured" in result["incomplete_reason"].lower()


def test_scan_reports_authenticated_rate_limit_when_token_set():
    os.environ["GITHUB_TOKEN"] = "ghp_examplenotarealtoken"
    real_client = github_scanner.httpx.AsyncClient
    github_scanner.httpx.AsyncClient = lambda **kw: real_client(
        transport=httpx.MockTransport(_rate_limited_transport), **kw
    )
    try:
        result = asyncio.run(scan_user_repos("octocat"))
    finally:
        github_scanner.httpx.AsyncClient = real_client
        os.environ.pop("GITHUB_TOKEN", None)

    assert result["incomplete"] is True
    assert "despite an authenticated github_token" in result["incomplete_reason"].lower()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
