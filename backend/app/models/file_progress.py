"""Per-file reading progress — tracks position in individual files."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class FileProgress(Base):
    """Reading position for a specific file (e.g. EPUB, PDF) of an edition."""

    __tablename__ = "file_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    edition_file_id: Mapped[int] = mapped_column(ForeignKey("edition_files.id"), index=True)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    current_page: Mapped[int] = mapped_column(Integer, default=0)
    total_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cfi_position: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    device: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
