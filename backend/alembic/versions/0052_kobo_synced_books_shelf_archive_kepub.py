"""kobo_synced_books lookup, shelf_archive for bidirectional sync, kepub support

Revision ID: 0052
Revises: 0051
"""
from alembic import op
import sqlalchemy as sa

revision = "0052"
down_revision = "0051"


def upgrade() -> None:
    # ── KoboSyncedBooks lookup table (Calibre-Web pattern) ────────────────
    op.create_table(
        "kobo_synced_books",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sync_token_id", sa.Integer, sa.ForeignKey("kobo_sync_tokens.id"), nullable=False, index=True),
        sa.Column("edition_id", sa.Integer, sa.ForeignKey("editions.id"), nullable=False, index=True),
        sa.Column("synced_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kobo_synced_unique", "kobo_synced_books", ["sync_token_id", "edition_id"], unique=True)

    # ── Shelf archive for bidirectional sync (device→server) ──────────────
    op.create_table(
        "kobo_shelf_archive",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("kobo_tag_id", sa.String(255), nullable=False),  # device-side tag ID
        sa.Column("shelf_id", sa.Integer, sa.ForeignKey("shelves.id"), nullable=True),  # linked local shelf
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # ── KEPUB tracking on edition_files ────────────────────────────────────
    with op.batch_alter_table("edition_files") as batch_op:
        batch_op.add_column(sa.Column("kepub_path", sa.String(512), nullable=True))
        batch_op.add_column(sa.Column("kepub_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("edition_files") as batch_op:
        batch_op.drop_column("kepub_hash")
        batch_op.drop_column("kepub_path")
    op.drop_table("kobo_shelf_archive")
    op.drop_index("ix_kobo_synced_unique", table_name="kobo_synced_books")
    op.drop_table("kobo_synced_books")
