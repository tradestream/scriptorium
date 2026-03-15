"""Notebooks — named cross-book collections of marginalia entries."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Notebook(Base):
    """A named research notebook containing marginalia from any books.

    Inspired by Booklore's Notebooks feature: a user can maintain multiple
    named notebooks (e.g., "Straussian reading of Plato", "Odyssey project")
    that aggregate marginalia entries across books.
    """

    __tablename__ = "notebooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    entries: Mapped[list["NotebookEntry"]] = relationship(
        "NotebookEntry", back_populates="notebook", cascade="all, delete-orphan"
    )


class NotebookEntry(Base):
    """A link from a Notebook to a Marginalium, optionally with a note."""

    __tablename__ = "notebook_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    notebook_id: Mapped[int] = mapped_column(ForeignKey("notebooks.id"), index=True)
    marginalium_id: Mapped[int] = mapped_column(ForeignKey("marginalia.id"), index=True)
    # Optional context note for why this entry is in the notebook
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    notebook: Mapped["Notebook"] = relationship("Notebook", back_populates="entries")

    __table_args__ = (
        UniqueConstraint("notebook_id", "marginalium_id", name="uq_notebook_marginalium"),
    )
