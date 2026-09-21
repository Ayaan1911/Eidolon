"""Trap hit logging: network fields, referrer, and login-form submissions.

Run from backend/:  python test_trap_hits.py  (also collected by pytest)
Uses an in-memory DB and stubs geolocation + ntfy, so no network and no eidolon.db.
"""

import os

os.environ["ADMIN_KEY"] = "test-admin-key"
os.environ["HONEYTOKEN_SECRET"] = "test-honeytoken-secret"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from database import Alert, Base, add_missing_alert_columns, get_db
from routers import traps
from services import admin_auth

SECRET_PASSWORD = "SuperSecret!Pa55word"

_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)


def _get_test_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


async def _fake_lookup(ip):
    return {"city": "Ashburn", "country": "United States", "lat": 1.0, "lon": 2.0,
            "isp": "Example Broadband", "org": "Example Networks Ltd", "as": "AS64500 Example Networks"}


async def _no_alert(*args, **kwargs):
    return None


traps.lookup_ip = _fake_lookup
traps.send_ntfy_alert = _no_alert
main.app.dependency_overrides[get_db] = _get_test_db
client = TestClient(main.app)


def _last_alert():
    with _Session() as db:
        return db.query(Alert).order_by(Alert.id.desc()).first()


def test_page_load_records_network_fields_and_referrer():
    r = client.get("/trap/t1", headers={"Referer": "https://www.example-search.test/?q=admin"})
    assert r.status_code == 200
    a = _last_alert()
    assert (a.isp, a.org, a.asn) == ("Example Broadband", "Example Networks Ltd", "AS64500 Example Networks")
    assert a.referer == "https://www.example-search.test/?q=admin"
    # A plain page load carries no login data at all.
    assert (a.email, a.password_attempted, a.password_length) == (None, None, None)


def test_direct_visit_has_no_referrer():
    client.get("/trap/t1")
    assert _last_alert().referer is None


def test_referer_is_capped():
    client.get("/trap/t1", headers={"Referer": "https://x.test/" + "a" * 5000})
    assert len(_last_alert().referer) == 500


def test_login_submission_stores_email_and_password_length_only():
    r = client.post(
        "/trap/t1/login",
        # A hostile or buggy client may send the raw password too - it must be dropped.
        json={"email": "victim@example.com", "password_length": len(SECRET_PASSWORD), "password": SECRET_PASSWORD},
        # Browsers send the trap page itself as the referrer on this fetch: that's noise, not an origin.
        headers={"Referer": "http://testserver/trap/t1"},
    )
    assert r.status_code == 204
    a = _last_alert()
    assert a.referer is None
    assert a.email == "victim@example.com"
    assert a.password_attempted is True and a.password_length == len(SECRET_PASSWORD)
    assert a.isp == "Example Broadband"  # login hits carry the same network context

    # The password must not be anywhere in the database: scan every column of every table.
    with _engine.connect() as conn:
        for table in ("alerts", "traps"):
            for row in conn.execute(text(f"SELECT * FROM {table}")):
                assert SECRET_PASSWORD not in " ".join(str(v) for v in row), (table, row)


def test_empty_password_is_recorded_as_not_attempted():
    client.post("/trap/t1/login", json={"email": "who@example.com", "password_length": 0})
    a = _last_alert()
    assert a.password_attempted is False and a.password_length == 0


def test_login_payload_is_validated():
    assert client.post("/trap/t1/login", json={"email": "a@b.co", "password_length": -1}).status_code == 422
    assert client.post("/trap/t1/login", json={"email": "a@b.co", "password_length": 99999}).status_code == 422
    assert client.post("/trap/t1/login", json={"email": "a" * 400, "password_length": 3}).status_code == 422


def test_alert_stream_exposes_new_fields_to_admin():
    token, _ = admin_auth.issue_token()
    rows = client.get("/api/traps/alerts", headers={"Authorization": f"Bearer {token}"}).json()
    login = next(r for r in rows if r["email"] == "victim@example.com")
    assert login["password_attempted"] is True and login["password_length"] == len(SECRET_PASSWORD)
    assert login["org"] == "Example Networks Ltd" and login["asn"].startswith("AS64500")
    assert "password" not in login and SECRET_PASSWORD not in str(rows)
    visit = next(r for r in rows if r["referer"] and "example-search" in r["referer"])
    assert visit["password_attempted"] is None and visit["email"] is None


def test_migration_adds_columns_to_an_old_database():
    old = create_engine("sqlite://", poolclass=StaticPool)
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE alerts (id INTEGER PRIMARY KEY, trap_id VARCHAR, ip VARCHAR, isp VARCHAR)"))
        conn.execute(text("INSERT INTO alerts (trap_id, ip, isp) VALUES ('old', '1.2.3.4', 'Legacy ISP')"))
    add_missing_alert_columns(old)
    add_missing_alert_columns(old)  # idempotent
    with old.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(alerts)"))}
        assert {"org", "asn", "referer", "email", "password_attempted", "password_length"} <= cols
        assert conn.execute(text("SELECT isp, org FROM alerts")).one() == ("Legacy ISP", None)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
