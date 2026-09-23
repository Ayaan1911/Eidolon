import re

# Filenames whose whole purpose is to hold placeholder values (.env.example,
# config.sample.yaml, settings.template.py, .env.dist, ...). A word-boundary
# match on the basename, not a bare substring check, so "resampler.py" isn't
# mistaken for a template file.
_EXAMPLE_FILENAME_RE = re.compile(r"\b(example|sample|template|dist)\b", re.IGNORECASE)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

_PATTERNS: dict[str, str] = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Google API Key": r"AIza[0-9A-Za-z\-_]{35}",
    "Private Key": r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----",
    "Slack Token": r"xox[baprs]-[0-9a-zA-Z]{10,48}",
    "Stripe Secret Key": r"sk_(?:live|test)_[0-9a-zA-Z]{24}",
    "Password in URL": r"[a-zA-Z][a-zA-Z0-9+.-]*://([^\s/:@]+):([^\s/:@]+)@[^\s/]+",
}

_CRITICAL_TYPES = {"AWS Access Key", "Google API Key", "Private Key", "Stripe Secret Key"}

# Case-insensitive denylist of obvious placeholder credentials — a scanner that
# flags its own defaults as leaks trains people to ignore it.
_PLACEHOLDER_VALUES = {
    "postgres", "test", "admin", "user", "username", "password", "change_me",
    "changeme", "your_password", "yourpassword", "example", "xxx", "placeholder",
    "secret", "root", "dummy", "guest", "demo",
}

# Specific known-public example values, filtered regardless of which pattern matched them.
_KNOWN_PLACEHOLDER_SECRETS = {"AKIAIOSFODNN7EXAMPLE"}


def _is_example_path(path: str) -> bool:
    filename = path.rsplit("/", 1)[-1]
    return bool(_EXAMPLE_FILENAME_RE.search(filename))


def _host_of(full_match: str) -> str:
    """The bare host from a scheme://user:pass@host[:port][/path] match."""
    return full_match.split("@", 1)[-1].split(":")[0].split("/")[0].lower()


def _is_placeholder(secret_type: str, match: re.Match, in_example_file: bool) -> bool:
    full = match.group()
    if full.upper() in _KNOWN_PLACEHOLDER_SECRETS:
        return True
    if secret_type == "Stripe Secret Key" and full.lower().startswith("sk_test_"):
        return True
    if secret_type == "Password in URL":
        user, password = match.group(1).lower(), match.group(2).lower()
        if user in _PLACEHOLDER_VALUES or password in _PLACEHOLDER_VALUES:
            return True
        # The same value for both is a near-universal local/Docker-Compose dev
        # convention (POSTGRES_USER=POSTGRES_PASSWORD=<project name>, etc.) -
        # a genuine leaked credential is never its own username, in any file.
        if user == password:
            return True
        if in_example_file:
            host = _host_of(full)
            # A file that exists specifically to hold placeholders gets one more
            # check: a host with no dot (a bare word - almost always a
            # docker-compose service name, never a real reachable host) or an
            # explicit loopback address. AWS/Stripe/Google/Slack/private-key
            # matches aren't touched by this - those have no placeholder shape.
            if host in _LOCAL_HOSTS or "." not in host:
                return True
    return False


def _mask(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def scan_text_for_secrets(text: str, path: str = "") -> list[dict]:
    """Scan text for known secret patterns. Never returns a raw matched value —
    only its masked form — since a false negative here is far cheaper than a leak.
    `path` (the file this text came from, if any) only ever narrows what counts
    as a placeholder - it never widens what gets flagged."""
    in_example_file = _is_example_path(path)
    findings = []
    for line_no, line in enumerate(text.split("\n"), start=1):
        for secret_type, pattern in _PATTERNS.items():
            for match in re.finditer(pattern, line):
                if _is_placeholder(secret_type, match, in_example_file):
                    continue
                findings.append(
                    {
                        "line": line_no,
                        "type": secret_type,
                        "masked_value": _mask(match.group()),
                        "severity": "CRITICAL" if secret_type in _CRITICAL_TYPES else "HIGH",
                    }
                )
    return findings


def _fake_url(scheme: str, user: str, password: str, host: str) -> str:
    """Assembles a fake connection string from parts at runtime. This file gets
    scanned like any other when Eidolon's own GitHub repo is a scan target, so a
    "scheme://user:pass@host" literal sitting anywhere in this source would be a
    real secret-shaped string in the text - the scanner would (correctly) flag
    its own tests. Building it from separate pieces means that full shape never
    appears as one contiguous run of characters anywhere in this file."""
    return scheme + "://" + user + ":" + password + "@" + host


def _demo() -> None:
    placeholders = "\n".join(
        [
            _fake_url("postgresql", "postgres", "postgres", "localhost:5432/app"),
            "AKIA" + "IOSFODNN7EXAMPLE",  # split like the URLs above, same reason
            "sk_test_" + "x" * 24,  # not a real Stripe key format
            _fake_url("mongodb", "user", "change_me", "localhost/db"),
            # Same shape as a real leak, but user == password - the new generic check.
            _fake_url("postgresql", "lumos", "lumos", "postgres:5432/lumos"),
        ]
    )
    assert scan_text_for_secrets(placeholders) == []

    # A locally-hosted placeholder is only suppressed by filename inside an
    # example/template file - the same content elsewhere must still be flagged.
    local_placeholder = _fake_url("postgresql", "dbuser", "Xk9mPqR2vNzT", "localhost:5432/app")
    assert scan_text_for_secrets(local_placeholder, path="config.py") != []
    assert scan_text_for_secrets(local_placeholder, path=".env.example") == []

    # A genuinely real-looking secret must still be caught even inside a file
    # that's usually all placeholders - filename alone never fully excludes a file.
    real = "\n".join(
        [
            _fake_url("postgresql", "dbuser", "Xk9mPqR2vNzT", "prod-db.internal:5432/app"),
            "AKIA" + "1234567890ABCDEF",
            "sk_live_" + "y" * 24,  # shaped like a real key, should still flag
        ]
    )
    types = {f["type"] for f in scan_text_for_secrets(real, path=".env.example")}
    assert types == {"Password in URL", "AWS Access Key", "Stripe Secret Key"}


if __name__ == "__main__":
    _demo()
    print("ok")
