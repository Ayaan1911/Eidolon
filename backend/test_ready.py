import pytest
from sqlalchemy import text

import database
from routers import ready

SECRET_BITS = ("postgres", "password", "hunter2", "db-host", "appuser", "sqlite")


def test_ready_on_a_healthy_database(client):
    r = client.get("/ready")
    assert r.status_code == 200 and r.json() == {"status": "ready", "commit": "unknown"}


def test_ready_reports_the_deployed_commit(client, monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abcdef1234567")
    assert client.get("/ready").json()["commit"] == "abcdef1"


def test_503_when_the_database_raises(client, monkeypatch, caplog):
    def boom():
        raise RuntimeError("connection to postgresql://appuser:hunter2@db-host.invalid failed")

    monkeypatch.setattr(database, "SessionLocal", boom)
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "not_ready", "reason": "database_unreachable"}
    for piece in SECRET_BITS:
        assert piece not in r.text + caplog.text
    assert "RuntimeError" in caplog.text  # the class name is logged, nothing else


def test_503_when_the_database_is_too_slow(client, monkeypatch):
    import time

    monkeypatch.setattr(ready, "DB_CHECK_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(ready, "_database_revision", lambda: time.sleep(0.5))
    r = client.get("/ready")
    assert r.status_code == 503 and r.json()["reason"] == "database_unreachable"


def test_503_when_the_stored_revision_is_not_head(client, session_factory):
    with session_factory() as db:
        db.execute(text("UPDATE alembic_version SET version_num = 'not-the-head'"))
        db.commit()
    r = client.get("/ready")
    assert r.status_code == 503 and r.json() == {"status": "not_ready", "reason": "migrations_out_of_date"}
    assert "not-the-head" not in r.text


def test_503_when_the_database_was_never_migrated(client, session_factory):
    with session_factory() as db:
        db.execute(text("DROP TABLE alembic_version"))
        db.commit()
    assert client.get("/ready").json()["reason"] == "migrations_out_of_date"


def test_health_never_touches_the_database(client, monkeypatch):
    def boom():
        raise RuntimeError("database is down")

    monkeypatch.setattr(database, "SessionLocal", boom)
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ready_is_rate_limited_per_ip(client):
    assert ready.READY_LIMIT == "60/minute"
    codes = [client.get("/ready").status_code for _ in range(61)]
    assert codes[:60] == [200] * 60 and codes[60] == 429


@pytest.mark.parametrize("method", ["get", "head"])
def test_root_answers_200_and_is_not_in_the_schema(client, method):
    assert getattr(client, method)("/").status_code == 200
    assert "/" not in client.get("/openapi.json").json()["paths"]
