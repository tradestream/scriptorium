# Forward reference — Work is defined in work.py and imported after Base is set up.
# TYPE_CHECKING import avoids circular imports at runtime.
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.work import Work

# ── Compatibility aliases ──────────────────────────────────────────────────────
# The books/book_files/book_contributors tables were dropped in migration 0034.
# These aliases let existing import sites continue to compile while the
# individual API files are updated to use Edition/Work directly.
# Remove these once all callers have been migrated.
from app.models.edition import (  # noqa: F401, E402, I001
    Edition as Book,
    EditionContributor as BookContributor,
    EditionFile as BookFile,
)
from app.models.work import (  # noqa: F401, E402, I001
    work_authors as book_authors,
    work_series as book_series,
    work_tags as book_tags,
)


class Author(Base):
    """Author model."""

    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    works: Mapped[list["Work"]] = relationship(
        "Work", secondary="work_authors", back_populates="authors"
    )


class Tag(Base):
    """Tag model for book categorization."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    works: Mapped[list["Work"]] = relationship(
        "Work", secondary="work_tags", back_populates="tags"
    )


class Series(Base):
    """Series model for book series."""

    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    works: Mapped[list["Work"]] = relationship(
        "Work", secondary="work_series", back_populates="series"
    )
