from datetime import datetime, timedelta, timezone

from database import Alert, utc_iso


def test_naive_value_is_treated_as_utc():
    assert utc_iso(datetime(2026, 11, 8, 12, 0, 0)) == "2026-11-08T12:00:00Z"


def test_aware_non_utc_value_is_converted_to_utc():
    india = timezone(timedelta(hours=5, minutes=30))
    assert utc_iso(datetime(2026, 11, 8, 17, 30, 0, tzinfo=india)) == "2026-11-08T12:00:00Z"


def test_value_already_in_utc_keeps_its_time():
    assert utc_iso(datetime(2026, 11, 8, 12, 0, 0, 123456, tzinfo=timezone.utc)) == "2026-11-08T12:00:00.123456Z"


def test_alerts_endpoint_marks_times_as_utc(client, admin_headers, session_factory, make_trap):
    trap_id = make_trap()
    with session_factory() as db:  # SQLite hands this back naive
        db.add(Alert(
                trap_id=trap_id, ip="203.0.113.1", location="x", latitude=0.0, longitude=0.0, isp="x",
                browser="x", os="x", device="x", timestamp=datetime(2026, 11, 8, 12, 0, 0),
            ))
        db.commit()
    rows = client.get("/api/traps/alerts", headers=admin_headers).json()
    assert rows[0]["timestamp"] == "2026-11-08T12:00:00Z"
