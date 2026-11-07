"""Alembic environment. The database URL comes from the same function the app uses."""

import logging

from alembic import context

from database import Base, build_engine
from db_config import database_url

config = context.config
target_metadata = Base.metadata  # what autogenerate and the drift test compare the database against


def _configure_and_run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite cannot ALTER most things in place; batch mode rebuilds the table instead.
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests hand in an open connection (config.attributes); the command line builds its own.
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure_and_run(connection)
        return
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    engine = build_engine(database_url())
    try:
        with engine.connect() as conn:
            _configure_and_run(conn)
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (--sql) mode is not supported: it would need the database URL in the output.")
run_migrations_online()
