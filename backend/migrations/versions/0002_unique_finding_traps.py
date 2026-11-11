"""Enforce one trap per finding without deleting existing traps or breaking their URLs."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
        connection.execute(sa.text("LOCK TABLE traps IN SHARE ROW EXCLUSIVE MODE"))
    traps = sa.table("traps", sa.column("finding_id"))
    duplicate = connection.execute(
        sa.select(traps.c.finding_id).where(traps.c.finding_id.is_not(None))
        .group_by(traps.c.finding_id).having(sa.func.count() > 1).limit(1)
    ).first()
    if duplicate:
        raise RuntimeError("Duplicate finding associations exist. Back up and resolve them before migrating; no trap records were changed.")
    # Keep lookup/enforcement coverage even on SQLite's non-transactional DDL.
    op.create_index("ux_traps_finding_id", "traps", ["finding_id"], unique=True, if_not_exists=True)
    op.drop_index("ix_traps_finding_id", table_name="traps")


def downgrade():
    op.create_index("ix_traps_finding_id", "traps", ["finding_id"], if_not_exists=True)
    op.drop_index("ux_traps_finding_id", table_name="traps")
