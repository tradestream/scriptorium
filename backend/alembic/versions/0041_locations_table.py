"""Add locations table and location_id FK on editions.

Revision ID: 0041
Revises: 0040
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_locations_parent_id", "locations", ["parent_id"])

    op.add_column("editions", sa.Column("location_id", sa.Integer, nullable=True))
    op.create_index("ix_editions_location_id", "editions", ["location_id"])


def downgrade() -> None:
    op.drop_index("ix_editions_location_id", table_name="editions")
    op.drop_column("editions", "location_id")
    op.drop_index("ix_locations_parent_id", table_name="locations")
    op.drop_table("locations")
