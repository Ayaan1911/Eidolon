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

engine = create_engine("sqlite:///eidolon.db", connect_args={"check_same_thread": False})
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


add_missing_columns(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
