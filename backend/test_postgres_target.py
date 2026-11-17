"""The destructive suite must not inherit an app's production connection."""

import pytest

from test_postgres import validate_test_target


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
@pytest.mark.parametrize("database", ["eidolon_ci", "eidolon_test"])
def test_explicit_disposable_loopback_target_is_allowed(host, database):
    raw = f"postgresql://test:test@{host}/{database}"
    assert validate_test_target(raw) == raw


@pytest.mark.parametrize("raw", [
    "postgresql://test:private-value@production.example/neondb?sslmode=require",
    "postgresql://test:private-value@localhost/neondb",
    "postgresql://test:private-value@localhost/eidolon_ci?host=production.example",
    "postgresql://test:private-value@localhost/eidolon_ci?dbname=neondb",
    "postgresql://test:private-value@/eidolon_ci",
    "sqlite:///eidolon_ci",
    "not a URL private-value",
    "",
])
def test_unsafe_targets_are_rejected_without_echoing_credentials(raw):
    with pytest.raises(pytest.UsageError) as error:
        validate_test_target(raw)
    assert "private-value" not in str(error.value)
    assert "delete data" in str(error.value)
