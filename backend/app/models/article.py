"""Article model — web articles saved via Instapaper for read-later on Kobo.

Articles are per-user (each family member has their own Instapaper account).
They share the tagging system with books but live in a separate table.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Article(Base):
    """A web article saved for later reading."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Instapaper sync
    instapaper_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True, index=True)
    instapaper_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Content
    url: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Reading state
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 - 1.0
    progress_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Cached markdown content (from Instapaper get_text)
    markdown_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Instapaper folder (null = main list, which syncs to Kobo)
    folder: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    saved_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User")
    tags: Mapped[list["ArticleTag"]] = relationship(
        "ArticleTag", back_populates="article", cascade="all, delete-orphan"
    )
    highlights: Mapped[list["ArticleHighlight"]] = relationship(
        "ArticleHighlight", back_populates="article", cascade="all, delete-orphan"
    )


class ArticleTag(Base):
    """Tag association for articles (uses the same Tag table as books)."""

    __tablename__ = "article_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), index=True)

    article: Mapped["Article"] = relationship("Article", back_populates="tags")


class ArticleHighlight(Base):
    """A highlight made on an article (imported from Instapaper)."""

    __tablename__ = "article_highlights"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    instapaper_highlight_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True)
    text: Mapped[str] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    article: Mapped["Article"] = relationship("Article", back_populates="highlights")
