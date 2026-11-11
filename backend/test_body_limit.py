"""In-memory ASGI tests also runnable with unittest, without network or third-party imports."""

import unittest

from services.body_limit import RequestBodyLimitMiddleware


def run_immediate(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coroutine.close()
    raise AssertionError("In-memory ASGI stubs unexpectedly suspended")


class BodyLimitTests(unittest.TestCase):
    def invoke(self, chunks, headers=(), disconnect=False):
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

        run_immediate(RequestBodyLimitMiddleware(app, 8)({"type": "http", "headers": list(headers)}, receive, send))
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


if __name__ == "__main__":
    unittest.main()
