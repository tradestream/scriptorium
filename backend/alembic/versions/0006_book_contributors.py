"""Add book_contributors table for translator/editor/illustrator/colorist roles.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "book_contributors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
    )
    op.create_index("ix_book_contributors_book_id", "book_contributors", ["book_id"])
    op.create_index("ix_book_contributors_role", "book_contributors", ["role"])


def downgrade() -> None:
    op.drop_index("ix_book_contributors_role", "book_contributors")
    op.drop_index("ix_book_contributors_book_id", "book_contributors")
    op.drop_table("book_contributors")
