# Eidolon

[![CI](https://github.com/Ayaan1911/Eidolon/actions/workflows/ci.yml/badge.svg)](https://github.com/Ayaan1911/Eidolon/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Backend](https://img.shields.io/badge/backend-Python%20%2F%20FastAPI-3776AB)
![Frontend](https://img.shields.io/badge/frontend-React%20%2F%20Vite-61DAFB)

> Eidolon answers one question: what can someone discover about you without you realizing it?

![Eidolon hero](docs/hero.jpg)

## Contents

- [What it does](#what-it-does)
- [Status](#status)
- [Structure](#structure)
- [Running locally](#running-locally)

## What it does

Eidolon works in two movements.

**The Mirror** shows you your own exposure — the same footprint an attacker would find:

- **Breach & password exposure** — checks an email against known breaches and checks a password against known breaches without sending it anywhere
- **Photo metadata** — pulls EXIF/GPS data out of a photo to show what it leaks about where it was taken
- **Repo secret scanning** — scans a GitHub user's public repos for committed secrets

Every check lands in one running dossier, and every finding comes with a reasoning panel
explaining why it matters — no numeric exposure score. That's deliberate: a single number invites
false confidence, so Eidolon sticks to narrative findings with full reasoning instead.

![Submitting a check, landing on a dossier finding, and opening the reasoning panel](docs/dossier-flow.gif)

**The Trap** plants deception tied to what the Mirror finds, so if someone acts on that exposure, you
know. Right now that's one working trap type: a decoy API key (`eidolon_live_...`) that's
self-verifying via an HMAC signature — no database required — and posts an ntfy alert with the
requester's IP and rough geolocation the moment it's used. Other trap types (tied directly to
Mirror findings) aren't built yet.

## Status

- **Mirror** — complete: all three checks above are built and working end to end.
- **Trap** — in progress:
  - [x] Honeytoken (self-verifying decoy API key, ntfy alert)
  - [x] Wire honeytoken generation into Mirror dossier findings

`legacy/` holds the previous implementation for reference only — it isn't part of the build.

## Structure

- `backend/` — FastAPI service (exposure checks + trap endpoints)
- `frontend/` — React + Vite + Tailwind UI

## Running locally

```bash
# backend
cd backend
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt   # runtime dependencies, pinned to exact versions
cp .env.example .env              # then edit it: real ADMIN_KEY / HONEYTOKEN_SECRET, or EIDOLON_ENV=dev
alembic upgrade head              # create or update the tables (SQLite file when EIDOLON_ENV=dev)
uvicorn main:app --reload --port 8001

# frontend
cd frontend
npm install
npm run dev
```

### Optional: a local Postgres instead of SQLite

With Docker installed, start a throwaway Postgres and point `DATABASE_URL` at it (in `backend/.env`).
`localhost` does not need SSL; the password below is a placeholder for this local container only.

```bash
docker run --name eidolon-pg -e POSTGRES_PASSWORD=local-only-password -e POSTGRES_DB=eidolon -p 5432:5432 -d postgres:17
# in backend/.env:
# DATABASE_URL=postgresql://postgres:local-only-password@localhost:5432/eidolon
alembic upgrade head
```

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | none | Postgres connection string (`postgres://` and `postgresql://` both work). Required unless `EIDOLON_ENV=dev`, where the default is the local SQLite file `backend/eidolon.db`. A host other than localhost must have `?sslmode=require`, otherwise the app refuses to start. Use Neon's **direct** (non-pooled) connection string. |
| `RETENTION_DAYS` | `90` | Trap hits (alerts) older than this are deleted at startup, at most 5000 rows per start. Traps are never deleted. |
| `PUBLIC_BASE_URL` | none | Optional. Address that trap and decoy links start with, e.g. `https://eidolon-api.example.com` (https required except on localhost; no path or query). If unset, the request's host is used with `https` forced (`http` only for localhost). An invalid value stops startup. |
| `LOG_LEVEL` | `INFO` | Optional. `DEBUG`, `INFO`, `WARNING` or `ERROR`; anything else stops startup. Outside `EIDOLON_ENV=dev` every log line is one JSON object (`timestamp`, `level`, `logger`, `message`, `request_id`, plus extra fields). Visitor IPs are masked in logs (`203.0.113.xxx`); the database keeps the full IP. |
| `TRUSTED_PROXY_HOPS` | `0` | Number of reverse proxies in front of the app (see below). |
| `ADMIN_KEY`, `HONEYTOKEN_SECRET` | none | Required secrets (see "Secrets"). |
| `EIDOLON_ENV` | none | `dev` skips the secret and database checks. Local development only. |

See `backend/.env.example` for the rest (`NTFY_TOPIC`, `GITHUB_TOKEN`, `CORS_ORIGINS`). Error messages
and logs never contain `DATABASE_URL` or its password.

## Endpoints for probes

| Endpoint | Use it for | What it checks |
|---|---|---|
| `GET /health` | "Is the process alive?" (liveness) | Nothing but the process: never touches the database. Returns `{"status": "ok", "commit": ...}`. |
| `GET /ready` | "Can it serve traffic?" (readiness); set this as Render's Health Check Path | `SELECT 1` on the database (2-second limit) and that the database's Alembic revision equals the newest migration in the repo. `200 {"status": "ready", "commit": ...}`, otherwise `503 {"status": "not_ready", "reason": "database_unreachable" or "migrations_out_of_date"}`. Rate limited to 60/minute per IP. |
| `GET /` (and `HEAD`) | Probes that just request the root | Always `200` with a short text body; not in the OpenAPI schema. |

Every response carries an `X-Request-ID` header (the client's own if it is letters, digits and hyphens, at most 64 characters; otherwise a generated UUID), and the same id is on every log line of that request.

## Running tests

```bash
# backend (from backend/, with the venv active)
pip install -r requirements-dev.txt   # requirements.txt plus pytest, pytest-cov, pytest-randomly, ruff
python -m pytest

# frontend
cd frontend
npm run lint
npm run build
```

Tests need no secrets or network: `backend/conftest.py` supplies dummy environment values,
a fresh in-memory database per test, and stubs for external services. The same checks run in
GitHub Actions on every push and pull request.

Python: the repo does not pin a version (Render's is set in its dashboard). The pinned
versions are tested in CI on Python 3.11 and 3.14 (Render runs 3.14).


## Deploying: the client IP behind a proxy

Rate limits and trap alerts need the visitor's real IP. On Render, a proxy sits in front of the
app, so the app has to decide whose word to take. `X-Forwarded-For` can be written by anyone.

- **Start command.** In the Render dashboard set it to:
  `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT --no-proxy-headers`
  `alembic upgrade head` runs first on every deploy so the tables exist (and are up to date) before the
  server accepts requests; if it fails, the server does not start. Run from the `backend` directory.
  The old command (`--proxy-headers --forwarded-allow-ips=*`) makes uvicorn trust the header from
  any sender and rewrite `request.client.host` itself, using the leftmost entry, which a visitor can
  forge. Until it is changed, the app only sees that spoofable address; the code below cannot fix it,
  because the rewrite happens before the app runs.
- **`TRUSTED_PROXY_HOPS`** (default `0`) is how many proxies sit in front of the app. With `0` the
  header is ignored and the socket address is used. With `N`, the app reads `X-Forwarded-For` from the
  right and takes the Nth entry from the end (never the leftmost), and falls back to the socket address
  if the header is short or not an IP.
- **Finding the right value.** Log in as admin, open the System page, and use "Client IP check" from your
  own network. Compare "Resolved IP" with your real public IP (search "what is my IP"). Try
  `TRUSTED_PROXY_HOPS=1` first; if "Resolved IP" is a Render/Cloudflare address instead of yours, try `2`.
  Pick the smallest value where it shows your own IP.


## Secrets

The backend refuses to start unless `ADMIN_KEY` (at least 12 characters) and `HONEYTOKEN_SECRET`
(at least 16) are set to real values, not blank and not the `CHANGE_ME...` placeholders from
`backend/.env.example`. The error names the variable and its length, never its value. Generate them:

```bash
python -c "import secrets; print(secrets.token_hex(32))"   # HONEYTOKEN_SECRET
python -c "import secrets; print(secrets.token_urlsafe(24))"   # ADMIN_KEY (the passphrase you log in with)
```

Set both in the Render dashboard (and in a local `backend/.env`, which is not committed). For local
development only, `EIDOLON_ENV=dev` skips the check; never set it on Render.

## What survives a redeploy

With `DATABASE_URL` pointing at Neon, **traps and trap hits (alerts) are stored in Postgres and survive
redeploys, restarts and spin-downs.** Neon pauses an idle database after about 5 minutes, so the first
request after a quiet period can take a few extra seconds while it wakes up.

Still in memory, so reset on every restart (acceptable here): rate-limit counters, the "one ntfy push
per trap per 5 minutes" timestamps, and the breach-metadata cache. Stateless things never needed storage:
honeytoken and admin-session signatures are recomputed from the secrets.
