"""Delete old trap hits (alerts) so the table cannot grow forever. Traps themselves are never deleted."""

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database import Alert

RETENTION_DAYS_ENV = "RETENTION_DAYS"
DEFAULT_RETENTION_DAYS = 90
# At most this many rows per run, so a big backlog cannot hold up startup. The next start continues.
MAX_DELETED_PER_RUN = 5000

log = logging.getLogger("eidolon.retention")


def retention_days() -> int:
    """RETENTION_DAYS as a positive whole number (default 90), or ValueError."""
    raw = os.environ.get(RETENTION_DAYS_ENV, "").strip()
    if not raw:
        return DEFAULT_RETENTION_DAYS
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(f"{RETENTION_DAYS_ENV} must be a whole number of days, 1 or more")
    return int(raw)


def delete_old_alerts(db: Session, now: datetime | None = None) -> int:
    """Delete up to MAX_DELETED_PER_RUN alerts older than the retention period; return how many."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days())

    # Oldest first, then delete exactly those ids (DELETE ... LIMIT is not portable across databases).
    old_ids = [
        row.id
        for row in db.query(Alert.id).filter(Alert.timestamp < cutoff).order_by(Alert.timestamp).limit(MAX_DELETED_PER_RUN)
    ]
    if not old_ids:
        return 0
    db.query(Alert).filter(Alert.id.in_(old_ids)).delete(synchronize_session=False)
    db.commit()
    log.info("retention: deleted %d old alert rows", len(old_ids))  # the count only, never row contents
    return len(old_ids)
