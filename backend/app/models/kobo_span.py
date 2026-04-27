"""KoboSpan id map for KEPUB round-tripping."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class KoboSpanMap(Base):
    """Per-chapter sequence of koboSpan ids extracted from a generated KEPUB.

    kepubify wraps every paragraph/sentence in ``<span class="koboSpan"
    id="kobo.N.M">``; Kobo Nickel reports reading position back to us using
    those ids in ``CurrentBookmark.Location.Value``. Without a stored map we
    cannot interpret an incoming bookmark or place the cursor at a real
    paragraph when emitting one.

    Keyed by EditionFile (the source EPUB whose .kepub_path holds the
    generated KEPUB) plus spine index. A ``span_ids`` payload is the JSON
    array of koboSpan ids in document order for one spine document.
    """

    __tablename__ = "kobo_span_maps"
    __table_args__ = (
        UniqueConstraint(
            "edition_file_id", "spine_index", name="uq_span_map_file_spine"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_file_id: Mapped[int] = mapped_column(
        ForeignKey("edition_files.id", ondelete="CASCADE"), index=True
    )
    spine_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_href: Mapped[str] = mapped_column(String(512), nullable=False)
    span_ids: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
