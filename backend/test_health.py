"""/health reports the deployed commit, so a fix going live can be checked
directly (curl /health) instead of via the Render dashboard.

Run from backend/:  python -m pytest test_health.py
"""


def test_health_reports_unknown_commit_when_render_var_is_unset(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "commit": "unknown"}


def test_health_reports_the_short_commit_when_render_sets_it(client, monkeypatch):
    # Render's actual value is the full 40-char SHA - only the short form is useful here.
    monkeypatch.setenv("RENDER_GIT_COMMIT", "17675db73e489fd4f7c7573bc3fe711ee5bb28a8")
    body = client.get("/health").json()
    assert body == {"status": "ok", "commit": "17675db"}
