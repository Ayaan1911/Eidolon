"""Regression check: a non-ASCII trap name must not crash the ntfy alert.

Run from backend/:  python test_ntfy_alert.py  (also collected by pytest)
"""

import asyncio
import os

import httpx

from services import ntfy_alert


def test_non_ascii_title_survives_as_utf8():
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["title"] = next(v for k, v in request.headers.raw if k.lower() == b"title")
        return httpx.Response(200)

    real_client = httpx.AsyncClient
    ntfy_alert.httpx.AsyncClient = lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    os.environ["NTFY_TOPIC"] = "test-topic"
    title = "Trap 'Prod DB — “backup” 日本語' triggered"
    try:
        asyncio.run(ntfy_alert.send_ntfy_alert(title, {"IP": "1.2.3.4"}))
    finally:
        ntfy_alert.httpx.AsyncClient = real_client

    assert sent["title"] == title.encode("utf-8")


if __name__ == "__main__":
    test_non_ascii_title_survives_as_utf8()
    print("ok")
