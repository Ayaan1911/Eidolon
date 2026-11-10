"""Logging for the whole app, configured once at startup (configure_logging).

Outside dev every line is one JSON object, so a log search can filter on fields (level, request_id)
instead of matching free text. In dev it is a plain readable line. Uvicorn's own loggers are pointed
at the same handler, so access lines and application lines look alike.

Nothing sensitive may reach a log line: visitor IPs are masked (mask_ip), and RedactFilter blanks
anything that looks like a database URL, a bearer token or one of our configured secrets, as a last
line of defense in case someone logs one by mistake.
"""

import ipaddress
import json
import logging
import logging.config
import os
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

LOG_LEVEL_ENV = "LOG_LEVEL"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
DEFAULT_LOG_LEVEL = "INFO"

# The id of the request being handled; "-" outside a request (startup, tests).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
# Letters, digits and hyphens only, 1-64 long: an id we will accept from a client and echo back.
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}")

REDACTED = "[redacted]"
_DATABASE_URL = re.compile(r"\b(?:postgres(?:ql)?|mysql|sqlite)(?:\+\w+)?://\S+", re.IGNORECASE)
_BEARER_TOKEN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
# Environment variables whose values must never appear in a log. Very short values are skipped
# (redacting "ab" everywhere would just wreck the log).
_SECRET_ENV_VARS = ("ADMIN_KEY", "HONEYTOKEN_SECRET", "GITHUB_TOKEN", "NTFY_TOPIC")
_MIN_SECRET_LENGTH = 8
# Attributes every LogRecord has; anything else on a record came from `extra=` and is logged too.
_STANDARD_RECORD_KEYS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "request_id"}


class LogConfigError(RuntimeError):
    pass


def log_level() -> str:
    """LOG_LEVEL as an upper-case name (default INFO). The error never contains the bad value."""
    raw = os.environ.get(LOG_LEVEL_ENV, "").strip().upper()
    if not raw:
        return DEFAULT_LOG_LEVEL
    if raw not in LOG_LEVELS:
        raise LogConfigError(f"{LOG_LEVEL_ENV} must be one of {', '.join(LOG_LEVELS)}")
    return raw


def new_request_id(incoming: str | None) -> str:
    """The client's X-Request-ID if it is safe to echo back, otherwise a fresh UUID4."""
    if incoming and REQUEST_ID_PATTERN.fullmatch(incoming):
        return incoming
    return str(uuid.uuid4())


def mask_ip(ip: str) -> str:
    """For logs only (the database keeps the full IP). IPv4: last octet -> xxx. IPv6: first 3 groups."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return "unknown"
    if address.version == 4:
        return ".".join(ip.split(".")[:3] + ["xxx"])
    return ":".join(address.exploded.split(":")[:3]) + "::xxx"


def redact(text: str) -> str:
    text = _DATABASE_URL.sub(REDACTED, text)
    text = _BEARER_TOKEN.sub(f"Bearer {REDACTED}", text)
    for name in _SECRET_ENV_VARS:
        secret = os.environ.get(name, "")
        if len(secret) >= _MIN_SECRET_LENGTH:
            text = text.replace(secret, REDACTED)
    return text


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        for key, value in vars(record).items():
            if key not in _STANDARD_RECORD_KEYS and isinstance(value, str):
                setattr(record, key, redact(value))
        if record.exc_info:  # turn the traceback into text now so it can be redacted too
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


class AccessLogMaskFilter(logging.Filter):
    """Uvicorn's access line starts with the visitor's "ip:port"; keep only the masked ip."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and record.args:
            client = str(record.args[0]).removeprefix("[")
            host = client.split("]")[0] if "]" in client else client.rsplit(":", 1)[0]
            record.args = (mask_ip(host), *record.args[1:])
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        when = datetime.fromtimestamp(record.created, timezone.utc)
        entry = {
            "timestamp": when.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        entry.update({k: v for k, v in vars(record).items() if k not in _STANDARD_RECORD_KEYS})
        if record.exc_text:
            entry["exception"] = record.exc_text
        return json.dumps(entry, default=str)


def configure_logging() -> None:
    """Set up logging for the app and uvicorn. Safe to call again (it replaces the handlers)."""
    dev = os.environ.get("EIDOLON_ENV") == "dev"
    level = log_level()
    # The same handler (and so the same format and filters) for the app and for uvicorn.
    uvicorn_logger = {"handlers": [], "level": level, "propagate": True}
    logging.getLogger("uvicorn.access").filters.clear()  # dictConfig adds filters; without this a second call doubles them
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {"()": RequestIdFilter},
                "redact": {"()": RedactFilter},
                "mask_access_ip": {"()": AccessLogMaskFilter},
            },
            "formatters": {
                "json": {"()": JsonFormatter},
                "dev": {"format": "%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "dev" if dev else "json",
                    # Order matters: the request id first, then redaction of the finished message.
                    "filters": ["request_id", "redact"],
                }
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "uvicorn": uvicorn_logger,
                "uvicorn.error": uvicorn_logger,
                "uvicorn.access": {**uvicorn_logger, "filters": ["mask_access_ip"]},
            },
        }
    )


class RequestIdMiddleware:
    """Gives every HTTP request an id: stored for the log lines and returned in X-Request-ID.
    Plain ASGI (not BaseHTTPMiddleware) so the id is still set when uvicorn writes its access line."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = new_request_id(incoming)
        token = request_id_var.set(request_id)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message["headers"], (b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
