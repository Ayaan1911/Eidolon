"""Reject oversized request bodies before FastAPI can spool multipart uploads."""

import asyncio
import json

MAX_REQUEST_BYTES = 11 * 1024 * 1024
MAX_OTHER_REQUEST_BYTES = 64 * 1024
BODY_READ_TIMEOUT_SECONDS = 30
MAX_ACTIVE_PHOTO_READS = 4


class RequestBodyLimitMiddleware:
    def __init__(self, app, max_bytes=MAX_REQUEST_BYTES, read_timeout=BODY_READ_TIMEOUT_SECONDS):
        self.app = app
        self.max_bytes = max_bytes
        self.read_timeout = read_timeout
        self.active_photo_reads = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        photo = scope.get("path") == "/api/exposure/photo"
        limit = self.max_bytes if photo else min(self.max_bytes, MAX_OTHER_REQUEST_BYTES)
        lengths = [value for key, value in scope["headers"] if key.lower() == b"content-length"]
        if lengths and (len(lengths) != 1 or len(lengths[0]) > 20 or not lengths[0].isdigit()):
            return await self.error(send, 400, "Invalid Content-Length")
        if lengths and int(lengths[0]) > limit:
            return await self.error(send, 413, "Request body exceeds limit")
        if scope.get("method") in ("GET", "HEAD", "OPTIONS") and not lengths and not any(
            key.lower() == b"transfer-encoding" for key, _ in scope["headers"]
        ):
            return await self.app(scope, receive, send)
        if photo and self.active_photo_reads >= MAX_ACTIVE_PHOTO_READS:
            return await self.error(send, 503, "Server busy")
        if photo:
            self.active_photo_reads += 1
        body = bytearray()
        try:
            try:
                async with asyncio.timeout(self.read_timeout if photo else min(self.read_timeout, 5)):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > limit:
                            return await self.error(send, 413, "Request body exceeds limit")
                        body.extend(chunk)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await self.error(send, 408, "Request body timed out")
        finally:
            if photo:
                self.active_photo_reads -= 1
        pending = True

        async def replay():
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def error(self, send, status, detail):
        body = json.dumps({"detail": detail}).encode()
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
