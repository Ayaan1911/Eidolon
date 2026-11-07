# Pass 5 inventory — what the database layer does today

Read-only survey of `main` at `9a1bf95` before moving to Postgres + Alembic. Nothing was changed to produce it.

## Where the database code lives

| Item | Location |
|---|---|
| Engine, `Base`, `SessionLocal`, models, ALTER helper, `get_db` | `backend/database.py` (the only module that builds an engine) |
| Schema creation at import time | `database.py:60` `Base.metadata.create_all(engine)` |
| Hand-written migration helper | `database.py:62-91` `_ADDED_COLUMNS`, `add_missing_columns(bind)`, called at import time |
| Session opened per request | `get_db()` (`database.py:94`): `SessionLocal()` in a generator, closed in `finally` |
| Routes that take a session | `routers/traps.py` (`create_trap`, `trigger_trap`, `trap_login_attempt`, `deploy_trap_for_finding`, `delete_trap`, `list_alerts`), `routers/exposure.py` (`exposure_repos`, read-only trap lookup, admin only) |
| Anything else opening its own session | none (`grep SessionLocal` finds only `database.py`) |
| Reads `DATABASE_URL` today? | **No.** The URL is the literal `sqlite:///eidolon.db` (relative path: a file in the process's working directory). No environment variable of any kind is read for the database. |
| Raw SQL | only `database.py:88` `ALTER TABLE {table} ADD COLUMN {name} {ddl}` (f-string, but fed from a constant dict, not user input). Tests also use `SELECT *` / `PRAGMA table_info` (`test_trap_hits.py`, `test_finding_traps.py`). |
| `sqlite3` module imports | none in app code |

## Tables

### `traps`

| Column | Type | Constraints / default | Notes |
|---|---|---|---|
| `id` | `String` | primary key | 8 hex chars from `uuid4().hex[:8]`, set by the app |
| `name` | `String` | NOT NULL | free text from the admin, or "Secret canary — …" |
| `created_at` | `DateTime` | default `datetime.utcnow` | naive UTC |
| `trigger_count` | `Integer` | default 0, nullable | incremented with `trap.trigger_count += 1` (read-modify-write) |
| `source_type` | `String` | nullable | `"secret"` for finding traps |
| `context` | `String` | nullable | `"repo:file"` |
| `finding_id` | `String` | nullable | 16 hex chars; queried by `Trap.finding_id == ...` and `.in_(...)`, **no index** |

### `alerts` (the "hits")

| Column | Type | Constraints / default | Notes |
|---|---|---|---|
| `id` | `Integer` | primary key, autoincrement | |
| `trap_id` | `String` | NOT NULL | **no foreign key, no index**; filtered in `delete_trap`; joined in `list_alerts` |
| `ip` | `String` | | now the resolved client IP (IPv4/IPv6 text) or `"unknown"` |
| `location` | `String` | | `"City, Country"` |
| `latitude`, `longitude` | `Float` | | |
| `isp` | `String` | | |
| `org`, `asn` | `String` | nullable | |
| `browser`, `os`, `device` | `String` | | from the visitor's User-Agent |
| `referer` | `String` | nullable | capped at 500 chars in code |
| `email` | `String` | nullable | typed into the fake login form; max 320 enforced by the request schema |
| `password_attempted` | `Boolean` | nullable | NULL for page loads |
| `password_length` | `Integer` | nullable | 0–1024, enforced by the request schema |
| `timestamp` | `DateTime` | default `datetime.utcnow` | naive UTC; **no index**, but `list_alerts` does `ORDER BY timestamp DESC LIMIT 50` |

No other tables. No relationships declared. `Alert.trap_id` -> `Trap.id` is only a convention (and an outer join).

## SQLite-specific behavior in use

| Item | Where | Postgres impact |
|---|---|---|
| `connect_args={"check_same_thread": False}` | `database.py:15` | SQLite-only argument; must not be passed to psycopg |
| Relative file path `eidolon.db` | `database.py:15` | Created in the current directory; on Render this is the ephemeral disk (the whole reason for this pass) |
| `Base.metadata.create_all` at import | `database.py:60` | Replaced by Alembic; importing a module must stop creating tables |
| `ALTER TABLE ... ADD COLUMN` helper using `inspect()` | `database.py:62-91` | Replaced by migrations. The baseline must include all columns the helper adds (`org`, `asn`, `referer`, `email`, `password_attempted`, `password_length`, `finding_id`) |
| `AUTOINCREMENT` | not written explicitly; SQLAlchemy `Integer` PK + `autoincrement=True` | On Postgres becomes an identity/serial column. Fine, but the sequence is separate state (not reset by deleting rows) |
| `?` placeholders / `PRAGMA` | tests only (`PRAGMA table_info` in the old-database migration test) | That test (`test_migration_adds_columns_to_an_old_database`) tests the helper being deleted, so it goes with it |
| Foreign keys | none declared | nothing to enforce (SQLite's FK pragma is off by default, Postgres always enforces) |
| JSON stored as text | none | n/a |
| Booleans | `Boolean` | SQLite stores 0/1 (with a CHECK constraint in SQLAlchemy's DDL), Postgres has a real `boolean`; API returns true/false either way |

## Datetime handling

- Defaults use `datetime.utcnow` (naive, deprecated in Python 3.12+; Render runs 3.14).
- Columns are `DateTime` without timezone: on Postgres this is `timestamp without time zone`.
- `routers/traps.py` returns `a.timestamp.isoformat()` in `AlertResponse.timestamp` (a plain `str`), e.g. `2026-11-07T15:43:23.123456` **with no `Z` or offset**.
- If columns become timezone-aware, Postgres returns aware datetimes (`+00:00`) while SQLite still returns naive ones, so the serialized string would change. The API output must stay identical, so the route must normalise to naive UTC before `isoformat()`.
- Latent bug (not fixed here): the frontend does `new Date(a.timestamp)`; JavaScript reads a string with no offset as **local time**, so a visitor-facing clock can be off by the viewer's UTC offset. The demo data uses a `Z` suffix, the real data does not.
- `datetime.utcnow().isoformat() + "Z"` is also used for the ntfy "Timestamp" field (`routers/traps.py`); it does not touch the database.

## Things that will behave differently on Postgres

1. **Concurrency.** SQLite serializes writers; Postgres does not. `trap.trigger_count += 1` is a read-modify-write, so two simultaneous hits can both read 4 and both write 5 (lost update). Not fixed in this pass; the fix is `UPDATE traps SET trigger_count = trigger_count + 1`.
2. **Blocking I/O in async handlers.** Every route is `async def` but uses the synchronous SQLAlchemy session. With a SQLite file a query takes microseconds; with Neon each query is a network round trip (and a first query after the database wakes up can take seconds), and during it the event loop is blocked for every other request. Not fixed here; the mitigation options are `def` routes (FastAPI runs them in a thread pool) or an async driver.
3. **Stale connections.** Neon suspends an idle database after 5 minutes. A pooled connection that was open before the suspend is dead; the next use raises a connection error unless the pool checks first (`pool_pre_ping`) or retires old connections (`pool_recycle`).
4. **Case sensitivity and collation.** Equality on `String` is case-sensitive on both. The only ordering is by `timestamp`, which has no collation issue.
5. **String length.** `String` with no length maps to `VARCHAR` with no limit on Postgres and to `TEXT`-like behaviour on SQLite; no limit is enforced in either. Values are bounded in application code (`referer` 500, `email` 320).
6. **Integer size.** Postgres `INTEGER` is 32-bit; `password_length` and `trigger_count` are far below the limit.
7. **Floats.** SQLAlchemy `Float` is double precision on Postgres; SQLite stores 8-byte reals. Same behavior for latitude/longitude.
8. **Missing indexes.** `alerts.trap_id`, `alerts.timestamp` and `traps.finding_id` are queried but unindexed. Harmless at SQLite scale, not forever on a growing table. The baseline migration will add them (and the models will declare them so autogenerate sees no drift).
9. **Sequences.** `alerts.id` comes from a sequence; deleting old rows (the retention job) does not reuse ids.
10. **Transactions.** `get_db` never rolls back explicitly; a failed request just closes the session, which rolls back an uncommitted transaction. Postgres puts a transaction into an aborted state after an error, so code must not reuse a session after a failed statement (currently it does not).
11. **Unknown trap ids.** Since Pass 4a, ids are validated before any insert, so there is no flood of junk rows to retain.

## Test setup that touches the database

- `conftest.py`: `engine` fixture = in-memory SQLite with `StaticPool`, `Base.metadata.create_all(eng)` (this is the one place `create_all` stays until Alembic exists; Step 6 moves tests onto the migrated schema), `session_factory`, and a `get_db` dependency override.
- `test_trap_hits.py::test_migration_adds_columns_to_an_old_database` builds an old-shaped table and calls `add_missing_columns` — it tests the helper being removed.
- `import main` (from `conftest.py`) imports `database.py`, which today creates `backend/eidolon.db` as a side effect (gitignored).

## Plan consequences

- Add `DATABASE_URL` handling in one function; fall back to SQLite only under `EIDOLON_ENV=dev`.
- Models get explicit indexes and timezone-aware timestamp columns; the alert route normalises timestamps to naive UTC so responses stay byte-for-byte the same.
- Alembic owns the schema; no `create_all`, no ALTER helper.
- Retention targets `alerts` only (never `traps`).
