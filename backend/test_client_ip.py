"""get_client_ip: which address the app believes a request came from.

Run from backend/:  python -m pytest test_client_ip.py
"""

import pytest
from starlette.requests import Request

from services.client_ip import MAX_TRUSTED_PROXY_HOPS, get_client_ip, trusted_proxy_hops

PEER = "10.0.0.1"  # the socket's address: in production, the proxy


def make_request(forwarded_for: str | None = None, peer: str | None = PEER) -> Request:
    headers = [(b"x-forwarded-for", forwarded_for.encode())] if forwarded_for is not None else []
    scope = {"type": "http", "headers": headers, "client": (peer, 5000) if peer else None}
    return Request(scope)


@pytest.fixture
def hops(monkeypatch):
    def set_hops(n):
        monkeypatch.setenv("TRUSTED_PROXY_HOPS", str(n))

    return set_hops


def test_default_is_zero_hops_and_ignores_the_header(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert trusted_proxy_hops() == 0
    assert get_client_ip(make_request("6.6.6.6")) == PEER


def test_zero_hops_ignores_a_forged_header(hops):
    hops(0)
    assert get_client_ip(make_request("1.2.3.4, 5.6.7.8")) == PEER


def test_render_uses_edge_ip_not_forgeable_forwarded_chain(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    request = Request({"type": "http", "client": (PEER, 5000), "headers": [
        (b"x-forwarded-for", b"1.2.3.4, 5.6.7.8"),
        (b"cf-connecting-ip", b"203.0.113.7"),
    ]})
    assert get_client_ip(request) == "203.0.113.7"


def test_render_missing_or_invalid_edge_ip_falls_back_to_peer(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    assert get_client_ip(make_request("1.2.3.4")) == PEER
    request = Request({"type": "http", "client": (PEER, 5000), "headers": [
        (b"cf-connecting-ip", b"not-an-ip"),
    ]})
    assert get_client_ip(request) == PEER


def test_no_client_at_all_is_reported_as_unknown(hops):
    hops(0)
    assert get_client_ip(make_request(peer=None)) == "unknown"


def test_one_hop_takes_the_last_entry_not_a_forged_first_one(hops):
    hops(1)
    # The client sent "9.9.9.9"; our one proxy appended the address it actually saw.
    assert get_client_ip(make_request("9.9.9.9, 203.0.113.7")) == "203.0.113.7"


def test_one_hop_with_a_single_entry(hops):
    hops(1)
    assert get_client_ip(make_request("203.0.113.7")) == "203.0.113.7"


def test_two_hops_takes_the_second_from_the_right(hops):
    hops(2)
    # forged by client, real client (seen by proxy 1), proxy 1 (seen by proxy 2)
    assert get_client_ip(make_request("9.9.9.9, 203.0.113.7, 198.51.100.2")) == "203.0.113.7"


def test_forged_left_entries_never_win(hops):
    hops(2)
    assert get_client_ip(make_request("1.1.1.1, 2.2.2.2, 3.3.3.3, 203.0.113.7, 198.51.100.2")) == "203.0.113.7"


def test_header_shorter_than_hops_falls_back_to_the_peer(hops):
    hops(3)
    assert get_client_ip(make_request("203.0.113.7, 198.51.100.2")) == PEER


def test_missing_header_falls_back_to_the_peer(hops):
    hops(1)
    assert get_client_ip(make_request()) == PEER


@pytest.mark.parametrize("bad", ["", "not-an-ip", "999.1.1.1", "1.2.3", "1.2.3.4:80", " , ", "unknown"])
def test_malformed_chosen_entry_falls_back_to_the_peer(hops, bad):
    hops(1)
    assert get_client_ip(make_request(f"203.0.113.7, {bad}")) == PEER


def test_whitespace_around_entries_is_ignored(hops):
    hops(1)
    assert get_client_ip(make_request("9.9.9.9 ,   203.0.113.7  ")) == "203.0.113.7"


def test_ipv6_entry_is_accepted_and_normalised(hops):
    hops(1)
    assert get_client_ip(make_request("9.9.9.9, 2001:0DB8:0:0:0:0:0:1")) == "2001:db8::1"


@pytest.mark.parametrize("bad", ["abc", "-1", "1.5", str(MAX_TRUSTED_PROXY_HOPS + 1), "99"])
def test_invalid_hops_setting_is_rejected(monkeypatch, bad):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", bad)
    with pytest.raises(ValueError, match="TRUSTED_PROXY_HOPS"):
        trusted_proxy_hops()


def test_blank_hops_setting_means_zero(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", " ")
    assert trusted_proxy_hops() == 0


# --- the same rule drives rate limiting and the stored alert IP ------------------------------


def login(client, forged_for):
    return client.post("/api/admin/login", json={"passphrase": "wrong"}, headers={"X-Forwarded-For": forged_for})


def test_rate_limit_cannot_be_dodged_by_forging_the_header_at_zero_hops(client, hops):
    hops(0)
    codes = [login(client, f"198.51.100.{i}").status_code for i in range(7)]
    assert codes == [401] * 5 + [429] * 2


def test_rate_limit_buckets_follow_the_trusted_entry(client, hops):
    hops(1)
    # Forging the left side changes nothing: the last entry is what counts, so this is one visitor.
    codes = [login(client, f"198.51.100.{i}, 203.0.113.7").status_code for i in range(7)]
    assert codes == [401] * 5 + [429] * 2
    # A different real visitor (different last entry) has their own bucket.
    assert login(client, "198.51.100.1, 203.0.113.8").status_code == 401


def test_alert_stores_the_resolved_ip(client, hops, make_trap, session_factory):
    from database import Alert

    make_trap("t1")
    hops(1)
    client.get("/trap/t1", headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.7"})
    with session_factory() as db:
        assert db.query(Alert).one().ip == "203.0.113.7"


# --- the admin diagnostic ----------------------------------------------------------------------


def test_diagnostic_requires_admin(client):
    assert client.get("/api/admin/diagnostics/client-ip").status_code == 401
    assert client.get("/api/admin/diagnostics/client-ip", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_diagnostic_reports_what_the_server_sees(client, admin_headers, hops):
    hops(1)
    r = client.get(
        "/api/admin/diagnostics/client-ip",
        headers={**admin_headers, "X-Forwarded-For": "6.6.6.6, 203.0.113.7", "Via": "1.1 proxy", "X-Real-IP": "203.0.113.7"},
    )
    body = r.json()
    assert body["socket_peer"] == "testclient"
    assert body["trusted_proxy_hops"] == 1
    assert body["resolved_ip"] == "203.0.113.7"
    assert body["headers"] == {
        "x-forwarded-for": "6.6.6.6, 203.0.113.7",
        "x-real-ip": "203.0.113.7",
        "via": "1.1 proxy",
    }
    assert "authorization" not in body["headers"]  # the admin token is never echoed back
