"""DATABASE_URL handling: what is accepted, what stops startup, and that no message leaks the URL.

Run from backend/:  python -m pytest test_db_config.py
All hostnames use the reserved .invalid domain, so nothing here can reach a real server.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import database
from db_config import DatabaseConfigError, database_url, is_sqlite, mask_url
from services.startup_checks import check_database

BACKEND_DIR = Path(__file__).resolve().parent
PASSWORD = "pw-NeverShowThis-4821"
REMOTE = f"//appuser:{PASSWORD}@db-host.example.invalid:5432/appdb"


@pytest.fixture
def env(monkeypatch):
    """Set DATABASE_URL and EIDOLON_ENV for one test. env("url") or env(None) for unset; dev=True for dev mode."""

    def set_env(url, dev=False):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("EIDOLON_ENV", raising=False)
        if url is not None:
            monkeypatch.setenv("DATABASE_URL", url)
        if dev:
            monkeypatch.setenv("EIDOLON_ENV", "dev")

    return set_env


# --- unset -----------------------------------------------------------------------------------


def test_unset_in_dev_falls_back_to_the_local_sqlite_file(env):
    env(None, dev=True)
    assert database_url() == "sqlite:///eidolon.db"


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_unset_outside_dev_refuses_to_start(env, blank):
    env(blank)
    with pytest.raises(DatabaseConfigError, match="DATABASE_URL is not set"):
        database_url()
    with pytest.raises(DatabaseConfigError):
        check_database()


# --- accepted forms --------------------------------------------------------------------------


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_postgres_forms_become_the_psycopg_driver(env, scheme):
    env(f"{scheme}:{REMOTE}?sslmode=require")
    assert database_url().startswith("postgresql+psycopg://")
    assert is_sqlite(database_url()) is False


@pytest.mark.parametrize("mode", ["require", "verify-ca", "verify-full"])
def test_ssl_modes_that_encrypt_are_accepted(env, mode):
    env(f"postgresql:{REMOTE}?sslmode={mode}")
    database_url()


def test_extra_provider_parameters_are_kept(env):
    env(f"postgresql:{REMOTE}?sslmode=require&channel_binding=require")
    assert "channel_binding=require" in database_url()


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_local_hosts_do_not_need_ssl(env, host):
    env(f"postgresql://u:p@{host}/appdb")
    database_url()


def test_sqlite_url_is_allowed_only_in_dev(env):
    env("sqlite:///some.db", dev=True)
    assert database_url() == "sqlite:///some.db"
    env("sqlite:///some.db")
    with pytest.raises(DatabaseConfigError):
        database_url()


# --- refused ---------------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["", "?sslmode=disable", "?sslmode=prefer", "?sslmode=allow", "?application_name=x"])
def test_remote_host_without_ssl_is_refused(env, query):
    env(f"postgresql:{REMOTE}{query}")
    with pytest.raises(DatabaseConfigError, match="without SSL"):
        database_url()


def test_remote_host_without_ssl_is_refused_even_in_dev(env):
    env(f"postgresql:{REMOTE}", dev=True)
    with pytest.raises(DatabaseConfigError):
        database_url()


@pytest.mark.parametrize(
    "bad",
    [
        f"mysql:{REMOTE}",
        f"postgresql+psycopg2:{REMOTE}?sslmode=require",
        "not a url at all",
        f"postgresql://appuser:{PASSWORD}@db-host.example.invalid:notaport/appdb?sslmode=require",
    ],
)
def test_unsupported_or_malformed_urls_are_refused(env, bad):
    env(bad)
    with pytest.raises(DatabaseConfigError):
        database_url()


# --- the URL must never appear in an error ---------------------------------------------------

LEAKY_CASES = [
    f"postgresql:{REMOTE}",  # missing SSL
    f"mysql:{REMOTE}",  # wrong driver
    f"postgresql://appuser:{PASSWORD}@db-host.example.invalid:notaport/appdb?sslmode=require",  # unparseable
    f"sqlite:///{PASSWORD}.db",  # SQLite outside dev
]


@pytest.mark.parametrize("url", LEAKY_CASES)
def test_error_messages_never_contain_any_part_of_the_url(env, url):
    env(url)
    with pytest.raises(DatabaseConfigError) as caught:
        database_url()
    text = str(caught.value) + repr(caught.value)
    for piece in (PASSWORD, "appuser", "db-host", "example.invalid", "appdb"):
        assert piece not in text
    assert caught.value.__cause__ is None  # no chained parser error that might quote the URL


def import_main(tmp_path, **overrides):
    """Import main in a fresh interpreter, the way uvicorn would on startup."""
    drop = ("DATABASE_URL", "EIDOLON_ENV", "ADMIN_KEY", "HONEYTOKEN_SECRET")
    env = {k: v for k, v in os.environ.items() if k not in drop}  # keep the rest: Windows needs SystemRoot
    env.update(ADMIN_KEY="a" * 20, HONEYTOKEN_SECRET="h" * 20, PYTHONPATH=str(BACKEND_DIR), **overrides)
    return subprocess.run([sys.executable, "-c", "import main"], cwd=tmp_path, env=env, capture_output=True, text=True)


@pytest.mark.parametrize("url", LEAKY_CASES)
def test_a_refused_startup_prints_nothing_secret(url, tmp_path):
    """The full traceback a real failed start would print."""
    result = import_main(tmp_path, DATABASE_URL=url)
    assert result.returncode != 0
    assert "DatabaseConfigError" in result.stderr
    for piece in (PASSWORD, "appuser", "db-host"):
        assert piece not in result.stderr + result.stdout


def test_unset_database_url_stops_a_real_startup(tmp_path):
    result = import_main(tmp_path)
    assert result.returncode != 0
    assert "DATABASE_URL is not set" in result.stderr
    assert not (tmp_path / "eidolon.db").exists()  # and it did not quietly create a local file


# --- masking and engine settings -------------------------------------------------------------


def test_mask_url_hides_the_password():
    masked = mask_url(f"postgresql+psycopg:{REMOTE}?sslmode=require")
    assert PASSWORD not in masked and "***" in masked


def test_postgres_engine_uses_the_named_settings_and_hides_the_password():
    engine = database.build_engine(f"postgresql+psycopg:{REMOTE}?sslmode=require")  # builds lazily, never connects
    assert engine.pool.size() == database.POOL_SIZE == 3
    assert engine.pool._max_overflow == database.MAX_OVERFLOW == 2
    assert engine.pool._recycle == database.POOL_RECYCLE_SECONDS == 300
    assert engine.pool._pre_ping is True
    assert PASSWORD not in repr(engine) + str(engine.url)  # SQLAlchemy masks it by default
    engine.dispose()


def test_sqlite_engine_keeps_the_thread_flag_and_pings():
    engine = database.build_engine("sqlite://")
    assert engine.pool._pre_ping is True
    engine.dispose()
