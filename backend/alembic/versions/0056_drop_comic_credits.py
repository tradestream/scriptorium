"""drop unused comic_credits table (unified into work_contributors)

Revision ID: 0056
Revises: 0055
"""
from alembic import op

revision = "0056"
down_revision = "0055"


def upgrade() -> None:
    op.drop_index("ix_comic_credits_unique", table_name="comic_credits")
    op.drop_table("comic_credits")


def downgrade() -> None:
    import sqlalchemy as sa
    op.create_table(
        "comic_credits",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id"), nullable=False, index=True),
        sa.Column("person_id", sa.Integer, sa.ForeignKey("authors.id"), nullable=False, index=True),
        sa.Column("role", sa.String(50), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_comic_credits_unique", "comic_credits", ["work_id", "person_id", "role"], unique=True)
