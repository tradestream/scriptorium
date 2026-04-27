"""create unified progress schema (reading_states, edition_positions, device_positions)

Step 1 of the unified-progress migration. Creates the three new tables
empty. Does not touch any existing reading-state tables and changes no
runtime behavior — backfill (0067) and the read-path switch land
separately.

Design: ``personal/design/unified_progress_schema.md``.

Revision ID: 0066
Revises: 0065
"""
from alembic import op
import sqlalchemy as sa

revision = "0066"
down_revision = "0065"


def upgrade() -> None:
    op.create_table(
        "reading_states",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "work_id",
            sa.Integer,
            sa.ForeignKey("works.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="want_to_read",
        ),
        sa.Column("times_started", sa.Integer, nullable=False, server_default="0"),
        sa.Column("times_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("last_opened", sa.DateTime, nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("review", sa.Text, nullable=True),
        sa.Column(
            "total_time_seconds", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint("user_id", "work_id", name="uq_reading_state_user_work"),
    )

    op.create_table(
        "edition_positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "edition_id",
            sa.Integer,
            sa.ForeignKey("editions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("current_format", sa.String(32), nullable=True),
        sa.Column("current_value", sa.String(2048), nullable=True),
        sa.Column("current_pct", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "current_device_id", sa.Integer, sa.ForeignKey("devices.id"), nullable=True
        ),
        sa.Column("current_updated_at", sa.DateTime, nullable=True),
        sa.Column("furthest_format", sa.String(32), nullable=True),
        sa.Column("furthest_value", sa.String(2048), nullable=True),
        sa.Column("furthest_pct", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("furthest_updated_at", sa.DateTime, nullable=True),
        sa.Column("furthest_reset_at", sa.DateTime, nullable=True),
        sa.Column("total_pages", sa.Integer, nullable=True),
        sa.Column(
            "time_spent_seconds", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint(
            "user_id", "edition_id", name="uq_edition_position_user_edition"
        ),
    )

    op.create_table(
        "device_positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "edition_id",
            sa.Integer,
            sa.ForeignKey("editions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "device_id",
            sa.Integer,
            sa.ForeignKey("devices.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("value", sa.String(2048), nullable=False),
        sa.Column("pct", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("raw_payload", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "edition_id",
            "device_id",
            name="uq_device_position_user_edition_device",
        ),
    )


def downgrade() -> None:
    op.drop_table("device_positions")
    op.drop_table("edition_positions")
    op.drop_table("reading_states")
