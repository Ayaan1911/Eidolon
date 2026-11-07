"""Every route that mints a key or creates/deploys/deletes a trap needs the admin session.

Run from backend/:  python -m pytest test_mint_routes.py
"""

import pytest

from services import honeytoken

BODY_TRAP = {"name": "canary"}
BODY_FINDING = {"repo": "octocat/leaky-repo", "file": "config/prod.env", "type": "AWS Access Key"}

# (method, path, json body)
GATED = [
    ("POST", "/api/traps/honeytoken", None),
    ("POST", "/api/findings/abc123/deploy-decoy", None),
    ("POST", "/api/traps", BODY_TRAP),
    ("POST", "/api/findings/abc123/deploy-trap", BODY_FINDING),
    ("DELETE", "/api/traps/whatever", None),
    ("GET", "/api/traps/alerts", None),
]


def call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers)


@pytest.mark.parametrize("method,path,body", GATED)
def test_missing_credentials_are_rejected(client, method, path, body):
    assert call(client, method, path, body).status_code == 401


@pytest.mark.parametrize("method,path,body", GATED)
@pytest.mark.parametrize(
    "authorization",
    ["Bearer junk", "Bearer ", "Basic abc", "eidolon_admin_1.deadbeef"],
    ids=["junk", "empty", "wrong-scheme", "no-scheme"],
)
def test_wrong_credentials_are_rejected(client, method, path, body, authorization):
    assert call(client, method, path, body, {"Authorization": authorization}).status_code == 401


@pytest.mark.parametrize("method,path,body", GATED)
def test_a_decoy_key_is_not_admin_credentials(client, method, path, body):
    decoy = honeytoken.generate_token()
    assert call(client, method, path, body, {"Authorization": f"Bearer {decoy}"}).status_code == 401
    assert call(client, method, path, body, {"X-API-Key": decoy}).status_code == 401


def test_admin_can_mint_a_decoy_key(client, admin_headers):
    r = client.post("/api/traps/honeytoken", headers=admin_headers)
    assert r.status_code == 200
    assert honeytoken.is_valid_token(r.json()["token"])


def test_admin_can_deploy_a_decoy_for_a_finding(client, admin_headers):
    r = client.post("/api/findings/abc123/deploy-decoy", headers=admin_headers)
    assert r.status_code == 200
    assert "abc123" in r.json()["token"]  # the finding id travels inside the token
    assert honeytoken.is_valid_token(r.json()["token"])


def test_admin_can_create_a_trap(client, admin_headers):
    r = client.post("/api/traps", json=BODY_TRAP, headers=admin_headers)
    assert r.status_code == 200 and "/trap/" in r.json()["trap_url"]


def test_unauthenticated_calls_leave_no_trap_rows(client, session_factory):
    from database import Trap

    client.post("/api/traps", json=BODY_TRAP)
    client.post("/api/findings/abc123/deploy-trap", json=BODY_FINDING)
    with session_factory() as db:
        assert db.query(Trap).count() == 0


def test_decoy_verify_route_stays_public_but_is_rate_limited(client):
    from routers.traps import VERIFY_LIMIT

    allowed = int(VERIFY_LIMIT.split("/")[0])
    codes = [client.get("/api/internal/verify").status_code for _ in range(allowed + 1)]
    assert codes == [401] * allowed + [429]
