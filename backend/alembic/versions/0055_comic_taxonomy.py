"""comic taxonomy: story arcs, publishers, imprints, comic credits, reading direction

Revision ID: 0055
Revises: 0054
"""
from alembic import op
import sqlalchemy as sa

revision = "0055"
down_revision = "0054"


def upgrade() -> None:
    # ── Publishers ─────────────────────────────────────────────────────────
    op.create_table(
        "publishers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("logo_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── Imprints (child of publisher) ──────────────────────────────────────
    op.create_table(
        "imprints",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("publisher_id", sa.Integer, sa.ForeignKey("publishers.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── Story Arcs ─────────────────────────────────────────────────────────
    op.create_table(
        "story_arcs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Story arc membership with reading order
    op.create_table(
        "story_arc_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("story_arc_id", sa.Integer, sa.ForeignKey("story_arcs.id"), nullable=False, index=True),
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id"), nullable=False, index=True),
        sa.Column("sequence_number", sa.Float, nullable=True),  # reading order (float for 1.5 inserts)
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── Comic Credits ──────────────────────────────────────────────────────
    op.create_table(
        "comic_credits",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id"), nullable=False, index=True),
        sa.Column("person_id", sa.Integer, sa.ForeignKey("authors.id"), nullable=False, index=True),
        sa.Column("role", sa.String(50), nullable=False, index=True),  # writer, penciler, inker, colorist, letterer, editor, cover_artist
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_comic_credits_unique", "comic_credits", ["work_id", "person_id", "role"], unique=True)

    # ── Add publisher/imprint/reading_direction to works ───────────────────
    with op.batch_alter_table("works") as batch_op:
        batch_op.add_column(sa.Column("publisher_id", sa.Integer, sa.ForeignKey("publishers.id"), nullable=True))
        batch_op.add_column(sa.Column("imprint_id", sa.Integer, sa.ForeignKey("imprints.id"), nullable=True))
        batch_op.add_column(sa.Column("reading_direction", sa.String(5), nullable=True))  # ltr, rtl
        batch_op.add_column(sa.Column("issue_number", sa.String(20), nullable=True))  # "1", "1.5", "Annual 1"
        batch_op.add_column(sa.Column("volume_number", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("page_count_comic", sa.Integer, nullable=True))  # from ComicInfo
        batch_op.add_column(sa.Column("comic_format", sa.String(50), nullable=True))  # TPB, HC, Single Issue, etc.


def downgrade() -> None:
    with op.batch_alter_table("works") as batch_op:
        batch_op.drop_column("comic_format")
        batch_op.drop_column("page_count_comic")
        batch_op.drop_column("volume_number")
        batch_op.drop_column("issue_number")
        batch_op.drop_column("reading_direction")
        batch_op.drop_column("imprint_id")
        batch_op.drop_column("publisher_id")
    op.drop_index("ix_comic_credits_unique", table_name="comic_credits")
    op.drop_table("comic_credits")
    op.drop_table("story_arc_entries")
    op.drop_table("story_arcs")
    op.drop_table("imprints")
    op.drop_table("publishers")
