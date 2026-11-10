import pytest
from fastapi.testclient import TestClient

import main
from services.public_url import PublicBaseUrlError, configured_base_url
from services.startup_checks import check_public_base_url


def trap_url(client, admin_headers, base="http://testserver"):
    r = TestClient(main.app, base_url=base).post("/api/traps", json={"name": "t"}, headers=admin_headers)
    return r.json()["trap_url"]


def test_unset_forces_https_on_the_request_host(client, admin_headers):
    assert trap_url(client, admin_headers, "http://api.example.com").startswith("https://api.example.com/trap/")


@pytest.mark.parametrize("base", ["http://localhost:8000", "http://127.0.0.1:8000", "http://dev.localhost:8000"])
def test_unset_keeps_http_on_localhost(client, admin_headers, base):
    assert trap_url(client, admin_headers, base).startswith(base + "/trap/")


def test_set_value_is_used_as_the_base(monkeypatch, client, admin_headers):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://eidolon.example.com/")
    assert trap_url(client, admin_headers, "http://internal:10000").startswith("https://eidolon.example.com/trap/")


def test_decoy_base_url_uses_the_same_helper(client, admin_headers):
    r = TestClient(main.app, base_url="http://api.example.com").post("/api/traps/honeytoken", headers=admin_headers)
    assert r.json()["base_url"] == "https://api.example.com"


@pytest.mark.parametrize("ok", ["https://a.example.com", "https://a.example.com/", "http://localhost:8000", "http://127.0.0.1"])
def test_valid_values(monkeypatch, ok):
    monkeypatch.setenv("PUBLIC_BASE_URL", ok)
    assert configured_base_url() == ok.rstrip("/")


@pytest.mark.parametrize(
    "bad",
    ["http://a.example.com", "ftp://a.example.com", "https://a.example.com/path", "https://a.example.com?x=1",
     "https://user:pw@a.example.com", "a.example.com", "https://:8000", "https://a.example.com:notaport"],
)
def test_invalid_values_stop_startup_without_echoing_the_value(monkeypatch, bad):
    monkeypatch.setenv("PUBLIC_BASE_URL", bad)
    with pytest.raises(PublicBaseUrlError) as e:
        check_public_base_url()
    assert bad not in str(e.value)


def test_unset_is_fine():
    assert configured_base_url() is None
