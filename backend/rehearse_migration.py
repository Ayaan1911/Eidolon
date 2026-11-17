"""Rehearse migration 0002 on the dedicated Neon test branch, never production."""

import getpass
import hashlib
import json
import os
import sys
import warnings
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

# This endpoint belongs to eidolon-migration-check, as shown in the Neon console.
# shortcut: this helper is pinned to that verified branch; re-verify the target if it is recreated.
TEST_HOST = "ep-nameless-paper-bejfe9hq.c-9.us-east-2.aws.neon.tech"


class RehearsalError(RuntimeError):
    pass


def test_branch_url(raw):
    try:
        url = make_url(raw.strip())
    except Exception:
        raise RehearsalError("Paste only the test branch's PostgreSQL connection URL.") from None
    if url.drivername not in {"postgres", "postgresql"} or url.host != TEST_HOST:
        raise RehearsalError("Wrong endpoint. Use eidolon-migration-check with connection pooling OFF.")
    # libpq query parameters can override the hostname: reject all except Neon's TLS options.
    if set(url.query) - {"sslmode", "channel_binding"}:
        raise RehearsalError("Unexpected connection options; use the direct URL from Neon.")
    if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise RehearsalError("The test connection must require SSL.")
    if not url.username or not url.password or "***" in url.password:
        raise RehearsalError("Use Copy snippet to copy the complete URL, including its hidden password.")
    return url.set(drivername="postgresql+psycopg")


def snapshot(connection):
    """Compare every stored field without printing or writing any copied row content."""
    result = {}
    for table in ("traps", "alerts"):
        digest, count = hashlib.sha256(), 0
        # Table names are fixed here; no input is interpolated into SQL.
        rows = connection.execute(text(f"SELECT * FROM {table} ORDER BY id"))
        try:
            for row in rows:
                digest.update(json.dumps(tuple(row), default=str, separators=(",", ":")).encode())
                digest.update(b"\n")
                count += 1
        finally:
            rows.close()
        result[table] = (count, digest.digest())
    return result


def rehearse(connection, config):
    if connection.dialect.name == "postgresql":
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(text("SET LOCAL statement_timeout = '60s'"))
        connection.execute(text("LOCK TABLE traps, alerts IN SHARE ROW EXCLUSIVE MODE"))
    if connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "0001":
        raise RehearsalError("Expected a fresh test copy at revision 0001. Stop and report this message.")
    duplicates = connection.execute(text(
        "SELECT count(*) FROM (SELECT finding_id FROM traps WHERE finding_id IS NOT NULL "
        "GROUP BY finding_id HAVING count(*) > 1) AS duplicate_findings"
    )).scalar_one()
    if duplicates:
        raise RehearsalError("Duplicate finding associations found. No migration was applied; report this message.")
    before = snapshot(connection)
    config.attributes["connection"] = connection
    for operation, revision in ((command.upgrade, "0002"), (command.downgrade, "0001"), (command.upgrade, "0002")):
        operation(config, revision)
        if connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != revision:
            raise RehearsalError("Migration revision check failed.")
        if snapshot(connection) != before:
            raise RehearsalError("Data changed during rehearsal. The test transaction will be rolled back.")
    indexes = inspect(connection).get_indexes("traps")
    if not any(i["name"] == "ux_traps_finding_id" and i["unique"]
               and i["column_names"] == ["finding_id"] for i in indexes):
        raise RehearsalError("The required unique finding index is missing.")
    return {table: count for table, (count, _) in before.items()}


def main():
    engine = None
    try:
        if not sys.stdin.isatty():
            raise RehearsalError("Run in an interactive terminal; do not pipe connection details.")
        with warnings.catch_warnings():
            # Never fall back to echoing a database password if hidden input is unavailable.
            warnings.simplefilter("error", getpass.GetPassWarning)
            raw = getpass.getpass("Paste ONLY eidolon-migration-check's direct connection URL (hidden): ")
        url = test_branch_url(raw)
        raw = None
        # Alembic imports database.py for metadata. Never load the developer's .env
        # or create its configured engine; all migration work uses our checked connection.
        os.environ.update(PYTHON_DOTENV_DISABLED="1", EIDOLON_ENV="dev", DATABASE_URL="sqlite://")
        config = Config(str(Path(__file__).with_name("alembic.ini")))
        engine = create_engine(url, connect_args={"connect_timeout": 10}, hide_parameters=True)
        print("Test branch endpoint verified. Running rehearsal...", flush=True)
        with engine.begin() as connection:
            counts = rehearse(connection, config)
        print("PASS: 0001 -> 0002 -> 0001 -> 0002.")
        print(f"Data preserved: {counts['traps']} traps, {counts['alerts']} alerts.")
        print("Unique finding index verified. No production connection was used.")
        return 0
    except RehearsalError as error:
        print(f"STOP: {error}")
        return 1
    except KeyboardInterrupt:
        print("Stopped. No connection details printed.")
        return 130
    except Exception as error:
        # Driver exceptions can contain credentials or copied data; print only the class.
        print(f"STOP: {type(error).__name__}. Connection details and row contents are hidden.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
