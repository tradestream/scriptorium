"""kobo_bookmarks table for Koblime-style device annotation sync

Revision ID: 0053
Revises: 0052
"""
from alembic import op
import sqlalchemy as sa

revision = "0053"
down_revision = "0052"


def upgrade() -> None:
    op.create_table(
        "kobo_bookmarks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("edition_id", sa.Integer, sa.ForeignKey("editions.id"), nullable=True, index=True),
        # Original Kobo Bookmark table fields
        sa.Column("bookmark_id", sa.String(255), nullable=False),  # Kobo BookmarkID (UUID)
        sa.Column("volume_id", sa.String(512), nullable=False, index=True),  # Kobo ContentID
        sa.Column("text", sa.Text, nullable=True),  # Highlighted passage
        sa.Column("annotation", sa.Text, nullable=True),  # User's note
        sa.Column("start_container_path", sa.String(500), nullable=True),
        sa.Column("start_container_child_index", sa.Integer, nullable=True),
        sa.Column("start_offset", sa.Integer, nullable=True),
        sa.Column("end_container_path", sa.String(500), nullable=True),
        sa.Column("end_container_child_index", sa.Integer, nullable=True),
        sa.Column("end_offset", sa.Integer, nullable=True),
        sa.Column("extra_annotation_data", sa.Text, nullable=True),  # JSON blob
        sa.Column("date_created", sa.DateTime, nullable=True),
        sa.Column("date_modified", sa.DateTime, nullable=True),
        # Sync metadata
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("synced_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kobo_bookmarks_unique", "kobo_bookmarks", ["user_id", "bookmark_id"], unique=True)

    # Content mapping table: Kobo VolumeID → Scriptorium edition
    op.create_table(
        "kobo_content_map",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("volume_id", sa.String(512), nullable=False, unique=True, index=True),
        sa.Column("edition_id", sa.Integer, sa.ForeignKey("editions.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("kobo_content_map")
    op.drop_index("ix_kobo_bookmarks_unique", table_name="kobo_bookmarks")
    op.drop_table("kobo_bookmarks")
