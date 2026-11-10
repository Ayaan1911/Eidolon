"""The one place that decides which base URL (scheme + host) links sent to the frontend start with.

Behind Render's proxy the app sees plain http (the start command uses --no-proxy-headers), so the
scheme from the request is not trustworthy. Instead: PUBLIC_BASE_URL if set, else the request's host
with https forced - except on localhost, where https would not work.
"""

import os
from urllib.parse import urlsplit

from fastapi import Request

LOCAL_HOSTS = {"localhost", "127.0.0.1"}


class PublicBaseUrlError(RuntimeError):
    pass


def _is_local(host: str | None) -> bool:
    return host is not None and (host in LOCAL_HOSTS or host.endswith(".localhost"))


def configured_base_url() -> str | None:
    """PUBLIC_BASE_URL normalised (no trailing slash), or None if unset. Raises PublicBaseUrlError
    if it is invalid; the message never contains the value."""
    raw = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if not raw:
        return None
    try:
        parts = urlsplit(raw.rstrip("/"))
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError on a bad port
    except ValueError:
        host = None
    if not host or parts.scheme not in ("http", "https") or parts.path or parts.query or parts.fragment or parts.username:
        raise PublicBaseUrlError(
            "PUBLIC_BASE_URL is invalid: it must look like https://api.example.com "
            "(scheme and host only: no path, query or credentials; http only for localhost)"
        )
    if parts.scheme == "http" and host not in LOCAL_HOSTS:
        raise PublicBaseUrlError("PUBLIC_BASE_URL must use https unless the host is localhost or 127.0.0.1")
    return f"{parts.scheme}://{parts.netloc}"


def public_base_url(request: Request) -> str:
    """Base URL for links in responses, with no trailing slash."""
    configured = configured_base_url()
    if configured:
        return configured
    scheme = "http" if _is_local(request.url.hostname) else "https"
    return f"{scheme}://{request.url.netloc}"
