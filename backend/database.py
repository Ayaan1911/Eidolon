"""SQLite-backed storage for the trap mechanism.

Phase 1 is deliberately ephemeral — the Mirror's breach/photo/repo checks never
persist anything server-side. Traps are the intentional exception: the entire
point of a trap is a durable log of who walked into it, so trap and alert
records are stored for real here instead of living only in a request/response
cycle.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from db_config import database_url, is_sqlite

# Connection settings for Postgres (Neon). Named so the reason for each number is next to it.
POOL_SIZE = 3  # a few connections are plenty; the free plan only allows a handful in total
MAX_OVERFLOW = 2  # extra connections allowed during a burst, closed again afterwards
POOL_RECYCLE_SECONDS = 300  # Neon suspends an idle database after 5 minutes: retire connections before that
CONNECT_TIMEOUT_SECONDS = 10  # waking a suspended database takes a few seconds; do not wait forever


def build_engine(url: str):
    if is_sqlite(url):
        # SQLite is for local development and tests only. The flag lets FastAPI's worker threads share it.
        return create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
    return create_engine(
        url,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_recycle=POOL_RECYCLE_SECONDS,
        # Before lending out a pooled connection, send a cheap "are you alive" query; a connection
        # that went stale while the database was suspended is replaced instead of failing a request.
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


engine = build_engine(database_url())
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class Trap(Base):
    __tablename__ = "traps"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    trigger_count = Column(Integer, default=0)
    # Set when a trap is deployed from a dossier finding rather than the standalone Trap Lab.
    source_type = Column(String, nullable=True)
    context = Column(String, nullable=True)
    # A stable hash of the finding it was deployed for (repo:file:line:type) - lets a
    # rescan recognize "this finding already has a trap" without a database of findings.
    finding_id = Column(String, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trap_id = Column(String, nullable=False)
    ip = Column(String)
    location = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    isp = Column(String)
    org = Column(String, nullable=True)
    asn = Column(String, nullable=True)
    browser = Column(String)
    os = Column(String)
    device = Column(String)
    referer = Column(String, nullable=True)
    # Only set on hits that came from the fake login form being submitted.
    # password_attempted stays NULL for a plain page load; the password itself
    # is never stored, only whether one was typed and how long it was.
    email = Column(String, nullable=True)
    password_attempted = Column(Boolean, nullable=True)
    password_length = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


# Temporary until Alembic takes over (next commit): never build tables on a real Postgres at import.
if is_sqlite(str(engine.url)):
    Base.metadata.create_all(engine)

# create_all never alters an existing table, so a database created before these
# columns existed needs them added in place.
_ADDED_COLUMNS = {
    "alerts": {
        "org": "VARCHAR",
        "asn": "VARCHAR",
        "referer": "VARCHAR",
        "email": "VARCHAR",
        "password_attempted": "BOOLEAN",
        "password_length": "INTEGER",
    },
    "traps": {
        "finding_id": "VARCHAR",
    },
}


def add_missing_columns(bind) -> None:
    inspector = inspect(bind)
    for table, columns in _ADDED_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        with bind.begin() as conn:
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


if is_sqlite(str(engine.url)):
    add_missing_columns(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
