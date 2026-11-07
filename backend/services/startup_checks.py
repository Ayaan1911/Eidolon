"""Refuse to start with missing, weak or placeholder secrets (fail closed).

A blank ADMIN_KEY or HONEYTOKEN_SECRET used to be accepted, which let anyone forge a valid
admin token (an HMAC with an empty key is still a valid HMAC). Error messages name the
variable and its length, never its value.
"""

import os

MIN_ADMIN_KEY_LENGTH = 12
MIN_HONEYTOKEN_SECRET_LENGTH = 16
# .env.example ships values starting with this, so copying it unchanged must not boot.
PLACEHOLDER_PREFIX = "change-me"
DEV_ENV_VAR = "EIDOLON_ENV"

_REQUIRED = {
    "ADMIN_KEY": MIN_ADMIN_KEY_LENGTH,
    "HONEYTOKEN_SECRET": MIN_HONEYTOKEN_SECRET_LENGTH,
}


class InsecureConfigError(RuntimeError):
    pass


def _problem(name: str, minimum: int) -> str | None:
    value = os.environ.get(name, "")
    if not value:
        return f"{name} is not set (length 0)"
    if value.lower().replace("_", "-").startswith(PLACEHOLDER_PREFIX):
        return f"{name} is still the placeholder from .env.example (length {len(value)})"
    if len(value) < minimum:
        return f"{name} is too short (length {len(value)}, need at least {minimum})"
    return None


def check_secrets() -> None:
    """Raise InsecureConfigError unless the secrets are usable. EIDOLON_ENV=dev skips the check."""
    if os.environ.get(DEV_ENV_VAR) == "dev":
        return
    problems = [p for name, minimum in _REQUIRED.items() if (p := _problem(name, minimum))]
    if problems:
        raise InsecureConfigError(
            "Refusing to start: " + "; ".join(problems) + f". Set real secrets, or {DEV_ENV_VAR}=dev for local development only."
        )
