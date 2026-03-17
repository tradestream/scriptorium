"""Add articles tables and Instapaper OAuth fields on users.

Revision ID: 0046
Revises: 0045
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Instapaper credentials on users
    op.add_column("users", sa.Column("instapaper_username", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("instapaper_password", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("instapaper_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("instapaper_secret", sa.String(255), nullable=True))

    # Articles table
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("instapaper_id", sa.Integer, nullable=True),
        sa.Column("instapaper_hash", sa.String(64), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("progress", sa.Float, server_default="0"),
        sa.Column("progress_timestamp", sa.DateTime, nullable=True),
        sa.Column("is_starred", sa.Boolean, server_default="0"),
        sa.Column("is_archived", sa.Boolean, server_default="0"),
        sa.Column("markdown_content", sa.Text, nullable=True),
        sa.Column("folder", sa.String(255), nullable=True),
        sa.Column("saved_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_articles_user_id", "articles", ["user_id"])
    op.create_index("ix_articles_instapaper_id", "articles", ["instapaper_id"], unique=True)

    # Article tags
    op.create_table(
        "article_tags",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("tag_id", sa.Integer, sa.ForeignKey("tags.id"), nullable=False),
    )
    op.create_index("ix_article_tags_article_id", "article_tags", ["article_id"])
    op.create_index("ix_article_tags_tag_id", "article_tags", ["tag_id"])

    # Article highlights
    op.create_table(
        "article_highlights",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("instapaper_highlight_id", sa.Integer, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("position", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_article_highlights_article_id", "article_highlights", ["article_id"])


def downgrade() -> None:
    op.drop_table("article_highlights")
    op.drop_table("article_tags")
    op.drop_table("articles")
    op.drop_column("users", "instapaper_secret")
    op.drop_column("users", "instapaper_token")
    op.drop_column("users", "instapaper_password")
    op.drop_column("users", "instapaper_username")
