"""Finding-linked traps: the deploy-trap endpoint, and trap status attached to
GitHub secret-scan findings.

Run from backend/:  python test_finding_traps.py  (also collected by pytest)
Uses an in-memory DB and a stubbed scanner, so no network and no eidolon.db.
"""

import os

os.environ["ADMIN_KEY"] = "test-admin-key"
os.environ["HONEYTOKEN_SECRET"] = "test-honeytoken-secret"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from database import Alert, Base, Trap, get_db
from routers import exposure
from services import admin_auth
from services.github_scanner import _finding_id

_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)


def _get_test_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


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


async def _fake_scan(username):
    return _SCAN_RESULT


exposure.scan_user_repos = _fake_scan
main.app.dependency_overrides[get_db] = _get_test_db
client = TestClient(main.app)


def admin_header():
    token, _ = admin_auth.issue_token()
    return {"Authorization": f"Bearer {token}"}


def scan():
    return client.post("/api/exposure/repos", json={"username": "octocat"})


def test_finding_id_is_stable_across_rescans():
    assert _finding_id("o/r", "a.py", 3, "AWS Access Key") == _finding_id("o/r", "a.py", 3, "AWS Access Key")
    assert _finding_id("o/r", "a.py", 3, "AWS Access Key") != _finding_id("o/r", "b.py", 3, "AWS Access Key")


def test_deploy_trap_requires_admin():
    body = {"repo": "octocat/leaky-repo", "file": "config/prod.env", "type": "AWS Access Key"}
    assert client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=body).status_code == 401


def test_deploy_trap_creates_a_named_trap_linked_to_the_finding():
    body = {"repo": "octocat/leaky-repo", "file": "config/prod.env", "type": "AWS Access Key"}
    r = client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=body, headers=admin_header())
    assert r.status_code == 200
    data = r.json()
    assert "/trap/" in data["trap_url"]

    with _Session() as db:
        trap = db.query(Trap).filter(Trap.finding_id == FINDING_ID).one()
        assert trap.id == data["id"]
        assert trap.source_type == "secret"
        assert "octocat/leaky-repo" in trap.name and "AWS Access Key" in trap.name


def test_deploy_trap_is_idempotent():
    body = {"repo": "octocat/leaky-repo", "file": "config/prod.env", "type": "AWS Access Key"}
    first = client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=body, headers=admin_header()).json()
    second = client.post(f"/api/findings/{FINDING_ID}/deploy-trap", json=body, headers=admin_header()).json()
    assert first == second
    with _Session() as db:
        assert db.query(Trap).filter(Trap.finding_id == FINDING_ID).count() == 1


def test_public_scan_never_reveals_trap_status():
    # No auth header at all - this is the ordinary public Mirror tool path.
    r = scan()
    assert r.status_code == 200
    finding = r.json()["results"][0]["findings"][0]
    assert finding["trap"] is None
    assert "trap_url" not in str(finding)


def test_admin_scan_shows_deployed_trap_status():
    r = client.post("/api/exposure/repos", json={"username": "octocat"}, headers=admin_header())
    finding = r.json()["results"][0]["findings"][0]
    assert finding["trap"] is not None
    assert finding["trap"]["hit_count"] == 0
    assert "/trap/" in finding["trap"]["trap_url"]


def test_hit_count_reflects_real_trap_triggers():
    with _Session() as db:
        trap = db.query(Trap).filter(Trap.finding_id == FINDING_ID).one()
        client.get(f"/trap/{trap.id}")
        client.get(f"/trap/{trap.id}")
    r = client.post("/api/exposure/repos", json={"username": "octocat"}, headers=admin_header())
    assert r.json()["results"][0]["findings"][0]["trap"]["hit_count"] == 2


def test_undeployed_finding_shows_no_trap_even_to_admin():
    other_id = _finding_id("octocat/other-repo", "b.py", 1, "Stripe Secret Key")
    with _Session() as db:
        assert db.query(Trap).filter(Trap.finding_id == other_id).first() is None


def test_delete_trap_requires_admin():
    with _Session() as db:
        trap_id = db.query(Trap).filter(Trap.finding_id == FINDING_ID).one().id
    assert client.delete(f"/api/traps/{trap_id}").status_code == 401


def test_delete_trap_removes_it_and_its_alerts():
    with _Session() as db:
        trap_id = db.query(Trap).filter(Trap.finding_id == FINDING_ID).one().id
        assert db.query(Alert).filter(Alert.trap_id == trap_id).count() == 2  # from the hit-count test above

    assert client.delete(f"/api/traps/{trap_id}", headers=admin_header()).status_code == 204

    with _Session() as db:
        assert db.query(Trap).filter(Trap.id == trap_id).first() is None
        assert db.query(Alert).filter(Alert.trap_id == trap_id).count() == 0

    # No trap left to find, so the finding reads as undeployed again.
    r = client.post("/api/exposure/repos", json={"username": "octocat"}, headers=admin_header())
    assert r.json()["results"][0]["findings"][0]["trap"] is None


def test_delete_trap_404s_for_an_unknown_id():
    assert client.delete("/api/traps/doesnotexist", headers=admin_header()).status_code == 404


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
