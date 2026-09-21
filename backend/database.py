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
_ADDED_ALERT_COLUMNS = {
    "org": "VARCHAR",
    "asn": "VARCHAR",
    "referer": "VARCHAR",
    "email": "VARCHAR",
    "password_attempted": "BOOLEAN",
    "password_length": "INTEGER",
}


def add_missing_alert_columns(bind) -> None:
    existing = {c["name"] for c in inspect(bind).get_columns("alerts")}
    with bind.begin() as conn:
        for name, ddl in _ADDED_ALERT_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE alerts ADD COLUMN {name} {ddl}"))


add_missing_alert_columns(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
