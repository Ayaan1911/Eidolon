"""baseline schema: the traps and alerts tables exactly as the models define them

Production data is disposable, so this migration only creates tables; it copies nothing.
It replaces the old create_all + ALTER TABLE helper, so every column that helper used to add
(org, asn, referer, email, password_attempted, password_length, finding_id) is simply here.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "traps",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("finding_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_traps"),
    )
    # Looked up on every repo scan ("does this finding already have a trap?").
    op.create_index("ix_traps_finding_id", "traps", ["finding_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trap_id", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("isp", sa.String(), nullable=True),
        sa.Column("org", sa.String(), nullable=True),
        sa.Column("asn", sa.String(), nullable=True),
        sa.Column("browser", sa.String(), nullable=True),
        sa.Column("os", sa.String(), nullable=True),
        sa.Column("device", sa.String(), nullable=True),
        sa.Column("referer", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("password_attempted", sa.Boolean(), nullable=True),
        sa.Column("password_length", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_alerts"),
    )
    # Deleting or counting one trap's alerts.
    op.create_index("ix_alerts_trap_id", "alerts", ["trap_id"])
    # The alert list sorts newest first; the retention job deletes by age.
    op.create_index("ix_alerts_timestamp", "alerts", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_alerts_timestamp", table_name="alerts")
    op.drop_index("ix_alerts_trap_id", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_traps_finding_id", table_name="traps")
    op.drop_table("traps")
