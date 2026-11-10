import json
import logging

import pytest
from fastapi.testclient import TestClient

import main
from services.logging_setup import (
    LogConfigError,
    configure_logging,
    log_level,
    mask_ip,
    new_request_id,
)
from services.startup_checks import check_log_level
from test_db_config import import_main


@pytest.fixture
def start_json_logging(monkeypatch):
    """Returns a function that switches on production-style (JSON) logging; the old setup is put back after.
    It is called inside the test body because pytest resets the root logger's level after fixture setup."""
    root = logging.getLogger()
    saved = root.handlers[:], root.level

    def start():
        monkeypatch.delenv("EIDOLON_ENV", raising=False)
        configure_logging()

    yield start
    root.handlers[:], root.level = saved


def last_json_line(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_json_line_has_the_required_keys(capsys, start_json_logging):
    start_json_logging()
    logging.getLogger("eidolon.test").info("hello %s", "world", extra={"trap": "t1"})
    entry = last_json_line(capsys)
    assert {"timestamp", "level", "logger", "message", "request_id", "trap"} <= entry.keys()
    assert entry["timestamp"].endswith("Z") and entry["level"] == "INFO"
    assert entry["logger"] == "eidolon.test" and entry["message"] == "hello world" and entry["trap"] == "t1"


def test_info_shows_by_default_and_log_level_filters(capsys, start_json_logging, monkeypatch):
    start_json_logging()
    logging.getLogger("eidolon.test").info("visible")
    assert "visible" in capsys.readouterr().out
    monkeypatch.setenv("LOG_LEVEL", "warning")
    configure_logging()
    logging.getLogger("eidolon.test").info("hidden")
    assert "hidden" not in capsys.readouterr().out


def test_dev_format_is_plain_text(monkeypatch, capsys):
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    monkeypatch.setenv("EIDOLON_ENV", "dev")
    configure_logging()
    logging.getLogger("eidolon.test").info("plain")
    out = capsys.readouterr().out
    root.handlers[:], root.level = saved
    assert "plain" in out and not out.startswith("{")


def test_invalid_log_level_stops_startup_without_echoing_it(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_LEVEL", "banana-level")
    with pytest.raises(LogConfigError) as e:
        check_log_level()
    assert "banana-level" not in str(e.value)
    result = import_main(tmp_path, LOG_LEVEL="banana-level", EIDOLON_ENV="dev")  # and a real start refuses too
    assert result.returncode != 0 and "LogConfigError" in result.stderr
    assert "banana-level" not in result.stderr + result.stdout


def test_default_log_level_is_info():
    assert log_level() == "INFO"


@pytest.mark.parametrize("hostile", ["x" * 65, "a b", "id\r\nSet-Cookie: x=1", "<script>", "../etc", ""])
def test_hostile_request_id_is_replaced(hostile):
    rid = new_request_id(hostile)
    assert rid != hostile and len(rid) == 36  # a generated UUID4


def test_good_request_id_is_kept():
    assert new_request_id("abc-123-DEF") == "abc-123-DEF"


def test_response_carries_a_request_id(client):
    assert client.get("/health", headers={"X-Request-ID": "trace-1"}).headers["x-request-id"] == "trace-1"
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) == 36
    assert client.get("/health", headers={"X-Request-ID": "bad id!"}).headers["x-request-id"] != "bad id!"


def test_log_lines_inside_a_request_carry_its_id(capsys, start_json_logging):
    start_json_logging()
    @main.app.get("/_log_probe")
    def probe():
        logging.getLogger("eidolon.test").info("inside")
        return {}

    try:
        TestClient(main.app).get("/_log_probe", headers={"X-Request-ID": "req-42"})
    finally:
        main.app.router.routes.pop()
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert [e["request_id"] for e in lines if e["message"] == "inside"] == ["req-42"]


@pytest.mark.parametrize(
    "ip, masked",
    [
        ("203.0.113.77", "203.0.113.xxx"),
        ("2001:db8:abcd:12:34:56:78:9a", "2001:0db8:abcd::xxx"),
        ("::1", "0000:0000:0000::xxx"),
        ("not an ip", "unknown"),
    ],
)
def test_ips_are_masked(ip, masked):
    assert mask_ip(ip) == masked


def test_access_log_line_masks_the_visitor_ip(capsys, start_json_logging):
    start_json_logging()
    logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "203.0.113.77:51234", "GET", "/health", "1.1", 200)
    out = capsys.readouterr().out
    assert "203.0.113.xxx" in out and "203.0.113.77" not in out and "51234" not in out


def test_secrets_never_reach_the_output(capsys, start_json_logging):
    start_json_logging()
    fake_db = "postgresql://appuser:Sup3rSecretPw@db-host.invalid/app?sslmode=require"
    fake_token = "Bearer abc.DEF-123_ghijkl"
    log = logging.getLogger("eidolon.test")
    log.warning("db %s", fake_db)
    log.warning("header %s", fake_token)
    log.warning("secret %s and again", "test-honeytoken-secret", extra={"detail": "test-honeytoken-secret"})
    try:
        raise RuntimeError(fake_db)
    except RuntimeError:
        log.exception("failed")
    out = capsys.readouterr().out
    for leaked in ("Sup3rSecretPw", "db-host.invalid", "abc.DEF-123_ghijkl", "test-honeytoken-secret", "test-admin-key"):
        assert leaked not in out
    assert out.count("[redacted]") >= 5
