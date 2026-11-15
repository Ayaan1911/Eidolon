"""Browser protections for API responses and the static decoy login page."""

import base64
import hashlib
import re
from pathlib import Path

from starlette.datastructures import MutableHeaders


class SecurityHeadersMiddleware:
    def __init__(self, app, production: bool):
        self.app = app
        self.headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
        if production:
            template = Path(__file__).resolve().parents[1] / "templates" / "fake_login.html"
            # The deployed template is static. Hash its scripts so the decoy form works
            # without allowing arbitrary inline JavaScript. read_text normalizes CRLF.
            scripts = re.findall(r"<script>(.*?)</script>", template.read_text(encoding="utf-8"), re.DOTALL)
            sources = " ".join(
                "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
                for script in scripts
            ) or "'none'"
            self.headers.update({
                "Strict-Transport-Security": "max-age=31536000",
                "Content-Security-Policy": (
                    "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                    "form-action 'none'; connect-src 'self'; style-src 'unsafe-inline'; "
                    f"script-src {sources}"
                ),
            })

    def __getattr__(self, name):
        # Preserve FastAPI's route/configuration API for tooling and existing tests.
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).update(self.headers)
            await send(message)

        await self.app(scope, receive, send_with_headers)
