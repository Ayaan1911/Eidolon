"""Placeholder-suppression heuristics: user==password, and the example/template/
sample-filename check. Plus a regression guard for the exact bug that started
this - the scanner flagging its own test fixtures when Eidolon's own GitHub
repo is a scan target.

Run from backend/:  python test_secret_scanner.py  (also collected by pytest)
"""

from services.secret_scanner import scan_text_for_secrets


def _fake_url(scheme: str, user: str, password: str, host: str) -> str:
    """Same reason as secret_scanner.py's own helper: this file is itself
    scanned when Eidolon's own repo is a target, so a "should still be
    flagged" fixture can't be a plain contiguous literal in this file either."""
    return scheme + "://" + user + ":" + password + "@" + host


# Real content from https://github.com/Ayaan1911/lumos - identical user/password,
# the exact false positive this heuristic exists for. Safe as plain literals: the
# user==password check suppresses these regardless of which file they sit in,
# including this one.
LUMOS_ENV_EXAMPLE = "\n".join(
    [
        "LUMOS_DATABASE_URL=postgresql://lumos:lumos@localhost:5432/lumos",
        "LUMOS_TEST_DATABASE_URL=postgresql://lumos:lumos@localhost:5433/lumos_test",
    ]
)
LUMOS_DOCKER_COMPOSE = "        postgresql://lumos:lumos@postgres:5432/lumos"


def test_lumos_env_example_is_clean():
    assert scan_text_for_secrets(LUMOS_ENV_EXAMPLE, path=".env.example") == []


def test_lumos_docker_compose_is_clean():
    # docker-compose.yml isn't an example/template-named file - this is caught
    # by the unconditional user==password rule, not the filename heuristic.
    assert scan_text_for_secrets(LUMOS_DOCKER_COMPOSE, path="docker/docker-compose.yml") == []


def test_user_equals_password_suppressed_regardless_of_filename():
    url = _fake_url("postgresql", "sameword", "sameword", "db.example.com:5432/app")
    assert scan_text_for_secrets(url, path="config.py") == []
    assert scan_text_for_secrets(url, path=".env.example") == []


def test_example_filename_only_suppresses_local_looking_hosts():
    local = _fake_url("postgresql", "dbuser", "Xk9mPqR2vNzT", "localhost:5432/app")
    bare_host = _fake_url("postgresql", "dbuser", "Xk9mPqR2vNzT", "postgres:5432/app")
    real = _fake_url("postgresql", "dbuser", "Xk9mPqR2vNzT", "db.actualcompany.com:5432/app")

    assert scan_text_for_secrets(local, path=".env.example") == []
    assert scan_text_for_secrets(bare_host, path="config.sample.yaml") == []
    # A real-looking external host still flags even inside an example file -
    # the filename heuristic narrows, it never blinds the scanner outright.
    assert scan_text_for_secrets(real, path=".env.example") != []


def test_example_filename_detection_is_word_bounded():
    from services.secret_scanner import _is_example_path

    assert _is_example_path(".env.example") is True
    assert _is_example_path("config/settings.template.py") is True
    assert _is_example_path("db.sample.yaml") is True
    assert _is_example_path(".env.dist") is True
    assert _is_example_path("resampler.py") is False  # substring, not a whole word
    assert _is_example_path("templates/index.html") is False  # a dir named templates, not the file


def test_same_content_outside_an_example_file_still_flags():
    local = _fake_url("postgresql", "dbuser", "Xk9mPqR2vNzT", "localhost:5432/app")
    assert scan_text_for_secrets(local, path="app/config.py") != []


def test_self_scan_does_not_flag_this_files_own_fixtures():
    """The exact original bug: Eidolon scanning its own GitHub repo found
    secret_scanner.py's demo fixtures and reported them as real findings."""
    with open("services/secret_scanner.py", encoding="utf-8") as f:
        own_source = f.read()
    assert scan_text_for_secrets(own_source, path="services/secret_scanner.py") == []

    with open(__file__, encoding="utf-8") as f:
        this_file = f.read()
    assert scan_text_for_secrets(this_file, path="test_secret_scanner.py") == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
