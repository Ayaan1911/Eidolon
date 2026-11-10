# Eidolon — learning notes

## Checklist

- [x] Pass 0 — verification (done: `docs/audit/pass-0-verification.md`)
- [x] Pass 1 — ReDoS hotfix (done on `fix/audit-pass-1`; 500 KB line now 0.046 s, `/health` stays under 1 s during a scan)
- [x] Pass 2 — test isolation and pinned dependencies (done on `fix/audit-pass-1`: 181 tests, pinned `requirements*.txt`)
- [x] Pass 3 — CI (done: CI green, PR #1 merged)
- [x] Pass 4a — trust boundary (done on `pass-4-trust-boundary`: client IP helper, fail-closed secrets, gated mint routes, hardened trap routes)
- [x] Pass 5 — Postgres on Neon with Alembic (done and verified in production: traps and hits survive redeploys, ntfy alerts arrive)
- [x] Pass 5b — five fixes: UTC timestamps, https links, atomic counter, event loop, CI on 3.14 (done and verified in production)
- [ ] Pass 6 — Docker and Compose
- [x] Pass 7 — logging, readiness and background geolocation (done on `pass-7-logging-readiness`, pending review)
- [ ] Pass 8 — Mirror honesty fixes
- [ ] Pass 9 — README and threat model
- [ ] Pass 10 — differentiator

## Pass 0 revision note

**What was verified.** Every audit claim was re-checked against `main` (`4426d5b`, unchanged since the old audit) and `fix/audit-pass-1`, in throwaway worktrees with fresh venvs and temp databases. Production got 7 read-only GET/OPTIONS requests.

**What was found.**
- The "Password in URL" regex is *quadratic*: 10/20/40/80 KB of letters took 0.1/0.4/1.6/13.9 s. A real scan of an 80 KB-line file froze the whole server for ~15 s on `main`; the fix branch keeps it responsive.
- Tests: `main` = 44 tests, 6 fail in file order (8 in random order) because tests share state; `fix/audit-pass-1` = 140 pass every time. Honeytoken verification is 58% covered on both.
- Blank `ADMIN_KEY`/`HONEYTOKEN_SECRET` are accepted at boot, and an admin token forged with an empty key was accepted locally.
- Unknown trap IDs create alert rows; trap, mint and verify routes have no rate limit; mint routes need no admin.
- Production predates `main` (no `commit` in `/health`), has `/docs` open, no security headers, and rejects foreign CORS origins.
- Not verifiable from the repo: the production start command, so why a forged `X-Forwarded-For` was trusted there is still open.

**Key concepts.**
- *Catastrophic backtracking*: a backtracking regex engine retries alternative splits when a match fails. Unbounded quantifiers that can all match the same characters (`[a-z]*` then `[^\s/:@]+`) make the retry count grow with input length — here quadratically, in nastier patterns exponentially. Fix: bound the quantifiers or use a linear-time engine.
- *Event-loop blocking*: an async server runs many requests on one thread; a CPU-bound call that never `await`s freezes all of them. Python's `re` holds the GIL, so a worker thread does not rescue a bad regex.
- *Trusting proxy headers*: behind a proxy the TCP peer is the proxy, so the client IP comes from `X-Forwarded-For`. Anyone can send that header; only trust it when it was appended by a proxy you control (trusted hops / allow-list), and take the right-most untrusted entry.
- *Ephemeral disks*: Render's free web service filesystem is wiped on restart, redeploy and idle spin-down, so a SQLite file there loses data. Use a managed database or a persistent disk.

**Likely interview questions.**
1. *What is ReDoS and how would you fix one?* — A regex whose match time explodes on crafted input because of backtracking. Bound the quantifiers, remove overlapping alternatives, cap input length, or use a linear engine like RE2; test with adversarial inputs.
2. *Why does one slow request hurt every user on an async server?* — One event loop thread serves all requests; blocking work stops it from running anything else. Move CPU work to a process pool, or make it fast.
3. *How do you get the real client IP behind a proxy safely?* — Read `X-Forwarded-For` only from trusted proxies, count trusted hops from the right, and fall back to the socket peer otherwise; never let a client-supplied header set a rate-limit key.

**Mistakes to avoid.**
- Trusting a self-reported header or a "blank = unset" env var (fail open instead of fail closed).
- Testing only the happy path of a regex: always add an adversarial 100 KB input.
- Believing a green test run means isolated tests: run in random order.
- Reading a single timing as a growth law: measure at several sizes.
- Auditing from an old clone or a dashboard you can't see; record "unverified" instead of guessing.

## Revision note — finishing `fix/audit-pass-1` (pinned deps, network guard, weak-module tests, CI)

**What changed and why.** Pass 0 found the fix branch unfinished. This pass: pinned every dependency to the version that passed the tests; added a guard that makes any real network call from a test fail; added 39 behavior tests for the four least-tested modules; rewrote the CI workflow (ruff, coverage floor, cache key); and added a `ruff.toml`. Tests went from 140 to 181; app-code coverage from 78% to 92%.

| Module | Coverage before | After |
|---|---|---|
| `breach_check.py` | 20% | 94% |
| `geolocation.py` | 27% | 100% |
| `honeytoken.py` | 58% | 100% |
| `photo_metadata.py` | 26% | 100% |
| overall (app code) | 78% | 92% |

### Key concepts

**Pinned requirements.** `backend/requirements.txt` now reads:

```
fastapi==0.162.2
uvicorn[standard]==0.54.0
pydantic[email]==2.14.3
```

`==` means "exactly this version". Before, `fastapi` alone meant "whatever is newest today", so two deploys a week apart could run different code. Pinning protects against a surprise upgrade breaking (or compromising) a deploy, and makes "it passed on my machine" mean the same thing as "it passed in CI". Trade-offs: you stop getting security fixes automatically, so you must bump versions on purpose; and only *direct* dependencies are pinned here — their own dependencies (starlette, for example) can still move unless you add a lock file. `requirements-dev.txt` starts with `-r requirements.txt`, so the test tools sit on top of the exact runtime set.

**Test isolation: `conftest.py`.** pytest runs the fixtures in this file for every test. Two of them:

```python
@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", ADMIN_KEY)
    monkeypatch.setenv("HONEYTOKEN_SECRET", HONEYTOKEN_SECRET)
```

`autouse=True` means no test has to ask for it. `monkeypatch` changes the environment for one test and puts it back afterwards, so tests cannot leak settings into each other.

```python
def guard(real):
    def wrapper(self, address):
        if not is_loopback(address):
            raise RuntimeError(f"Test tried a real network connection to {address!r}; mock it")
        return real(self, address)
    return wrapper
monkeypatch.setattr(socket.socket, "connect", guard(real_connect))
```

This is the network guard: it replaces `socket.connect` so that any connection to a non-loopback address raises. Loopback stays allowed because the Windows event loop talks to itself over `127.0.0.1`. Result: a forgotten mock fails loudly instead of quietly calling the internet. (No existing test was secretly using the network — the 140 passed unchanged.)

**One of the new tests (geolocation).**

```python
def test_failed_lookup_still_serves_the_page_and_logs_the_hit(...):
    mock_ip_api(monkeypatch, handler)
    r = client.get("/trap/t1")
    assert r.status_code == 200
    a = last_alert(session_factory)
    assert (a.location, a.isp) == ("Unknown, Unknown", "Unknown")
```

`mock_ip_api` swaps `httpx.AsyncClient` for one backed by `httpx.MockTransport`, a fake server inside the process. The test is run six times (parametrized) with different failures: an API "fail" body, 429, 500, connect timeout, read timeout, connect error. I checked these tests are real by breaking the code on purpose (changing `except httpx.HTTPError` to a different exception): 7 tests failed. The same trick on the honeytoken compare, the photo hemisphere sign and the breach error handling failed 5, 1 and 4 tests.

**The CI workflow, line by line** (`.github/workflows/ci.yml`):

- `on: push:` and `pull_request:` — run on every push to any branch and on every PR.
- `permissions: contents: read` — the job's token can only read the repo, the safest default.
- `jobs: backend:` / `runs-on: ubuntu-latest` — a fresh Linux VM for each run.
- `defaults.run.working-directory: backend` — every `run:` step starts in `backend/`.
- `actions/checkout@v4` — downloads the repo.
- `actions/setup-python@v5` with `python-version: "3.11"` — installs Python; `cache: pip` plus `cache-dependency-path` (both requirements files) reuses downloaded packages when those files did not change. Both files are listed because the dev file only *includes* the runtime one.
- `pip install -r requirements-dev.txt` — the pinned runtime + test tools.
- `ruff check .` — static check; rules come from `backend/ruff.toml` (pyflakes + the serious pycodestyle errors).
- `python -m pytest --cov=... --cov-fail-under=89` — runs the tests (in random order, because pytest-randomly is installed) and fails the job if coverage of app code drops below 89%, which is 3 points under the measured 92%. No secrets: `conftest.py` provides dummy values.
- `frontend:` job — `setup-node` 22, `npm ci` (exact lockfile install), `npm run lint` (oxlint exits 0 on warnings, so the 2 known warnings don't fail it), `npm run build` with a dummy `VITE_API_BASE`.

**What coverage measures — and cannot prove.** Coverage counts which lines ran during the tests. It cannot tell whether the tests *checked* anything: a test that calls a function and asserts nothing still colours the lines green. Two defences used here: assert real outcomes, and mutation-check (break the code, see tests fail). Lines that ran can still be wrong for inputs you never tried, and missing lines (breach_check 17, 32, 42) show what is untested, not that 94% is "safe".

**Why mocks, and the risk of over-mocking.** Tests must be fast, repeatable and offline, and you cannot make ip-api time out on demand — a mock can. The risk: a mock only returns what you told it to. If the real API changes its response shape, your mocked tests stay green while production breaks. Mitigations: keep mocks shaped like real responses, mock at the lowest layer (HTTP transport, not your own functions), and keep a few real checks outside CI.

### Likely interview questions

1. *What does pinning dependencies protect you from, and what does it cost?* — It stops an unreviewed upgrade changing your deploy, and makes builds reproducible. It costs you automatic security patches, so you need a routine (Dependabot or a monthly bump) and ideally a lock file for transitive packages.
2. *Is 92% coverage good?* — It is a floor-raising number, not proof of quality. Lines running is not behavior being verified; I check that tests fail when the code is deliberately broken, and I set the CI floor a few points under the measured value so it catches regressions without causing noise.
3. *How do you test code that calls external APIs?* — Replace the HTTP layer with a fake transport, cover success, error status, timeout and malformed responses, and block real network access in the test suite so nothing depends on the internet.

### Mistakes to avoid

- Writing a test that cannot fail (no assertion on behavior) just to colour lines.
- Mocking your own function instead of the HTTP boundary, which hides bugs in the glue code.
- Pinning once and never bumping.
- Declaring CI "done" before seeing it green on GitHub (still open here).
- Setting a coverage floor equal to today's number: any small refactor then fails the build.

### Follow-ups found (not fixed in this pass)

- Ruff's own default rule set reports 13 findings, none of them unused imports/variables: import ordering (`database.py`, `main.py`, `test_scanner_regex_safety.py`: I001), FastAPI `Depends()`/`File()` in argument defaults (B008, the normal FastAPI idiom, 8 hits in `routers/`), `datetime.utcnow()` (DTZ003, `routers/traps.py:199`), one string join (FLY002, `test_secret_scanner.py:25`). `backend/ruff.toml` narrows the check to pyflakes + serious errors so CI is green; revisit when adding formatting rules.
- `check_email_exposure` puts the upstream error text (which includes the request URL with the email) into the 502 `detail`; a non-JSON ip-api reply would, by reading the code, raise an uncaught `ValueError` in `lookup_ip` (unverified; not tested because the test would pin a bug).
- Python version is still not pinned in the repo.

## Revision note — Pass 4a: trust boundary

**What changed and why.** Pass 0 showed that the app believed whatever a visitor told it. This pass makes four changes:

1. One function, `get_client_ip`, decides the visitor's IP, and it never takes the leftmost `X-Forwarded-For` entry.
2. The app refuses to start with weak or blank secrets, and admin sessions use a separately derived signing key.
3. The routes that mint decoy keys or create/deploy traps now require the admin session.
4. Trap routes check the id first and do nothing for an invalid one; valid hits push to ntfy at most once per trap per 5 minutes; every trap route has a per-IP rate limit.

Tests: 181 → 293. App-code coverage 92% → 93%.

### Key concepts

**Trusting proxy headers, and reading `X-Forwarded-For` from the right.** Behind Render's proxy the TCP peer is the proxy, so the visitor's address arrives in a header. Anyone can send that header. Each proxy *appends* what it saw on the right, so the left side may be forged and the right side is what our own proxies wrote:

```python
entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",")]
if len(entries) < hops:
    return peer  # fewer proxies than expected: the header is not what we were told to trust
chosen = entries[-hops]  # 1 = the last entry, 2 = the one before it, ...
```

`TRUSTED_PROXY_HOPS` (default 0) is how many proxies we own. With 0 the header is ignored. Every fallback returns the socket peer, never a guess. The old start command (`--proxy-headers --forwarded-allow-ips=*`) is worse than any of this: uvicorn rewrites `request.client.host` itself from the leftmost entry before our code runs, so the start command has to change (README, "Deploying").

**Fail-closed configuration.** The old code accepted a blank `ADMIN_KEY`, which is a valid (empty) HMAC key, so a forged admin token verified. Now:

```python
if os.environ.get(DEV_ENV_VAR) == "dev":
    return
problems = [p for name, minimum in _REQUIRED.items() if (p := _problem(name, minimum))]
if problems:
    raise InsecureConfigError("Refusing to start: " + "; ".join(problems) + ...)
```

"Fail closed" means that when something is missing or wrong, the safe outcome (not starting) happens by default, and being insecure needs an explicit opt-in (`EIDOLON_ENV=dev`). The error names the variable and its length, never the value, because error messages end up in logs.

**Key separation and constant-time comparison.**

```python
def _signing_key() -> bytes:
    ...
    return hmac.new(honeytoken_secret.encode(), SIGNING_KEY_LABEL + b":" + admin_key.encode(), hashlib.sha256).digest()
```

Admin tokens were already signed with `HONEYTOKEN_SECRET`, the same key that signs the public decoy keys, with the passphrase placed inside the message. Now the signing key is derived from both secrets with a fixed label (`eidolon/admin-session/v1`), so one key never serves two jobs and rotating either secret revokes all sessions. The task suggested deriving the key from `ADMIN_KEY` alone; I did not, because a human-chosen passphrase can be guessed offline from a captured token, while `HONEYTOKEN_SECRET` is random. Comparisons use `hmac.compare_digest`, which takes the same time wherever the first difference is; the passphrase is hashed first so even its length does not leak:

```python
return hmac.compare_digest(hashlib.sha256(candidate.encode()).digest(), hashlib.sha256(expected.encode()).digest())
```

**Validate before side effects.** Previously `/trap/{any-id}` wrote a database row, called ip-api and pushed to ntfy before anything checked the id. Now:

```python
trap = db.query(Trap).filter(Trap.id == trap_id).first()
if not trap:
    log.info("trap page requested for an unknown id %r", clean(trap_id))
    return _page()
```

The visitor sees the same page, so nothing reveals which ids exist, but the attacker pays for nothing and we spend nothing. Order matters: cheapest, side-effect-free check first; expensive or irreversible actions last.

**Alert deduplication and the limits of in-memory state.**

```python
def should_alert(key: str) -> bool:
    now = time.monotonic()
    last = _last_alert_at.get(key)
    if last is not None and now - last < ALERT_WINDOW_SECONDS:
        return False
    _last_alert_at[key] = now
    return True
```

Repeat hits are still saved and counted; only the phone push is throttled, so one visitor refreshing the page cannot flood ntfy. The dictionary lives in process memory, so it resets on restart and each web worker would have its own copy. Acceptable here (worst case: one extra push); it would not be for anything that must be exact. `time.monotonic()` is used instead of wall-clock time so clock changes cannot break the window.

**Sanitising visitor text.** Headers like `User-Agent` are controlled by the visitor. Before they go into a log line or the ntfy body, `clean()` replaces control characters (newlines included) and caps the length, so nobody can forge extra log lines or alert fields.

### Likely interview questions

1. *Why take `X-Forwarded-For` from the right?* — Each proxy appends the address it saw to the right end, so the left side is whatever the client sent and can be forged. You count the number of proxies you own from the right, and fall back to the socket address if the header does not fit that shape.
2. *What does "fail closed" mean, and where did you apply it?* — When config is missing or invalid, deny or refuse by default instead of running in a weaker mode. The app now won't start with blank, short or placeholder secrets, and a blank key can't sign or verify admin tokens even in dev mode.
3. *Why check the id before logging or calling external services?* — Unauthenticated requests should not be able to cause writes, paid/third-party calls or notifications. Validate cheaply first, so invalid traffic costs almost nothing and reveals nothing.

### Mistakes to avoid

- Reading the leftmost `X-Forwarded-For` entry, or trusting the header with no idea how many proxies are in front.
- Changing the code but not the start command: uvicorn's own `--proxy-headers` rewrites the address first.
- A blank secret treated as "set" (an empty HMAC key still produces valid signatures).
- Putting a secret's value in an error message or log.
- Using one key for two purposes (public decoy keys and admin sessions).
- Tests that pass only because an id they use happens not to exist: unknown trap ids now do nothing, so those tests had to create a real trap.

### Left unfixed (found along the way)

- `/trap/{id}` and `/trap/{id}/login` still do synchronous database calls inside async handlers, and the geolocation lookup still runs before the response (up to 5 s).
- INFO logs are not shown yet: no logging is configured, so only warnings and errors reach the console (Pass 7).
- The Dossier "decoy" button still sends the in-memory counter instead of the finding hash (Pass 8).
- Admin sessions issued before this deploy stop working (the signing key changed); log in again.

## Revision note — Pass 5: Postgres on Neon with Alembic

**What changed and why.** Traps and hits lived in a SQLite file on Render's free disk, which is wiped on every redeploy and spin-down, and the schema was changed by a hand-written `ALTER TABLE` helper. Now:

- The app reads one `DATABASE_URL` (`backend/db_config.py`), uses Postgres in production, and refuses to start if it is missing outside `EIDOLON_ENV=dev`, or points at a remote host without SSL.
- The engine has a small pool, `pool_pre_ping`, `pool_recycle` and a connect timeout, tuned for Neon suspending idle databases.
- Alembic owns the schema (`backend/migrations/`). `create_all` and the `ALTER TABLE` helper are gone. The deploy command runs `alembic upgrade head` first.
- Old hits are deleted at startup (`RETENTION_DAYS`, default 90, at most 5000 rows per start).
- CI got a Postgres job.

Tests: 293 → 350 passed (+3 skipped locally; they run in the CI Postgres job). App-code coverage 94%. **The Postgres checks have not been seen to pass**: there is no Postgres on this machine and running one from a third-party package was not allowed, so the first real run is the CI `postgres` job.

### Key concepts

**Ephemeral disk vs managed database.** A container's disk belongs to that one container; when Render rebuilds or restarts it, the disk is new. A managed database (Neon) is a separate service that keeps its own storage, so the app can be thrown away and rebuilt without losing data. The guard against ever going back is fail-closed config:

```python
if not raw:
    if _is_dev():
        return SQLITE_DEV_URL
    raise DatabaseConfigError(f"{DATABASE_URL_ENV} is not set. Refusing to start without a database ...")
```

SQLite is only reachable by explicitly saying `EIDOLON_ENV=dev`. Remote hosts must also encrypt:

```python
if sslmode not in SSL_MODES:   # {"require", "verify-ca", "verify-full"}
    raise DatabaseConfigError(f"{DATABASE_URL_ENV} points at a remote host without SSL. ...")
```

The messages never contain the URL, because the URL holds the password. The parser's own exception is dropped (`raise ... from None`) since it can quote the URL, and a test feeds URLs with a recognisable password and host and asserts no piece appears in any message or startup traceback.

**Connection pooling, and why `pool_pre_ping` matters when a database scales to zero.** Opening a database connection is slow, so the app keeps a few open and lends them out (a pool). Neon pauses an idle database after 5 minutes; any connection that was open before then is dead, but the pool does not know. Without a check, the first request afterwards fails. With it:

```python
return create_engine(url, pool_size=3, max_overflow=2, pool_recycle=300,
                     pool_pre_ping=True, connect_args={"connect_timeout": 10})
```

`pool_pre_ping` sends a trivial query before handing out a connection and replaces it if dead; `pool_recycle=300` retires connections before Neon would; `connect_timeout=10` stops a waking database from hanging a request forever; the small pool respects the free plan's connection limit.

**Schema migrations, upgrade, downgrade and the version table.** A migration is a numbered script that moves the database schema one step; Alembic records which step the database is on in a one-row table, `alembic_version`. `upgrade head` runs every step not yet applied; running it again does nothing. `downgrade` runs the undo half. Our baseline:

```python
def upgrade() -> None:
    op.create_table("traps", ..., sa.PrimaryKeyConstraint("id", name="pk_traps"))
    op.create_index("ix_traps_finding_id", "traps", ["finding_id"])
    ...
def downgrade() -> None:
    op.drop_index("ix_alerts_timestamp", table_name="alerts")
    ...
```

Why not `create_all`? It only creates missing tables and never changes existing ones, so any schema change needed a hand-written `ALTER TABLE`. Migrations make every change explicit, reviewable and repeatable on any database. `migrations/env.py` takes the URL from the same function as the app (`database_url()`), never from `alembic.ini`, so a password can't end up in a file.

**Migration-drift testing.** Models and migrations are two descriptions of the same schema, and they can disagree if someone edits a model and forgets the migration. The test asks Alembic to compare them:

```python
command.upgrade(alembic_config(), "head")
context = MigrationContext.configure(connection, opts={"compare_type": True})
assert compare_metadata(context, Base.metadata) == []
```

An empty list means no difference. I checked it by adding a column to a model without a migration: the test failed. The same test runs against real Postgres in CI, and the test suite itself builds its databases with the migrations, so tests exercise the real schema.

**Data retention.** A log table that only grows eventually becomes a cost and a privacy liability (it stores visitor IPs). `delete_old_alerts` deletes hits older than `RETENTION_DAYS`, in a bounded batch so a huge backlog can't delay startup:

```python
old_ids = [row.id for row in db.query(Alert.id).filter(Alert.timestamp < cutoff)
           .order_by(Alert.timestamp).limit(MAX_DELETED_PER_RUN)]
db.query(Alert).filter(Alert.id.in_(old_ids)).delete(synchronize_session=False)
```

It selects ids first and then deletes them because `DELETE ... LIMIT` isn't portable between SQLite and Postgres. Traps are never deleted, and only the count is logged.

**Timestamps.** Columns are now `DateTime(timezone=True)` with an aware UTC default. Postgres returns aware values and SQLite naive ones, but the API must not change, so `_naive_utc_iso` converts back to the old format (UTC, no offset) before sending.

### Likely interview questions

1. *Why use migrations instead of `create_all`?* — `create_all` can only create what's missing; it can't alter or version anything. Migrations give an ordered, reviewable history of schema changes, an `alembic_version` record of where each database is, and a way to undo a step.
2. *What does `pool_pre_ping` do and when do you need it?* — It tests a pooled connection with a cheap query before use and replaces it if it died. You need it whenever connections can go stale silently: a database that suspends when idle (Neon), a restarted database, or a firewall that drops idle connections.
3. *How do you stop a configuration mistake from sending production data to the wrong place?* — Make the unsafe state impossible by default: refuse to start without `DATABASE_URL` unless an explicit dev flag is set, require SSL for remote hosts, and never print the URL in errors. Fail at startup, loudly, rather than limping on with a local disk.

### Mistakes to avoid

- Importing code that connects to a database at import time (I did this once with a placeholder host: `create_all` ran at import and tried a real connection; use `.invalid` hostnames in examples and keep import side-effect free).
- Putting the database URL in a config file such as `alembic.ini`, or printing it in an error.
- Using Neon's pooled connection string with migrations and session-level features; use the direct one.
- Editing a model without a migration (the drift test exists for this), or editing a migration that has already run on production instead of adding a new one.
- Assuming SQLite behaviour carries over: concurrent writers, time zones and booleans differ on Postgres, which is why CI runs a real Postgres.

### Left unfixed (found along the way)

- Every route is `async def` but uses the blocking SQLAlchemy session. With SQLite that cost microseconds; with Neon each query is a network round trip, and during it the whole event loop waits. Next candidates: make the DB-touching routes plain `def`, or move to an async driver.
- `trap.trigger_count += 1` is a read-modify-write; two simultaneous hits can lose one count on Postgres. The fix is a single `UPDATE ... SET trigger_count = trigger_count + 1`.
- The frontend parses the API's offset-less timestamps as local time (`new Date("2026-11-08T12:00:00")`), so the log clock can be off by the viewer's UTC offset.
- Database errors that reach the logs can name the host and user (the driver includes them); the password is never included.
- INFO-level logs (the retention count) are not visible until logging is configured (Pass 7).

## Pass 5b revision note — five small fixes

**What changed and why.** Production testing of Pass 5 found five defects; this pass fixes those and nothing else.

1. *Timestamps.* The API sent `2026-11-08T12:00:00` (no offset) and the browser read it as local time, so the clock was off by the viewer's UTC offset (5.5 h in India). One helper, `utc_iso`, now produces `2026-11-08T12:00:00Z` everywhere (alerts list, the honeytoken push).
2. *https links.* Render's proxy hides the original scheme (`--no-proxy-headers`), so links started with `http://`. One helper, `public_base_url`, uses the optional `PUBLIC_BASE_URL`, else the request host with `https` forced (except localhost).
3. *Atomic counter.* `trap.trigger_count += 1` became one SQL `UPDATE ... SET trigger_count = trigger_count + 1`, in the same transaction as the hit insert.
4. *Event loop.* Routes that only touch the database became plain `def` (FastAPI runs them in a thread pool). Routes that also `await` the network (trap page, trap login, repo scan) stay `async` and call small sync database helpers through `run_in_threadpool`. Each helper opens, uses and closes its own session in its own thread.
5. *CI.* Backend tests run on Python 3.11 and 3.14 (Render runs 3.14), the Postgres job runs on 3.14 and now includes the concurrency test, runners are pinned to `ubuntu-24.04`, and checkout / setup-python / setup-node moved to v7 (Node 24).

### Key concepts

**UTC and timezone-aware timestamps.** UTC is the one clock that is the same everywhere. An *aware* datetime carries its offset; a *naive* one does not say what clock it is on. We store UTC and say so when we send it:

```python
def utc_iso(ts: datetime) -> str:
    ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
    return ts.isoformat().replace("+00:00", "Z")
```

**Why a missing offset marker is ambiguous.** `2026-11-08T12:00:00` could be noon in London or noon in Mumbai. JavaScript guesses *local time* for it, so a UTC value got shifted by the viewer's offset. With the `Z`, `new Date(ts)` knows it is UTC and `toLocaleTimeString` shows the viewer's own time:

```js
const d = new Date(ts)               // "…Z" is read as UTC
d.toLocaleTimeString([], { hour12: false })   // shown in the viewer's time zone
```

**The original-scheme problem behind a proxy.** Render terminates https and talks plain http to the app, so the app sees `http`. Trusting forwarded headers would fix that but also lets visitors forge them, so instead the scheme is decided by us:

```python
scheme = "http" if _is_local(request.url.hostname) else "https"
return f"{scheme}://{request.url.netloc}"
```

**Read-modify-write races and atomic updates.** `+= 1` reads the number into Python, adds one, and writes it back. Two hits that read `4` at the same moment both write `5`: one hit is lost. Letting the database do the add means each update sees the latest value (the row is locked for the moment it takes):

```python
db.query(Trap).filter(Trap.id == trap_id).update(
    {Trap.trigger_count: Trap.trigger_count + 1}, synchronize_session=False)
```

**Blocking calls on an async server.** An `async def` handler runs on the single event-loop thread. A blocking database call inside it freezes *every* request until it returns (on Neon, a network round trip each). A plain `def` handler is run by FastAPI in a worker thread instead. For handlers that must `await` the network, only the database part goes to a worker:

```python
name = await run_in_threadpool(_trap_name, trap_id)      # query in a worker thread
fields = await _hit_fields(request)                      # network call, no session held
await run_in_threadpool(_store_hit, trap_id, fields, True)
```

A session is created, used and closed inside one helper (`session_scope()`), so it is never passed between threads or shared between requests. Measured with a 1-second query: `/health` waited 1.03 s before, 0.02 s after.

**Testing against the runtime you deploy.** Tests on 3.11 say nothing about 3.14: dependencies, deprecations and removed APIs differ. CI now runs the version production runs, and the concurrency test runs on real Postgres, because SQLite cannot reproduce the race.

### Likely interview questions

1. *Why send timestamps with a `Z` instead of local time?* — Store and transmit one unambiguous clock (UTC) and convert to local time only where a person reads it. An offset-less string forces the reader to guess.
2. *What is a lost update and how do you prevent it?* — Two transactions read the same value and both write back a result based on it, so one change disappears. Prevent it with an atomic `UPDATE x = x + 1`, a row lock (`SELECT ... FOR UPDATE`) or optimistic versioning.
3. *Why not just keep `async def` and call the database directly?* — The driver blocks the one event-loop thread, so every other request stalls during each query. Use plain `def` (thread pool), `run_in_threadpool`, or an async driver.

### Mistakes to avoid

- Patching the date format in each caller instead of the one helper that every response goes through.
- Trusting `X-Forwarded-Proto` from the client, or building links from `request.base_url` behind a proxy.
- Testing a race on SQLite: it serializes writes, so the bug never shows. Use Postgres and real threads.
- Opening a session in the event loop thread (or a dependency) and using it in a worker thread; open it where it is used.
- Measuring "not blocked" from after the block ended; measure from when the slow query *began*.
- Changing pins blindly when a new Python version fails: find out which package and why first.

### Left unfixed (found along the way)

- The ip-api geolocation lookup still happens inside the request before the hit is stored (a slow lookup delays the page by up to 5 s). Follow-up: move it to a background task and update the row afterwards.
- The startup retention cleanup in `main.py` uses a blocking session inside the async lifespan (once per start, so left alone).
- `exposure_password` and `exposure_photo` are `async def` with CPU work (zxcvbn, Pillow) on the event loop; they touch no database, so they were out of scope.
- The concurrency test only runs where `DATABASE_URL` is Postgres (the CI Postgres job); it could not be run on this machine, which has no Postgres.
- `FindingCard` shows a client-side `new Date()` for decoy deploy time; it was already local time and is unchanged.

## Pass 7 revision note — logging, readiness, background geolocation

**What changed and why.**
1. *Logging.* `print()` is gone and logging is configured once at startup (`services/logging_setup.py`). Outside dev every line is one JSON object; every request gets an id; IPs are masked and secrets redacted. Before, INFO messages (retention count, unknown trap ids) were silently dropped.
2. *Readiness.* `/health` still only says the process is alive. `/ready` also checks the database and that its migration version equals the repo's newest migration, so Render can stop sending traffic to an instance that cannot work. `/` answers probes instead of 404.
3. *Latency.* The trap page used to wait for the ip-api lookup (up to 5 s). Now it stores the hit, answers the visitor, and a background task does the lookup, fills in the location and sends the push. Measured with a 2-second lookup: the page answered after 2.034 s before, 0.031 s after.

### Key concepts

**Structured JSON logging.** A printed sentence can only be searched as text; a JSON line has named fields, so a log viewer can filter `level=WARNING` or `request_id=...` exactly:

```python
entry = {"timestamp": ..., "level": record.levelname, "logger": record.name,
         "message": record.getMessage(), "request_id": getattr(record, "request_id", "-")}
return json.dumps(entry, default=str)
```

**Request correlation ids.** Many requests interleave in one log. An id stored in a `ContextVar` (a value that follows the current request, even into worker threads) is stamped on every line, so one request's lines can be pulled out together. A client may suggest an id, but only a strict pattern is echoed back, so a hostile header cannot inject line breaks into our logs or responses:

```python
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}")
return incoming if incoming and REQUEST_ID_PATTERN.fullmatch(incoming) else str(uuid.uuid4())
```

**Never log secrets or full IPs.** Logs are copied to other systems and read by more people than the database. So the code masks IPs (`203.0.113.xxx`), logs exception *class names* only (driver errors can contain hosts and URLs), and `RedactFilter` blanks database URLs, bearer tokens and our configured secrets as a last line of defense. A filter is a safety net, not a licence to log secrets.

**Liveness versus readiness.** Liveness ("is the process running?") should never fail because a dependency is down, or a database outage would make the platform restart healthy servers over and over. Readiness ("can it do its job right now?") is allowed to fail:

```python
@app.get("/health")          # liveness: no database
async def health(): return {"status": "ok", ...}
@router.get("/ready")        # readiness: database + migration version
```

**Health checks that touch a database, and their risks.** Every probe costs a query (and wakes a suspended Neon database); if the check is slow it can pile up; if it is open to the world it is a free way to hammer the database, hence the 2-second limit and the rate limit; and its answers must be generic (`database_unreachable`), never an error message that leaks a host or user. On Render, a failing check means the instance is taken out of rotation and, if it stays failing, restarted.

**Slow work after the response, and what it cannot guarantee.** `BackgroundTasks` run after the response is sent, so the visitor does not wait. But nobody is left to receive an error, so the task must catch everything and log it; and if the server stops right after the response, the task may never run (the hit stays stored as "Unknown" and no push goes out). That trade is fine for a location lookup; it would not be for something that must happen.

```python
hit_id = await run_in_threadpool(_store_hit, trap_id, fields, True)   # stored first
background.add_task(_finish_hit, hit_id, fields["ip"], push)          # lookup + update + push, later
return _page()
```

**Why the dedupe slot is claimed before the response.** `should_alert(...)` both checks and marks the 5-minute slot. If it ran in the background, two hits arriving together could both see the slot free before either marked it, and both would push. Claiming it in the request, one hit at a time on the event loop, makes only one hit the "pusher"; the background task just carries out what was already decided.

### Likely interview questions

1. *What is the difference between a liveness and a readiness probe?* — Liveness asks whether the process should be restarted; readiness asks whether it should receive traffic. Liveness must not depend on other services; readiness should.
2. *Why return only a generic reason from a public readiness endpoint?* — Error text from a database driver can include hostnames, usernames or URLs. A public endpoint should say what is wrong in a word ("database_unreachable") and leave the detail to access-controlled logs.
3. *What can go wrong with a background task after the response?* — It may never run (the process stops), its errors have nowhere to go unless it catches and logs them, and it must not reuse the request's database session, which is closed by then.

### Mistakes to avoid

- Logging an exception message or `repr(request)` "just for debugging": driver and HTTP errors carry URLs, hosts and tokens. Log the class name.
- Putting a database call in `/health`: one database outage then makes the platform restart healthy servers.
- Trusting a client-supplied request id without validating it (header and log injection).
- Doing a check-then-mark (the dedupe slot) in a task that runs later, where two requests can both pass the check.
- Writing a test for "the page answers fast" with `TestClient`: it waits for background tasks, so it measures nothing. Use raw ASGI calls and watch the moment the response is sent.
- Assuming pytest leaves logging alone: a fixture that configures logging is undone by pytest's own handling; configure inside the test body.

### Left unfixed (found along the way)

- The honeytoken endpoint (`/api/internal/verify`) still does its geolocation lookup inside the request. Its response must look like a plain auth failure, so it could use the same background pattern.
- `/ready` uses the app's own connection pool; on a free Neon database each probe can wake a suspended database (that is the point of the check, but it costs compute hours).
- The in-memory 5-minute dedupe resets on restart (unchanged, documented since Pass 4a).
- Alembic's own command-line output uses its own logging setup, not the JSON one; it only runs at deploy time.
