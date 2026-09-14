import re

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


def _is_placeholder(secret_type: str, match: re.Match) -> bool:
    full = match.group()
    if full.upper() in _KNOWN_PLACEHOLDER_SECRETS:
        return True
    if secret_type == "Stripe Secret Key" and full.lower().startswith("sk_test_"):
        return True
    if secret_type == "Password in URL":
        user, password = match.group(1), match.group(2)
        return user.lower() in _PLACEHOLDER_VALUES or password.lower() in _PLACEHOLDER_VALUES
    return False


def _mask(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def scan_text_for_secrets(text: str) -> list[dict]:
    """Scan text for known secret patterns. Never returns a raw matched value —
    only its masked form — since a false negative here is far cheaper than a leak."""
    findings = []
    for line_no, line in enumerate(text.split("\n"), start=1):
        for secret_type, pattern in _PATTERNS.items():
            for match in re.finditer(pattern, line):
                if _is_placeholder(secret_type, match):
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


def _demo() -> None:
    placeholders = "\n".join(
        [
            "postgresql://postgres:postgres@localhost:5432/app",
            "AKIAIOSFODNN7EXAMPLE",
            "sk_test_" + "x" * 24,  # synthetic — not a real Stripe key format
            "mongodb://user:change_me@localhost/db",
        ]
    )
    assert scan_text_for_secrets(placeholders) == []

    real = "\n".join(
        [
            "postgresql://dbuser:Xk9mPqR2vNzT@prod-db.internal:5432/app",
            "AKIA1234567890ABCDEF",
            "sk_live_" + "y" * 24,  # synthetic — shaped like a real key, should still flag
        ]
    )
    types = {f["type"] for f in scan_text_for_secrets(real)}
    assert types == {"Password in URL", "AWS Access Key", "Stripe Secret Key"}


if __name__ == "__main__":
    _demo()
    print("ok")
