"""Checks that only make sense against a real Postgres. They are skipped unless DATABASE_URL points
at one, so the normal local run is unaffected. CI runs them in a job with a Postgres service
container, after `alembic upgrade head` / `downgrade base` / `upgrade head`.

Run from backend/:  DATABASE_URL=postgresql://user:pass@localhost/db python -m pytest test_postgres.py
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import main
from database import Alert, Base, Trap, get_db
from services import retention

# Read when the file is imported, before conftest's per-test fixtures clear DATABASE_URL.
PG_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL.startswith(("postgres://", "postgresql")), reason="needs a Postgres DATABASE_URL")


@pytest.fixture
def pg_engine(monkeypatch):
    from db_config import database_url

    monkeypatch.setenv("DATABASE_URL", PG_URL)  # conftest removed it for this test; database_url() needs it
    engine = create_engine(database_url())
    yield engine
    engine.dispose()


@pytest.fixture
def pg_client(pg_engine):
    """The real app, pointed at the Postgres database, with clean tables."""
    Session = sessionmaker(bind=pg_engine)
    with Session() as db:
        db.query(Alert).delete()
        db.query(Trap).delete()
        db.commit()

    def get_pg_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = get_pg_db
    from fastapi.testclient import TestClient

    yield TestClient(main.app), Session


def test_schema_matches_the_models(pg_engine):
    with pg_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_timestamp_columns_are_timezone_aware(pg_engine):
    columns = {c["name"]: c["type"] for c in inspect(pg_engine).get_columns("alerts")}
    assert columns["timestamp"].timezone is True


def test_create_a_trap_record_a_hit_read_it_back_and_delete_old_hits(pg_client, admin_headers):
    client, Session = pg_client

    created = client.post("/api/traps", json={"name": "smoke trap"}, headers=admin_headers)
    assert created.status_code == 200
    trap_id = created.json()["id"]

    assert client.get(f"/trap/{trap_id}").status_code == 200  # a real hit through the real route

    rows = client.get("/api/traps/alerts", headers=admin_headers).json()
    assert [r["trap_id"] for r in rows] == [trap_id]
    # The API format is unchanged: UTC with no offset, e.g. 2026-11-08T12:00:00.123456
    assert datetime.fromisoformat(rows[0]["timestamp"]).tzinfo is None

    with Session() as db:
        assert db.query(Trap).filter(Trap.id == trap_id).one().trigger_count == 1
        db.add(Alert(trap_id=trap_id, ip="203.0.113.9", timestamp=datetime.now(timezone.utc) - timedelta(days=400)))
        db.commit()
        assert retention.delete_old_alerts(db) == 1  # only the 400-day-old row
        assert db.query(Alert).count() == 1
        assert db.query(Trap).count() == 1  # the trap itself is kept
