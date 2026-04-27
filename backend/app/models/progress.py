from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Device(Base):
    """Device model for syncing reading progress (Kobo, KOReader, etc.)."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    device_type: Mapped[str] = mapped_column(String(50))  # kobo, koreader, calibre, etc.
    device_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    device_id_string: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class KoboSyncToken(Base):
    """Authentication token for Kobo device sync.

    The Kobo protocol uses URL-path-based auth tokens. Each token maps to
    a user and optionally a specific device. The sync_token tracks the
    device's last-known sync state for incremental updates.
    """

    __tablename__ = "kobo_sync_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id"), nullable=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Sync state — tracks what the device has already received
    books_last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    books_last_created: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reading_state_last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    shelves: Mapped[list["KoboTokenShelf"]] = relationship(
        "KoboTokenShelf", cascade="all, delete-orphan"
    )


class KoboTokenShelf(Base):
    """Junction table: which shelves feed into a Kobo sync token.

    If a token has no entries here, all books from visible libraries sync.
    If it has entries, only books on those shelves sync.
    """

    __tablename__ = "kobo_token_shelves"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("kobo_sync_tokens.id"), index=True)
    shelf_id: Mapped[int] = mapped_column(ForeignKey("shelves.id"), index=True)


class KoboSyncedBook(Base):
    """Lookup table: tracks which editions have been sent to a device.

    Calibre-Web pattern — enables O(1) 'already synced?' checks and
    prevents re-sending books on subsequent sync requests.
    """

    __tablename__ = "kobo_synced_books"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_token_id: Mapped[int] = mapped_column(ForeignKey("kobo_sync_tokens.id"), index=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class KoboShelfArchive(Base):
    """Tracks shelves/tags created on the Kobo device for bidirectional sync.

    When a user creates a collection on their Kobo, it syncs back as a shelf
    in Scriptorium. Soft-deleted when the device removes the tag.
    """

    __tablename__ = "kobo_shelf_archive"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kobo_tag_id: Mapped[str] = mapped_column(String(255))
    shelf_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shelves.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    is_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class KOReaderProgress(Base):
    """Reading progress synced from KOReader devices.

    KOReader's Progress Sync plugin sends a document hash + progress string.
    The document key is typically MD5(filename). We store it verbatim so we
    can round-trip it back to the device without requiring book matching.
    """

    __tablename__ = "koreader_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    document: Mapped[str] = mapped_column(String(255), index=True)
    progress: Mapped[str] = mapped_column(String(1024), default="0")
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    device: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class ReadingGoal(Base):
    """Per-user, per-year reading goal (target number of books)."""

    __tablename__ = "reading_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    year: Mapped[int] = mapped_column()
    target_books: Mapped[int] = mapped_column(default=12)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
