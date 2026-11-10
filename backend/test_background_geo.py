"""The trap page answers the visitor first; geolocation, the location update and the push happen after.

TestClient waits for background work before returning, so the timing tests talk to the app through
raw ASGI calls and watch the moment the response is sent.
"""

import asyncio
import json
import logging
import time

import pytest

import main
from database import Alert, Trap
from routers import traps

LOOKUP_SECONDS = 2
GEO = {"city": "Ashburn", "country": "United States", "lat": 1.0, "lon": 2.0, "isp": "Example Broadband"}


class Call:
    """One raw ASGI request. `responded` is set when the response body has been sent, while the
    app may still be running background work; `finished` when it has completely returned."""

    def __init__(self, path, method="GET", body=b""):
        self.sent = []
        self.responded = asyncio.Event()
        self.started = time.perf_counter()
        self.response_seconds = None
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
            "client": ("203.0.113.9", 4321),
        }
        pending = [{"type": "http.request", "body": body, "more_body": False}]
        never = asyncio.Event()

        async def receive():
            if pending:
                return pending.pop()
            await never.wait()

        async def send(message):
            self.sent.append(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                self.response_seconds = time.perf_counter() - self.started
                self.responded.set()

        self.finished = asyncio.create_task(main.app(scope, receive, send))

    @property
    def status(self):
        return self.sent[0]["status"]

    @property
    def body(self):
        return b"".join(m.get("body", b"") for m in self.sent[1:])


@pytest.fixture
def pushes(monkeypatch):
    sent = []

    async def record(title, fields):
        sent.append((title, fields))

    monkeypatch.setattr(traps, "send_ntfy_alert", record)
    return sent


def slow_lookup(monkeypatch, result=GEO, seconds=LOOKUP_SECONDS):
    async def lookup(ip):
        await asyncio.sleep(seconds)
        if isinstance(result, Exception):
            raise result
        return dict(result)

    monkeypatch.setattr(traps, "lookup_ip", lookup)


def alerts(session_factory):
    with session_factory() as db:
        return db.query(Alert).order_by(Alert.id).all()


def test_page_answers_before_the_slow_lookup_and_the_push_follows_with_the_location(
    monkeypatch, make_trap, pushes, session_factory
):
    make_trap("t1", name="Prod DB")
    slow_lookup(monkeypatch)

    async def scenario():
        call = Call("/trap/t1")
        await call.responded.wait()
        # --- the visitor already has their answer; the lookup (2 s) is still running ---
        assert call.response_seconds < 0.5
        rows = alerts(session_factory)
        assert len(rows) == 1 and rows[0].location == "Unknown, Unknown"  # the hit exists immediately
        with session_factory() as db:
            assert db.query(Trap).one().trigger_count == 1
        assert pushes == []
        await call.finished
        return call

    call = asyncio.run(scenario())
    print(f"trap page answered in {call.response_seconds:.3f}s with a {LOOKUP_SECONDS}s lookup")
    assert call.status == 200 and b"<" in call.body
    assert [a.location for a in alerts(session_factory)] == ["Ashburn, United States"]  # filled in afterwards
    ((title, fields),) = pushes
    assert title == "Trap 'Prod DB' triggered"
    assert fields["Location"] == "Ashburn, United States" and fields["ISP"] == "Example Broadband"


@pytest.mark.parametrize("result", [RuntimeError("boom"), {}], ids=["lookup raises", "lookup times out"])
def test_failed_lookup_still_pushes_without_a_location_and_the_response_is_unchanged(
    client, monkeypatch, make_trap, pushes, session_factory, caplog, result
):
    make_trap("t1")
    normal = client.get("/trap/t1")  # a normal (stubbed, successful) hit to compare against
    pushes.clear()
    traps._last_alert_at.clear()
    slow_lookup(monkeypatch, result=result, seconds=0)
    caplog.set_level(logging.INFO)

    r = client.get("/trap/t1")
    assert r.status_code == 200 and r.text == normal.text
    ((_, fields),) = pushes
    assert "Location" not in fields and "ISP" not in fields and fields["IP"] == "testclient"
    assert alerts(session_factory)[-1].location == "Unknown, Unknown"
    if isinstance(result, Exception):
        assert "RuntimeError" in caplog.text and "boom" not in caplog.text


def test_second_hit_inside_the_window_is_recorded_without_a_push(client, make_trap, pushes, session_factory):
    make_trap("t1")
    client.get("/trap/t1")
    client.get("/trap/t1")
    assert len(alerts(session_factory)) == 2 and len(pushes) == 1


def test_a_hit_during_the_first_ones_lookup_does_not_push_again(monkeypatch, make_trap, pushes, session_factory):
    make_trap("t1")
    slow_lookup(monkeypatch, seconds=0.2)

    async def scenario():
        # The second hit arrives while the first one's lookup is still running in the background. (One at a
        # time through the database: the test's in-memory SQLite shares a single connection.)
        first = Call("/trap/t1")
        await first.responded.wait()
        second = Call("/trap/t1")
        await asyncio.gather(first.finished, second.finished)

    asyncio.run(scenario())
    assert len(alerts(session_factory)) == 2 and len(pushes) == 1


def test_unknown_id_has_no_row_no_lookup_and_no_push(client, monkeypatch, pushes, session_factory):
    seen = []

    async def lookup(ip):
        seen.append(ip)
        return {}

    monkeypatch.setattr(traps, "lookup_ip", lookup)
    assert client.get("/trap/nope").status_code == 200
    assert client.post("/trap/nope/login", json={"email": "", "password_length": 0}).status_code == 204
    assert alerts(session_factory) == [] and seen == [] and pushes == []


def test_failing_push_is_logged_and_does_not_crash(client, monkeypatch, make_trap, session_factory, caplog):
    make_trap("t1")

    async def broken(title, fields):
        raise RuntimeError("ntfy exploded")

    monkeypatch.setattr(traps, "send_ntfy_alert", broken)
    r = client.get("/trap/t1")
    assert r.status_code == 200 and len(alerts(session_factory)) == 1
    assert "push step failed: RuntimeError" in caplog.text and "ntfy exploded" not in caplog.text


def test_login_hit_is_stored_at_once_and_located_afterwards(monkeypatch, make_trap, pushes, session_factory):
    make_trap("t1")
    slow_lookup(monkeypatch)
    payload = json.dumps({"email": "a@example.com", "password_length": 5}).encode()

    async def scenario():
        call = Call("/trap/t1/login", method="POST", body=payload)
        await call.responded.wait()
        assert call.response_seconds < 0.5 and call.status == 204
        assert alerts(session_factory)[0].location == "Unknown, Unknown"
        await call.finished

    asyncio.run(scenario())
    (row,) = alerts(session_factory)
    assert row.location == "Ashburn, United States" and row.email == "a@example.com" and row.password_length == 5
    assert pushes == []  # login submissions never push
