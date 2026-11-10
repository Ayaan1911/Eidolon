"""Trap routes decide validity first: an unknown id or a bad key has no side effects.
Valid hits are logged and counted, but the ntfy push is throttled.

Run from backend/:  python -m pytest test_trap_hardening.py
"""

import logging

import pytest

from database import Alert, Trap
from routers import traps
from services import honeytoken

PASSWORD = "Sup3rSecret!Passw0rd"


@pytest.fixture
def pushes(monkeypatch):
    """Every ntfy push the app tries to send."""
    sent = []

    async def record(title, fields):
        sent.append((title, fields))

    monkeypatch.setattr(traps, "send_ntfy_alert", record)
    return sent


@pytest.fixture
def lookups(monkeypatch):
    """Every IP the app tries to geolocate."""
    seen = []

    async def record(ip):
        seen.append(ip)
        return {}

    monkeypatch.setattr(traps, "lookup_ip", record)
    return seen


@pytest.fixture
def clock(monkeypatch):
    """Controllable replacement for the clock the push throttle reads."""
    now = {"t": 1000.0}
    monkeypatch.setattr(traps.time, "monotonic", lambda: now["t"])
    return now


def count(session_factory, model):
    with session_factory() as db:
        return db.query(model).count()


# --- unknown ids ------------------------------------------------------------------------------


def test_unknown_trap_page_looks_normal_but_has_no_side_effects(client, make_trap, pushes, lookups, session_factory):
    make_trap("real")
    known = client.get("/trap/real")
    unknown = client.get("/trap/doesnotexist")

    assert unknown.status_code == known.status_code == 200
    assert unknown.text == known.text  # same page, nothing to tell them apart
    assert count(session_factory, Alert) == 1  # only the real trap's hit
    assert lookups == ["testclient"]  # geolocation ran once, for the real hit only
    assert len(pushes) == 1


def test_unknown_trap_login_looks_normal_but_has_no_side_effects(client, pushes, lookups, session_factory):
    r = client.post("/trap/doesnotexist/login", json={"email": "x@example.com", "password_length": 8})
    assert r.status_code == 204
    assert count(session_factory, Alert) == 0
    assert lookups == [] and pushes == []


def test_unknown_id_is_logged_at_info_with_control_characters_removed(client, caplog):
    caplog.set_level(logging.INFO, logger="eidolon.traps")
    client.get("/trap/bad%0d%0aFORGED%20LOG%20LINE")
    # Only this logger's lines: with logging now at INFO, the test client's own request log is in caplog too.
    text = "\n".join(r.getMessage() for r in caplog.records if r.name == "eidolon.traps")
    assert "unknown id" in text
    assert "\r" not in text and "\n" not in text  # one single line


def test_bad_honeytoken_has_no_side_effects(client, pushes, lookups, caplog):
    caplog.set_level(logging.INFO, logger="eidolon.traps")
    good = honeytoken.generate_token()
    tampered = good[:-1] + ("0" if good[-1] != "0" else "1")  # always differs from the real signature
    for headers in ({}, {"X-API-Key": "junk"}, {"X-API-Key": tampered}):
        assert client.get("/api/internal/verify", headers=headers).status_code == 401
    assert lookups == [] and pushes == []
    assert tampered not in caplog.text and "junk" not in caplog.text  # the key itself is never logged


# --- valid hits -------------------------------------------------------------------------------


def test_valid_hit_is_logged_geolocated_and_pushed(client, make_trap, pushes, lookups, session_factory):
    make_trap("t1", name="Prod DB")
    client.get("/trap/t1")
    assert count(session_factory, Alert) == 1
    assert lookups == ["testclient"]
    assert [title for title, _ in pushes] == ["Trap 'Prod DB' triggered"]


def test_repeat_hits_push_once_per_window_but_are_still_logged_and_counted(
    client, make_trap, pushes, clock, session_factory
):
    make_trap("t1")
    for _ in range(4):
        clock["t"] += 10  # all inside the 5-minute window
        client.get("/trap/t1")

    assert len(pushes) == 1
    assert count(session_factory, Alert) == 4
    with session_factory() as db:
        assert db.query(Trap).filter(Trap.id == "t1").one().trigger_count == 4


def test_push_resumes_after_the_window(client, make_trap, pushes, clock):
    make_trap("t1")
    client.get("/trap/t1")
    clock["t"] += traps.ALERT_WINDOW_SECONDS - 1
    client.get("/trap/t1")
    assert len(pushes) == 1
    clock["t"] += 2  # now past the window
    client.get("/trap/t1")
    assert len(pushes) == 2


def test_each_trap_has_its_own_window(client, make_trap, pushes):
    make_trap("t1")
    make_trap("t2")
    client.get("/trap/t1")
    client.get("/trap/t2")
    assert len(pushes) == 2


def test_valid_decoy_key_pushes_once_per_window_and_still_looks_like_a_failure(client, pushes, clock):
    key = honeytoken.generate_token()
    for _ in range(3):
        clock["t"] += 5
        assert client.get("/api/internal/verify", headers={"X-API-Key": key}).status_code == 401
    assert len(pushes) == 1
    assert pushes[0][0] == "Honeytoken triggered"


def test_login_hits_are_all_logged_and_do_not_push(client, make_trap, pushes, session_factory):
    make_trap("t1")
    for _ in range(3):
        client.post("/trap/t1/login", json={"email": "a@b.co", "password_length": 4})
    assert count(session_factory, Alert) == 3
    assert pushes == []  # login submissions never sent a push, and still don't


# --- rate limits ------------------------------------------------------------------------------


def test_trap_page_is_rate_limited(client, make_trap):
    make_trap("t1")
    allowed = int(traps.TRAP_PAGE_LIMIT.split("/")[0])
    codes = [client.get("/trap/t1").status_code for _ in range(allowed + 1)]
    assert codes == [200] * allowed + [429]


def test_trap_login_is_rate_limited(client, make_trap):
    make_trap("t1")
    allowed = int(traps.TRAP_LOGIN_LIMIT.split("/")[0])
    body = {"email": "a@b.co", "password_length": 4}
    codes = [client.post("/trap/t1/login", json=body).status_code for _ in range(allowed + 1)]
    assert codes == [204] * allowed + [429]


# --- sanitising and secrets -------------------------------------------------------------------


def test_clean_strips_control_characters_and_caps_length():
    assert traps.clean("a\r\nb\x07c\x00d") == "a  b c d"
    assert len(traps.clean("x" * 1000)) == 80
    assert len(traps.clean("x" * 1000, limit=10)) == 10


def test_visitor_text_cannot_inject_lines_into_the_push(client, make_trap, pushes):
    make_trap("t1")
    # HTTP forbids raw newlines in headers, so a tab stands in for "a control character".
    client.get("/trap/t1", headers={"User-Agent": "Evil\tBrowser/1.0"})
    for value in pushes[0][1].values():
        assert not any(ord(ch) < 32 for ch in value)


def test_password_never_appears_in_responses_logs_alerts_or_the_database(
    client, make_trap, pushes, caplog, engine, admin_headers
):
    from sqlalchemy import text

    caplog.set_level(logging.DEBUG)
    make_trap("t1")
    responses = [
        client.get("/trap/t1"),
        client.post("/trap/t1/login", json={"email": "v@example.com", "password": PASSWORD, "password_length": len(PASSWORD)}),
        client.get("/api/traps/alerts", headers=admin_headers),
    ]
    haystack = "".join(r.text for r in responses) + caplog.text + repr(pushes)
    with engine.connect() as conn:
        for table in ("alerts", "traps"):
            haystack += repr(conn.execute(text(f"SELECT * FROM {table}")).fetchall())

    assert PASSWORD not in haystack
    assert "test-honeytoken-secret" not in haystack and "test-admin-key" not in haystack
