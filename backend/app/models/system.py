"""System-wide single-row settings table."""

from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class SystemSettings(Base):
    """Single-row table for app-wide mutable settings (id always = 1)."""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    naming_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    naming_pattern: Mapped[str] = mapped_column(String(500), default="{authors}/{title}")
    # Enrichment API keys (override env vars; null = use env)
    hardcover_api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    comicvine_api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    google_books_api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    isbndb_api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    amazon_cookie: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    librarything_api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
