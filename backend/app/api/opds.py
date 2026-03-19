"""OPDS 1.2 Catalog — Atom feed server for e-reader compatibility.

Mounted at /opds (not /api/v1) with HTTP Basic Auth.

Feeds:
  GET /opds/catalog                  — root navigation
  GET /opds/books?page=N             — all books (acquisition)
  GET /opds/authors                  — authors navigation
  GET /opds/authors/{id}             — author books (acquisition)
  GET /opds/series                   — series navigation
  GET /opds/series/{id}              — series books (acquisition)
  GET /opds/tags                     — tags navigation
  GET /opds/tags/{id}                — tag books (acquisition)
  GET /opds/search?q=...             — search results (acquisition)
  GET /opds/opensearch.xml           — OpenSearch descriptor
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Author, Book, Series, Tag
from app.models.user import User

router = APIRouter(prefix="/opds", tags=["opds"])

_security = HTTPBasic(realm="Scriptorium", auto_error=False)

PAGE_SIZE = 30

ATOM_NS = "http://www.w3.org/2005/Atom"
OPDS_NS = "http://opds-spec.org/2010/catalog"
DC_NS = "http://purl.org/dc/terms/"
PSE_NS = "http://vaemendis.net/opds-pse/ns"

MIME_NAV = "application/atom+xml;profile=opds-catalog;kind=navigation"
MIME_ACQ = "application/atom+xml;profile=opds-catalog;kind=acquisition"
MIME_EPUB = "application/epub+zip"
MIME_PDF = "application/pdf"
MIME_XML = "application/atom+xml"


# ── Auth ───────────────────────────────────────────────────────────────────────

async def _basic_auth(
    credentials: Optional[HTTPBasicCredentials] = Depends(_security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """HTTP Basic Auth for OPDS clients."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Basic realm="Scriptorium"'},
        )
    stmt = select(User).where(User.username == credentials.username, User.is_active.is_(True))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="Scriptorium"'},
        )
    from app.services.auth import verify_password
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="Scriptorium"'},
        )
    return user


# ── XML helpers ────────────────────────────────────────────────────────────────

def _feed(feed_id: str, title: str, updated: str, feed_type: str) -> Element:
    feed = Element("feed", {
        "xmlns": ATOM_NS,
        "xmlns:pse": PSE_NS,
        "xmlns:opds": OPDS_NS,
        "xmlns:dc": DC_NS,
    })
    _sub(feed, "id", feed_id)
    _sub(feed, "title", title)
    _sub(feed, "updated", updated)
    author_el = SubElement(feed, "author")
    _sub(author_el, "name", "Scriptorium")
    _link(feed, "/opds/catalog", "start", MIME_NAV)
    _link(feed, "/opds/search?q={searchTerms}", "search",
          "application/opensearchdescription+xml")
    return feed


def _sub(parent: Element, tag: str, text: str) -> Element:
    el = SubElement(parent, tag)
    el.text = text
    return el


def _link(parent: Element, href: str, rel: str, type_: str, **attrs) -> Element:
    return SubElement(parent, "link", href=href, rel=rel, type=type_, **attrs)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _book_updated(book: Book) -> str:
    ts = getattr(book, "updated_at", None) or getattr(book, "created_at", None)
    if ts and not isinstance(ts, str):
        return ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(ts or _now())[:19] + "Z"


def _book_entry(feed: Element, book: Book, base_url: str) -> None:
    entry = SubElement(feed, "entry")
    _sub(entry, "title", book.title)
    _sub(entry, "id", f"urn:uuid:{book.uuid}")
    _sub(entry, "updated", _book_updated(book))

    for author in (book.authors or []):
        ae = SubElement(entry, "author")
        _sub(ae, "name", author.name)

    if book.description:
        s = SubElement(entry, "summary")
        s.text = book.description[:500]

    if book.language:
        l = SubElement(entry, f"{{{DC_NS}}}language")
        l.text = book.language

    if book.published_date:
        d = SubElement(entry, f"{{{DC_NS}}}issued")
        d.text = str(book.published_date)[:10]

    if book.cover_hash:
        _link(entry, f"{base_url}/api/v1/books/{book.id}/cover",
              f"{OPDS_NS}/image", "image/jpeg")
        _link(entry, f"{base_url}/api/v1/books/{book.id}/cover",
              f"{OPDS_NS}/image/thumbnail", "image/jpeg")

    _link(entry, f"/book/{book.id}", "alternate", "text/html", title=book.title)

    for f in (book.files or []):
        fmt = (f.format or "").lower()
        mime = MIME_EPUB if fmt == "epub" else (MIME_PDF if fmt == "pdf" else "application/octet-stream")
        if fmt == "cbz":
            mime = "application/vnd.comicbook+zip"
        elif fmt == "cbr":
            mime = "application/vnd.comicbook-rar"
        _link(entry, f"{base_url}/api/v1/books/{book.id}/download/{f.id}",
              f"{OPDS_NS}/acquisition", mime, title=fmt.upper())

        # OPDS-PSE: page streaming for comics
        if fmt in ("cbz", "cbr"):
            pse_link = _link(
                entry,
                f"{base_url}/api/v1/books/{book.id}/files/{f.id}/pages/{{pageNumber}}",
                "http://vaemendis.net/opds-pse/stream",
                "image/jpeg",
                title="Page Stream",
            )
            pse_link.set("pse:count", str(book.page_count_comic or 0) if hasattr(book, 'page_count_comic') else "0")


def _xml_response(feed: Element) -> Response:
    xml_str = tostring(feed, encoding="unicode")
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    return Response(content=xml_str, media_type=MIME_XML)


def _paginate_links(feed: Element, path: str, page: int, total: int, **extra) -> None:
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    params = "&".join(f"{k}={v}" for k, v in extra.items())
    sep = "&" if params else ""
    _link(feed, f"{path}?page=0{sep}{params}", "first", MIME_ACQ)
    _link(feed, f"{path}?page={pages - 1}{sep}{params}", "last", MIME_ACQ)
    if page > 0:
        _link(feed, f"{path}?page={page - 1}{sep}{params}", "previous", MIME_ACQ)
    if page < pages - 1:
        _link(feed, f"{path}?page={page + 1}{sep}{params}", "next", MIME_ACQ)


def _base_url(request: Request) -> str:
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{scheme}://{host}"


async def _books_page(db: AsyncSession, stmt) -> list[Book]:
    result = await db.execute(
        stmt.options(selectinload(Book.authors), selectinload(Book.files))
    )
    return result.unique().scalars().all()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/opensearch.xml", include_in_schema=False)
async def opensearch_descriptor(request: Request, _user: User = Depends(_basic_auth)):
    base = _base_url(request)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">\n'
        "  <ShortName>Scriptorium</ShortName>\n"
        "  <Description>Search Scriptorium book catalog</Description>\n"
        f'  <Url type="{MIME_ACQ}" template="{base}/opds/search?q={{searchTerms}}&amp;page={{startPage?}}"/>\n'
        f'  <Url type="text/html" template="{base}/search?q={{searchTerms}}"/>\n'
        "</OpenSearchDescription>"
    )
    return Response(content=xml, media_type="application/opensearchdescription+xml")


@router.get("/catalog")
@router.get("")
async def opds_root(request: Request, _user: User = Depends(_basic_auth)):
    """Root OPDS navigation feed."""
    now = _now()
    feed = _feed("urn:scriptorium:catalog", "Scriptorium Library", now, MIME_NAV)
    entries = [
        ("urn:scriptorium:all-books",   "All Books",   "Browse the complete library",     "/opds/books",   MIME_ACQ),
        ("urn:scriptorium:by-author",   "By Author",   "Browse books by author",           "/opds/authors", MIME_NAV),
        ("urn:scriptorium:by-series",   "By Series",   "Browse books by series",           "/opds/series",  MIME_NAV),
        ("urn:scriptorium:by-tag",      "By Tag",      "Browse books by tag or genre",     "/opds/tags",    MIME_NAV),
        ("urn:scriptorium:by-arc",     "Story Arcs",  "Browse comics by story arc",       "/opds/arcs",    MIME_NAV),
        ("urn:scriptorium:search",      "Search",      "Search for books by title/author", "/opds/search?q=", MIME_ACQ),
    ]
    for eid, title, summary, href, mime in entries:
        e = SubElement(feed, "entry")
        _sub(e, "title", title)
        _sub(e, "id", eid)
        _sub(e, "updated", now)
        _sub(e, "summary", summary)
        SubElement(e, "content", type="text").text = summary
        _link(e, href, "subsection", mime)
    return _xml_response(feed)


@router.get("/books")
async def opds_all_books(
    request: Request,
    page: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    base = _base_url(request)
    total = await db.scalar(select(func.count(Book.id))) or 0
    books = await _books_page(
        db,
        select(Book).order_by(Book.title)
        .offset(page * PAGE_SIZE).limit(PAGE_SIZE),
    )
    feed = _feed("urn:scriptorium:all-books", "All Books", _now(), MIME_ACQ)
    _paginate_links(feed, "/opds/books", page, total)
    for book in books:
        _book_entry(feed, book, base)
    return _xml_response(feed)


@router.get("/authors")
async def opds_authors(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    stmt = (
        select(Author, func.count(Book.id).label("cnt"))
        .join(Author.books)
        .group_by(Author.id)
        .order_by(Author.name)
        .limit(500)
    )
    rows = (await db.execute(stmt)).all()
    feed = _feed("urn:scriptorium:authors", "Authors", _now(), MIME_NAV)
    for author, cnt in rows:
        e = SubElement(feed, "entry")
        _sub(e, "title", author.name)
        _sub(e, "id", f"urn:scriptorium:author:{author.id}")
        _sub(e, "updated", _now())
        SubElement(e, "content", type="text").text = f"{cnt} book{'s' if cnt != 1 else ''}"
        _link(e, f"/opds/authors/{author.id}", "subsection", MIME_ACQ)
    return _xml_response(feed)


@router.get("/authors/{author_id}")
async def opds_author_books(
    author_id: int,
    request: Request,
    page: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    base = _base_url(request)
    author = (await db.execute(select(Author).where(Author.id == author_id))).scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    total = await db.scalar(
        select(func.count(Book.id)).where(Book.authors.any(Author.id == author_id))
    ) or 0
    books = await _books_page(
        db,
        select(Book).where(Book.authors.any(Author.id == author_id))
        .order_by(Book.title)
        .offset(page * PAGE_SIZE).limit(PAGE_SIZE),
    )
    feed = _feed(f"urn:scriptorium:author:{author_id}", f"Books by {author.name}", _now(), MIME_ACQ)
    _paginate_links(feed, f"/opds/authors/{author_id}", page, total)
    for book in books:
        _book_entry(feed, book, base)
    return _xml_response(feed)


@router.get("/series")
async def opds_series(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    stmt = (
        select(Series, func.count(Book.id).label("cnt"))
        .join(Series.books)
        .group_by(Series.id)
        .order_by(Series.name)
        .limit(500)
    )
    rows = (await db.execute(stmt)).all()
    feed = _feed("urn:scriptorium:series", "Series", _now(), MIME_NAV)
    for series, cnt in rows:
        e = SubElement(feed, "entry")
        _sub(e, "title", series.name)
        _sub(e, "id", f"urn:scriptorium:series:{series.id}")
        _sub(e, "updated", _now())
        SubElement(e, "content", type="text").text = f"{cnt} book{'s' if cnt != 1 else ''}"
        _link(e, f"/opds/series/{series.id}", "subsection", MIME_ACQ)
    return _xml_response(feed)


@router.get("/series/{series_id}")
async def opds_series_books(
    series_id: int,
    request: Request,
    page: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    base = _base_url(request)
    series = (await db.execute(select(Series).where(Series.id == series_id))).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    total = await db.scalar(
        select(func.count(Book.id)).where(Book.series.any(Series.id == series_id))
    ) or 0
    books = await _books_page(
        db,
        select(Book).where(Book.series.any(Series.id == series_id))
        .order_by(Book.title)
        .offset(page * PAGE_SIZE).limit(PAGE_SIZE),
    )
    feed = _feed(f"urn:scriptorium:series:{series_id}", series.name, _now(), MIME_ACQ)
    _paginate_links(feed, f"/opds/series/{series_id}", page, total)
    for book in books:
        _book_entry(feed, book, base)
    return _xml_response(feed)


@router.get("/tags")
async def opds_tags(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    stmt = (
        select(Tag, func.count(Book.id).label("cnt"))
        .join(Tag.books)
        .group_by(Tag.id)
        .order_by(Tag.name)
        .limit(500)
    )
    rows = (await db.execute(stmt)).all()
    feed = _feed("urn:scriptorium:tags", "Tags", _now(), MIME_NAV)
    for tag, cnt in rows:
        e = SubElement(feed, "entry")
        _sub(e, "title", tag.name)
        _sub(e, "id", f"urn:scriptorium:tag:{tag.id}")
        _sub(e, "updated", _now())
        SubElement(e, "content", type="text").text = f"{cnt} book{'s' if cnt != 1 else ''}"
        _link(e, f"/opds/tags/{tag.id}", "subsection", MIME_ACQ)
    return _xml_response(feed)


@router.get("/tags/{tag_id}")
async def opds_tag_books(
    tag_id: int,
    request: Request,
    page: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    base = _base_url(request)
    tag = (await db.execute(select(Tag).where(Tag.id == tag_id))).scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    total = await db.scalar(
        select(func.count(Book.id)).where(Book.tags.any(Tag.id == tag_id))
    ) or 0
    books = await _books_page(
        db,
        select(Book).where(Book.tags.any(Tag.id == tag_id))
        .order_by(Book.title)
        .offset(page * PAGE_SIZE).limit(PAGE_SIZE),
    )
    feed = _feed(f"urn:scriptorium:tag:{tag_id}", tag.name, _now(), MIME_ACQ)
    _paginate_links(feed, f"/opds/tags/{tag_id}", page, total)
    for book in books:
        _book_entry(feed, book, base)
    return _xml_response(feed)


@router.get("/arcs")
async def opds_story_arcs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    """OPDS navigation feed listing story arcs."""
    from app.models.comic import StoryArc, StoryArcEntry
    arcs = (await db.execute(
        select(StoryArc).order_by(StoryArc.name)
    )).scalars().all()

    feed = _feed("urn:scriptorium:arcs", "Story Arcs", _now(), MIME_NAV)
    for arc in arcs:
        e = SubElement(feed, "entry")
        _sub(e, "title", arc.name)
        _sub(e, "id", f"urn:scriptorium:arc:{arc.id}")
        _sub(e, "updated", _now())
        if arc.description:
            _sub(e, "summary", arc.description)
        _link(e, f"/opds/arcs/{arc.id}", "subsection", MIME_ACQ)
    return _xml_response(feed)


@router.get("/arcs/{arc_id}")
async def opds_story_arc_books(
    arc_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    """OPDS acquisition feed for books in a story arc (reading order)."""
    from app.models.comic import StoryArc, StoryArcEntry
    arc = (await db.execute(select(StoryArc).where(StoryArc.id == arc_id))).scalar_one_or_none()
    if not arc:
        raise HTTPException(status_code=404, detail="Story arc not found")

    base = _base_url(request)
    stmt = (
        select(Book)
        .join(StoryArcEntry, StoryArcEntry.work_id == Book.work_id)
        .where(StoryArcEntry.story_arc_id == arc_id)
        .options(selectinload(Book.work).options(selectinload(Work.authors)), selectinload(Book.files))
        .order_by(StoryArcEntry.sequence_number.nulls_last(), Book.title)
    )
    books = (await db.execute(stmt)).unique().scalars().all()

    feed = _feed(f"urn:scriptorium:arc:{arc_id}", arc.name, _now(), MIME_ACQ)
    for book in books:
        _book_entry(feed, book, base)
    return _xml_response(feed)


@router.get("/search")
async def opds_search(
    request: Request,
    q: str = Query(""),
    page: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_basic_auth),
):
    base = _base_url(request)
    feed = _feed(f'urn:scriptorium:search:{q}', f'Search: "{q}"', _now(), MIME_ACQ)

    if not q.strip():
        return _xml_response(feed)

    try:
        from app.services.search import search_service
        books, total = await search_service.search(db, q, limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    except Exception:
        pattern = f"%{q}%"
        total = await db.scalar(
            select(func.count(Book.id)).where(Book.title.ilike(pattern))
        ) or 0
        books = await _books_page(
            db,
            select(Book).where(Book.title.ilike(pattern))
            .offset(page * PAGE_SIZE).limit(PAGE_SIZE),
        )

    _paginate_links(feed, "/opds/search", page, total, q=q)
    for book in books:
        _book_entry(feed, book, base)
    return _xml_response(feed)
