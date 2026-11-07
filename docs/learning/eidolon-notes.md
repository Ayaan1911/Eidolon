# Eidolon — learning notes

## Checklist

- [x] Pass 0 — verification (done: `docs/audit/pass-0-verification.md`)
- [x] Pass 1 — ReDoS hotfix (done on `fix/audit-pass-1`; 500 KB line now 0.046 s, `/health` stays under 1 s during a scan)
- [x] Pass 2 — test isolation and pinned dependencies (done on `fix/audit-pass-1`: 181 tests, pinned `requirements*.txt`)
- [x] Pass 3 — CI (done: CI green, PR #1 merged)
- [x] Pass 4a — trust boundary (done on `pass-4-trust-boundary`: client IP helper, fail-closed secrets, gated mint routes, hardened trap routes)
- [ ] Pass 5 — Postgres on Neon with Alembic
- [ ] Pass 6 — Docker and Compose
- [ ] Pass 7 — logging and readiness
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
