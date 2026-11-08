"""Where the database is, decided in ONE place (the app and Alembic both call database_url()).

Rules:
- DATABASE_URL set: it must be Postgres (postgres:// and postgresql:// both accepted), and any
  host that is not this machine must require SSL.
- DATABASE_URL unset: only EIDOLON_ENV=dev may fall back to a local SQLite file. Anywhere else the
  app refuses to start, so production can never quietly write to Render's wiped disk.

Error messages here describe the problem but NEVER include the URL or any part of it, because
the URL contains the database password and error messages end up in logs.
"""

import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

# The engine is built when `database` is imported, which happens before main.py reaches its own
# load_dotenv(). Loading backend/.env here too means a local DATABASE_URL is seen by the app AND by
# Alembic. Variables already set in the real environment (Render) still win.
load_dotenv()

DATABASE_URL_ENV = "DATABASE_URL"
SQLITE_DEV_URL = "sqlite:///eidolon.db"
PG_DRIVER = "postgresql+psycopg"  # SQLAlchemy's name for psycopg 3
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Any of these makes the connection encrypted; "require" is what Neon's connection string uses.
SSL_MODES = {"require", "verify-ca", "verify-full"}


class DatabaseConfigError(RuntimeError):
    pass


def _is_dev() -> bool:
    return os.environ.get("EIDOLON_ENV") == "dev"


def _is_local(host: str | None) -> bool:
    # No host means a unix socket, which is also this machine.
    return not host or host in LOCAL_HOSTS or host.startswith("/")


def database_url() -> str:
    """The SQLAlchemy URL to use, or DatabaseConfigError. The result contains the password:
    never print it (use mask_url)."""
    raw = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not raw:
        if _is_dev():
            return SQLITE_DEV_URL
        raise DatabaseConfigError(
            f"{DATABASE_URL_ENV} is not set. Refusing to start without a database "
            "(a local file would be wiped on every deploy). Set it, or EIDOLON_ENV=dev for local development only."
        )

    # Rewrite the scheme as plain text first, so Heroku/Neon-style postgres:// URLs work.
    for prefix in ("postgres://", "postgresql://"):
        if raw.startswith(prefix):
            raw = PG_DRIVER + "://" + raw[len(prefix):]
            break

    try:
        url = make_url(raw)
    except Exception:  # the parser's own message can quote the URL, so drop it entirely
        raise DatabaseConfigError(f"{DATABASE_URL_ENV} is not a valid database URL.") from None

    if url.get_backend_name() == "sqlite":
        if not _is_dev():
            raise DatabaseConfigError(f"{DATABASE_URL_ENV} must be a Postgres URL outside EIDOLON_ENV=dev.")
        return raw
    if url.drivername != PG_DRIVER:
        raise DatabaseConfigError(f"{DATABASE_URL_ENV} must be a postgres:// or postgresql:// URL.")

    if not _is_local(url.host):
        sslmode = url.query.get("sslmode")
        if isinstance(sslmode, tuple):  # the parameter was repeated
            sslmode = sslmode[-1]
        if sslmode not in SSL_MODES:
            raise DatabaseConfigError(
                f"{DATABASE_URL_ENV} points at a remote host without SSL. "
                "Add ?sslmode=require (the connection string from your provider already has it)."
            )
    return raw


def is_sqlite(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def mask_url(url: str | URL) -> str:
    """The URL with the password replaced by ***, for the rare place a URL must be shown."""
    return make_url(url).render_as_string(hide_password=True)
