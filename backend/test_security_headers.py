"""Exercise response protections without sockets or external services."""

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

import main
from services.security_headers import SecurityHeadersMiddleware

BACKEND_DIR = Path(__file__).resolve().parent


def run_immediate(coroutine):
    # These ASGI stubs never suspend; no event loop or loopback socket is needed.
    try:
        coroutine.send(None)
    except StopIteration:
        return
    finally:
        coroutine.close()
    raise AssertionError("Unexpected asynchronous work in the in-memory stub")


@pytest.mark.parametrize("status", [200, 401, 413, 429, 500])
def test_protection_headers_preserve_success_and_error_responses(status):
    sent = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"), (b"x-frame-options", b"SAMEORIGIN"),
            (b"x-request-id", b"test-request"),
        ]})
        await send({"type": "http.response.body", "body": b'{"detail":"unchanged"}'})

    async def send(message):
        sent.append(message)

    run_immediate(SecurityHeadersMiddleware(app, production=True)({"type": "http"}, None, send))
    headers = dict(sent[0]["headers"])
    assert sent[0]["status"] == status
    assert sent[1]["body"] == b'{"detail":"unchanged"}'
    assert headers[b"content-type"] == b"application/json"
    assert headers[b"x-request-id"] == b"test-request"
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert headers[b"x-frame-options"] == b"DENY"
    assert headers[b"referrer-policy"] == b"no-referrer"
    assert headers[b"permissions-policy"] == b"camera=(), microphone=(), geolocation=()"
    assert headers[b"strict-transport-security"] == b"max-age=31536000"
    assert b"frame-ancestors 'none'" in headers[b"content-security-policy"]


def test_decoy_script_is_allowed_by_hash_without_allowing_other_inline_scripts():
    middleware = SecurityHeadersMiddleware(None, production=True)
    policy = middleware.headers["Content-Security-Policy"]
    template = (BACKEND_DIR / "templates" / "fake_login.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", template, re.DOTALL)
    assert len(scripts) == 1
    digest = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    directives = dict(part.strip().split(" ", 1) for part in policy.split(";"))
    assert directives["script-src"] == f"'sha256-{digest}'"
    assert directives["connect-src"] == "'self'"  # the form's JSON POST still works
    assert directives["form-action"] == "'none'"  # native form submissions stay blocked


def test_dev_docs_are_not_blocked_by_production_script_or_https_policy():
    headers = SecurityHeadersMiddleware(None, production=False).headers
    assert "Content-Security-Policy" not in headers
    assert "Strict-Transport-Security" not in headers


def test_non_http_scopes_pass_through_unchanged():
    scope = {"type": "websocket"}
    seen = []

    async def app(incoming, receive, send):
        seen.append(incoming)

    run_immediate(SecurityHeadersMiddleware(app, production=True)(scope, None, None))
    assert seen == [scope]


@pytest.mark.parametrize("preflight", [False, True])
def test_actual_app_protects_body_limit_and_cors_rejections(preflight):
    sent = []
    headers = [(b"content-length", b"99999999")]
    if preflight:
        headers = [(b"origin", b"https://untrusted.example"), (b"access-control-request-method", b"POST")]
    scope = {"type": "http", "method": "OPTIONS" if preflight else "POST",
             "path": "/api/exposure/photo", "headers": headers, "query_string": b"",
             "scheme": "http", "server": ("localhost", 80), "client": ("127.0.0.1", 1234)}

    async def receive():
        raise AssertionError("Rejected requests must not read the body")

    async def send(message):
        sent.append(message)

    run_immediate(main.app(scope, receive, send))
    assert sent[0]["status"] == (400 if preflight else 413)
    assert dict(sent[0]["headers"])[b"x-frame-options"] == b"DENY"
    assert b"x-request-id" in dict(sent[0]["headers"])


def test_fastapi_unhandled_errors_also_receive_security_headers():
    api = FastAPI()
    sent = []

    @api.get("/crash")
    async def crash():
        raise RuntimeError("test failure")

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "GET", "path": "/crash", "headers": [],
             "query_string": b"", "scheme": "http"}
    with pytest.raises(RuntimeError, match="test failure"):
        run_immediate(SecurityHeadersMiddleware(api, production=True)(scope, None, send))
    assert sent[0]["status"] == 500
    assert dict(sent[0]["headers"])[b"x-content-type-options"] == b"nosniff"


@pytest.mark.parametrize("mode", ["dev", "production", "", "Dev"])
def test_only_explicit_dev_mode_exposes_documentation(mode, tmp_path):
    # A fresh import exercises the actual app construction. No database connection
    # is made: the URL and secrets are local test placeholders, never user config.
    env = dict(os.environ)
    env.update(
        EIDOLON_ENV=mode,
        DATABASE_URL="postgresql://test:test@localhost/unused",
        ADMIN_KEY="test-admin-passphrase",
        HONEYTOKEN_SECRET="test-honeytoken-signing-secret",
        PUBLIC_BASE_URL="https://api.example.invalid",
        TRUSTED_PROXY_HOPS="0",
        LOG_LEVEL="INFO",
        PYTHON_DOTENV_DISABLED="1",
        PYTHONPATH=str(BACKEND_DIR),
    )
    script = (
        "import json; import main; "
        "print(json.dumps({'paths':[getattr(route,'path',None) for route in main.app.routes], "
        "'schema':main.app.openapi_url}))"
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout.splitlines()[-1])
    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        assert (path in config["paths"]) == (mode == "dev")
    assert config["schema"] == ("/openapi.json" if mode == "dev" else None)
