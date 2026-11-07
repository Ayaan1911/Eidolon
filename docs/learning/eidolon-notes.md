# Eidolon — learning notes

## Checklist

- [x] Pass 0 — verification (done: `docs/audit/pass-0-verification.md`)
- [x] Pass 1 — ReDoS hotfix *(built on `fix/audit-pass-1`, needs review: regex 80 KB 13.9 s → 0.007 s; live `/health` stall 15.7 s → 0.83 s)*
- [ ] Pass 2 — test isolation and pinned dependencies *(tests isolated on `fix/audit-pass-1`, 140/140 in file and random order, but runtime requirements are still **unpinned**, so not ticked)*
- [ ] Pass 3 — CI *(workflow written on `fix/audit-pass-1`, never run on GitHub, so not ticked)*
- [ ] Pass 4 — trust boundary
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
