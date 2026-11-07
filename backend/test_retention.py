"""Retention: old alerts are deleted in bounded batches; recent alerts and traps are kept.

Run from backend/:  python -m pytest test_retention.py
"""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import main
from database import Alert, Trap
from services import retention

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def add_alerts(session_factory, ages_in_days, trap_id="t1"):
    with session_factory() as db:
        db.add_all([Alert(trap_id=trap_id, ip="203.0.113.1", timestamp=NOW - timedelta(days=d)) for d in ages_in_days])
        db.commit()


def ages_left(session_factory):
    with session_factory() as db:
        return sorted((NOW - a.timestamp.replace(tzinfo=timezone.utc)).days for a in db.query(Alert))


def test_default_is_ninety_days(monkeypatch):
    monkeypatch.delenv("RETENTION_DAYS", raising=False)
    assert retention.retention_days() == 90


def test_setting_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("RETENTION_DAYS", "30")
    assert retention.retention_days() == 30


@pytest.mark.parametrize("bad", ["0", "-5", "abc", "1.5", "ten"])
def test_invalid_setting_is_rejected(monkeypatch, bad):
    monkeypatch.setenv("RETENTION_DAYS", bad)
    with pytest.raises(ValueError, match="RETENTION_DAYS"):
        retention.retention_days()


def test_old_rows_are_deleted_and_recent_rows_kept(session_factory):
    add_alerts(session_factory, [1, 30, 89, 91, 120, 400])
    with session_factory() as db:
        assert retention.delete_old_alerts(db, now=NOW) == 3
    assert ages_left(session_factory) == [1, 30, 89]


def test_row_just_inside_the_window_is_kept(session_factory):
    add_alerts(session_factory, [90])  # exactly 90 days old: not older than the cutoff
    with session_factory() as db:
        assert retention.delete_old_alerts(db, now=NOW + timedelta(seconds=-1)) == 0


def test_custom_retention_period_is_used(session_factory, monkeypatch):
    monkeypatch.setenv("RETENTION_DAYS", "10")
    add_alerts(session_factory, [5, 11, 20])
    with session_factory() as db:
        assert retention.delete_old_alerts(db, now=NOW) == 2
    assert ages_left(session_factory) == [5]


def test_one_run_deletes_at_most_the_batch_limit_oldest_first(session_factory, monkeypatch):
    monkeypatch.setattr(retention, "MAX_DELETED_PER_RUN", 3)
    add_alerts(session_factory, [100, 200, 300, 400, 500])  # all expired
    with session_factory() as db:
        assert retention.delete_old_alerts(db, now=NOW) == 3
    assert ages_left(session_factory) == [100, 200]  # the three oldest went first

    with session_factory() as db:  # the next run continues the backlog
        assert retention.delete_old_alerts(db, now=NOW) == 2
    assert ages_left(session_factory) == []


def test_nothing_to_delete_returns_zero(session_factory):
    with session_factory() as db:
        assert retention.delete_old_alerts(db, now=NOW) == 0


def test_traps_are_never_deleted(session_factory, make_trap):
    make_trap("t1")
    add_alerts(session_factory, [500, 600])
    with session_factory() as db:
        retention.delete_old_alerts(db, now=NOW)
        assert db.query(Trap).count() == 1
        assert db.query(Alert).count() == 0


def test_only_the_count_is_logged(session_factory, caplog):
    caplog.set_level(logging.INFO, logger="eidolon.retention")
    add_alerts(session_factory, [500])
    with session_factory() as db:
        retention.delete_old_alerts(db, now=NOW)
    assert [r.getMessage() for r in caplog.records] == ["retention: deleted 1 old alert rows"]
    assert "203.0.113.1" not in caplog.text  # no row contents


def test_startup_runs_the_cleanup_once(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "delete_old_alerts", lambda db: calls.append(db))
    monkeypatch.setattr(main, "SessionLocal", lambda: _FakeSession())
    with TestClient(main.app):  # entering the context runs the startup hook
        assert len(calls) == 1


def test_startup_survives_a_database_error(monkeypatch, caplog):
    def broken(db):
        raise RuntimeError("could not connect to db.example.invalid with password hunter2")

    monkeypatch.setattr(main, "delete_old_alerts", broken)
    monkeypatch.setattr(main, "SessionLocal", lambda: _FakeSession())
    with TestClient(main.app) as client:  # startup completes and the API still answers
        assert client.get("/health").status_code == 200
    assert "RuntimeError" in caplog.text
    assert "hunter2" not in caplog.text and "example.invalid" not in caplog.text  # only the type is logged


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
