"""Reject oversized request bodies before FastAPI can spool multipart uploads."""

import json

MAX_REQUEST_BYTES = 11 * 1024 * 1024


class RequestBodyLimitMiddleware:
    def __init__(self, app, max_bytes=MAX_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        lengths = [value for key, value in scope["headers"] if key.lower() == b"content-length"]
        if lengths and (len(lengths) != 1 or len(lengths[0]) > 20 or not lengths[0].isdigit()):
            return await self.error(send, 400, "Invalid Content-Length")
        if lengths and int(lengths[0]) > self.max_bytes:
            return await self.error(send, 413, "Request body exceeds limit")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                return await self.error(send, 413, "Request body exceeds limit")
            body.extend(chunk)
            if not message.get("more_body", False):
                break
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
