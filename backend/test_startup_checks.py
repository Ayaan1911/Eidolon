"""The app must refuse to start with missing, short or placeholder secrets.

Run from backend/:  python -m pytest test_startup_checks.py
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from services.startup_checks import (
    MIN_ADMIN_KEY_LENGTH,
    MIN_HONEYTOKEN_SECRET_LENGTH,
    InsecureConfigError,
    check_secrets,
)

GOOD_ADMIN = "a" * MIN_ADMIN_KEY_LENGTH
GOOD_HONEY = "h" * MIN_HONEYTOKEN_SECRET_LENGTH
BACKEND_DIR = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _not_dev(monkeypatch):
    # conftest turns dev mode on so main can be imported; these tests need it off.
    monkeypatch.delenv("EIDOLON_ENV", raising=False)


def set_secrets(monkeypatch, admin, honey):
    monkeypatch.setenv("ADMIN_KEY", admin)
    monkeypatch.setenv("HONEYTOKEN_SECRET", honey)


def test_good_secrets_pass(monkeypatch):
    set_secrets(monkeypatch, GOOD_ADMIN, GOOD_HONEY)
    check_secrets()


def test_blank_secrets_are_refused(monkeypatch):
    set_secrets(monkeypatch, "", "")
    with pytest.raises(InsecureConfigError) as err:
        check_secrets()
    message = str(err.value)
    assert "ADMIN_KEY is not set (length 0)" in message
    assert "HONEYTOKEN_SECRET is not set (length 0)" in message


def test_unset_secrets_are_refused(monkeypatch):
    monkeypatch.delenv("ADMIN_KEY")
    monkeypatch.delenv("HONEYTOKEN_SECRET")
    with pytest.raises(InsecureConfigError):
        check_secrets()


def test_short_secrets_are_refused_without_echoing_the_value(monkeypatch):
    short_admin, short_honey = "Adm1nShort", "Hon3yShort"
    set_secrets(monkeypatch, short_admin, short_honey)
    with pytest.raises(InsecureConfigError) as err:
        check_secrets()
    message = str(err.value)
    assert f"ADMIN_KEY is too short (length {len(short_admin)}, need at least {MIN_ADMIN_KEY_LENGTH})" in message
    assert "HONEYTOKEN_SECRET is too short" in message
    assert short_admin not in message and short_honey not in message


@pytest.mark.parametrize("placeholder", ["CHANGE_ME_choose_a_long_passphrase", "change-me-please-now", "Change_Me_xxxxxxxxxxxxx"])
def test_placeholders_from_env_example_are_refused(monkeypatch, placeholder):
    set_secrets(monkeypatch, placeholder, GOOD_HONEY)
    with pytest.raises(InsecureConfigError) as err:
        check_secrets()
    assert "placeholder" in str(err.value)
    assert placeholder not in str(err.value)


def test_env_example_ships_placeholders_that_fail_the_check(monkeypatch):
    values = {}
    for line in (BACKEND_DIR / ".env.example").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            name, _, value = line.partition("=")
            values[name] = value
    set_secrets(monkeypatch, values["ADMIN_KEY"], values["HONEYTOKEN_SECRET"])
    with pytest.raises(InsecureConfigError):
        check_secrets()


def test_dev_mode_allows_weak_secrets(monkeypatch):
    monkeypatch.setenv("EIDOLON_ENV", "dev")
    set_secrets(monkeypatch, "", "x")
    check_secrets()


@pytest.mark.parametrize("value", ["Dev", "development", "1", "true"])
def test_only_the_exact_word_dev_counts(monkeypatch, value):
    monkeypatch.setenv("EIDOLON_ENV", value)
    set_secrets(monkeypatch, "", "")
    with pytest.raises(InsecureConfigError):
        check_secrets()


def run_import_main(env_overrides: dict, cwd: Path):
    """Import main in a fresh interpreter, the way uvicorn would on startup."""
    env = {k: v for k, v in os.environ.items() if k not in ("EIDOLON_ENV", "ADMIN_KEY", "HONEYTOKEN_SECRET")}
    # A local Postgres URL passes the database check; nothing connects just by importing main.
    env.update({"DATABASE_URL": "postgresql://u:p@localhost/app"}, **env_overrides, PYTHONPATH=str(BACKEND_DIR))
    return subprocess.run([sys.executable, "-c", "import main"], cwd=cwd, env=env, capture_output=True, text=True)


def test_importing_main_fails_on_a_weak_config_and_does_not_leak_the_value(tmp_path):
    secret = "tooShort1"
    result = run_import_main({"ADMIN_KEY": secret, "HONEYTOKEN_SECRET": GOOD_HONEY}, tmp_path)
    assert result.returncode != 0
    assert "ADMIN_KEY is too short" in result.stderr
    assert secret not in result.stderr and GOOD_HONEY not in result.stderr


def test_importing_main_works_with_good_secrets(tmp_path):
    result = run_import_main({"ADMIN_KEY": GOOD_ADMIN, "HONEYTOKEN_SECRET": GOOD_HONEY}, tmp_path)
    assert result.returncode == 0, result.stderr


def test_bad_trusted_proxy_hops_stops_startup(tmp_path):
    result = run_import_main(
        {"ADMIN_KEY": GOOD_ADMIN, "HONEYTOKEN_SECRET": GOOD_HONEY, "TRUSTED_PROXY_HOPS": "lots"}, tmp_path
    )
    assert result.returncode != 0
    assert "TRUSTED_PROXY_HOPS" in result.stderr
