"""external identifiers (multi-source: Metron, CVDB, etc.)

Revision ID: 0057
Revises: 0056
"""
from alembic import op
import sqlalchemy as sa

revision = "0057"
down_revision = "0056"


def upgrade() -> None:
    op.create_table(
        "external_identifiers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id"), nullable=False, index=True),
        sa.Column("source", sa.String(50), nullable=False, index=True),  # metron, cvdb, comicvine, mal, anilist, etc.
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=True),  # direct link to the source page
        sa.Column("priority", sa.Integer, default=0),  # higher = preferred
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_ext_id_unique", "external_identifiers", ["work_id", "source", "external_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ext_id_unique", table_name="external_identifiers")
    op.drop_table("external_identifiers")
