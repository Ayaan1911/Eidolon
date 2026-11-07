"""Finding-linked traps: the deploy-trap endpoint, and trap status attached to
GitHub secret-scan findings.

Run from backend/:  python -m pytest test_finding_traps.py
The scanner is stubbed, so no network. Every test starts with an empty database.
"""

import pytest

from database import Alert, Trap
from routers import exposure
from services.github_scanner import _finding_id

_SCAN_RESULT = {
    "username": "octocat",
    "repos_scanned": 1,
    "total_findings": 1,
    "results": [
        {
            "repo": "octocat/leaky-repo",
            "findings": [
                {
                    "id": _finding_id("octocat/leaky-repo", "config/prod.env", 12, "AWS Access Key"),
                    "file": "config/prod.env",
                    "line": 12,
                    "type": "AWS Access Key",
                    "masked_value": "AKIA...MPLE",
                    "severity": "CRITICAL",
                }
            ],
        }
    ],
    "incomplete": False,
    "incomplete_reason": None,
}
FINDING_ID = _SCAN_RESULT["results"][0]["findings"][0]["id"]
BODY = {"repo": "octocat/leaky-repo", "file": "config/prod.env", "type": "AWS Access Key"}


@pytest.fixture(autouse=True)
def _stub_scanner(monkeypatch):
    async def fake_scan(username):
        return _SCAN_RESULT

    monkeypatch.setattr(exposure, "scan_user_repos", fake_scan)


@pytest.fixture
def deployed_trap_id(client, admin_headers):
    r = client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=BODY, headers=admin_headers)
    assert r.status_code == 200
    return r.json()["id"]


def scan(client, headers=None):
    return client.post("/api/exposure/repos", json={"username": "octocat"}, headers=headers)


def test_finding_id_is_stable_across_rescans():
    assert _finding_id("o/r", "a.py", 3, "AWS Access Key") == _finding_id("o/r", "a.py", 3, "AWS Access Key")
    assert _finding_id("o/r", "a.py", 3, "AWS Access Key") != _finding_id("o/r", "b.py", 3, "AWS Access Key")


def test_deploy_trap_requires_admin(client):
    assert client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=BODY).status_code == 401


def test_deploy_trap_creates_a_named_trap_linked_to_the_finding(client, admin_headers, session_factory):
    r = client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=BODY, headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "/trap/" in data["trap_url"]

    with session_factory() as db:
        trap = db.query(Trap).filter(Trap.finding_id == FINDING_ID).one()
        assert trap.id == data["id"]
        assert trap.source_type == "secret"
        assert "octocat/leaky-repo" in trap.name and "AWS Access Key" in trap.name


def test_deploy_trap_is_idempotent(client, admin_headers, session_factory):
    first = client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=BODY, headers=admin_headers).json()
    second = client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=BODY, headers=admin_headers).json()
    assert first == second
    with session_factory() as db:
        assert db.query(Trap).filter(Trap.finding_id == FINDING_ID).count() == 1


def test_public_scan_never_reveals_trap_status(client, deployed_trap_id):
    # A trap exists, but with no auth header at all (the ordinary public Mirror tool
    # path) the scan must say nothing about it.
    r = scan(client)
    assert r.status_code == 200
    finding = r.json()["results"][0]["findings"][0]
    assert finding["trap"] is None
    assert "trap_url" not in str(finding)


def test_admin_scan_shows_deployed_trap_status(client, admin_headers, deployed_trap_id):
    finding = scan(client, admin_headers).json()["results"][0]["findings"][0]
    assert finding["trap"] is not None
    assert finding["trap"]["hit_count"] == 0
    assert "/trap/" in finding["trap"]["trap_url"]


def test_hit_count_reflects_real_trap_triggers(client, admin_headers, deployed_trap_id):
    client.get(f"/trap/{deployed_trap_id}")
    client.get(f"/trap/{deployed_trap_id}")
    finding = scan(client, admin_headers).json()["results"][0]["findings"][0]
    assert finding["trap"]["hit_count"] == 2


def test_undeployed_finding_shows_no_trap_even_to_admin(client, admin_headers, session_factory):
    other_id = _finding_id("octocat/other-repo", "b.py", 1, "Stripe Secret Key")
    with session_factory() as db:
        assert db.query(Trap).filter(Trap.finding_id == other_id).first() is None
    assert scan(client, admin_headers).json()["results"][0]["findings"][0]["trap"] is None


def test_delete_trap_requires_admin(client, deployed_trap_id):
    assert client.delete(f"/api/traps/{deployed_trap_id}").status_code == 401


def test_delete_trap_removes_it_and_its_alerts(client, admin_headers, session_factory, deployed_trap_id):
    client.get(f"/trap/{deployed_trap_id}")
    client.get(f"/trap/{deployed_trap_id}")
    with session_factory() as db:
        assert db.query(Alert).filter(Alert.trap_id == deployed_trap_id).count() == 2

    assert client.delete(f"/api/traps/{deployed_trap_id}", headers=admin_headers).status_code == 204

    with session_factory() as db:
        assert db.query(Trap).filter(Trap.id == deployed_trap_id).first() is None
        assert db.query(Alert).filter(Alert.trap_id == deployed_trap_id).count() == 0

    # No trap left to find, so the finding reads as undeployed again.
    assert scan(client, admin_headers).json()["results"][0]["findings"][0]["trap"] is None


def test_delete_trap_404s_for_an_unknown_id(client, admin_headers):
    assert client.delete("/api/traps/doesnotexist", headers=admin_headers).status_code == 404
