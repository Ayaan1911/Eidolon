"""Guard the rehearsal's target and prove the upgrade/downgrade preserves copied rows."""

import warnings

import pytest
from alembic import command
from sqlalchemy import text

from conftest import alembic_config
import rehearse_migration
from rehearse_migration import TEST_HOST, RehearsalError, rehearse, snapshot, test_branch_url as checked_url


def url(host=TEST_HOST, query="sslmode=require&channel_binding=require"):
    return f"postgresql://test:dummy-password@{host}/neondb?{query}"


def test_only_the_exact_direct_test_endpoint_is_allowed():
    checked = checked_url(url())
    assert checked.host == TEST_HOST
    assert checked.drivername == "postgresql+psycopg"


@pytest.mark.parametrize("raw", [
    url("production.example.com"),
    url(TEST_HOST.replace(".c-", "-pooler.c-")),
    url(query="sslmode=disable"),
    url(query="sslmode=require&host=production.example.com"),
    url(query="sslmode=require&hostaddr=127.0.0.1"),
    url(query="sslmode=require&service=production"),
    "not a connection URL",
])
def test_other_endpoints_and_connection_overrides_are_rejected_without_echoing_input(raw):
    with pytest.raises(RehearsalError) as error:
        checked_url(raw)
    assert "dummy-password" not in str(error.value)
    assert raw not in str(error.value)


def test_rehearsal_preserves_all_fields_and_finishes_at_0002(engine):
    with engine.begin() as connection:
        config = alembic_config(connection)
        command.downgrade(config, "0001")
        connection.execute(text("INSERT INTO traps (id, name, finding_id, trigger_count) "
                                "VALUES ('saved-url', 'copied trap', 'finding', 4)"))
        connection.execute(text("INSERT INTO alerts (trap_id, ip) VALUES ('saved-url', '192.0.2.1')"))
        before = snapshot(connection)
        assert rehearse(connection, config) == {"traps": 1, "alerts": 1}
        assert snapshot(connection) == before
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0002"


def test_duplicate_findings_stop_before_any_migration(engine):
    with engine.begin() as connection:
        config = alembic_config(connection)
        command.downgrade(config, "0001")
        connection.execute(text("INSERT INTO traps (id, name, finding_id) VALUES "
                                "('first', 'one', 'duplicate'), ('second', 'two', 'duplicate')"))
        before = snapshot(connection)
        with pytest.raises(RehearsalError, match="Duplicate finding associations"):
            rehearse(connection, config)
        assert snapshot(connection) == before
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001"


def test_changed_row_content_is_rejected_even_if_row_counts_match(engine, monkeypatch):
    with engine.begin() as connection:
        config = alembic_config(connection)
        command.downgrade(config, "0001")
        connection.execute(text("INSERT INTO traps (id, name, trigger_count) VALUES ('saved', 'trap', 4)"))
        upgrade = command.upgrade

        def corrupting_upgrade(settings, revision):
            upgrade(settings, revision)
            connection.execute(text("UPDATE traps SET trigger_count = 5 WHERE id = 'saved'"))

        monkeypatch.setattr(command, "upgrade", corrupting_upgrade)
        with pytest.raises(RehearsalError, match="Data changed during rehearsal"):
            rehearse(connection, config)


def test_noninteractive_input_is_refused_before_asking_for_a_connection(monkeypatch, capsys):
    monkeypatch.setattr(rehearse_migration.sys.stdin, "isatty", lambda: False)

    def forbidden_prompt(*args):
        raise AssertionError("Connection input must not be read")

    monkeypatch.setattr(rehearse_migration.getpass, "getpass", forbidden_prompt)
    assert rehearse_migration.main() == 1
    assert "interactive terminal" in capsys.readouterr().out


def test_hidden_input_failure_never_falls_back_to_echoing_a_password(monkeypatch, capsys):
    monkeypatch.setattr(rehearse_migration.sys.stdin, "isatty", lambda: True)

    def unsafe_prompt(*args):
        warnings.warn("Hidden input is unavailable", rehearse_migration.getpass.GetPassWarning)
        raise AssertionError("Must stop before reading echoed input")

    monkeypatch.setattr(rehearse_migration.getpass, "getpass", unsafe_prompt)
    assert rehearse_migration.main() == 1
    assert "GetPassWarning" in capsys.readouterr().out
