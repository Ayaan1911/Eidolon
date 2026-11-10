"""Proves a slow database query does not freeze the event loop: while one request is stuck in a
1-second query, /health must still answer at once."""

import asyncio
import time

import httpx
import pytest
from sqlalchemy.orm import Session

import main

QUERY_SECONDS = 1.0
MAX_HEALTH_SECONDS = 0.5  # "well under" the 1-second query


def _slow_first_query(monkeypatch):
    real_query = Session.query
    slow_once = []
    monkeypatch.setattr(Session, "entered_at", [], raising=False)  # when the slow query began

    def slow_query(self, *args, **kwargs):
        if not slow_once:  # only the first query is slow; it sleeps in the worker thread running it
            slow_once.append(1)
            Session.entered_at.append(time.perf_counter())
            time.sleep(QUERY_SECONDS)
        return real_query(self, *args, **kwargs)

    monkeypatch.setattr(Session, "query", slow_query)


async def _health_latency_during(method, path, headers):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as c:
        slow = asyncio.create_task(c.request(method, path, headers=headers))
        while not Session.entered_at:  # wait until the slow query has started
            await asyncio.sleep(0.005)
        response = await c.get("/health")
        # Measured from when the query began: if the query had frozen the event loop, this
        # request could not even start until the whole second was over.
        elapsed = time.perf_counter() - Session.entered_at[0]
        assert response.status_code == 200
        assert (await slow).status_code < 300
        return elapsed


# One route that awaits things (async + run_in_threadpool) and one plain `def` route.
@pytest.mark.parametrize("method, path, needs_admin", [("GET", "/trap/t1", False), ("GET", "/api/traps/alerts", True)])
def test_health_answers_while_a_query_is_slow(monkeypatch, make_trap, admin_headers, method, path, needs_admin):
    make_trap("t1")
    _slow_first_query(monkeypatch)
    elapsed = asyncio.run(_health_latency_during(method, path, admin_headers if needs_admin else {}))
    print(f"/health took {elapsed:.3f}s while the query slept {QUERY_SECONDS}s ({path})")
    assert elapsed < MAX_HEALTH_SECONDS
