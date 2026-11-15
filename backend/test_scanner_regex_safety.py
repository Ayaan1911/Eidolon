"""Regex-safety and detection regression tests for the secret scanner.

The scanner runs on attacker-controlled repo content (any public GitHub user can be
scanned), so no pattern may take super-linear time. Each adversarial input is run
two ways: straight through every raw pattern (proves the regexes themselves are
linear, independent of the line-length cap) and through scan_text (the real path).

Run from backend/:  python -m pytest test_scanner_regex_safety.py
"""

import asyncio
import re
import time

import httpx
import pytest

from services import github_scanner
from services.secret_scanner import _PATTERNS, MAX_LINE_CHARS, scan_text, scan_text_for_secrets

# Generous: linear matching takes milliseconds here; the old pattern took 7+ seconds
# at 80 KB. Anything near this budget means a regression, not a slow machine.
TIME_BUDGET_SECONDS = 1.0
SIZES = (80_000, 500_000)


def _repeat(unit: str, size: int) -> str:
    return unit * (size // len(unit))


# Each input targets the weak spot of at least one pattern: long runs of a pattern's own
# alphabet, many partial prefixes, and near-miss URLs that fail only at the very end.
ADVERSARIAL = {
    "letters": lambda n: "a" * n,
    "digits": lambda n: "1" * n,
    "scheme_chars": lambda n: "a+.-" * (n // 4),
    "url_fragments": lambda n: _repeat("a://", n),
    "colon_slash_fragments": lambda n: _repeat("://", n),
    "scheme_then_user_run": lambda n: "http://" + "u" * n,
    "user_colon_pass_no_at": lambda n: "http://u:" + "p" * n,
    "many_colons_no_at": lambda n: "http://" + "u:" * (n // 2),
    "many_userinfo_no_host": lambda n: _repeat("http://u:p@", n),
    "near_miss_host_slash": lambda n: "http://u:p@" + "h" * n + "/",
    "at_signs": lambda n: "@" * n,
    "aws_prefix_repeated": lambda n: _repeat("AKIA", n),
    "aws_almost": lambda n: _repeat("AKIA" + "A" * 15 + " ", n),
    "google_prefix_repeated": lambda n: _repeat("AIza", n),
    "google_almost": lambda n: _repeat("AIza" + "a" * 34 + " ", n),
    "private_key_prefix_repeated": lambda n: _repeat("-----BEGIN ", n),
    "private_key_long_word": lambda n: "-----BEGIN " + "A" * n,
    "private_key_words": lambda n: "-----BEGIN " + "A " * (n // 2),
    "slack_prefix_repeated": lambda n: _repeat("xoxb-", n),
    "stripe_prefix_repeated": lambda n: _repeat("sk_live_", n),
    "stripe_almost": lambda n: _repeat("sk_live_" + "a" * 23 + " ", n),
}


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("name", ADVERSARIAL)
def test_every_pattern_is_linear_on_adversarial_input(name, size):
    text = ADVERSARIAL[name](size)
    for secret_type, pattern in _PATTERNS.items():
        start = time.perf_counter()
        list(re.finditer(pattern, text))
        elapsed = time.perf_counter() - start
        assert elapsed < TIME_BUDGET_SECONDS, f"{secret_type} took {elapsed:.2f}s on {name} ({size} chars)"


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("name", ADVERSARIAL)
def test_scan_text_is_fast_on_adversarial_input(name, size):
    text = ADVERSARIAL[name](size)
    start = time.perf_counter()
    scan_text(text)
    assert time.perf_counter() - start < TIME_BUDGET_SECONDS


def test_adversarial_input_split_into_many_normal_lines_is_fast():
    # Short lines bypass the length cap, so this exercises the regexes at the line sizes
    # that actually get scanned.
    line = "http://" + "u:" * 1500
    text = "\n".join([line] * 200)  # ~600 KB
    start = time.perf_counter()
    scan_text(text)
    assert time.perf_counter() - start < TIME_BUDGET_SECONDS


# --- detection must still work -------------------------------------------------------


def _url(user: str, password: str, host: str, scheme: str = "postgresql") -> str:
    # Assembled at runtime so no secret-shaped literal sits in this source file.
    return scheme + "://" + user + ":" + password + "@" + host


def test_password_in_url_is_detected_and_masked():
    secret_password = "Xk9mPqR2vNzT"
    url = _url("dbuser", secret_password, "prod-db.internal:5432/app")
    findings = scan_text_for_secrets(f"DATABASE_URL={url}", path="config.py")
    assert [f["type"] for f in findings] == ["Password in URL"]
    # The match ends at the host:port (the path is not part of it), so the mask shows
    # only the first and last 4 chars of that - never the password.
    assert findings[0]["masked_value"] == "post...5432"
    assert secret_password not in repr(findings)


def test_password_in_url_detected_at_end_of_a_long_but_allowed_line():
    url = _url("dbuser", "Xk9mPqR2vNzT", "prod-db.internal")
    line = "x" * (MAX_LINE_CHARS - len(url) - 10) + " " + url
    assert len(line) <= MAX_LINE_CHARS
    assert [f["type"] for f in scan_text_for_secrets(line)] == ["Password in URL"]


def test_other_schemes_still_match():
    for scheme in ("mongodb", "mysql", "redis", "amqps", "git+ssh", "ftp"):
        found = scan_text_for_secrets(_url("svc", "Xk9mPqR2vNzT", "db.example.org", scheme))
        assert [f["type"] for f in found] == ["Password in URL"], scheme


def test_placeholder_urls_are_still_ignored():
    assert scan_text_for_secrets(_url("postgres", "postgres", "localhost:5432/app")) == []
    assert scan_text_for_secrets(_url("user", "change_me", "localhost/db")) == []


def test_each_other_secret_type_is_detected_and_masked():
    samples = {
        "AWS Access Key": "AKIA" + "1234567890ABCDEF",
        "Google API Key": "AIza" + "a" * 35,
        "Private Key": "-----BEGIN RSA PRIVATE KEY-----",
        "Slack Token": "xoxb-" + "1234567890ab",
        "Stripe Secret Key": "sk_live_" + "y" * 24,
    }
    for secret_type, value in samples.items():
        findings = scan_text_for_secrets(f"key = {value}")
        assert [f["type"] for f in findings] == [secret_type], secret_type
        assert findings[0]["masked_value"] == f"{value[:4]}...{value[-4:]}"
        assert value not in repr(findings)


def test_private_key_with_and_without_algorithm_word():
    assert scan_text_for_secrets("-----BEGIN PRIVATE KEY-----")
    assert scan_text_for_secrets("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert scan_text_for_secrets("-----BEGIN " + "A" * 33 + " PRIVATE KEY-----") == []


# --- long-line cap is visible, not silent --------------------------------------------


def test_over_long_lines_are_skipped_and_counted():
    secret = "AKIA" + "1234567890ABCDEF"
    long_line = secret + " " + "x" * MAX_LINE_CHARS
    outcome = scan_text(f"{long_line}\nok line\n{secret}")
    assert outcome.skipped_long_lines == 1
    assert [f["line"] for f in outcome.findings] == [3]  # only the short line was scanned


def test_line_at_exactly_the_cap_is_scanned():
    assert scan_text("a" * MAX_LINE_CHARS).skipped_long_lines == 0
    assert scan_text("a" * (MAX_LINE_CHARS + 1)).skipped_long_lines == 1


# --- scan_user_repos wiring: skipped lines and total byte budget ---------------------


def _patch_github(monkeypatch, files: dict[str, str], sizes: dict[str, int] | None = None):
    """Serve one repo whose tree is `files`; sizes override each file's declared size."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            if request.url.path.endswith("/repos"):
                return httpx.Response(
                    200, json=[{"name": "r", "owner": {"login": "octocat"}, "fork": False}]
                )
            tree = [
                {"path": p, "type": "blob", "size": (sizes or {}).get(p, len(c))}
                for p, c in files.items()
            ]
            return httpx.Response(200, json={"tree": tree})
        path = request.url.path.rsplit("/", 1)[-1]
        match = next((c for p, c in files.items() if p.endswith(path)), "")
        return httpx.Response(200, stream=httpx.ByteStream(match.encode()))

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        github_scanner.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )


def test_scan_reports_skipped_long_lines(monkeypatch):
    _patch_github(monkeypatch, {"bundle.js": "x" * (MAX_LINE_CHARS + 1) + "\nfine\n"})
    result = asyncio.run(github_scanner.scan_user_repos("octocat"))
    assert result["skipped_long_lines"] == 1
    assert result["incomplete"] is False


def test_scan_stops_at_total_byte_budget(monkeypatch):
    monkeypatch.setattr(github_scanner, "MAX_TOTAL_BYTES", 1000)
    files = {f"f{i}.txt": "nothing here" for i in range(3)}
    _patch_github(monkeypatch, files, sizes={name: 400 for name in files})
    result = asyncio.run(github_scanner.scan_user_repos("octocat"))
    assert result["incomplete"] is True
    assert "budget" in result["incomplete_reason"]


def test_scan_under_budget_is_complete(monkeypatch):
    _patch_github(monkeypatch, {"a.txt": "hello"})
    result = asyncio.run(github_scanner.scan_user_repos("octocat"))
    assert result["incomplete"] is False and result["incomplete_reason"] is None
