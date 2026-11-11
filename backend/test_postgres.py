"""Checks that only make sense against a real Postgres. They are skipped unless DATABASE_URL points
at one, so the normal local run is unaffected. CI runs them in a job with a Postgres service
container, after `alembic upgrade head` / `downgrade base` / `upgrade head`.

Run from backend/:  DATABASE_URL=postgresql://user:pass@localhost/db python -m pytest test_postgres.py
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from conftest import alembic_config
import main
import database
from database import Alert, Base, Trap
from routers.traps import count_hit
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
def pg_client(pg_engine, monkeypatch):
    """The real app, pointed at the Postgres database, with clean tables."""
    Session = sessionmaker(bind=pg_engine)
    with Session() as db:
        db.query(Alert).delete()
        db.query(Trap).delete()
        db.commit()

    monkeypatch.setattr(database, "SessionLocal", Session)
    from fastapi.testclient import TestClient

    yield TestClient(main.app), Session


def test_schema_matches_the_models(pg_engine):
    with pg_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_timestamp_columns_are_timezone_aware(pg_engine):
    columns = {c["name"]: c["type"] for c in inspect(pg_engine).get_columns("alerts")}
    assert columns["timestamp"].timezone is True


def test_unique_finding_migration_preserves_deployed_url_and_alert(pg_engine):
    with pg_engine.begin() as connection:
        config = alembic_config(connection)
        command.downgrade(config, "0001")
        connection.execute(text("INSERT INTO traps (id, name, finding_id) VALUES ('pg-old-url', 'old trap', 'pg-finding')"))
        connection.execute(text("INSERT INTO alerts (trap_id, ip) VALUES ('pg-old-url', '127.0.0.1')"))
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT id, name FROM traps WHERE finding_id = 'pg-finding'")).one() == ('pg-old-url', 'old trap')
        assert connection.execute(text("SELECT trap_id, ip FROM alerts WHERE trap_id = 'pg-old-url'")).one() == ('pg-old-url', '127.0.0.1')
        connection.execute(text("DELETE FROM alerts WHERE trap_id = 'pg-old-url'"))
        connection.execute(text("DELETE FROM traps WHERE id = 'pg-old-url'"))


def test_create_a_trap_record_a_hit_read_it_back_and_delete_old_hits(pg_client, admin_headers):
    client, Session = pg_client

    created = client.post("/api/traps", json={"name": "smoke trap"}, headers=admin_headers)
    assert created.status_code == 200
    trap_id = created.json()["id"]

    assert client.get(f"/trap/{trap_id}").status_code == 200  # a real hit through the real route

    rows = client.get("/api/traps/alerts", headers=admin_headers).json()
    assert [r["trap_id"] for r in rows] == [trap_id]
    # UTC with an explicit marker, e.g. 2026-11-08T12:00:00.123456Z
    assert rows[0]["timestamp"].endswith("Z")

    with Session() as db:
        assert db.query(Trap).filter(Trap.id == trap_id).one().trigger_count == 1
        db.add(Alert(trap_id=trap_id, ip="203.0.113.9", timestamp=datetime.now(timezone.utc) - timedelta(days=400)))
        db.commit()
        assert retention.delete_old_alerts(db) == 1  # only the 400-day-old row
        assert db.query(Alert).count() == 1
        assert db.query(Trap).count() == 1  # the trap itself is kept


def test_simultaneous_hits_are_all_counted(pg_client):
    _, Session = pg_client
    with Session() as db:
        db.add(Trap(id="race", name="race"))
        db.commit()

    threads, per_thread = 16, 10
    start = threading.Barrier(threads)  # release every thread at once to force overlap

    def hammer():
        start.wait()
        for _ in range(per_thread):
            with Session() as db:  # a separate session per thread, as in production
                count_hit(db, "race")
                db.commit()

    workers = [threading.Thread(target=hammer) for _ in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()

    with Session() as db:
        assert db.query(Trap).filter(Trap.id == "race").one().trigger_count == threads * per_thread


def test_simultaneous_finding_deployments_return_one_trap(pg_client):
    from fastapi import Request
    from models.schemas import FindingTrapRequest
    from routers.traps import deploy_trap_for_finding

    _, Session = pg_client
    barrier = threading.Barrier(8)

    def deploy(_):
        barrier.wait(timeout=10)
        body = FindingTrapRequest(repo="owner/repo", file="config", type="API key")
        request = Request({"type": "http", "scheme": "https", "server": ("example.com", 443), "path": "/", "headers": []})
        return deploy_trap_for_finding("same-finding", body, request).id

    with ThreadPoolExecutor(max_workers=8) as workers:
        ids = list(workers.map(deploy, range(8)))
    assert len(set(ids)) == 1
    with Session() as db:
        assert db.query(Trap).filter(Trap.finding_id == "same-finding").count() == 1
