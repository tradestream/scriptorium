"""External identifiers — links works to external databases.

Supports multiple sources per work with priority-based selection:
Metron, ComicVine (CVDB), MyAnimeList, AniList, MangaDex, etc.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ExternalIdentifier(Base):
    """A link from a Work to an external database."""

    __tablename__ = "external_identifiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


# Known sources with URL templates
SOURCE_URLS = {
    "metron": "https://metron.cloud/issue/{id}/",
    "comicvine": "https://comicvine.gamespot.com/issue/4000-{id}/",
    "mal": "https://myanimelist.net/manga/{id}",
    "anilist": "https://anilist.co/manga/{id}",
    "mangadex": "https://mangadex.org/title/{id}",
    "goodreads": "https://www.goodreads.com/book/show/{id}",
    "google": "https://books.google.com/books?id={id}",
    "hardcover": "https://hardcover.app/books/{id}",
    "openlibrary": "https://openlibrary.org/works/{id}",
}
