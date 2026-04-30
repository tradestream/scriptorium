"""Per-page inventory for comic archives (and eventually PDFs).

Currently the comic-page endpoints (``GET /books/{id}/files/{fid}/pages``
and ``/pages/{n}``) crack open the ZIP and walk ``namelist()`` on every
request. For a 200-page comic that's 200 archive opens per read-through.
This table caches the inventory at scan time so reads become a single
indexed SELECT.

Pattern borrowed from Komga, which exposes per-page metadata (number,
filename, media type, dimensions, size) for both reading and admin
duplicate-detection. We start with the small subset the reader actually
needs (number, filename, media type, size); width / height come later
if the reader grows a needs them.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class EditionFilePage(Base):
    """One archive entry from a CBZ / CBR / future PDF book file."""

    __tablename__ = "edition_file_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_file_id: Mapped[int] = mapped_column(
        ForeignKey("edition_files.id", ondelete="CASCADE"), index=True
    )
    # 1-based page number, matching the existing reader contract.
    page_number: Mapped[int] = mapped_column(Integer)
    # Path *within* the archive (for ZIP) or page index marker (for PDF).
    # Stored verbatim so the reader can hand it back to the archive
    # extractor on demand.
    filename: Mapped[str] = mapped_column(String(1024))
    # Looked up from the file extension — ``image/jpeg``, ``image/png``,
    # ``image/webp``, etc. Stored so the read path doesn't re-derive it.
    media_type: Mapped[str] = mapped_column(String(64))
    # Uncompressed size from ``ZipInfo.file_size``. Optional for PDFs
    # where it's not always cheaply available.
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Image dimensions (decoded). Populated lazily — initial inventory
    # build skips them because decoding every page on import is
    # expensive. The reader can backfill or compute on demand.
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "edition_file_id", "page_number", name="uq_edition_file_page_number"
        ),
        Index(
            "ix_edition_file_pages_file_page",
            "edition_file_id",
            "page_number",
        ),
    )
