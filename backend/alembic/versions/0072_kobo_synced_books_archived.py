"""kobo_synced_books.archived_at

Adds device-side archive tracking. When a Kobo deletes a book locally
(DELETE ``/v1/library/{uuid}``), the row is kept but stamped with
``archived_at`` so the next sync pass doesn't re-send the same book.
The user has to explicitly re-add via Scriptorium to clear the flag.

Revision ID: 0072
Revises: 0071
"""
import sqlalchemy as sa
from alembic import op


revision = "0072"
down_revision = "0071"


def upgrade() -> None:
    with op.batch_alter_table("kobo_synced_books") as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_kobo_synced_books_archived_at",
        "kobo_synced_books",
        ["archived_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kobo_synced_books_archived_at",
        table_name="kobo_synced_books",
    )
    with op.batch_alter_table("kobo_synced_books") as batch_op:
        batch_op.drop_column("archived_at")
