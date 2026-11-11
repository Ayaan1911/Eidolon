"""The Alembic migrations must build exactly the schema the models describe.

Run from backend/:  python -m pytest test_migrations.py
These run on a temporary SQLite file; CI runs the same checks against a real Postgres.
"""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from conftest import alembic_config
from database import Base

APP_TABLES = {"traps", "alerts"}


@pytest.fixture
def sqlite_url(tmp_path, monkeypatch):
    """A throwaway SQLite database, handed to the migrations the same way production hands over
    DATABASE_URL (EIDOLON_ENV=dev, set by conftest, is what allows a SQLite URL)."""
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migrations_and_models_do_not_drift(sqlite_url):
    command.upgrade(alembic_config(), "head")

    engine = create_engine(sqlite_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)
    engine.dispose()

    # An empty list means the models and the migrations describe the same schema. If this fails,
    # a model changed without a new migration (run: alembic revision --autogenerate).
    assert differences == []


def test_upgrade_creates_the_tables_and_the_version_row(sqlite_url):
    command.upgrade(alembic_config(), "head")
    assert table_names(sqlite_url) == APP_TABLES | {"alembic_version"}


def test_downgrade_to_base_then_upgrade_again(sqlite_url):
    config = alembic_config()
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    assert table_names(sqlite_url) <= {"alembic_version"}  # app tables are gone

    command.upgrade(config, "head")
    assert table_names(sqlite_url) == APP_TABLES | {"alembic_version"}


def test_upgrade_head_twice_is_a_no_op(sqlite_url):
    config = alembic_config()
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # already at head: must not try to create tables again
    assert table_names(sqlite_url) == APP_TABLES | {"alembic_version"}


def test_baseline_has_the_indexes_the_code_relies_on(sqlite_url):
    command.upgrade(alembic_config(), "head")
    engine = create_engine(sqlite_url)
    inspector = inspect(engine)
    indexed = {(table, tuple(ix["column_names"])) for table in APP_TABLES for ix in inspector.get_indexes(table)}
    engine.dispose()
    assert {("traps", ("finding_id",)), ("alerts", ("trap_id",)), ("alerts", ("timestamp",))} <= indexed


def test_duplicate_associations_fail_without_changing_deployed_traps(sqlite_url):
    config = alembic_config()
    command.upgrade(config, "0001")
    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO traps (id, name, finding_id, trigger_count) VALUES ('a', 'first', 'finding', 2), ('b', 'second', 'finding', 3)"))
        connection.execute(text("INSERT INTO alerts (trap_id) VALUES ('b')"))
    with pytest.raises(RuntimeError, match="Duplicate finding associations"):
        command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id, name, trigger_count FROM traps ORDER BY id")).all() == [('a', 'first', 2), ('b', 'second', 3)]
        assert connection.execute(text("SELECT trap_id FROM alerts")).scalar_one() == 'b'
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == '0001'
    engine.dispose()


def test_unique_index_and_downgrade_preserve_old_urls(sqlite_url):
    config = alembic_config()
    command.upgrade(config, "0001")
    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO traps (id, name, finding_id) VALUES ('old-url', 'original', 'finding')"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert next(i for i in inspect(connection).get_indexes('traps') if i['name'] == 'ux_traps_finding_id')['unique']
    command.downgrade(config, "0001")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id, name, finding_id FROM traps")).all() == [('old-url', 'original', 'finding')]
    engine.dispose()
