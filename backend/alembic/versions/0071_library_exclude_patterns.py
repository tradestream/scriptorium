"""libraries.exclude_patterns

Per-library JSON-encoded glob list. Merged with built-in defaults and
optional ``.scriptoriumignore`` file at scan time so scanners and the
ingest watcher can skip junk directories (``__MACOSX``, ``@eaDir``,
``backup/``, ``.tmp``, half-downloaded files) before they ever hit the
hash / metadata / FTS pipeline.

Revision ID: 0071
Revises: 0070
"""
import sqlalchemy as sa
from alembic import op


revision = "0071"
down_revision = "0070"


def upgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.add_column(sa.Column("exclude_patterns", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.drop_column("exclude_patterns")
