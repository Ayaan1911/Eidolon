# Pass 0 — verification of audit claims

**Summary.** `main` is still `4426d5b` (2026-09-25), the same commit both audits describe, so any disagreement between them is about depth of checking, not code version. I re-checked each claim against the current code and against local runs (two git worktrees, fresh venvs, temp databases, nothing in the user's working tree touched). The headline claims hold: the "Password in URL" regex is quadratic, and on `main` one 80 KB line blocked the whole event loop for ~15 s (a concurrent `/health` took 15.7 s). It is fixed on `fix/audit-pass-1` (same request: `/health` ≤ 0.83 s). The test-isolation claim holds too (main: 38 pass / 6 fail in file order, 36 / 8 in random order); `fix/audit-pass-1` passes 140/140 in file order twice and in random order three times. Blank `ADMIN_KEY` and `HONEYTOKEN_SECRET` are accepted at boot, and an admin token signed with an empty key was accepted by the admin-gated alerts route (locally). Unknown trap IDs create alert rows, trap routes and mint routes have no rate limit and the mint routes need no admin. Production predates `main` HEAD: its `/health` has no `commit` field although `main` returns one. Things I could **not** verify: the production start command (not in the repo), why production trusted a forged `X-Forwarded-For`, Render env vars and the auto-deploy setting.

Environment: Python 3.11.9 venvs on Windows; fastapi 0.162.1, starlette 1.10.0, uvicorn 0.54.0, slowapi 0.1.10 (unpinned installs, so these are "latest at install time"). Source attribution: your prompt does not tell me which audit made which claim, so the "Source" column says *prompt* (claim as listed in the task) or *own audit* (EIDOLON_AUDIT.md, uncommitted); I do not guess "old" vs "newer".

## Git state (step 1)

- Working directory: branch `fix/audit-pass-1`, HEAD `33452bb`; only untracked file is `EIDOLON_AUDIT.md` (left alone, as instructed).
- `main` = `origin/main` = `4426d5b`. `main` has not moved since the old audit, so `4426d5b..main` is empty.
- Branches: `main` (pushed), `fix/audit-pass-1` (pushed; after `git fetch origin`, `origin/fix/audit-pass-1` = `33452bb` = local). Remote-tracking also has `origin/HEAD -> origin/main`.
- Commits on `fix/audit-pass-1` not in `main` (5): `b17fb05` regex linear, `219c7df` line cap + byte budget + worker thread, `cc0d97d` regex-safety tests, `4f93711` test isolation (conftest), `33452bb` CI. Diffstat: 15 files, +609 / −318.

## Tests and coverage (step 3)

Run from `backend/`, each worktree with its own venv (`pip install -r requirements.txt` plus `pytest pytest-cov pytest-randomly httpx` by hand). Coverage = app code only (`services routers database main models`).

| | main | fix/audit-pass-1 |
|---|---|---|
| tests collected | 44 | 140 |
| plain run (`-p no:randomly`) | 38 passed, **6 failed** | 140 passed (×2) |
| random order | 36 passed, **8 failed** | 140 passed (×3 incl. seeds 1, 777, one random) |
| total coverage | 77% | 78% |
| `breach_check.py` | 20% | 20% |
| `photo_metadata.py` | 26% | 26% |
| `geolocation.py` | 27% | 27% |
| `honeytoken.py` | 58% | 58% |

Failures on main (plain run): `test_admin_auth::test_rotating_admin_key_revokes_tokens` (assert False, line 68); `test_finding_traps::` `test_deploy_trap_creates_a_named_trap_linked_to_the_finding`, `test_deploy_trap_is_idempotent`, `test_hit_count_reflects_real_trap_triggers`, `test_delete_trap_requires_admin`, `test_delete_trap_removes_it_and_its_alerts` (`NoResultFound` / `assert 0 == 1`: tests depend on rows created by earlier tests, plus module-level env/DB mutation). Random order adds `test_trap_hits::test_alert_stream_exposes_new_fields_to_admin` and `test_finding_traps::test_admin_scan_shows_deployed_trap_status`.

Claims: 44 tests ✔; 6 fail in one run ✔; ~77% ✔ (81% if test files are counted — the number depends on the `--cov` target); honeytoken ~58% ✔. The fix branch added **no** tests for honeytoken, breach check, photo or geolocation: those four modules are exactly as uncovered as before.

## Findings

Severity is re-rated by me; "Pass" is the planned pass from your prompt.

| # | Claim | Source | Verdict | Evidence | Severity | Pass |
|---|---|---|---|---|---|---|
| 1 | "Password in URL" regex has catastrophic/quadratic backtracking | prompt, own audit | **Confirmed** (quadratic, not exponential); **Already fixed on fix/audit-pass-1** | `secret_scanner.py:16` `[a-zA-Z][a-zA-Z0-9+.-]*://([^\s/:@]+):([^\s/:@]+)@[^\s/]+`. Single line of `a`s: 10 KB 0.099 s, 20 KB 0.399 s, 40 KB 1.598 s, 80 KB 13.9 s (×4 per doubling, up to ×8.7 at the largest step). Fix branch: 0.001 / 0.002 / 0.004 / 0.007 s. Earlier own measurement: 500 KB = 568.5 s on main vs 0.046 s | Critical | 1 |
| 2 | The blocking scan stalls every other request | prompt | **Confirmed** (main); **Already fixed** (fix) | Local uvicorn, stubbed GitHub file fetch returning 80 KB of `a`, real `POST /api/exposure/repos`, concurrent `GET /health` probes. main: scan 17.1 s, `/health` max latency **15.7 s**. fix: scan 2.3 s (incl. startup), `/health` max 0.83 s, `skipped_long_lines: 1` | Critical | 1 |
| 3 | Attacker needs a public repo with one crafted file | prompt | **Confirmed** | Real scanner path: `github_scanner.scan_user_repos` → `_is_candidate` (size ≤ `MAX_FILE_BYTES = 500_000`, per the tree's `size` field; skips tests/lockfiles/binaries/`node_modules`) → `_fetch_file` → `scan_text_for_secrets` **called directly in the async handler**. Needed: a non-fork public repo, any ordinary filename (e.g. `config.txt`, `.env`), content = one line of ≥ 80 KB letters (up to 499,999 bytes; 500 KB ≈ 9.5 min of frozen server on this machine). Then POST the repo owner's username to `/api/exposure/repos` (public, 5/min per IP). Many files multiply the stall | Critical | 1 |
| 4 | Other regexes are safe | own audit | **Confirmed** | Only 6 secret patterns + `_EXAMPLE_FILENAME_RE` + `_TEST_FILENAME` + the CORS localhost regex exist (`grep re.compile/finditer`). Only "Password in URL" has an unbounded quantifier feeding another unbounded class. Others are fixed-length or bounded; `Private Key` `([A-Z]+ )?` is optional/single (bounded on fix branch). No nested quantifiers or overlapping alternations. Filename regexes only see ≤ 255-char names | — | 1 |
| 5 | 6 tests fail in a single run on main | prompt | **Confirmed**; **Already fixed on fix/audit-pass-1** | See test table | High (process) | 2 |
| 6 | Requirements unpinned; pytest missing from requirements | prompt | **Confirmed** (main). fix adds `requirements-dev.txt` (pytest, pytest-randomly, not pinned) but runtime deps remain **unpinned** | `backend/requirements.txt`: 11 bare names. README never says how to run tests | Medium | 2 |
| 7 | Forged `X-Forwarded-For` accepted in production | own audit | **Partly true — mechanism reproduced locally; production cause Unverified** | Code: rate limiter keys on `slowapi.util.get_remote_address` = `request.client.host` (`exposure.py`); traps log `request.client.host` (`traps.py` `_record_hit`, `verify_key`). No XFF parsing in the app. The app only sees the forged value if **uvicorn rewrites `client.host`** (`--proxy-headers`, on by default, applies only to peers in `--forwarded-allow-ips`, default `127.0.0.1`). Local (peer 127.0.0.1, so trusted by default): no header → 8 wrong logins gave 5×401 then 3×429; forged XFF changing each request → 8×401 (limit bypassed); alert IPs stored `203.0.113.9` (forged) vs `127.0.0.1`; `--no-proxy-headers` → forged header ignored (429s, IP 127.0.0.1). The **production start command is not in the repo** (no render.yaml/Procfile/Dockerfile; README shows only `uvicorn main:app --reload --port 8001`). On Render the peer is Render's proxy, not 127.0.0.1, so production only trusts XFF if the dashboard command has `--forwarded-allow-ips` set to a wide value or `FORWARDED_ALLOW_IPS=*` is set — I cannot see either. My local run does not prove that production is configured that way | High | 4 |
| 8 | Honeytoken mint and deploy-decoy are reachable without admin | prompt | **Confirmed** | `traps.py`: `create_honeytoken` and `deploy_decoy` have no `Depends(require_admin)`; local call without auth → 200. Frontend calls `deploy-decoy` with no auth header (`api.js:75`) | Medium | 4 |
| 9 | Trap routes and `/trap/{id}/login` have no rate limit | prompt | **Confirmed** | No `@limiter.limit` on `trigger_trap`, `trap_login_attempt`, `verify_key`, mint routes, `/health` | High | 4 |
| 10 | `/trap/{id}/login` (and GET `/trap/{id}`) accept non-existent trap IDs | prompt | **Confirmed** | Local, temp DB: `POST /trap/NOSUCHID/login` → 204, `GET /trap/NOSUCHID2` → 200; **2 alert rows** created with those fake IDs. `Alert.trap_id` has no foreign key. Unbounded unauthenticated DB growth, on top of an ip-api call per hit | High | 4 |
| 11 | Empty-string secrets are accepted (fail-open) | own audit | **Confirmed** | Local, both vars set to `""`: app boots, `/health` 200, honeytoken mint 200, and an admin token forged with an empty HMAC key got **200 on `GET /api/traps/alerts`**. With both vars **unset** (not blank): boots; mint returns 500; forged token → 401 (`KeyError` is caught in `is_valid_admin_token`). `passphrase_matches` itself rejects empty `ADMIN_KEY` | Critical *if* Render has blank vars (Unverified) | 4 |
| 12 | `.env.example` has placeholder values to test | prompt | **Refuted (nuance)** | Every variable in `.env.example` is blank (`HONEYTOKEN_SECRET=`, `ADMIN_KEY=`, …). So "placeholder values" = the blank case above | — | 4 |
| 13 | Admin tokens are signed with a separate secret vs the passphrase | prompt | **Partly true** | `admin_auth._signature` = `honeytoken.sign("admin:<exp>:<ADMIN_KEY>")`, i.e. HMAC keyed by `HONEYTOKEN_SECRET`, with the passphrase inside the signed message. So two secrets are needed, not one, but if `HONEYTOKEN_SECRET` is blank the passphrase adds nothing an attacker needs (see #11, the forgery used an empty `ADMIN_KEY` too). Tokens are not revocable individually | Medium | 4 |
| 14 | Hardcoded fallback secrets | prompt | **Refuted** | Only env default found: `RENDER_GIT_COMMIT` → `"unknown"`. No fallback passphrase/secret | — | — |
| 15 | SQLite on Render's ephemeral disk loses data | own audit | **Confirmed** (by code + documented Render behavior; production disk not inspected) | `database.py:15` `sqlite:///eidolon.db`; docstring itself says "ephemeral". Code comments admit the honeytoken path avoids the DB for that reason, but Trap Lab traps and alert history are lost on every restart/redeploy/idle spin-down (free tier) | High | 5 |
| 16 | Geolocation is plain HTTP | prompt | **Confirmed** | `geolocation.py` `IP_API_BASE = "http://ip-api.com/json"`; sends only the visitor IP (in the URL path), no key. Free ip-api is HTTP-only, so HTTPS needs another provider or paid plan | Medium | 8 |
| 17 | A slow/failed geolocation lookup breaks or delays the trap response | prompt | **Partly true** | `timeout=5.0`; `httpx.HTTPError` (incl. timeouts) caught → `{}`. But `lookup_ip` and `send_ntfy_alert` (5 s timeout each) are **awaited before the response** in `trap/{id}`: worst case ≈ 10 s added to the response, and a non-JSON 200 from ip-api would raise `ValueError` (uncaught → 500). DB calls are synchronous inside async handlers | Medium | 4/7 |
| 18 | ntfy topic comes only from env, long and unguessable | prompt | **Partly true / Unverified** | `NTFY_TOPIC` only from `os.environ`; unset → logged `print`, alert skipped. `.env.example` suggests `eidolon-trap-` + `token_urlsafe(18)` (≈ 24 random chars, 144 bits) — the *recommended shape*; the actual production topic is not visible to me. Anyone knowing the topic can read/post | Low | — |
| 19 | Numeric scores still returned | own audit | **Confirmed** (API), **not consumed** by the UI | `breach_check._risk_score` → `risk_score` (0–100) in `/api/exposure/email`; `password_strength` → `score` (zxcvbn 0–4) in `/api/exposure/password`. `grep` in `frontend/src` finds no read of `risk_score`/`score`; `checkPasswordStrength` in `api.js` has no caller. Violates the "no numeric scoring" rule at the API level only | Medium | 8 |
| 20 | k-anonymity breached-password check exists | prompt | **Refuted** | No range/hash-prefix call anywhere (`grep sha1|range/|pwned|k-anon` empty). Breach check is email-only via XposedOrNot | Low | 8 |
| 21 | Full password sent to backend | prompt | **Confirmed (endpoint exists)**: `POST /api/exposure/password` takes the plaintext password and runs zxcvbn server-side; the current UI never calls it | Medium | 8 |
| 22 | Mirror→Trap decoy button sends the in-memory counter, not the finding hash | prompt | **Confirmed** | `FindingsContext.jsx:8` `let nextId = 0` → `id: nextId++`; `FindingCard.jsx:113` `deployDecoy(finding.id)` sends it. The Trap button uses `finding.raw.id` (the real hash, `FindingCard.jsx:67`). So decoy tokens carry `0`, `1`, … not the finding hash | Medium | 8 |
| 23 | Alerts don't name the finding | prompt | **Confirmed** | `verify_key` alert fields: Timestamp, IP, Location, Endpoint — the finding id embedded in the token is never decoded | Low | 8 |
| 24 | No `.github` on main | prompt | **Confirmed** (exists on fix: `.github/workflows/ci.yml`, never executed on GitHub — `gh` not installed here, run status unverified) | `git ls-tree` | Medium | 3 |
| 25 | No Dockerfile / render.yaml | prompt | **Confirmed** | `git ls-files` | Low | 6 |
| 26 | print() vs logging | prompt | **Confirmed**: 3 `print()` calls (2 in `ntfy_alert.py`, 1 `print("ok")` in a `__main__` block of `secret_scanner.py`); 0 uses of `logging` | Low | 7 |
| 27 | `/health` is liveness only, no commit field | prompt | **Refuted for the code, true for production** | `main.py:41` returns `{"status","commit"}` (added in `17675db`). Production returned `{"status":"ok"}` only → deployed backend is older | Medium | 7 |
| 28 | `/docs` and `/openapi.json` enabled | prompt | **Confirmed** | No `docs_url=None` in `main.py`; production `/docs` 200 text/html, `/openapi.json` 200 (15 paths) — full route map, including admin and trap endpoints, is public | Low | 4 |
| 29 | Admin token stored in localStorage | prompt | **Confirmed** | `frontend/src/lib/adminAuth.js` (`localStorage.setItem/getItem`) — readable by any XSS; token lifetime 24 h | Medium | 4 |
| 30 | README mentions nonexistent `legacy/`; lacks live links, architecture diagram, env guide | prompt | **Confirmed** | README line 47 "`legacy/` holds the previous implementation"; no `legacy/` in the tree. Only badge links; no deployed URLs; no diagram; "Running locally" never mentions `.env`/required variables | Low | 9 |
| 31 | Frontend lint warnings | prompt | **2 warnings, 0 errors** | oxlint: `lib/systemCards.jsx:3:14` and `context/FindingsContext.jsx:27:17`, both `react(only-export-components)` | Low | — |

CORS and production-header claims are covered in the production check below.

## Production check (step 11) — 7 requests, all GET/OPTIONS

(You allowed at most 8: `/health`, `/docs`, `/openapi.json` ×2 [I fetched it twice, once for the body and once to count paths], OPTIONS preflight, one GET to a non-existent path, and `GET /` on Vercel.)

- `GET /health` → 200 `{"status":"ok"}` — **no `commit` field**, so the deployed backend predates `main` HEAD (`17675db`/`4426d5b`). It cannot tell me *which* older commit is live.
- `GET /docs` → 200 HTML; `GET /openapi.json` → 200, 15 paths.
- `OPTIONS /api/exposure/email` with `Origin: https://evil-random-origin.example` → **400 "Disallowed CORS origin"**: the foreign origin is **not** allowed. No `access-control-allow-origin` header returned.
- `GET /definitely-not-here` → 404 JSON; no stack trace seen (I did not provoke a 500).
- Render responses carry **no** security headers (no HSTS, `X-Content-Type-Options`, `X-Frame-Options`, CSP); `x-render-origin-server: uvicorn`, behind Cloudflare.
- Vercel `GET /` → 200, has `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`; **no CSP, no X-Frame-Options, no nosniff**; `Access-Control-Allow-Origin: *` (static HTML, harmless). Last-Modified 2026-11-02.

## Route inventory (step 6)

"HMAC checked before write" = the token is verified before any write.

| Method | Path | Auth | Rate limit | DB write | External call | HMAC before write |
|---|---|---|---|---|---|---|
| GET | `/health` | none | none | no | none | n/a |
| GET | `/docs`, `/redoc`, `/openapi.json` | none | none | no | none | n/a |
| POST | `/api/admin/login` | none (passphrase in body) | 5/min | no | none | n/a (issues token) |
| POST | `/api/exposure/email` | none | 10/min | no | XposedOrNot | n/a |
| POST | `/api/exposure/password` | none | 10/min | no | none | n/a |
| POST | `/api/exposure/photo` | none | 10/min | no | none | n/a |
| POST | `/api/exposure/repos` | none (admin optional: adds trap info) | 5/min | no (read) | GitHub API + raw.githubusercontent | n/a |
| POST | `/api/traps` | admin | none | **yes** | none | admin token verified first |
| GET | `/trap/{trap_id}` | none | **none** | **yes** (alert, `trigger_count`) | ip-api, ntfy | no token at all; unknown IDs accepted |
| POST | `/trap/{trap_id}/login` | none | **none** | **yes** | ip-api | no token; unknown IDs accepted |
| POST | `/api/findings/{id}/deploy-trap` | admin | none | **yes** | none | admin token first |
| DELETE | `/api/traps/{trap_id}` | admin | none | **yes** | none | admin token first |
| POST | `/api/traps/honeytoken` | **none** | **none** | no | none | n/a (mints a token) |
| POST | `/api/findings/{id}/deploy-decoy` | **none** | **none** | no | none | n/a (mints a token) |
| GET | `/api/internal/verify` | none | **none** | no | ip-api, ntfy (only if token valid) | yes — verified before any external call; no DB write |
| GET | `/api/traps/alerts` | admin | none | no (read, limit 50) | none | admin token first |

Because anyone can mint a valid decoy token for free and `/api/internal/verify` fires ip-api + ntfy for a valid one with no rate limit, an unauthenticated caller can spam your ntfy topic (reasoned from code; I did not trigger it, per your rule).

## Things you must verify by hand

1. **Render environment variables**: are `ADMIN_KEY` and `HONEYTOKEN_SECRET` set and non-empty? (Blank = forgeable admin tokens, finding #11.) Also `FORWARDED_ALLOW_IPS`, `CORS_ORIGINS`, `NTFY_TOPIC`, `GITHUB_TOKEN`.
2. **Render start command** (Settings → Start Command): does it contain `--proxy-headers`, `--forwarded-allow-ips`, `--reload`?
3. **Auto-deploy setting** and which commit is live (production has no `commit` field, so compare the Render deploy log with `git log`).
4. **Real client IP**, manual procedure (do this yourself, I did not): (a) find your public IP (e.g. open https://ifconfig.me in a browser). (b) From that same network open `https://eidolon-2515.onrender.com/trap/<id of a trap you own>` once (this creates one real alert — expected). (c) Open Trap Lab → alerts, find the newest alert and compare its IP with (a). Equal = correct. A Render/Cloudflare address = proxy IP being logged (wrong). (d) Optional second hit with a forged `X-Forwarded-For: 203.0.113.50` header (`curl -H`): if the new alert shows `203.0.113.50`, the forged header is trusted. Remember each hit may send an ntfy notification.
5. Whether `ADMIN_KEY` has ever been used on a device with the frontend open on an untrusted origin (token is in localStorage).

## Things that contradicted the assumptions in the prompt

- `main` is **not** ahead of the old audit: `4426d5b..main` is empty, both audits describe identical code.
- `fix/audit-pass-1` **is** pushed (`origin/fix/audit-pass-1` = `33452bb`), not unpushed — you confirmed that yourself.
- "ReDoS … catastrophic": it is **quadratic**, not exponential; still devastating (80 KB ≈ 14 s, 500 KB ≈ 9.5 min).
- `.env.example` has no placeholder values — all are blank.
- `/health` **does** have a `commit` field in the code; only production lacks it.
- The production start command is not in the repo, so "why a forged X-Forwarded-For was accepted in production" cannot be answered from code. I reproduced the mechanism locally only.
- Frontend never reads `risk_score`/`score` and never calls the password endpoint; the "full password sent to the backend" risk is an unused endpoint, not live user flow.
- The fix branch passes its own tests but adds **no** coverage for honeytoken/breach/photo/geolocation, does not pin runtime dependencies, and its CI workflow has never run on GitHub (unverified).
- Production request count: 7 (within your 8).
