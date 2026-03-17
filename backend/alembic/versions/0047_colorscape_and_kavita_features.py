"""Add cover_color (ColorScape), author photo_url, annotation is_spoiler.

Revision ID: 0047
Revises: 0046
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ColorScape — dominant color from cover
    op.add_column("editions", sa.Column("cover_color", sa.String(7), nullable=True))
    # Author photos
    op.add_column("authors", sa.Column("photo_url", sa.String(1024), nullable=True))
    # Annotation spoiler flag
    op.add_column("annotations", sa.Column("is_spoiler", sa.Boolean, server_default="0", nullable=False))
    # Collection pinning
    op.add_column("collections", sa.Column("is_pinned", sa.Boolean, server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("collections", "is_pinned")
    op.drop_column("annotations", "is_spoiler")
    op.drop_column("authors", "photo_url")
    op.drop_column("editions", "cover_color")
