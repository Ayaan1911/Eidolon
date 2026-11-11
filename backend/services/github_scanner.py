import asyncio
import hashlib
import os
import re
from urllib.parse import quote

import httpx

from services.secret_scanner import scan_text

GITHUB_API = "https://api.github.com"
MAX_REPOS = 10
MAX_FILE_BYTES = 500_000
# Total declared bytes fetched for one scan request, across all repos. Bounds the
# fan-out of a single unauthenticated request; the per-file cap above bounds one file.
MAX_TOTAL_BYTES = 20_000_000
CONCURRENCY = 5
# One scan fetches at most this many files, in small batches, and gives up after the deadline.
# What was scanned by then is returned and the result says it is partial.
MAX_FILES = 200
BATCH_SIZE = 10
SCAN_DEADLINE_SECONDS = 60
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


PUBLIC_ERROR = "The GitHub scan is unavailable right now. Try again later."


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
    # Public text: it must not reveal whether the server has a token. The admin
    # diagnostic (/api/admin/github-token) is where the token's state is shown.
    where = "mid-scan; results are partial" if mid_scan else "before any repos could be scanned"
    return f"GitHub's rate limit was reached {where}. Try again later."


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


def _within_budget(candidates: list[dict], remaining: int) -> tuple[list[dict], int, bool]:
    """Longest prefix of candidates whose declared sizes fit in `remaining` bytes.
    Returns (kept, bytes_used, truncated)."""
    kept, used = [], 0
    for item in candidates:
        size = item.get("size", 0)
        if used + size > remaining:
            return kept, used, True
        kept.append(item)
        used += size
    return kept, used, False


async def _list_repos(client: httpx.AsyncClient, username: str) -> tuple[list[dict], bool]:
    try:
        resp = await client.get(
            f"{GITHUB_API}/users/{username}/repos",
            params={"sort": "updated", "direction": "desc", "per_page": 30},
            headers=_headers(),
        )
    except httpx.HTTPError:
        raise GitHubScanError(PUBLIC_ERROR) from None

    if _is_rate_limited(resp):
        return [], True
    if resp.status_code == 404:
        raise GitHubScanError("GitHub user not found", status_code=404)
    if resp.status_code != 200:
        # Includes 401/403 (our token expired or revoked): the visitor gets the same public text.
        raise GitHubScanError(PUBLIC_ERROR)

    repos = [r for r in resp.json() if not r.get("fork")]
    return repos[:MAX_REPOS], False


async def _get_tree(
    client: httpx.AsyncClient, owner: str, repo: str, branch: str
) -> tuple[list[dict], bool, bool]:
    """(files, rate_limited, truncated). Truncated: GitHub cut a huge tree short."""
    resp = await client.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
        params={"recursive": "1"},
        headers=_headers(),
    )
    if _is_rate_limited(resp):
        return [], True, False
    if resp.status_code in (404, 409):  # no such branch, or an empty repository: nothing to scan
        return [], False, False
    resp.raise_for_status()
    body = resp.json()
    return body.get("tree", []), False, bool(body.get("truncated"))


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


async def _scan_repos(client: httpx.AsyncClient, repos: list[dict], state: dict) -> None:
    """Scan repos one by one, adding to `state` as it goes, so a deadline keeps what was found so far."""
    sem = asyncio.Semaphore(CONCURRENCY)
    bytes_left = MAX_TOTAL_BYTES
    files_left = MAX_FILES

    for repo in repos:
        if files_left <= 0:
            state["reasons"].append(f"file limit reached ({MAX_FILES} files per scan); later files were not scanned")
            return
        owner, name = repo["owner"]["login"], repo["name"]
        branch = repo.get("default_branch") or "main"
        try:
            tree, rate_limited, truncated = await _get_tree(client, owner, name, branch)
        except (httpx.HTTPError, ValueError):
            state["repos_failed"] += 1
            continue
        if rate_limited:
            state["reasons"].append(_rate_limit_reason(mid_scan=True))
            return
        state["repos_scanned"] += 1
        state["trees_truncated"] += truncated

        candidates = [
            item
            for item in tree
            if item.get("type") == "blob" and _is_candidate(item["path"], item.get("size", 0))
        ]
        candidates, used, over_budget = _within_budget(candidates, bytes_left)
        bytes_left -= used
        over_files = len(candidates) > files_left
        candidates = candidates[:files_left]
        files_left -= len(candidates)

        repo_label = f"{owner}/{name}"
        entry = None
        for i in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[i : i + BATCH_SIZE]
            contents = await asyncio.gather(
                *(_fetch_file(client, owner, name, branch, item["path"], sem) for item in batch)
            )
            for item, content in zip(batch, contents):
                if content is None:
                    state["files_failed"] += 1
                    continue
                state["files_scanned"] += 1
                # Worker thread so a normal heavy scan doesn't starve the event loop.
                # This does NOT rescue a catastrophic regex: `re` holds the GIL while it
                # matches, so such a pattern would still freeze the loop. Linear patterns
                # (secret_scanner._PATTERNS) and MAX_LINE_CHARS are the real protection.
                outcome = await asyncio.to_thread(scan_text, content, item["path"])
                state["skipped_long_lines"] += outcome.skipped_long_lines
                for finding in outcome.findings:
                    full = {**finding, "file": item["path"]}
                    full["id"] = _finding_id(repo_label, full["file"], full["line"], full["type"])
                    if entry is None:
                        entry = {"repo": repo_label, "findings": []}
                        state["results"].append(entry)
                    entry["findings"].append(full)
                    state["total_findings"] += 1

        if over_files:
            state["reasons"].append(f"file limit reached ({MAX_FILES} files per scan); later files were not scanned")
            return
        if over_budget:
            state["reasons"].append(
                f"scan size budget reached ({MAX_TOTAL_BYTES // 1_000_000} MB per scan); "
                "later files and repos were not scanned"
            )
            return


async def scan_user_repos(username: str) -> dict:
    # No default headers on the client itself: _list_repos/_get_tree (api.github.com)
    # attach _headers() explicitly per call; _fetch_file (raw.githubusercontent.com)
    # deliberately does not, so the same client can't leak an auth header across domains.
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        repos, rate_limited = await _list_repos(client, username)
        state = {
            "results": [], "total_findings": 0, "repos_scanned": 0, "files_scanned": 0,
            "files_failed": 0, "repos_failed": 0, "trees_truncated": 0, "skipped_long_lines": 0,
            "reasons": [_rate_limit_reason(mid_scan=False)] if rate_limited else [],
        }
        if not rate_limited:
            try:
                async with asyncio.timeout(SCAN_DEADLINE_SECONDS):
                    await _scan_repos(client, repos, state)
            except TimeoutError:
                state["reasons"].append(
                    f"the {SCAN_DEADLINE_SECONDS}-second scan time limit was reached; results are partial"
                )

    reasons = state.pop("reasons")
    # Nothing is hidden: failures and cut-short trees make the scan "incomplete" and are counted.
    if state["repos_failed"]:
        reasons.append(f"{state['repos_failed']} repositories could not be read")
    if state["files_failed"]:
        reasons.append(f"{state['files_failed']} files could not be fetched")
    if state["trees_truncated"]:
        reasons.append(f"{state['trees_truncated']} repositories are too large for GitHub to list in full")
    return {
        "username": username,
        **state,
        "incomplete": bool(reasons),
        "incomplete_reason": "; ".join(reasons) or None,
    }


async def check_token() -> dict:
    """Is the configured GITHUB_TOKEN accepted? Uses GitHub's rate_limit endpoint (it costs no quota).
    The answer never contains the token."""
    if not os.environ.get("GITHUB_TOKEN"):
        return {"configured": False, "status": "not_configured"}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(f"{GITHUB_API}/rate_limit", headers=_headers())
        if resp.status_code == 401:
            return {"configured": True, "status": "rejected"}  # expired or revoked: make a new one
        resp.raise_for_status()
        core = resp.json()["resources"]["core"]
        return {"configured": True, "status": "accepted", "limit": core["limit"], "remaining": core["remaining"]}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"configured": True, "status": "unknown"}
