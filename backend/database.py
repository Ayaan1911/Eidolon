"""SQLite-backed storage for the trap mechanism.

Phase 1 is deliberately ephemeral — the Mirror's breach/photo/repo checks never
persist anything server-side. Traps are the intentional exception: the entire
point of a trap is a durable log of who walked into it, so trap and alert
records are stored for real here instead of living only in a request/response
cycle.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
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


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trap_id = Column(String, nullable=False)
    ip = Column(String)
    location = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    isp = Column(String)
    browser = Column(String)
    os = Column(String)
    device = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
