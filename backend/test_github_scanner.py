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
        return httpx.Response(200, stream=httpx.ByteStream(b"nothing interesting here"))

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


# --- scan limits: nothing is hidden, a scan can be partial ---------------------------


def _serve(monkeypatch, files, *, truncated=False, raw_status=200, delay=0.0, repos=1):
    async def handler(request: httpx.Request) -> httpx.Response:
        if delay:
            await asyncio.sleep(delay)
        if request.url.host == "api.github.com":
            if request.url.path.endswith("/repos"):
                return httpx.Response(
                    200, json=[{"name": f"r{i}", "owner": {"login": "octocat"}, "fork": False} for i in range(repos)]
                )
            tree = [{"path": p, "type": "blob", "size": len(c)} for p, c in files.items()]
            return httpx.Response(200, json={"tree": tree, "truncated": truncated})
        return httpx.Response(raw_status, stream=httpx.ByteStream(
            files.get(request.url.path.rsplit("/", 1)[-1], "").encode()
        ))

    _mock_github(monkeypatch, handler)


def test_scan_stops_at_the_file_limit_and_says_so(monkeypatch):
    monkeypatch.setattr(github_scanner, "MAX_FILES", 5)
    monkeypatch.setattr(github_scanner, "BATCH_SIZE", 2)
    _serve(monkeypatch, {f"f{i}.txt": "hello" for i in range(12)})
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["files_scanned"] == 5
    assert result["incomplete"] is True and "file limit" in result["incomplete_reason"]


def test_failed_fetches_and_truncated_trees_are_reported(monkeypatch):
    _serve(monkeypatch, {"a.txt": "x", "b.txt": "y"}, truncated=True, raw_status=500)
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["files_failed"] == 2 and result["files_scanned"] == 0
    assert result["trees_truncated"] == 1
    assert result["incomplete"] is True
    assert "2 files could not be fetched" in result["incomplete_reason"]
    assert "too large" in result["incomplete_reason"]


def test_raw_file_growth_is_bounded_even_when_tree_claims_small_size(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/repos"):
            return httpx.Response(200, json=[{"name": "r", "owner": {"login": "octocat"}, "fork": False}])
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"tree": [{"path": "a.txt", "type": "blob", "size": 1}]})
        return httpx.Response(200, stream=httpx.ByteStream(b"x" * (github_scanner.MAX_FILE_BYTES + 1)))

    _mock_github(monkeypatch, handler)
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["files_scanned"] == 0 and result["files_failed"] == 1
    assert result["incomplete"] is True


def test_actual_downloads_share_one_scan_budget(monkeypatch):
    monkeypatch.setattr(github_scanner, "MAX_TOTAL_BYTES", 7)
    monkeypatch.setattr(github_scanner, "BATCH_SIZE", 2)

    def handler(request):
        if request.url.path.endswith("/repos"):
            return httpx.Response(200, json=[{"name": "r", "owner": {"login": "octocat"}, "fork": False}])
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"tree": [
                {"path": "a.txt", "type": "blob", "size": 1},
                {"path": "b.txt", "type": "blob", "size": 1},
            ]})
        return httpx.Response(200, stream=httpx.ByteStream(b"12345"))

    _mock_github(monkeypatch, handler)
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["files_scanned"] == 1 and result["files_failed"] == 1
    assert "scan size budget" in result["incomplete_reason"]


def test_discarded_oversized_files_still_consume_download_budget(monkeypatch):
    monkeypatch.setattr(github_scanner, "MAX_FILE_BYTES", 5)
    monkeypatch.setattr(github_scanner, "MAX_TOTAL_BYTES", 12)

    def handler(request):
        if request.url.path.endswith("/repos"):
            return httpx.Response(200, json=[{"name": "r", "owner": {"login": "octocat"}, "fork": False}])
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"tree": [
                {"path": f"{i}.txt", "type": "blob", "size": 1} for i in range(3)
            ]})
        return httpx.Response(200, stream=httpx.ByteStream(b"123456"))

    _mock_github(monkeypatch, handler)
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["files_scanned"] == 0
    assert "scan size budget" in result["incomplete_reason"]


def test_encoded_raw_response_is_skipped_before_decompression(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/repos"):
            return httpx.Response(200, json=[{"name": "r", "owner": {"login": "octocat"}, "fork": False}])
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"tree": [{"path": "a.txt", "type": "blob", "size": 1}]})
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=b"compressed")

    _mock_github(monkeypatch, handler)
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["files_failed"] == 1 and result["incomplete"] is True


@pytest.mark.parametrize("count,next_page", [(github_scanner.MAX_REPOS + 1, False), (1, True)])
def test_repo_cap_and_next_page_are_reported(monkeypatch, count, next_page):
    def handler(request):
        if request.url.path.endswith("/repos"):
            headers = {"Link": '<https://api.github.com/users/octocat/repos?page=2>; rel="next"'} if next_page else {}
            return httpx.Response(200, headers=headers, json=[
                {"name": f"r{i}", "owner": {"login": "octocat"}, "fork": False} for i in range(count)
            ])
        return httpx.Response(200, json={"tree": []})

    _mock_github(monkeypatch, handler)
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["incomplete"] is True
    assert "repository limit" in result["incomplete_reason"]


def test_a_repo_that_cannot_be_listed_is_counted_not_hidden(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/repos"):
            return httpx.Response(200, json=[{"name": "r", "owner": {"login": "octocat"}, "fork": False}])
        return httpx.Response(500)

    _mock_github(monkeypatch, handler)
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["repos_failed"] == 1 and result["incomplete"] is True


def test_missing_repo_tree_is_not_reported_as_a_clean_scan(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/repos"):
            return httpx.Response(200, json=[{"name": "r", "owner": {"login": "octocat"}, "fork": False}])
        return httpx.Response(404)

    _mock_github(monkeypatch, handler)
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["repos_failed"] == 1
    assert result["repos_scanned"] == 0
    assert result["incomplete"] is True


def test_deadline_returns_partial_results(monkeypatch):
    monkeypatch.setattr(github_scanner, "SCAN_DEADLINE_SECONDS", 0.3)
    _serve(monkeypatch, {"a.txt": "x"}, delay=0.2, repos=3)  # each repo needs 0.4s+
    result = asyncio.run(scan_user_repos("octocat"))
    assert result["incomplete"] is True and "time limit" in result["incomplete_reason"]


def test_token_check_reports_state_without_the_token(client, admin_headers, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_examplenotarealtoken")
    for handler, expected in (
        (lambda r: httpx.Response(401, json={"message": "Bad credentials"}), "rejected"),
        (lambda r: httpx.Response(200, json={"resources": {"core": {"limit": 5000, "remaining": 4999}}}), "accepted"),
        (lambda r: httpx.Response(500), "unknown"),
    ):
        real = httpx.AsyncClient
        monkeypatch.setattr(github_scanner.httpx, "AsyncClient", lambda handler=handler, real=real, **kw: real(transport=httpx.MockTransport(handler), **kw))
        r = client.get("/api/admin/diagnostics/github-token", headers=admin_headers)
        assert r.json()["status"] == expected and "ghp_" not in r.text
        monkeypatch.setattr(github_scanner.httpx, "AsyncClient", real)


def test_token_check_when_not_configured(client, admin_headers, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    r = client.get("/api/admin/diagnostics/github-token", headers=admin_headers)
    assert r.json() == {"configured": False, "status": "not_configured"}


def test_token_check_is_admin_only(client):
    assert client.get("/api/admin/diagnostics/github-token").status_code == 401


@pytest.mark.parametrize("name", ["", "-a", "a-", "a--b", "a_b", "a b", "a/b", "../x", "a" * 40, chr(228), "a%2Fb"])
def test_bad_github_usernames_are_rejected_before_any_request(client, name):
    assert client.post("/api/exposure/repos", json={"username": name}).status_code == 422


@pytest.mark.parametrize("name", ["a", "octocat", "a-b-c", "A1", "a" * 39])
def test_valid_github_usernames_pass_validation(name):
    from models.schemas import RepoScanRequest

    assert RepoScanRequest(username=name).username == name
