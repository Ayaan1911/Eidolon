"""In-memory ASGI tests also runnable with unittest, without network or third-party imports."""

import asyncio
import unittest
from pathlib import Path

from services.body_limit import MAX_REQUEST_BYTES, RequestBodyLimitMiddleware


def run_immediate(coroutine):
    return asyncio.run(coroutine)


class BodyLimitTests(unittest.TestCase):
    def invoke(self, chunks, headers=(), disconnect=False, max_bytes=8):
        requests = [{"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
                    for i, chunk in enumerate(chunks)]
        if disconnect:
            requests = [{"type": "http.disconnect"}]
        reads, parsed, sent = [], [], []

        async def receive():
            reads.append(1)
            return requests.pop(0)

        async def send(message):
            sent.append(message)

        async def app(scope, receive, send):
            parsed.append((await receive())["body"])
            await send({"type": "http.response.start", "status": 204, "headers": []})

        run_immediate(RequestBodyLimitMiddleware(app, max_bytes)({"type": "http", "headers": list(headers)}, receive, send))
        return reads, parsed, sent

    def test_declared_oversize_is_rejected_without_reading(self):
        reads, parsed, sent = self.invoke([], [(b"content-length", b"9")])
        self.assertEqual((reads, parsed, sent[0]["status"]), ([], [], 413))

    def test_chunked_multipart_is_rejected_before_parser(self):
        _, parsed, sent = self.invoke([b"--bound", b"ary"], [(b"content-type", b"multipart/form-data; boundary=boundary")])
        self.assertEqual((parsed, sent[0]["status"]), ([], 413))

    def test_understated_length_does_not_bypass_cap(self):
        _, parsed, sent = self.invoke([b"1234", b"56789"], [(b"content-length", b"1")])
        self.assertEqual((parsed, sent[0]["status"]), ([], 413))

    def test_exact_limit_is_replayed_unchanged(self):
        _, parsed, sent = self.invoke([b"1234", b"5678"])
        self.assertEqual((parsed, sent[0]["status"]), ([b"12345678"], 204))

    def test_invalid_or_duplicate_lengths_are_rejected(self):
        for headers in ([(b"content-length", b"-1")], [(b"content-length", b"1")] * 2,
                        [(b"content-length", b"9" * 5000)]):
            _, parsed, sent = self.invoke([], headers)
            self.assertEqual((parsed, sent[0]["status"]), ([], 400))

    def test_disconnect_has_no_side_effects(self):
        _, parsed, sent = self.invoke([], disconnect=True)
        self.assertEqual((parsed, sent), ([], []))

    def test_empty_chunks_are_not_accumulated_as_messages(self):
        _, parsed, sent = self.invoke([b""] * 1000 + [b"ok"])
        self.assertEqual((parsed, sent[0]["status"]), ([b"ok"], 204))

    def test_stalled_body_times_out_before_parser(self):
        parsed, sent = [], []

        async def receive():
            await asyncio.Future()

        async def send(message):
            sent.append(message)

        async def app(scope, receive, send):
            parsed.append(True)

        run_immediate(RequestBodyLimitMiddleware(app, read_timeout=0.01)(
            {"type": "http", "headers": []}, receive, send,
        ))
        self.assertEqual((parsed, sent[0]["status"]), ([], 408))

    def test_stalled_uploads_leave_capacity_for_health(self):
        async def check():
            release = asyncio.Event()
            sent = []

            async def stalled_receive():
                await release.wait()
                return {"type": "http.request", "body": b"ok", "more_body": False}

            async def unused_receive():
                raise AssertionError("Health requests should not wait for a body")

            async def send(message):
                sent.append(message)

            async def app(scope, receive, send):
                await send({"type": "http.response.start", "status": 204, "headers": []})

            middleware = RequestBodyLimitMiddleware(app)
            post = {"type": "http", "method": "POST", "path": "/api/exposure/photo", "headers": []}
            tasks = [asyncio.create_task(middleware(post, stalled_receive, send)) for _ in range(4)]
            await asyncio.sleep(0)
            self.assertEqual(middleware.active_photo_reads, 4)
            await middleware(post, stalled_receive, send)
            self.assertEqual(sent[-2]["status"], 503)
            await middleware({"type": "http", "method": "GET", "path": "/health", "headers": []}, unused_receive, send)
            self.assertEqual(sent[-1]["status"], 204)
            async def admin_receive():
                return {"type": "http.request", "body": b"{}", "more_body": False}
            await middleware({"type": "http", "method": "POST", "path": "/api/admin/login", "headers": []}, admin_receive, send)
            self.assertEqual(sent[-1]["status"], 204)
            release.set()
            await asyncio.gather(*tasks)
            self.assertEqual(middleware.active_photo_reads, 0)

        asyncio.run(check())

    def test_nonphoto_requests_have_a_smaller_limit(self):
        _, parsed, sent = self.invoke([], [(b"content-length", b"65537")], max_bytes=MAX_REQUEST_BYTES)
        self.assertEqual((parsed, sent[0]["status"]), ([], 413))

    def test_deploy_command_does_not_reject_health_before_middleware(self):
        render = Path(__file__).resolve().parents[1] / "render.yaml"
        self.assertNotIn("--limit-concurrency", render.read_text())


if __name__ == "__main__":
    unittest.main()
