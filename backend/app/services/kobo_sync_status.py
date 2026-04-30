"""Kobo sync status management — cleanup when shelves change.

Inspired by Calibre-Web's kobo_sync_status.py. Handles:
- Removing synced-book records when a shelf is un-flagged from Kobo sync
- Archiving books that are no longer on any sync shelf
- Cleaning up orphaned sync records
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def update_sync_shelves(user_id: int, db: AsyncSession) -> dict:
    """Reconcile KoboSyncedBooks with current sync_to_kobo shelves.

    Call this after a shelf's sync_to_kobo flag changes.
    Removes synced-book records for editions no longer on any sync shelf.

    Returns: {"removed": int, "archived": int}
    """
    from app.models.edition import Edition
    from app.models.progress import KoboSyncedBook, KoboSyncToken
    from app.models.shelf import Shelf, ShelfBook

    removed = 0
    archived = 0

    # Get all sync tokens for this user
    token_result = await db.execute(
        select(KoboSyncToken.id).where(KoboSyncToken.user_id == user_id)
    )
    token_ids = [r[0] for r in token_result.all()]
    if not token_ids:
        return {"removed": 0, "archived": 0}

    # Get all edition IDs currently on sync shelves
    sync_shelf_result = await db.execute(
        select(Shelf.id).where(Shelf.user_id == user_id, Shelf.sync_to_kobo == True)
    )
    sync_shelf_ids = [r[0] for r in sync_shelf_result.all()]

    if sync_shelf_ids:
        # Editions on sync shelves (via work_id)
        on_shelf_result = await db.execute(
            select(Edition.id)
            .join(ShelfBook, ShelfBook.work_id == Edition.work_id)
            .where(ShelfBook.shelf_id.in_(sync_shelf_ids))
        )
        on_shelf_edition_ids = set(r[0] for r in on_shelf_result.all())
    else:
        on_shelf_edition_ids = set()

    # Find synced books NOT on any sync shelf anymore
    for token_id in token_ids:
        synced_result = await db.execute(
            select(KoboSyncedBook).where(KoboSyncedBook.sync_token_id == token_id)
        )
        for synced_book in synced_result.scalars().all():
            if synced_book.edition_id not in on_shelf_edition_ids:
                await db.delete(synced_book)
                removed += 1

    if removed:
        logger.info("Removed %d stale synced-book records for user %d", removed, user_id)

    return {"removed": removed, "archived": archived}


async def on_shelf_sync_changed(shelf_id: int, user_id: int, db: AsyncSession) -> None:
    """Called when a shelf's sync_to_kobo flag changes.

    Triggers a reconciliation pass to clean up synced-book records.
    """
    await update_sync_shelves(user_id, db)


async def on_book_removed_from_shelf(
    shelf_id: int,
    work_id: int,
    user_id: int,
    db: AsyncSession,
) -> None:
    """Called when a book is removed from a sync shelf.

    Checks if the book is still on any other sync shelf; if not,
    removes it from KoboSyncedBooks so the device gets a removal event.
    """
    from app.models.edition import Edition
    from app.models.progress import KoboSyncedBook, KoboSyncToken
    from app.models.shelf import Shelf, ShelfBook

    # Check: is the book still on any other sync shelf?
    still_synced = await db.execute(
        select(ShelfBook.id)
        .join(Shelf, Shelf.id == ShelfBook.shelf_id)
        .where(
            ShelfBook.work_id == work_id,
            Shelf.user_id == user_id,
            Shelf.sync_to_kobo == True,
        )
    )
    if still_synced.scalar_one_or_none():
        return  # Still on another sync shelf — no action needed

    # Find edition IDs for this work
    edition_result = await db.execute(
        select(Edition.id).where(Edition.work_id == work_id)
    )
    edition_ids = [r[0] for r in edition_result.all()]
    if not edition_ids:
        return

    # Remove from KoboSyncedBooks
    token_result = await db.execute(
        select(KoboSyncToken.id).where(KoboSyncToken.user_id == user_id)
    )
    token_ids = [r[0] for r in token_result.all()]

    for token_id in token_ids:
        await db.execute(
            delete(KoboSyncedBook).where(
                KoboSyncedBook.sync_token_id == token_id,
                KoboSyncedBook.edition_id.in_(edition_ids),
            )
        )

    logger.debug("Removed synced-book records for work %d (user %d)", work_id, user_id)
