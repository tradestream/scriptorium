"""Full-text search service using SQLite FTS5."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, Work

# Standalone FTS5 table — no content= backing so SQLite never reads the
# books table for columns that don't exist there (like authors).
# We manage all content manually through index_book / deindex_book.
FTS_TABLE_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(
    title,
    description,
    authors,
    isbn,
    tokenize='unicode61'
);
"""

# Trigger: keep the FTS index consistent when a work row is deleted.
# Title/author updates are handled explicitly by index_work() in scanner.py.
FTS_TRIGGERS_DDL = [
    """
    CREATE TRIGGER IF NOT EXISTS works_fts_delete
    BEFORE DELETE ON works BEGIN
        INSERT INTO books_fts(books_fts, rowid, title, description, authors, isbn)
        VALUES ('delete', old.id, old.title, COALESCE(old.description,''), '', '');
    END;
    """,
]


async def ensure_fts(conn) -> None:
    """Create the standalone FTS5 table if it doesn't exist or has wrong schema."""
    # Detect the old content-table version by checking for 'content' in the DDL.
    # If it exists as a content-table, drop it so we can create the standalone version.
    row = await conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='books_fts'"
    )
    existing_sql = (row.fetchone() or (None,))[0] or ""
    if "content=" in existing_sql:
        # Old content-table schema — drop and recreate
        await conn.exec_driver_sql("DROP TABLE IF EXISTS books_fts")
        await conn.exec_driver_sql("DROP TRIGGER IF EXISTS books_fts_insert")
        await conn.exec_driver_sql("DROP TRIGGER IF EXISTS books_fts_update")

    await conn.exec_driver_sql(FTS_TABLE_DDL)  # IF NOT EXISTS — safe to call always
    # Drop the old books-table trigger if it still exists (books table was dropped in 0034)
    await conn.exec_driver_sql("DROP TRIGGER IF EXISTS books_fts_delete")
    for ddl in FTS_TRIGGERS_DDL:
        await conn.exec_driver_sql(ddl)


class SearchService:
    """Full-text search over books using SQLite FTS5."""

    async def index_book(self, db: AsyncSession, book: Book, author_names: list[str]) -> None:
        """Insert or replace a book's entry in the FTS index (including authors)."""
        authors_str = " ".join(author_names)
        # Delete existing entry first (content table syncs via triggers for basic
        # fields, but authors are denormalised here so we update manually)
        await db.execute(
            text(
                "INSERT INTO books_fts(books_fts, rowid, title, description, authors, isbn) "
                "VALUES ('delete', :id, :title, :desc, :authors, :isbn)"
            ),
            {
                "id": book.id,
                "title": book.title or "",
                "desc": book.description or "",
                "authors": authors_str,
                "isbn": book.isbn or "",
            },
        )
        await db.execute(
            text(
                "INSERT INTO books_fts(rowid, title, description, authors, isbn) "
                "VALUES (:id, :title, :desc, :authors, :isbn)"
            ),
            {
                "id": book.id,
                "title": book.title or "",
                "desc": book.description or "",
                "authors": authors_str,
                "isbn": book.isbn or "",
            },
        )

    async def index_work(self, db: AsyncSession, work: Work, author_names: list[str]) -> None:
        """Insert or replace a Work's entry in the FTS index (keyed on work.id)."""
        authors_str = " ".join(author_names)
        # Collect ISBNs from editions for searchability
        from sqlalchemy import select as _sel
        from app.models import Edition
        isbn_rows = await db.execute(
            _sel(Edition.isbn, Edition.isbn_10).where(Edition.work_id == work.id, Edition.isbn.isnot(None))
        )
        isbn_parts = []
        for r in isbn_rows:
            if r[0]:
                isbn_parts.append(r[0])
            if r[1]:
                isbn_parts.append(r[1])
        isbn_str = " ".join(isbn_parts)

        await db.execute(
            text(
                "INSERT INTO books_fts(books_fts, rowid, title, description, authors, isbn) "
                "VALUES ('delete', :id, :title, :desc, :authors, :isbn)"
            ),
            {"id": work.id, "title": work.title or "", "desc": work.description or "",
             "authors": authors_str, "isbn": isbn_str},
        )
        await db.execute(
            text(
                "INSERT INTO books_fts(rowid, title, description, authors, isbn) "
                "VALUES (:id, :title, :desc, :authors, :isbn)"
            ),
            {"id": work.id, "title": work.title or "", "desc": work.description or "",
             "authors": authors_str, "isbn": isbn_str},
        )

    async def deindex_work(self, db: AsyncSession, work: Work) -> None:
        """Remove a Work from the FTS index."""
        await db.execute(
            text(
                "INSERT INTO books_fts(books_fts, rowid, title, description, authors, isbn) "
                "VALUES ('delete', :id, :title, :desc, '', '')"
            ),
            {"id": work.id, "title": work.title or "", "desc": work.description or ""},
        )

    async def deindex_book(self, db: AsyncSession, book: Book) -> None:
        """Remove a book from the FTS index."""
        await db.execute(
            text(
                "INSERT INTO books_fts(books_fts, rowid, title, description, authors, isbn) "
                "VALUES ('delete', :id, :title, :desc, '', :isbn)"
            ),
            {
                "id": book.id,
                "title": book.title or "",
                "desc": book.description or "",
                "isbn": book.isbn or "",
            },
        )

    async def search(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 50,
        offset: int = 0,
        library_id: int | None = None,
    ) -> tuple[list[Book], int]:
        """Search books using FTS5, optionally filtered by library."""
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from app.models.edition import Edition
        from app.models.work import Work

        # Escape FTS5 special characters in user query, then add prefix wildcard
        fts_query = _build_fts_query(query)

        # FTS rowids are work.id values (set by index_work)
        fts_sql = text(
            "SELECT rowid FROM books_fts WHERE books_fts MATCH :q "
            "ORDER BY rank LIMIT :limit OFFSET :offset"
        )
        result = await db.execute(fts_sql, {"q": fts_query, "limit": limit, "offset": offset})
        work_ids = [row[0] for row in result]

        if not work_ids:
            return [], 0

        # Count total matches
        count_sql = text("SELECT COUNT(*) FROM books_fts WHERE books_fts MATCH :q")
        total = (await db.scalar(count_sql, {"q": fts_query})) or 0

        # Fetch Edition records for matching works, preserving FTS rank order
        from sqlalchemy import case
        from app.models.library import Library

        visible_lib_ids = select(Library.id).where(Library.is_hidden == False)
        stmt = (
            select(Edition)
            .join(Edition.work)
            .where(Edition.work_id.in_(work_ids))
            .where(Edition.library_id.in_(visible_lib_ids))
            .options(
                joinedload(Edition.work).options(
                    joinedload(Work.authors),
                    joinedload(Work.tags),
                    joinedload(Work.series),
                    joinedload(Work.contributors),
                ),
                joinedload(Edition.files),
                joinedload(Edition.contributors),
            )
        )
        if library_id is not None:
            stmt = stmt.where(Edition.library_id == library_id)

        # Preserve FTS rank order by work_id position
        order_case = case(
            {work_id: idx for idx, work_id in enumerate(work_ids)},
            value=Edition.work_id,
        )
        stmt = stmt.order_by(order_case)

        books_result = await db.execute(stmt)
        books = list(books_result.unique().scalars().all())

        return books, total

    async def rebuild_index(self, db: AsyncSession) -> int:
        """Rebuild the entire FTS index from the works table."""
        from sqlalchemy import select as _sel
        from sqlalchemy.orm import joinedload
        from app.models.edition import Edition
        from app.models.work import Work

        # Standalone FTS5 table supports regular DELETE
        await db.execute(text("DELETE FROM books_fts"))

        stmt = _sel(Work).options(joinedload(Work.authors), joinedload(Work.editions))
        result = await db.execute(stmt)
        works = result.unique().scalars().all()

        for work in works:
            author_names = [a.name for a in work.authors]
            isbn_str = " ".join(e.isbn for e in work.editions if e.isbn)
            await db.execute(
                text(
                    "INSERT INTO books_fts(rowid, title, description, authors, isbn) "
                    "VALUES (:id, :title, :desc, :authors, :isbn)"
                ),
                {
                    "id": work.id,
                    "title": work.title or "",
                    "desc": work.description or "",
                    "authors": " ".join(author_names),
                    "isbn": isbn_str,
                },
            )

        await db.commit()
        return len(works)


def _build_fts_query(query: str) -> str:
    """Convert a user query string into a safe FTS5 MATCH expression."""
    # Strip FTS5 special chars that could cause syntax errors
    safe = query.replace('"', "").replace("'", "").strip()
    if not safe:
        return '""'
    # Quote each token and add * for prefix matching
    tokens = safe.split()
    return " ".join(f'"{t}"*' for t in tokens)


search_service = SearchService()
