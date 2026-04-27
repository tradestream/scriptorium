"""drop legacy progress tables (read_progress, kobo_book_states, user_editions)

Step 4 (final) of the unified-progress migration. The unified schema
(reading_states, edition_positions, device_positions) has been the
read source since step 3b and the only write target since step 4.

Downgrade is unsupported: the data was migrated forward in 0067 and
the legacy tables are not maintained from that point on. Rolling back
to a release that still expects them requires a fresh restore from
backup.

Revision ID: 0068
Revises: 0067
"""
from alembic import op


revision = "0068"
down_revision = "0067"


def upgrade() -> None:
    op.drop_table("read_progress")
    op.drop_table("kobo_book_states")
    op.drop_table("user_editions")


def downgrade() -> None:
    raise NotImplementedError(
        "0068 is forward-only. Restore from a pre-0068 backup if you need "
        "the legacy progress tables back; the schema diverged enough that "
        "automated downgrade would silently lose state."
    )
