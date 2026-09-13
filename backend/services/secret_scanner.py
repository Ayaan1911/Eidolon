import re

_PATTERNS: dict[str, str] = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Google API Key": r"AIza[0-9A-Za-z\-_]{35}",
    "Private Key": r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----",
    "Slack Token": r"xox[baprs]-[0-9a-zA-Z]{10,48}",
    "Stripe Secret Key": r"sk_live_[0-9a-zA-Z]{24}",
    "Password in URL": r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/:@]+:[^\s/:@]+@[^\s/]+",
}

_CRITICAL_TYPES = {"AWS Access Key", "Google API Key", "Private Key", "Stripe Secret Key"}


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
                findings.append(
                    {
                        "line": line_no,
                        "type": secret_type,
                        "masked_value": _mask(match.group()),
                        "severity": "CRITICAL" if secret_type in _CRITICAL_TYPES else "HIGH",
                    }
                )
    return findings
