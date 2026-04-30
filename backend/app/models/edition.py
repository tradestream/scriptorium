"""Edition model — a specific physical or digital copy of a Work."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Edition(Base):
    """A specific physical or digital copy of a Work.

    Edition-level data: ISBN, publisher, published date, format, page count,
    cover image, file attachments, translator credits, and ABS link.
    The household can own multiple editions of the same Work (e.g. paperback
    and Kindle) without duplicating work-level metadata.
    """

    __tablename__ = "editions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Preserved from the source Book.uuid so Kobo sync URLs stay stable
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    library_id: Mapped[int] = mapped_column(ForeignKey("libraries.id"), index=True)

    # Edition-specific bibliographic data
    isbn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    isbn_10: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    asin: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Language override — set when this edition is a translation
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Primary format label (epub, pdf, cbz, mobi, physical, audiobook, …)
    format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Cover image stored on disk as {uuid}.{cover_format}
    cover_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cover_format: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Dominant color extracted from cover (hex, e.g. "#3B82F6")
    cover_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)

    # JSON array of field names locked from enrichment edits
    locked_fields: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # External system links
    abs_item_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    physical_copy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    # Physical book details
    binding: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # hardcover, paperback, mass_market, etc.
    condition: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # new, like_new, good, fair, poor
    purchase_price: Mapped[Optional[float]] = mapped_column(nullable=True)
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    purchase_from: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Physical location tracking
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # legacy free-text
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)

    # True after bulk identifier extraction has scanned this edition's files
    identifiers_scanned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    # True after OPF/ComicInfo embedded metadata extraction
    opf_scanned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    # True if the EPUB declares rendition:layout=pre-paginated (children's
    # books, manga, photo books, comics-as-EPUB). Affects Kobo format
    # advertisement (EPUB3FL) and skips KEPUB conversion for these titles.
    is_fixed_layout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    @property
    def reading_status(self) -> None:
        """Stub for BookRead schema — actual value is injected by the list endpoint."""
        return None

    # ── Relationships ─────────────────────────────────────────────────────────
    work: Mapped["Work"] = relationship("Work", back_populates="editions")
    library: Mapped["Library"] = relationship("Library", back_populates="editions")
    location_ref: Mapped[Optional["Location"]] = relationship(
        "Location", back_populates="editions", foreign_keys=[location_id]
    )
    files: Mapped[list["EditionFile"]] = relationship(
        "EditionFile", back_populates="edition", cascade="all, delete-orphan"
    )
    contributors: Mapped[list["EditionContributor"]] = relationship(
        "EditionContributor", back_populates="edition", cascade="all, delete-orphan"
    )
    loans: Mapped[list["Loan"]] = relationship(
        "Loan", back_populates="edition", cascade="all, delete-orphan"
    )

    @property
    def translators(self) -> list[str]:
        return [c.name for c in self.contributors if c.role == "translator"]

    @property
    def location_name(self) -> Optional[str]:
        """Return the location tree path, or the legacy free-text location."""
        if self.location_ref:
            return self.location_ref.tree_path
        return self.location

    # ── BookRead compatibility properties ────────────────────────────────────
    # These delegate to self.work so BookRead.model_validate(edition) works.
    @property
    def title(self) -> str:
        return self.work.title

    @property
    def subtitle(self) -> Optional[str]:
        return self.work.subtitle

    @property
    def description(self) -> Optional[str]:
        return self.work.description

    @property
    def authors(self):
        return self.work.authors

    @property
    def tags(self):
        return self.work.tags

    @property
    def series(self):
        return self.work.series

    @property
    def esoteric_enabled(self) -> bool:
        return self.work.esoteric_enabled

    @property
    def lexile(self) -> Optional[int]:
        return self.work.lexile

    @property
    def lexile_code(self) -> Optional[str]:
        return self.work.lexile_code

    @property
    def ar_level(self) -> Optional[float]:
        return self.work.ar_level

    @property
    def ar_points(self) -> Optional[float]:
        return self.work.ar_points

    @property
    def flesch_kincaid_grade(self) -> Optional[float]:
        return self.work.flesch_kincaid_grade

    @property
    def age_range(self) -> Optional[str]:
        return self.work.age_range

    @property
    def interest_level(self) -> Optional[str]:
        return self.work.interest_level

    @property
    def goodreads_id(self) -> Optional[str]:
        return self.work.goodreads_id

    @property
    def google_id(self) -> Optional[str]:
        return self.work.google_id

    @property
    def hardcover_id(self) -> Optional[str]:
        return self.work.hardcover_id

    @property
    def goodreads_rating(self) -> Optional[float]:
        return self.work.goodreads_rating

    @property
    def goodreads_rating_count(self) -> Optional[int]:
        return self.work.goodreads_rating_count

    @property
    def amazon_rating(self) -> Optional[float]:
        return self.work.amazon_rating

    @property
    def amazon_rating_count(self) -> Optional[int]:
        return self.work.amazon_rating_count

    @property
    def editors(self) -> list[str]:
        return [c.name for c in self.work.contributors if c.role == "editor"]

    @property
    def illustrators(self) -> list[str]:
        return [c.name for c in self.work.contributors if c.role == "illustrator"]

    @property
    def colorists(self) -> list[str]:
        return [c.name for c in self.work.contributors if c.role == "colorist"]


class EditionFile(Base):
    """A file attached to an Edition (EPUB, PDF, CBZ, KEPUB, etc.).

    One edition may have multiple files of different formats — e.g. the
    original EPUB plus a converted KEPUB for the Kobo.
    """

    __tablename__ = "edition_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(10), index=True)
    file_path: Mapped[str] = mapped_column(String(512), unique=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    file_size: Mapped[int] = mapped_column()
    # KEPUB conversion cache (for Kobo sync)
    kepub_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    kepub_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    edition: Mapped["Edition"] = relationship("Edition", back_populates="files")


class EditionContributor(Base):
    """Edition-level contributor (translator)."""

    __tablename__ = "edition_contributors"

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), index=True)  # translator

    edition: Mapped["Edition"] = relationship("Edition", back_populates="contributors")


class Loan(Base):
    """Records the lending of a specific Edition.

    Lend to an internal user (loaned_to_user_id) or an external person
    (loaned_to_name free text). Exactly one of the two should be set.
    """

    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), index=True)

    # Recipient — internal user xor free-text name
    loaned_to_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    loaned_to_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    loaned_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    due_back: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    edition: Mapped["Edition"] = relationship("Edition", back_populates="loans")
