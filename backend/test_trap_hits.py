"""Trap hit logging: network fields, referrer, and login-form submissions.

Run from backend/:  python -m pytest test_trap_hits.py
Geolocation and ntfy are stubbed in conftest.py (no network), and every test gets
its own empty in-memory database.
"""

import pytest
from sqlalchemy import text

from database import Alert

SECRET_PASSWORD = "SuperSecret!Pa55word"
LOGIN = {"email": "victim@example.com", "password_length": len(SECRET_PASSWORD)}


@pytest.fixture(autouse=True)
def _trap_t1(make_trap):
    make_trap("t1")  # these tests hit /trap/t1, which must be a real trap


@pytest.fixture
def last_alert(session_factory):
    def get():
        with session_factory() as db:
            return db.query(Alert).order_by(Alert.id.desc()).first()

    return get


def test_page_load_records_network_fields_and_referrer(client, last_alert):
    r = client.get("/trap/t1", headers={"Referer": "https://www.example-search.test/?q=admin"})
    assert r.status_code == 200
    a = last_alert()
    assert (a.isp, a.org, a.asn) == ("Example Broadband", "Example Networks Ltd", "AS64500 Example Networks")
    assert a.referer == "https://www.example-search.test/?q=admin"
    # A plain page load carries no login data at all.
    assert (a.email, a.password_attempted, a.password_length) == (None, None, None)


def test_direct_visit_has_no_referrer(client, last_alert):
    client.get("/trap/t1")
    assert last_alert().referer is None


def test_referer_is_capped(client, last_alert):
    client.get("/trap/t1", headers={"Referer": "https://x.test/" + "a" * 5000})
    assert len(last_alert().referer) == 500


def test_login_submission_stores_email_and_password_length_only(client, last_alert, engine):
    r = client.post(
        "/trap/t1/login",
        # A hostile or buggy client may send the raw password too - it must be dropped.
        json={**LOGIN, "password": SECRET_PASSWORD},
        # Browsers send the trap page itself as the referrer on this fetch: that's noise, not an origin.
        headers={"Referer": "http://testserver/trap/t1"},
    )
    assert r.status_code == 204
    a = last_alert()
    assert a.referer is None
    assert a.email == "victim@example.com"
    assert a.password_attempted is True and a.password_length == len(SECRET_PASSWORD)
    assert a.isp == "Example Broadband"  # login hits carry the same network context

    # The password must not be anywhere in the database: scan every column of every table.
    with engine.connect() as conn:
        for table in ("alerts", "traps"):
            for row in conn.execute(text(f"SELECT * FROM {table}")):
                assert SECRET_PASSWORD not in " ".join(str(v) for v in row), (table, row)


def test_empty_password_is_recorded_as_not_attempted(client, last_alert):
    client.post("/trap/t1/login", json={"email": "who@example.com", "password_length": 0})
    a = last_alert()
    assert a.password_attempted is False and a.password_length == 0


def test_login_payload_is_validated(client):
    assert client.post("/trap/t1/login", json={"email": "a@b.co", "password_length": -1}).status_code == 422
    assert client.post("/trap/t1/login", json={"email": "a@b.co", "password_length": 99999}).status_code == 422
    assert client.post("/trap/t1/login", json={"email": "a" * 400, "password_length": 3}).status_code == 422


def test_alert_stream_exposes_new_fields_to_admin(client, admin_headers):
    client.get("/trap/t1", headers={"Referer": "https://www.example-search.test/?q=admin"})
    client.post("/trap/t1/login", json={**LOGIN, "password": SECRET_PASSWORD})

    rows = client.get("/api/traps/alerts", headers=admin_headers).json()
    login = next(r for r in rows if r["email"] == "victim@example.com")
    assert login["password_attempted"] is True and login["password_length"] == len(SECRET_PASSWORD)
    assert login["org"] == "Example Networks Ltd" and login["asn"].startswith("AS64500")
    assert "password" not in login and SECRET_PASSWORD not in str(rows)
    visit = next(r for r in rows if r["referer"] and "example-search" in r["referer"])
    assert visit["password_attempted"] is None and visit["email"] is None
