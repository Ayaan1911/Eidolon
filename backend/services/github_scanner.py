import asyncio
import hashlib
import os
import re
from urllib.parse import quote

import httpx

from services.secret_scanner import scan_text_for_secrets

GITHUB_API = "https://api.github.com"
MAX_REPOS = 10
MAX_FILE_BYTES = 500_000
CONCURRENCY = 5
REQUEST_TIMEOUT = 10.0

_NOISY_DIR_PARTS = {"node_modules", "dist", "build", "vendor", ".git"}
_NOISY_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
# Test code is full of deliberately secret-shaped fixtures (it has to be, to
# test a scanner or an auth flow), so it's skipped by path convention in every
# scanned repo rather than by rewriting individual fixture strings.
# ponytail: a real key hardcoded in a test file is missed too; accepted trade.
_TEST_DIR_PARTS = {"test", "tests", "__tests__", "spec", "specs", "testdata"}
_TEST_FILENAME = re.compile(
    r"^(test_.+\.py|.+_test\.(py|go|rb)|conftest\.py|.+\.(test|spec)\.[cm]?[jt]sx?|.+Tests?\.(java|kt|cs))$"
)
_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".zip", ".gz",
    ".tar", ".exe", ".dll", ".so", ".dylib", ".woff", ".woff2", ".ttf",
    ".eot", ".mp4", ".mp3", ".class", ".jar", ".pyc", ".bin",
}


class GitHubScanError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _headers() -> dict[str, str]:
    """Headers for api.github.com calls only - never attach these to a
    raw.githubusercontent.com request. That CDN doesn't need a token for public
    content, and empirically, sending one anyway gets a separately cached copy
    that can be well behind a request with no Authorization header at all
    (observed: a fresh push not showing up in a same-second authenticated
    fetch, while an unauthenticated fetch of the identical URL was current)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Eidolon-SecretScanner"}
    # ponytail: unauthenticated GitHub API calls are capped at 60/hour; set GITHUB_TOKEN in .env for 5000/hour
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        # "token" (not "Bearer") - the classic scheme for a classic personal access token.
        headers["Authorization"] = f"token {token}"
    return headers


def _rate_limit_reason(mid_scan: bool) -> str:
    where = "mid-scan; results are partial" if mid_scan else "before any repos could be scanned"
    if os.environ.get("GITHUB_TOKEN"):
        return (
            f"GitHub API rate limit reached {where}, despite an authenticated GITHUB_TOKEN "
            "(5,000/hour) - GitHub's API load may be unusually high right now"
        )
    return (
        f"GitHub API rate limit reached {where} - no GITHUB_TOKEN is configured, "
        "so this account is capped at 60 requests/hour"
    )


def _is_rate_limited(resp: httpx.Response) -> bool:
    return resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0"


def _finding_id(repo: str, file: str, line: int, secret_type: str) -> str:
    """A stable fingerprint of a finding's identity (not its value), so the same
    secret keeps the same id across rescans and a deployed trap can be matched
    back to it without persisting scan results."""
    digest = hashlib.sha256(f"{repo}:{file}:{line}:{secret_type}".encode()).hexdigest()
    return digest[:16]


def _is_candidate(path: str, size: int) -> bool:
    if size > MAX_FILE_BYTES:
        return False
    parts = path.split("/")
    if any(p in _NOISY_DIR_PARTS or p.lower() in _TEST_DIR_PARTS for p in parts[:-1]):
        return False
    filename = parts[-1]
    if _TEST_FILENAME.match(filename):
        return False
    if filename in _NOISY_FILENAMES or filename.endswith(".min.js"):
        return False
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext not in _BINARY_EXTENSIONS


async def _list_repos(client: httpx.AsyncClient, username: str) -> tuple[list[dict], bool]:
    try:
        resp = await client.get(
            f"{GITHUB_API}/users/{username}/repos",
            params={"sort": "updated", "direction": "desc", "per_page": 30},
            headers=_headers(),
        )
    except httpx.HTTPError as e:
        raise GitHubScanError(f"Could not reach GitHub API: {e}") from e

    if _is_rate_limited(resp):
        return [], True
    if resp.status_code == 404:
        raise GitHubScanError(f"GitHub user '{username}' not found", status_code=404)
    resp.raise_for_status()

    repos = [r for r in resp.json() if not r.get("fork")]
    return repos[:MAX_REPOS], False


async def _get_tree(client: httpx.AsyncClient, owner: str, repo: str, branch: str) -> tuple[list[dict], bool]:
    resp = await client.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
        params={"recursive": "1"},
        headers=_headers(),
    )
    if _is_rate_limited(resp):
        return [], True
    if resp.status_code == 404:
        return [], False
    resp.raise_for_status()
    return resp.json().get("tree", []), False


async def _fetch_file(
    client: httpx.AsyncClient, owner: str, repo: str, branch: str, path: str, sem: asyncio.Semaphore
) -> str | None:
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{quote(path, safe='/')}"
    async with sem:
        try:
            # No _headers() here - see its docstring for why raw.githubusercontent.com
            # specifically must not get an Authorization header.
            resp = await client.get(url, timeout=REQUEST_TIMEOUT)
            return resp.text if resp.status_code == 200 else None
        except httpx.HTTPError:
            return None


async def scan_user_repos(username: str) -> dict:
    # No default headers on the client itself: _list_repos/_get_tree (api.github.com)
    # attach _headers() explicitly per call; _fetch_file (raw.githubusercontent.com)
    # deliberately does not, so the same client can't leak an auth header across domains.
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        repos, rate_limited = await _list_repos(client, username)
        if rate_limited:
            return {
                "username": username,
                "repos_scanned": 0,
                "total_findings": 0,
                "results": [],
                "incomplete": True,
                "incomplete_reason": _rate_limit_reason(mid_scan=False),
            }

        sem = asyncio.Semaphore(CONCURRENCY)
        results = []
        total_findings = 0
        repos_scanned = 0
        incomplete = False

        for repo in repos:
            owner = repo["owner"]["login"]
            name = repo["name"]
            branch = repo.get("default_branch") or "main"

            try:
                tree, rate_limited = await _get_tree(client, owner, name, branch)
            except httpx.HTTPError:
                continue
            if rate_limited:
                incomplete = True
                break

            candidates = [
                item
                for item in tree
                if item.get("type") == "blob" and _is_candidate(item["path"], item.get("size", 0))
            ]
            contents = await asyncio.gather(
                *(_fetch_file(client, owner, name, branch, item["path"], sem) for item in candidates)
            )

            repo_label = f"{owner}/{name}"
            repo_findings = []
            for item, content in zip(candidates, contents):
                if content is None:
                    continue
                for finding in scan_text_for_secrets(content, path=item["path"]):
                    full = {**finding, "file": item["path"]}
                    full["id"] = _finding_id(repo_label, full["file"], full["line"], full["type"])
                    repo_findings.append(full)

            repos_scanned += 1
            if repo_findings:
                total_findings += len(repo_findings)
                results.append({"repo": repo_label, "findings": repo_findings})

        return {
            "username": username,
            "repos_scanned": repos_scanned,
            "total_findings": total_findings,
            "results": results,
            "incomplete": incomplete,
            "incomplete_reason": _rate_limit_reason(mid_scan=True) if incomplete else None,
        }
