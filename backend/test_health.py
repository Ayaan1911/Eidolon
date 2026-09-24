"""/health reports the deployed commit, so a fix going live can be checked
directly (curl /health) instead of via the Render dashboard.

Run from backend/:  python test_health.py  (also collected by pytest)
"""

import os

os.environ["ADMIN_KEY"] = "test-admin-key"
os.environ["HONEYTOKEN_SECRET"] = "test-honeytoken-secret"

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_health_reports_unknown_commit_when_render_var_is_unset():
    os.environ.pop("RENDER_GIT_COMMIT", None)
    body = client.get("/health").json()
    assert body == {"status": "ok", "commit": "unknown"}


def test_health_reports_the_short_commit_when_render_sets_it():
    # Render's actual value is the full 40-char SHA - only the short form is useful here.
    os.environ["RENDER_GIT_COMMIT"] = "17675db73e489fd4f7c7573bc3fe711ee5bb28a8"
    try:
        body = client.get("/health").json()
        assert body == {"status": "ok", "commit": "17675db"}
    finally:
        os.environ.pop("RENDER_GIT_COMMIT", None)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
