"""Comic-specific models: publishers, imprints, story arcs, credits.

Provides the Publisher → Imprint → Series → Volume → Issue hierarchy
used by comic collections, plus story arc tracking with reading order
and granular credit roles (writer, penciler, inker, colorist, etc.).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Publisher(Base):
    """Comic book publisher (DC, Marvel, Image, Dark Horse, etc.)."""

    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    imprints: Mapped[list["Imprint"]] = relationship("Imprint", back_populates="publisher")


class Imprint(Base):
    """Publisher imprint (e.g. Vertigo under DC, Icon under Marvel)."""

    __tablename__ = "imprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    publisher: Mapped["Publisher"] = relationship("Publisher", back_populates="imprints")


class StoryArc(Base):
    """A story arc spanning multiple issues/works (e.g. Crisis on Infinite Earths)."""

    __tablename__ = "story_arcs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    entries: Mapped[list["StoryArcEntry"]] = relationship(
        "StoryArcEntry", back_populates="story_arc", order_by="StoryArcEntry.sequence_number"
    )


class StoryArcEntry(Base):
    """A work's position within a story arc (with reading order)."""

    __tablename__ = "story_arc_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_arc_id: Mapped[int] = mapped_column(ForeignKey("story_arcs.id"), index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    sequence_number: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    story_arc: Mapped["StoryArc"] = relationship("StoryArc", back_populates="entries")


class ComicCredit(Base):
    """A credit role for a person on a comic work.

    Roles: writer, penciler, inker, colorist, letterer, editor, cover_artist
    Uses the existing Author table for person identity.
    """

    __tablename__ = "comic_credits"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), index=True)
    role: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


# Valid comic credit roles
COMIC_ROLES = [
    "writer",
    "penciler",
    "inker",
    "colorist",
    "letterer",
    "editor",
    "cover_artist",
]
