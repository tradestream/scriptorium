"""file-level progress, content restrictions, embedding vectors

Revision ID: 0050
Revises: 0049
"""
from alembic import op
import sqlalchemy as sa

revision = "0050"
down_revision = "0049"


def upgrade() -> None:
    # ── File-level progress ───────────────────────────────────────────────
    op.create_table(
        "file_progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("edition_file_id", sa.Integer, sa.ForeignKey("edition_files.id"), nullable=False, index=True),
        sa.Column("percentage", sa.Float, default=0.0, nullable=False),
        sa.Column("current_page", sa.Integer, default=0, nullable=False),
        sa.Column("total_pages", sa.Integer, nullable=True),
        sa.Column("cfi_position", sa.String(500), nullable=True),  # EPUB CFI
        sa.Column("device", sa.String(50), nullable=True),  # kobo, koreader, browser
        sa.Column("last_read_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # ── Content restrictions ──────────────────────────────────────────────
    # Age rating on works
    with op.batch_alter_table("works") as batch_op:
        batch_op.add_column(sa.Column("age_rating", sa.String(20), nullable=True))  # everyone, teen, mature, adult
        batch_op.add_column(sa.Column("content_rating", sa.String(20), nullable=True))  # G, PG, PG-13, R, X

    # Per-user max age rating
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("max_age_rating", sa.String(20), nullable=True))  # null = unrestricted

    # ── Embedding vectors ─────────────────────────────────────────────────
    with op.batch_alter_table("works") as batch_op:
        batch_op.add_column(sa.Column("embedding", sa.Text, nullable=True))  # JSON array of floats
        batch_op.add_column(sa.Column("search_text", sa.Text, nullable=True))  # composite searchable text


def downgrade() -> None:
    op.drop_table("file_progress")
    with op.batch_alter_table("works") as batch_op:
        batch_op.drop_column("search_text")
        batch_op.drop_column("embedding")
        batch_op.drop_column("content_rating")
        batch_op.drop_column("age_rating")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("max_age_rating")
