"""Add isbn_10 column and normalize existing ISBNs to ISBN-13.

Revision ID: 0038
Revises: 0037
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def _isbn10_to_isbn13(isbn10: str) -> str:
    """Convert ISBN-10 to ISBN-13 (inline for migration portability)."""
    base = "978" + isbn10[:9]
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(base))
    check = (10 - (total % 10)) % 10
    return base + str(check)


def _isbn13_to_isbn10(isbn13: str) -> str | None:
    """Convert ISBN-13 to ISBN-10 (only for 978 prefix)."""
    if not isbn13.startswith("978"):
        return None
    base = isbn13[3:12]
    total = sum(int(ch) * (10 - i) for i, ch in enumerate(base))
    remainder = (11 - (total % 11)) % 11
    check = "X" if remainder == 10 else str(remainder)
    return base + check


def _clean(raw: str) -> str:
    import re
    return re.sub(r"[\s\-]+", "", raw.strip())


def upgrade() -> None:
    # Add isbn_10 column
    op.add_column("editions", sa.Column("isbn_10", sa.String(10), nullable=True))
    op.create_index("ix_editions_isbn_10", "editions", ["isbn_10"])

    # Backfill: normalize existing ISBNs
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, isbn FROM editions WHERE isbn IS NOT NULL AND isbn != ''")
    ).fetchall()

    for row in rows:
        edition_id, raw_isbn = row[0], _clean(row[1])
        if not raw_isbn:
            continue

        if len(raw_isbn) == 10 and (raw_isbn[:9].isdigit() and (raw_isbn[9].isdigit() or raw_isbn[9] in "xX")):
            # ISBN-10 → convert to ISBN-13, cache original as isbn_10
            isbn13 = _isbn10_to_isbn13(raw_isbn)
            conn.execute(
                sa.text("UPDATE editions SET isbn = :isbn13, isbn_10 = :isbn10 WHERE id = :id"),
                {"isbn13": isbn13, "isbn10": raw_isbn, "id": edition_id},
            )
        elif len(raw_isbn) == 13 and raw_isbn.isdigit():
            # Already ISBN-13 → derive isbn_10 if 978-prefix
            isbn10 = _isbn13_to_isbn10(raw_isbn)
            if isbn10:
                conn.execute(
                    sa.text("UPDATE editions SET isbn_10 = :isbn10 WHERE id = :id"),
                    {"isbn10": isbn10, "id": edition_id},
                )
        # else: non-standard ISBN string, leave as-is


def downgrade() -> None:
    op.drop_index("ix_editions_isbn_10", table_name="editions")
    op.drop_column("editions", "isbn_10")
