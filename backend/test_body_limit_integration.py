from services.body_limit import MAX_REQUEST_BYTES


def test_oversized_multipart_rejected_before_form_parser(client, monkeypatch):
    async def unexpected_parser(*args, **kwargs):
        raise AssertionError("Multipart parsing ran before the total body limit")

    monkeypatch.setattr("starlette.requests.Request._get_form", unexpected_parser)
    response = client.post("/api/exposure/photo", content=b"", headers={
        "content-type": "multipart/form-data; boundary=test", "content-length": str(MAX_REQUEST_BYTES + 1),
    })
    assert response.status_code == 413
    assert response.headers.get("x-request-id")
