from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

MARGINALIUM_KINDS = (
    "observation",  # default — general note
    "insight",      # interpretive insight
    "question",     # open question for future reading
    "theme",        # thematic note
    "symbol",       # symbolic interpretation
    "character",    # character analysis
    "parallel",     # reference to a parallel passage elsewhere
    "structure",    # structural / formal observation
    "context",      # historical or cultural context
    "esoteric",     # Straussian / hidden-meaning reading
    "boring",       # Strauss's Fifth Key — boring passages hide dynamite
)

# Depth of reading at which the note was made (from Melzer/Strauss levels)
READING_LEVELS = (
    "surface",    # literal / plot-level reading
    "exoteric",   # conventional public teaching
    "esoteric",   # hidden philosophical teaching
    "meta",       # about the text's own self-presentation
)


class Marginalium(Base):
    """A Scriptorium-native scholarly note on a book passage.

    Distinct from device-synced Annotations (Kobo highlights/notes/bookmarks).
    Supports richer kinds and cross-referencing.
    """

    __tablename__ = "marginalia"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), index=True)

    # Kind of scholarly note
    kind: Mapped[str] = mapped_column(String(30), default="observation", index=True)

    # The note body
    content: Mapped[str] = mapped_column(Text)

    # Passage location (EPUB CFI, "page:N", chapter label, line ref, etc.)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    chapter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # JSON array of location strings linking to related passages
    related_refs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Comma-separated or JSON-style freeform tags
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Reading depth: surface | exoteric | esoteric | meta
    reading_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Attribution — for notes quoting external commentators (e.g. "Leo Strauss")
    commentator: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Source citation (book title, article, page number, etc.)
    source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
