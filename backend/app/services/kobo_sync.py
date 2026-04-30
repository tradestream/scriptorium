"""Kobo device sync service.

Implements the reverse-engineered Kobo store sync protocol so Kobo e-readers
can sync their library, reading progress, and bookmarks with Scriptorium
instead of Kobo's official cloud.

The protocol uses URL-path-based auth tokens (not headers) and exchanges JSON
payloads that mirror the Kobo storeapi.kobo.com responses.

References:
  - Calibre-Web kobo.py (most mature Python implementation)
  - Komga Kobo sync
  - BookLore Kobo integration
"""

import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Book, BookFile, Edition, EditionFile, Library, Work
from app.models.progress import (
    Device,
    KoboSyncedBook,
    KoboSyncToken,
    KoboTokenShelf,
)
from app.models.shelf import ShelfBook

logger = logging.getLogger(__name__)

# Number of books per sync page (Kobo devices expect pagination)
SYNC_PAGE_SIZE = 10  # Small pages like BookLore (5-10) for Kobo device compatibility


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _kobo_timestamp(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime as Kobo-compatible ISO 8601 string."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Token Management
# ---------------------------------------------------------------------------

async def generate_sync_token(
    user_id: int,
    db: AsyncSession,
    device_id: Optional[int] = None,
    shelf_ids: Optional[list[int]] = None,
) -> KoboSyncToken:
    """Generate a new Kobo sync auth token for a user.

    Any ``shelf_ids`` provided are filtered to the requesting user's own
    shelves before being attached — without this, a user could attach another
    user's shelves and sync their books to a Kobo device.
    """
    token_str = secrets.token_hex(32)

    sync_token = KoboSyncToken(
        user_id=user_id,
        device_id=device_id,
        token=token_str,
        is_active=True,
    )
    db.add(sync_token)
    await db.flush()

    if shelf_ids:
        from app.models.shelf import Shelf

        owned_rows = await db.execute(
            select(Shelf.id).where(
                Shelf.id.in_(shelf_ids), Shelf.user_id == user_id
            )
        )
        owned_ids = {row[0] for row in owned_rows.all()}
        for sid in shelf_ids:
            if sid in owned_ids:
                db.add(KoboTokenShelf(token_id=sync_token.id, shelf_id=sid))

    await db.commit()
    await db.refresh(sync_token)
    return sync_token


async def revoke_sync_token_for_user(
    token_id: int, user_id: int, db: AsyncSession
) -> bool:
    """Revoke a sync token, but only if it belongs to ``user_id``.

    Returns True if the token was revoked, False if it does not exist or
    belongs to another user. Callers should treat False as 404 to avoid
    leaking token-id existence across accounts.
    """
    stmt = select(KoboSyncToken).where(
        KoboSyncToken.id == token_id,
        KoboSyncToken.user_id == user_id,
    )
    result = await db.execute(stmt)
    sync_token = result.scalar_one_or_none()
    if sync_token:
        sync_token.is_active = False
        await db.commit()
        return True
    return False


async def validate_sync_token(
    token: str,
    db: AsyncSession,
) -> Optional[KoboSyncToken]:
    """Validate a Kobo sync token and return it if active."""
    stmt = select(KoboSyncToken).where(
        KoboSyncToken.token == token,
        KoboSyncToken.is_active == True,
    )
    result = await db.execute(stmt)
    sync_token = result.scalar_one_or_none()

    if sync_token:
        sync_token.last_used = _utcnow()
        await db.commit()

    return sync_token


async def list_user_sync_tokens(
    user_id: int,
    db: AsyncSession,
) -> list[KoboSyncToken]:
    """List all sync tokens for a user."""
    stmt = select(KoboSyncToken).where(
        KoboSyncToken.user_id == user_id
    ).order_by(KoboSyncToken.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def build_initialization_response(auth_token: str, base_url: str) -> dict:
    """Build the /v1/initialization response.

    Returns the full Kobo Resources object (matching what the real Kobo store
    returns) with our library/image/tags URLs overriding the store defaults.
    This prevents devices from rejecting the response due to missing fields.
    """
    kobo_base = f"{base_url}/kobo/{auth_token}"

    # Full Kobo Resources object — based on BookLore's reverse-engineered template.
    # We override library_sync, image_host, image_url_*, and tags with our URLs.
    resources = {
        "account_page": "https://www.kobo.com/account/settings",
        "account_page_rakuten": "https://my.rakuten.co.jp/",
        "add_device": "https://storeapi.kobo.com/v1/user/add-device",
        "add_entitlement": "https://storeapi.kobo.com/v1/library/{RevisionIds}",
        "affiliaterequest": "https://storeapi.kobo.com/v1/affiliate",
        "audiobook_landing_page": "https://www.kobo.com/{region}/{language}/audiobooks",
        "authorproduct_recommendations": "https://storeapi.kobo.com/v1/products/books/authors/recommendations",
        "autocomplete": "https://storeapi.kobo.com/v1/products/autocomplete",
        "book": "https://storeapi.kobo.com/v1/products/books/{ProductId}",
        "book_detail_page": "https://www.kobo.com/{region}/{language}/ebook/{slug}",
        "book_landing_page": "https://www.kobo.com/ebooks",
        "book_subscription": "https://storeapi.kobo.com/v1/products/books/subscriptions",
        "categories": "https://storeapi.kobo.com/v1/categories",
        "categories_page": "https://www.kobo.com/ebooks/categories",
        "category": "https://storeapi.kobo.com/v1/categories/{CategoryId}",
        "category_featured_lists": "https://storeapi.kobo.com/v1/categories/{CategoryId}/featured",
        "category_products": "https://storeapi.kobo.com/v1/categories/{CategoryId}/products",
        "configuration_data": "https://storeapi.kobo.com/v1/configuration",
        "content_access_book": "https://storeapi.kobo.com/v1/products/books/{ProductId}/access",
        "daily_deal": "https://storeapi.kobo.com/v1/products/dailydeal",
        "deals": "https://storeapi.kobo.com/v1/deals",
        "delete_entitlement": "https://storeapi.kobo.com/v1/library/{Ids}",
        "delete_tag": "https://storeapi.kobo.com/v1/library/tags/{TagId}",
        "delete_tag_items": "https://storeapi.kobo.com/v1/library/tags/{TagId}/items/delete",
        "device_auth": "https://storeapi.kobo.com/v1/auth/device",
        "device_refresh": "https://storeapi.kobo.com/v1/auth/refresh",
        "dictionary_host": "https://ereaderfiles.kobo.com",
        "discovery_host": "https://discovery.kobobooks.com",
        "eula_page": "https://www.kobo.com/termsofuse?style=onestore",
        "exchange_auth": "https://storeapi.kobo.com/v1/auth/exchange",
        "external_book": "https://storeapi.kobo.com/v1/products/books/external/{Ids}",
        "featured_list": "https://storeapi.kobo.com/v1/products/featured/{FeaturedListId}",
        "featured_lists": "https://storeapi.kobo.com/v1/products/featured",
        "get_download_keys": "https://storeapi.kobo.com/v1/library/downloadkeys",
        "get_download_link": "https://storeapi.kobo.com/v1/library/downloadlink",
        "get_tests_request": "https://storeapi.kobo.com/v1/analytics/gettests",
        "gpb_flow_enabled": "False",
        "help_page": "https://www.kobo.com/help",
        "kobo_audiobooks_enabled": "False",
        "kobo_display_price": "False",
        "kobo_nativeborrow_enabled": "False",
        "kobo_onestorelibrary_enabled": "False",
        "kobo_redeem_enabled": "False",
        "kobo_shelfie_enabled": "False",
        "kobo_subscriptions_enabled": "False",
        "kobo_superpoints_enabled": "False",
        "kobo_wishlist_enabled": "False",
        "library_book": "https://storeapi.kobo.com/v1/user/library/books/{LibraryItemId}",
        "library_items": "https://storeapi.kobo.com/v1/user/library",
        "library_metadata": "https://storeapi.kobo.com/v1/library/{Ids}/metadata",
        "library_prices": "https://storeapi.kobo.com/v1/user/library/previews/prices",
        "library_search": "https://storeapi.kobo.com/v1/library/search",
        "love_dashboard_page": "https://www.kobo.com/{region}/{language}/kobosuperpoints",
        "magazine_landing_page": "https://www.kobo.com/emagazines",
        "notebooks": "https://storeapi.kobo.com/api/internal/notebooks",
        "notifications_registration_issue": "https://storeapi.kobo.com/v1/notifications/registration",
        "oauth_host": "https://oauth.kobo.com",
        "password_retrieval_page": "https://www.kobo.com/passwordretrieval.html",
        "post_analytics_event": "https://storeapi.kobo.com/v1/analytics/event",
        "privacy_page": "https://www.kobo.com/privacypolicy?style=onestore",
        "product_nextread": "https://storeapi.kobo.com/v1/products/{ProductIds}/nextread",
        "product_prices": "https://storeapi.kobo.com/v1/products/{ProductIds}/prices",
        "product_recommendations": "https://storeapi.kobo.com/v1/products/{ProductId}/recommendations",
        "product_reviews": "https://storeapi.kobo.com/v1/products/{ProductIds}/reviews",
        "products": "https://storeapi.kobo.com/v1/products",
        "rating": "https://storeapi.kobo.com/v1/products/{ProductId}/rating/{Rating}",
        "reading_services_host": "https://readingservices.kobo.com",
        "registration_page": "https://authorize.kobo.com/signup?returnUrl=http://kobo.com/",
        "related_items": "https://storeapi.kobo.com/v1/products/{Id}/related",
        "remaining_book_series": "https://storeapi.kobo.com/v1/products/books/series/{SeriesId}",
        "rename_tag": "https://storeapi.kobo.com/v1/library/tags/{TagId}",
        "review": "https://storeapi.kobo.com/v1/products/reviews/{ReviewId}",
        "search": "https://storeapi.kobo.com/v1/products",
        "sign_in_page": "https://auth.kobobooks.com/ActivateOnWeb",
        "social_authorization_host": "https://social.kobobooks.com:8443",
        "social_host": "https://social.kobobooks.com",
        "store_home": "www.kobo.com/{region}/{language}",
        "store_host": "www.kobo.com",
        "store_newreleases": "https://www.kobo.com/{region}/{language}/List/new-releases/961XUjtsU0qxkFItWOutGA",
        "store_search": "https://www.kobo.com/{region}/{language}/Search?Query={query}",
        "store_top50": "https://www.kobo.com/{region}/{language}/ebooks/Top",
        "tag_items": "https://storeapi.kobo.com/v1/library/tags/{TagId}/Items",
        "taste_profile": "https://storeapi.kobo.com/v1/products/tasteprofile",
        "update_accessibility_to_preview": "https://storeapi.kobo.com/v1/library/{EntitlementIds}/preview",
        "use_one_store": "True",
        "user_loyalty_benefits": "https://storeapi.kobo.com/v1/user/loyalty/benefits",
        "user_platform": "https://storeapi.kobo.com/v1/user/platform",
        "user_profile": "https://storeapi.kobo.com/v1/user/profile",
        "user_ratings": "https://storeapi.kobo.com/v1/user/ratings",
        "user_recommendations": "https://storeapi.kobo.com/v1/user/recommendations",
        "user_reviews": "https://storeapi.kobo.com/v1/user/reviews",
        "user_wishlist": "https://storeapi.kobo.com/v1/user/wishlist",
        "userguide_host": "https://ereaderfiles.kobo.com",
        "wishlist_page": "https://www.kobo.com/{region}/{language}/account/wishlist",
    }

    # Override all library-operation URLs. The v3.0.24 config that
    # produced 32 content rows on the device used the FULL override set.
    # Stripping to Komga's minimal set (v3.0.30) broke entitlement
    # processing — zero rows. Komga's minimal approach only works because
    # Komga proxies unhandled requests to the real Kobo store; we don't.
    resources["library_sync"] = f"{kobo_base}/v1/library/sync"
    resources["library_items"] = f"{kobo_base}/v1/library/{{ItemId}}"
    resources["library_metadata"] = f"{kobo_base}/v1/library/{{Ids}}/metadata"
    resources["library_book"] = f"{kobo_base}/v1/library/{{LibraryItemId}}"
    resources["reading_state"] = f"{kobo_base}/v1/library/{{ItemId}}/state"
    resources["image_host"] = base_url
    resources["image_url_quality_template"] = (
        f"{base_url}/covers/{{ImageId}}/{{Width}}/{{Height}}/false/image.jpg"
    )
    resources["image_url_template"] = f"{base_url}/covers/{{ImageId}}/image.jpg"
    resources["tags"] = f"{kobo_base}/v1/library/tags"
    # FastAPI paths are case-sensitive; advertise lowercase so the
    # device follows what the routes actually expose. The previous
    # template used uppercase ``/Items`` and would 404 on older
    # firmware that follows the advertised URL literally.
    resources["tag_items"] = f"{kobo_base}/v1/library/tags/{{TagId}}/items"
    resources["delete_tag"] = f"{kobo_base}/v1/library/tags/{{TagId}}"
    resources["delete_tag_items"] = f"{kobo_base}/v1/library/tags/{{TagId}}/items/delete"

    return {"Resources": resources}


# ---------------------------------------------------------------------------
# Library Sync — Edition-first
# ---------------------------------------------------------------------------

async def get_sync_payload(
    sync_token: KoboSyncToken,
    db: AsyncSession,
    base_url: str,
) -> tuple[list[dict], bool]:
    """Build the /v1/library/sync response payload.

    Queries Edition rows (joined to their Work for metadata).
    Falls back to Book rows for instances that haven't been migrated yet.
    """
    user_id = sync_token.user_id

    # Resolve shelves to sync: token-attached shelves + all user shelves with sync_to_kobo=True
    shelf_rows = await db.execute(
        select(KoboTokenShelf.shelf_id).where(KoboTokenShelf.token_id == sync_token.id)
    )
    token_shelf_ids = [row[0] for row in shelf_rows]

    # Also include any shelf the user has flagged for Kobo sync
    from app.models.shelf import Shelf
    kobo_shelf_rows = await db.execute(
        select(Shelf.id).where(Shelf.user_id == user_id, Shelf.sync_to_kobo == True)
    )
    kobo_sync_ids = [row[0] for row in kobo_shelf_rows]
    # Merge: union of token shelves and sync_to_kobo shelves
    token_shelf_ids = list(set(token_shelf_ids + kobo_sync_ids))

    # Per-user library access: a token only sees libraries its user can access.
    # See api/auth.py:get_accessible_library_ids — None means admin (no filter).
    from app.api.auth import get_accessible_library_ids
    from app.models.user import User as _User

    sync_user = await db.get(_User, user_id)
    if sync_user is None:
        return [], False
    accessible_lib_ids = await get_accessible_library_ids(db, sync_user)

    # Query editions joined to their work
    stmt = (
        select(Edition)
        .join(Library, Edition.library_id == Library.id)
        .options(
            selectinload(Edition.files),
            selectinload(Edition.work).options(
                selectinload(Work.authors),
                selectinload(Work.series),
            ),
        )
        .order_by(Edition.updated_at.desc())
    )
    if accessible_lib_ids is not None:
        stmt = stmt.where(Edition.library_id.in_(accessible_lib_ids))

    # Shelf filter: include editions whose work is on one of the token's shelves.
    # Only apply if the shelves actually have books — otherwise sync everything
    # from visible libraries (the pre-shelf-filter behavior).
    if token_shelf_ids:
        has_books = await db.scalar(
            select(ShelfBook.id).where(ShelfBook.shelf_id.in_(token_shelf_ids)).limit(1)
        )
        if has_books:
            stmt = stmt.where(
                select(ShelfBook.work_id)
                .where(
                    ShelfBook.work_id == Edition.work_id,
                    ShelfBook.shelf_id.in_(token_shelf_ids),
                )
                .exists()
        )

    is_incremental = bool(sync_token.books_last_modified)

    if is_incremental:
        # Incremental: only books changed since last sync, AND not
        # archived by the device. Without the archive filter an
        # ``Edition.updated_at`` bump (cover refresh, metadata enrich)
        # silently re-emits a book the user already deleted from the
        # device, which is exactly what the device-side delete is
        # supposed to prevent.
        stmt = stmt.where(Edition.updated_at > sync_token.books_last_modified).where(
            ~select(KoboSyncedBook.id)
            .where(
                KoboSyncedBook.sync_token_id == sync_token.id,
                KoboSyncedBook.edition_id == Edition.id,
                KoboSyncedBook.archived_at.is_not(None),
            )
            .exists()
        )
    else:
        # Initial sync: exclude books already sent (KoboSyncedBooks
        # lookup). Archived rows count as "already sent" for this
        # purpose — the inner subquery doesn't restrict on
        # ``archived_at``, so any synced row (active or archived)
        # blocks re-emission.
        stmt = stmt.where(
            ~select(KoboSyncedBook.id)
            .where(
                KoboSyncedBook.sync_token_id == sync_token.id,
                KoboSyncedBook.edition_id == Edition.id,
            )
            .exists()
        )

    stmt = stmt.limit(SYNC_PAGE_SIZE + 1)

    result = await db.execute(stmt)
    editions = list(result.scalars().all())

    has_more = len(editions) > SYNC_PAGE_SIZE
    if has_more:
        editions = editions[:SYNC_PAGE_SIZE]

    # Batch-fetch unified progress rows for these editions (and their works).
    from app.models.reading import EditionPosition as _EP
    from app.models.reading import ReadingState as _RS

    edition_ids = [e.id for e in editions]
    work_ids = [e.work_id for e in editions if e.work_id is not None]

    ep_map: dict[int, _EP] = {}
    rs_map: dict[int, _RS] = {}
    if edition_ids:
        for ep in (
            await db.execute(
                select(_EP).where(
                    _EP.user_id == user_id, _EP.edition_id.in_(edition_ids)
                )
            )
        ).scalars().all():
            ep_map[ep.edition_id] = ep
    if work_ids:
        for rs in (
            await db.execute(
                select(_RS).where(_RS.user_id == user_id, _RS.work_id.in_(work_ids))
            )
        ).scalars().all():
            rs_map[rs.work_id] = rs

    # Pull the per-work series position from the ``work_series`` association
    # so the Series block we emit carries a real number. Without this Kobo
    # gets ``"Number": "0"`` for every book and can't sort series collections
    # correctly. One book per series is the common case, so we just take the
    # first row per work.
    series_position_map: dict[int, float] = {}
    if work_ids:
        from app.models.work import work_series as _ws

        for row in (
            await db.execute(
                select(_ws.c.work_id, _ws.c.position)
                .where(_ws.c.work_id.in_(work_ids))
                .where(_ws.c.position.is_not(None))
            )
        ).all():
            # First-write wins — work_series can have multiple entries per
            # work (rare; arc/sub-series). Kobo only supports one series.
            series_position_map.setdefault(row.work_id, float(row.position))

    items = []
    # Per-edition is_new is driven by books_last_created, NOT by whether
    # the sync itself is incremental. A book added in the interval between
    # two incremental syncs is still a NewEntitlement to the device.
    books_last_created = sync_token.books_last_created
    for edition in editions:
        epub_file = _get_kobo_compatible_file_edition(edition.files)
        if not epub_file:
            continue

        edition_is_new = (
            books_last_created is None
            or (edition.created_at and edition.created_at > books_last_created)
        )

        ep = ep_map.get(edition.id)
        rs = rs_map.get(edition.work_id) if edition.work_id is not None else None

        # Resolve a real KoboSpan id for the bookmark when we have one
        # extracted from this edition's KEPUB. Falls back inside
        # _build_reading_state to chapter-only restore otherwise.
        span_chapter_href, span_id = await _resolve_emit_span(
            ep, list(edition.files or []), db
        )

        entry = _build_edition_entry(
            edition=edition,
            edition_file=epub_file,
            ep=ep,
            rs=rs,
            auth_token=sync_token.token,
            base_url=base_url,
            is_new=edition_is_new,
            span_chapter_href=span_chapter_href,
            span_id=span_id,
            series_position=series_position_map.get(edition.work_id) if edition.work_id else None,
        )
        items.append(entry)

    # ── Separate ChangedReadingState for books whose state changed but
    # whose Edition record did not (so they aren't in `editions` above).
    # CWA L340-353: only emit ChangedReadingState when the book is NOT in
    # the current entitlement batch, otherwise the device sees duplicates.
    if is_incremental and sync_token.reading_state_last_modified is not None:
        batch_edition_ids = set(edition_ids)
        # Synced editions for this token, archive-filtered: the device
        # has explicitly removed archived books locally, and a fresh
        # ChangedReadingState would silently bring them back.
        synced_ids_result = await db.execute(
            select(KoboSyncedBook.edition_id).where(
                KoboSyncedBook.sync_token_id == sync_token.id,
                KoboSyncedBook.archived_at.is_(None),
            )
        )
        synced_ids = {row[0] for row in synced_ids_result}
        candidate_ids = synced_ids - batch_edition_ids
        if candidate_ids:
            # Pull EditionPositions for any candidate that has changed since
            # the last sync, joined with their Edition for span lookup.
            extra_rows = (
                await db.execute(
                    select(_EP, Edition)
                    .join(Edition, Edition.id == _EP.edition_id)
                    .options(selectinload(Edition.files))
                    .where(
                        _EP.user_id == user_id,
                        _EP.edition_id.in_(candidate_ids),
                        _EP.current_updated_at
                        > sync_token.reading_state_last_modified,
                    )
                )
            ).all()
            for ep, ed in extra_rows:
                rs = (
                    await db.execute(
                        select(_RS).where(
                            _RS.user_id == user_id, _RS.work_id == ed.work_id
                        )
                    )
                ).scalar_one_or_none() if ed.work_id is not None else None
                span_chapter_href, span_id = await _resolve_emit_span(
                    ep, list(ed.files or []), db
                )
                items.append(
                    {
                        "ChangedReadingState": {
                            "ReadingState": _build_reading_state(
                                ed.uuid,
                                ep=ep,
                                rs=rs,
                                span_chapter_href=span_chapter_href,
                                span_id=span_id,
                            )
                        }
                    }
                )

    # ── Removal detection ───────────────────────────────────────────
    # Three flavours, all incremental-only (the initial sync hasn't
    # established a baseline yet):
    #
    #   a) ORPHAN — Edition deleted entirely. We have no uuid to send,
    #      so we silently delete the KoboSyncedBook row.
    #   b) FILTER-CHANGE — Edition still exists but no longer matches
    #      the token's library access + shelf filter (user removed the
    #      book from a synced shelf, revoked library access, etc.).
    #      Emit ChangedEntitlement + IsRemoved=true so the device drops
    #      the book on next sync, then stamp archived_at on the row.
    #   c) ARCHIVED — already handled by the device-side DELETE
    #      endpoint; nothing to emit here.
    #
    # Both (a) and (b) flow through the same diff: previously-synced &
    # not-archived MINUS currently-allowed.
    if is_incremental:
        # Currently-allowed set: same library access + shelf filter as
        # the main query, no pagination, no updated_at cursor. Returns
        # ``Edition.id`` for every edition the token *should* see right
        # now.
        allowed_stmt = select(Edition.id).join(
            Library, Edition.library_id == Library.id
        )
        if accessible_lib_ids is not None:
            allowed_stmt = allowed_stmt.where(
                Edition.library_id.in_(accessible_lib_ids)
            )
        if token_shelf_ids:
            shelf_has_books = await db.scalar(
                select(ShelfBook.id)
                .where(ShelfBook.shelf_id.in_(token_shelf_ids))
                .limit(1)
            )
            if shelf_has_books:
                allowed_stmt = allowed_stmt.where(
                    select(ShelfBook.work_id)
                    .where(
                        ShelfBook.work_id == Edition.work_id,
                        ShelfBook.shelf_id.in_(token_shelf_ids),
                    )
                    .exists()
                )
        currently_allowed_ids = {
            row[0] for row in (await db.execute(allowed_stmt)).all()
        }

        # Previously-synced (and not yet archived) rows for this token,
        # joined to Edition so we have the uuid to send to the device.
        synced_rows = (
            await db.execute(
                select(KoboSyncedBook, Edition)
                .outerjoin(Edition, Edition.id == KoboSyncedBook.edition_id)
                .where(
                    KoboSyncedBook.sync_token_id == sync_token.id,
                    KoboSyncedBook.archived_at.is_(None),
                )
            )
        ).all()

        from datetime import datetime as _now_dt
        removal_count = 0
        for synced_row, ed in synced_rows:
            if ed is None:
                # Orphan (case a): row points at a deleted Edition. No
                # uuid available; just drop the bookkeeping row.
                await db.delete(synced_row)
                continue
            if ed.id in currently_allowed_ids:
                continue
            # Case b: filter changed; emit a removal and stamp archived.
            # Cap removals per-batch so a giant shelf rearrangement
            # doesn't blow the payload — leftover rows surface on the
            # next sync round-trip.
            if removal_count >= SYNC_PAGE_SIZE:
                break
            items.append(
                {
                    "ChangedEntitlement": {
                        "BookEntitlement": {
                            "Accessibility": "Full",
                            "ActivePeriod": {"From": _kobo_timestamp(_utcnow())},
                            "Created": _kobo_timestamp(ed.created_at),
                            "CrossRevisionId": ed.uuid,
                            "Id": ed.uuid,
                            "IsHiddenFromArchive": True,
                            "IsLocked": False,
                            "IsRemoved": True,
                            "LastModified": _kobo_timestamp(_utcnow()),
                            "OriginCategory": "Imported",
                            "RevisionId": ed.uuid,
                            "Status": "Active",
                        }
                    }
                }
            )
            synced_row.archived_at = _now_dt.utcnow()
            removal_count += 1

    # Record synced editions in lookup table (Calibre-Web pattern).
    #
    # Cursor advancement policy: during the initial-fill phase (is_incremental
    # == False), the query exclusively uses the KoboSyncedBook NOT EXISTS
    # filter — the timestamp cursor is NOT consulted at all. Advancing
    # books_last_modified page-by-page would flip the query into incremental
    # mode on the next call and cause the updated_at > cursor filter to
    # skip editions whose timestamp is <= the cursor's. That's catastrophic
    # for bulk-imported libraries where every book shares one import
    # timestamp: after the first page sets the cursor, the second page
    # filters the entire batch out and the device gets stuck at 10 books.
    #
    # So: during initial fill, do NOT advance books_last_modified until the
    # fill is fully complete (has_more == False). On the final page, advance
    # to the current wall-clock so the next sync flips cleanly into the
    # incremental branch. During incremental mode we can advance normally.
    if editions:
        if is_incremental:
            sync_token.books_last_modified = max(e.updated_at for e in editions)
        elif not has_more:
            # Initial fill just finished this request. Mark the switchover
            # to incremental mode at "now" so subsequent syncs use the
            # updated_at > cursor path.
            sync_token.books_last_modified = datetime.utcnow()

        created_timestamps = [e.created_at for e in editions if e.created_at]
        if created_timestamps:
            new_max_created = max(created_timestamps)
            if (
                sync_token.books_last_created is None
                or new_max_created > sync_token.books_last_created
            ):
                sync_token.books_last_created = new_max_created
        for edition in editions:
            # Upsert: skip if already recorded
            existing = await db.execute(
                select(KoboSyncedBook.id).where(
                    KoboSyncedBook.sync_token_id == sync_token.id,
                    KoboSyncedBook.edition_id == edition.id,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(KoboSyncedBook(
                    sync_token_id=sync_token.id,
                    edition_id=edition.id,
                ))

    # Advance reading_state cursor to now so future incremental syncs only
    # emit ChangedReadingState for states modified after this point.
    sync_token.reading_state_last_modified = datetime.utcnow()

    # ── Shelf tags (appear as collections on the Kobo device) ─────────────
    # Build a mapping of edition UUID → shelf names for tagged books
    if token_shelf_ids and editions:
        work_ids = [e.work_id for e in editions]
        shelf_book_rows = await db.execute(
            select(ShelfBook.work_id, Shelf.name)
            .join(Shelf, Shelf.id == ShelfBook.shelf_id)
            .where(ShelfBook.shelf_id.in_(token_shelf_ids), ShelfBook.work_id.in_(work_ids))
        )
        # Map work_id → list of shelf names
        work_shelves: dict[int, list[str]] = {}
        for wid, sname in shelf_book_rows:
            work_shelves.setdefault(wid, []).append(sname)

        # Build tag entries for each shelf.
        # On first sync use NewTag; on incremental use ChangedTag (CWA L394/L399).
        tag_envelope = "ChangedTag" if is_incremental else "NewTag"
        seen_tags: set[str] = set()
        for edition in editions:
            shelf_names = work_shelves.get(edition.work_id, [])
            for sname in shelf_names:
                tag_id = f"SC-{sname.replace(' ', '-')}"
                if tag_id not in seen_tags:
                    seen_tags.add(tag_id)
                    items.append({
                        tag_envelope: {
                            "Tag": {
                                "Created": edition.created_at.isoformat() + "Z" if edition.created_at else None,
                                "Id": tag_id,
                                "Items": [
                                    {"RevisionId": e.uuid, "Type": "ProductRevisionTagItem"}
                                    for e in editions
                                    if sname in work_shelves.get(e.work_id, [])
                                ],
                                "LastModified": edition.updated_at.isoformat() + "Z" if edition.updated_at else None,
                                "Name": sname,
                                "Type": "UserTag",
                            }
                        }
                    })

    await db.commit()
    return items, has_more


def _get_kobo_compatible_file_edition(files: list[EditionFile]) -> Optional[EditionFile]:
    """Find the best Kobo-compatible file from an edition's files."""
    priority = {"kepub": 0, "epub": 1, "pdf": 2}
    compatible = [f for f in files if f.format.lower() in priority]
    if not compatible:
        return None
    return sorted(compatible, key=lambda f: priority.get(f.format.lower(), 99))[0]


def _get_kobo_compatible_file(files: list[BookFile]) -> Optional[BookFile]:
    """Legacy: find the best Kobo-compatible file from a book's files."""
    priority = {"kepub": 0, "epub": 1, "pdf": 2}
    compatible = [f for f in files if f.format.lower() in priority]
    if not compatible:
        return None
    return sorted(compatible, key=lambda f: priority.get(f.format.lower(), 99))[0]


def _build_download_urls(
    edition: Edition,
    edition_files: list[EditionFile],
    kobo_base: str,
) -> list[dict]:
    """Build the DownloadUrls list for the Kobo device.

    Format advertisement strategy (matches Komga KoboController.kt L753-760):
      - If the EPUB is fixed-layout (rendition:layout=pre-paginated): advertise
        EPUB3FL and serve the raw EPUB. KEPUB conversion breaks fixed-layout
        rendering — Kobo Nickel handles fixed-layout natively under EPUB3FL.
      - If kepubify is available OR source is already KEPUB: advertise KEPUB
        (device uses Kobo WebKit with chapter tracking, reading stats)
      - If kepubify is NOT available and source is EPUB: advertise EPUB3 + EPUB
        (CWA fallback — device uses Adobe Digital Editions WebKit)
      - PDF sources: advertise PDF

    The download URL always uses the SOURCE format (/download/epub) — the
    server converts to KEPUB transparently in get_download_path() via
    ensure_kepub(), which itself skips conversion for fixed-layout titles.

    DrmType is intentionally omitted (CWA kobo.py L601: "Not required").
    """
    from app.services.kepub import _find_kepubify

    kepubify_available = _find_kepubify() is not None
    is_fixed_layout = bool(getattr(edition, "is_fixed_layout", False))
    kepubs = [f for f in edition_files if f.format.lower() == "kepub"]
    candidates = kepubs if kepubs else [
        f for f in edition_files if f.format.lower() in ("epub", "pdf")
    ]
    urls = []
    for f in candidates:
        fmt_key = f.format.lower()
        if fmt_key == "kepub":
            formats_to_advertise = ["KEPUB"]
        elif fmt_key == "epub" and is_fixed_layout:
            # Fixed-layout EPUBs (children's books, manga, photo books): the
            # device renders these natively; KEPUB conversion mangles them.
            formats_to_advertise = ["EPUB3FL"]
        elif fmt_key == "epub" and kepubify_available:
            # Komga pattern: advertise KEPUB when conversion is possible
            formats_to_advertise = ["KEPUB"]
        elif fmt_key == "epub":
            # CWA fallback: no kepubify, serve raw EPUB
            formats_to_advertise = ["EPUB3", "EPUB"]
        elif fmt_key == "pdf":
            formats_to_advertise = ["PDF"]
        else:
            continue

        for kobo_format in formats_to_advertise:
            urls.append(
                {
                    "Format": kobo_format,
                    "Size": f.file_size,
                    "Url": f"{kobo_base}/v1/library/{edition.uuid}/download/{fmt_key}",
                    "Platform": "Generic",
                }
            )
    return urls


def _build_edition_entry(
    edition: Edition,
    edition_file: EditionFile,
    *,
    ep: "Optional[EditionPosition]" = None,
    rs: "Optional[ReadingState]" = None,
    auth_token: str,
    base_url: str,
    is_new: bool = True,
    span_chapter_href: Optional[str] = None,
    span_id: Optional[str] = None,
    series_position: Optional[float] = None,
) -> dict:
    """Build a single Kobo library sync entry for an Edition.

    ``ep`` and ``rs`` are the unified-progress rows the emit path now
    reads from (see ``_load_emit_state``). ``span_chapter_href`` /
    ``span_id`` are precomputed by ``_resolve_emit_span`` so this stays
    a sync function. When both span values are provided the emitted
    bookmark uses the real KoboSpan id.
    """
    kobo_base = f"{base_url}/kobo/{auth_token}"
    work = edition.work

    author_list: list[str] = []
    if work and work.authors:
        author_list = [a.name for a in work.authors]

    series_name = None
    series_number = series_position
    if work and work.series:
        series_name = work.series[0].name

    envelope_key = "NewEntitlement" if is_new else "ChangedEntitlement"

    entry: dict[str, Any] = {
        envelope_key: {
            "BookEntitlement": {
                "Accessibility": "Full",
                # ActivePeriod.From must be <= "now" for Nickel to treat the
                # entitlement as currently active. CWA cps/kobo.py L504 uses
                # datetime.now(timezone.utc); using edition.created_at can
                # cause devices with clock drift to interpret old entitlements
                # as expired.
                "ActivePeriod": {"From": _kobo_timestamp(_utcnow())},
                "Created": _kobo_timestamp(edition.created_at),
                "CrossRevisionId": edition.uuid,
                "Id": edition.uuid,
                "IsHiddenFromArchive": False,
                "IsLocked": False,
                "IsRemoved": False,
                "LastModified": _kobo_timestamp(edition.updated_at),
                "OriginCategory": "Imported",
                "RevisionId": edition.uuid,
                "Status": "Active",
            },
            "BookMetadata": {
                "Categories": ["00000000-0000-0000-0000-000000000001"],
                "ContributorRoles": [{"Name": name} for name in author_list],
                "Contributors": author_list,
                "CoverImageId": (
                    f"{edition.uuid}-{edition.cover_hash}"
                    if edition.cover_hash
                    else None
                ),
                "CrossRevisionId": edition.uuid,
                "CurrentDisplayPrice": {"CurrencyCode": "USD", "TotalAmount": 0},
                "CurrentLoveDisplayPrice": {"TotalAmount": 0},
                "Description": (work.description if work else None) or "",
                "DownloadUrls": _build_download_urls(edition, edition.files or [], kobo_base),
                "EntitlementId": edition.uuid,
                "ExternalIds": [],
                "Genre": "00000000-0000-0000-0000-000000000001",
                "IsEligibleForKoboLove": False,
                "IsInternetArchive": False,
                "IsPreOrder": False,
                "IsSocialEnabled": True,
                "Language": edition.language or (work.language if work else None) or "en",
                "PhoneticPronunciations": {},
                "PublicationDate": _kobo_timestamp(edition.published_date),
                "Publisher": {"Imprint": "", "Name": edition.publisher or ""},
                "RevisionId": edition.uuid,
                "Title": work.title if work else edition.uuid,
                "WorkId": edition.uuid,
            },
        }
    }

    if series_name:
        # Kobo's metadata-style guide expects ``Number`` as a clean
        # numeric string. Format whole numbers without a trailing
        # ``.0`` so collection sort keys read "3" not "3.0", but keep
        # fractional positions ("3.5") intact for in-between volumes.
        if series_number is None:
            number_str = "0"
            number_float = 0.0
        else:
            number_float = float(series_number)
            number_str = str(int(number_float)) if number_float.is_integer() else f"{number_float:g}"
        entry[envelope_key]["BookMetadata"]["Series"] = {
            "Name": series_name,
            "Number": number_str,
            "NumberFloat": number_float,
            "Id": series_name,
        }

    # Komga KoboController.kt L361-368 + comment at L397:
    #   "Kobo does not process ChangedEntitlement even if it contains a
    #    ReadingState"
    # Pattern: ALWAYS include a ReadingState on NewEntitlement, using an
    # empty "ReadyToRead" default when the book has no stored state. Kobo
    # firmware appears to expect every NewEntitlement to carry a reading
    # state; omitting it can cause Nickel to silently discard the entry.
    # For ChangedEntitlement, Kobo ignores the embedded ReadingState — so
    # reading-state updates for already-known books should be emitted as
    # separate ChangedReadingState envelopes (TODO: implement that path).
    if is_new:
        if ep is not None or rs is not None:
            entry[envelope_key]["ReadingState"] = _build_reading_state(
                edition.uuid,
                ep=ep,
                rs=rs,
                span_chapter_href=span_chapter_href,
                span_id=span_id,
            )
        else:
            entry[envelope_key]["ReadingState"] = _build_empty_reading_state(
                edition.uuid, edition.created_at
            )

    return entry


def _build_empty_reading_state(entity_uuid: str, created_at: datetime) -> dict:
    """Build a default empty ReadingState for a book with no recorded progress.

    Matches Komga's getEmptyReadProgressForBook() pattern — ReadyToRead
    status at 0%. Used when emitting NewEntitlement for a book the user has
    never opened. Without this, Nickel may reject the entitlement as
    malformed (Komga found this empirically; see KoboController.kt L365).
    """
    ts = _kobo_timestamp(created_at)
    return {
        "EntitlementId": entity_uuid,
        "Created": ts,
        "LastModified": ts,
        "PriorityTimestamp": ts,
        "StatusInfo": {
            "LastModified": ts,
            "Status": "ReadyToRead",
            "TimesStartedReading": 0,
        },
        "Statistics": {
            "LastModified": ts,
            "SpentReadingMinutes": 0,
            "RemainingTimeMinutes": 0,
        },
        "CurrentBookmark": {
            "LastModified": ts,
            "ContentSourceProgressPercent": 0,
            "Location": {"Source": "", "Type": "KoboSpan", "Value": ""},
            "ProgressPercent": 0,
        },
    }


# Canonical-status → Kobo wire-status. Kobo doesn't have an "abandoned"
# concept; Whispersym/Komga both surface it as plain "Reading" so the
# entitlement stays visible on the device.
_KOBO_STATUS_FROM_CANONICAL = {
    "want_to_read": "ReadyToRead",
    "reading": "Reading",
    "completed": "Finished",
    "abandoned": "Reading",
}


def _build_reading_state(
    entity_uuid: str,
    *,
    ep: Optional["EditionPosition"] = None,
    rs: Optional["ReadingState"] = None,
    span_chapter_href: Optional[str] = None,
    span_id: Optional[str] = None,
) -> dict:
    """Build the Kobo ReadingState object from the unified-progress rows.

    Reads ``ReadingState`` (work-level lifecycle: status, times_started,
    timestamps) plus ``EditionPosition`` (cursor: pct, format, value,
    time_spent). The legacy ``KoboBookState`` is no longer the source of
    truth here — dual-write keeps it populated through step 4 only as a
    rollback safety net.

    When ``span_chapter_href`` + ``span_id`` are provided (computed by
    ``_resolve_emit_span`` from the koboSpan map), the bookmark Source/
    Value carry the real Kobo position so Nickel restores at the exact
    paragraph. When the span map is unavailable, we fall back to a
    synthetic ``spine#N`` token (chapter-only restore).
    """
    if rs is None and ep is None:
        # Should never happen — caller knows there's at least one source.
        # Emit an empty-ish state so we don't crash the sync.
        ts = _kobo_timestamp(_utcnow())
        return _build_empty_reading_state(entity_uuid, _utcnow())

    last_modified = (
        ep.current_updated_at
        if ep and ep.current_updated_at
        else (rs.last_opened if rs and rs.last_opened else _utcnow())
    )
    created_at = (
        ep.created_at if ep else (rs.created_at if rs else _utcnow())
    )

    status = _KOBO_STATUS_FROM_CANONICAL.get(
        (rs.status if rs else "want_to_read"), "ReadyToRead"
    )
    times_started = rs.times_started if rs else 0

    status_info: dict = {
        "LastModified": _kobo_timestamp(last_modified),
        "Status": status,
        "TimesStartedReading": times_started,
    }
    if rs and rs.started_at:
        status_info["LastTimeStartedReading"] = _kobo_timestamp(rs.started_at)
    elif last_modified:
        status_info["LastTimeStartedReading"] = _kobo_timestamp(last_modified)
    if rs and rs.completed_at and status == "Finished":
        status_info["LastTimeFinished"] = _kobo_timestamp(rs.completed_at)

    # ContentSourceProgressPercent is on the wire as 0–100; EditionPosition
    # stores the canonical 0–1 fraction.
    pct = ((ep.current_pct if ep else 0.0) or 0.0) * 100.0

    # Bookmark location: prefer precomputed real-span values; otherwise
    # try to split the EditionPosition.current_value (kobo_span format
    # stores "chapter_href#span_id"); fall back to chapter-only when the
    # cursor isn't a kobo_span (e.g. cfi or percent — those don't carry
    # a chapter reference, so emit empty Source + synthetic spine#0).
    if span_id is not None:
        location_source = span_chapter_href or _split_kobo_value_chapter(ep) or ""
        location_value = span_id
    elif ep and ep.current_format == "kobo_span" and ep.current_value:
        chapter, rest = _split_kobo_value(ep.current_value)
        location_source = chapter or ""
        # rest may be "spine#N" (synthetic) or a real koboSpan id.
        location_value = rest or "spine#0"
    else:
        location_source = ""
        location_value = "spine#0"

    seconds = ep.time_spent_seconds if ep else 0

    return {
        "EntitlementId": entity_uuid,
        "Created": _kobo_timestamp(created_at),
        "LastModified": _kobo_timestamp(last_modified),
        "PriorityTimestamp": _kobo_timestamp(last_modified),
        "StatusInfo": status_info,
        "Statistics": {
            "LastModified": _kobo_timestamp(last_modified),
            "SpentReadingMinutes": (seconds or 0) // 60,
            # Round-trip the device's own time-left estimate when we
            # have one stored. ``0`` is the "no estimate" default Kobo
            # tolerates when nothing meaningful is available.
            "RemainingTimeMinutes": (
                ep.remaining_time_minutes
                if ep is not None and ep.remaining_time_minutes is not None
                else 0
            ),
        },
        "CurrentBookmark": {
            "LastModified": _kobo_timestamp(last_modified),
            "ContentSourceProgressPercent": pct,
            "Location": {
                "Source": location_source,
                "Type": "KoboSpan",
                "Value": location_value,
            },
            "ProgressPercent": pct,
        },
    }


def _split_kobo_value(value: str) -> tuple[str, str]:
    """Split ``"chapter_href#span_id"`` into (chapter, span). Tolerant of
    legacy ``"chapter_href#spine#N"`` — splits at the first ``#`` only."""
    if not value:
        return "", ""
    if "#" not in value:
        return value, ""
    chapter, rest = value.split("#", 1)
    return chapter, rest


def _split_kobo_value_chapter(ep: Optional["EditionPosition"]) -> Optional[str]:
    if not ep or not ep.current_value:
        return None
    chapter, _ = _split_kobo_value(ep.current_value)
    return chapter or None


async def _resolve_emit_span(
    ep: "Optional[EditionPosition]",
    edition_files: list[EditionFile],
    db: AsyncSession,
) -> tuple[Optional[str], Optional[str]]:
    """Pick the (chapter_href, span_id) to emit for a given EditionPosition.

    Three cases:
    1. The cursor is already in ``kobo_span`` format with a real span id
       (not the legacy ``spine#N`` synthetic) — return the parts directly.
    2. Anything else: look up the closest span by global progress against
       the stored KoboSpan map for this edition's KEPUB.

    Returns (None, None) when no koboSpan map is available, so the caller
    falls back to chapter-only ``spine#N`` inside ``_build_reading_state``.
    """
    if ep is None:
        return None, None

    epub = next(
        (f for f in edition_files if (f.format or "").lower() == "epub"), None
    )

    # Case 1: cursor is already a real koboSpan id from a prior Kobo write.
    if ep.current_format == "kobo_span" and ep.current_value:
        chapter, rest = _split_kobo_value(ep.current_value)
        if chapter and rest and not rest.startswith("spine#"):
            return chapter, rest

    # Case 2: cursor is a CFI (most recent write came from the web reader).
    # Translate via the koboSpan map for this edition's KEPUB so the
    # device opens at the right chapter / nearest paragraph.
    if ep.current_format == "cfi" and ep.current_value and epub is not None:
        from app.services.kobo_spans import cfi_to_span_lookup

        resolved = await cfi_to_span_lookup(ep.current_value, epub.id, db)
        if resolved:
            chapter_href, span_id, _spine_index = resolved
            return chapter_href, span_id

    # Case 3: derive from raw progress against the span map.
    if epub is None:
        return None, None
    from app.services.kobo_spans import span_for_progress

    progress = ep.current_pct or 0.0
    resolved = await span_for_progress(epub.id, progress, db)
    if not resolved:
        return None, None
    chapter_href, span_id, _spine_index = resolved
    return chapter_href, span_id


# ---------------------------------------------------------------------------
# Reading State Updates (device → server)
# ---------------------------------------------------------------------------

async def _find_edition_by_any_id(
    identifier: str, db: AsyncSession
) -> Optional[Edition]:
    """Resolve an Edition by UUID or numeric id.

    The Kobo protocol identifies entitlements by the string we sent as
    `EntitlementId`. Older Scriptorium releases sent numeric ids; current
    releases send UUIDs. Devices retain cached entitlements across app
    upgrades, so handlers must accept either form.
    """
    result = await db.execute(select(Edition).where(Edition.uuid == identifier))
    edition = result.scalar_one_or_none()
    if edition is not None:
        return edition
    if identifier.isdigit():
        result = await db.execute(select(Edition).where(Edition.id == int(identifier)))
        return result.scalar_one_or_none()
    return None


async def update_reading_state(
    book_uuid: str,
    user_id: int,
    state_data: dict,
    db: AsyncSession,
) -> Optional["EditionPosition"]:
    """Process a reading state update from a Kobo device.

    Resolves the device's payload into a unified-progress write via
    ``write_progress``. Returns the updated ``EditionPosition`` (caller
    only checks truthiness for the success-result envelope).
    """
    from app.models.reading import EditionPosition as _EP
    from app.services.unified_progress import write_progress

    edition = await _find_edition_by_any_id(book_uuid, db)
    if edition is None:
        logger.warning("Reading state update for unknown UUID: %s", book_uuid)
        return None
    edition_id = edition.id

    # ── Status: translate Kobo's enum into our canonical lifecycle hint.
    status_info = state_data.get("StatusInfo", {})
    raw_status = status_info.get("Status")
    kobo_to_canonical = {
        "ReadyToRead": None,           # no hint — let cursor pct decide
        "Reading": "reading",
        "Finished": "completed",
    }
    status_hint = kobo_to_canonical.get(raw_status)

    # ── Cursor position. Three layers of fallback for the bookmark:
    # 1. Real koboSpan id from the device → ``chapter_href#span_id``.
    # 2. Synthetic ``spine#N`` we emitted → ``chapter_href#spine#N``.
    # 3. No bookmark, just a ContentSourceProgressPercent → format=percent.
    bookmark = state_data.get("CurrentBookmark", {})
    location = bookmark.get("Location", {}) or {}
    chapter_source = location.get("Source", "") or ""
    val = location.get("Value", "") or ""

    cursor_format = "percent"
    cursor_value = "0"
    if val.startswith("spine#") or "#" in val:
        # Real koboSpan id or our synthetic — pack into the kobo_span shape.
        cursor_format = "kobo_span"
        cursor_value = f"{chapter_source}#{val}" if chapter_source else val
    elif val and chapter_source:
        cursor_format = "kobo_span"
        cursor_value = f"{chapter_source}#{val}"

    if "ContentSourceProgressPercent" in bookmark:
        raw_pct = bookmark["ContentSourceProgressPercent"]
    elif "ProgressPercent" in bookmark:
        raw_pct = bookmark["ProgressPercent"]
    else:
        raw_pct = None

    # ``Finished`` always means 100% regardless of what the device sent.
    if raw_status == "Finished":
        cursor_pct = 1.0
    elif raw_pct is not None:
        cursor_pct = max(0.0, min(1.0, float(raw_pct) / 100.0))
    else:
        cursor_pct = None

    # If we have *no* cursor signal at all (status-only update) reuse
    # whatever EditionPosition already holds so we don't regress to 0.
    if cursor_pct is None or (cursor_format == "percent" and not raw_pct):
        existing = (
            await db.execute(
                select(_EP).where(_EP.user_id == user_id, _EP.edition_id == edition_id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            cursor_pct = cursor_pct if cursor_pct is not None else (existing.current_pct or 0.0)
            if cursor_format == "percent" and existing.current_format and existing.current_value:
                cursor_format = existing.current_format
                cursor_value = existing.current_value
        else:
            cursor_pct = 0.0
    if cursor_format == "percent":
        cursor_value = str(round(cursor_pct * 100.0, 4))

    # ── Time-spent delta. Kobo reports SpentReadingMinutes cumulatively
    # per device, so subtract whatever EditionPosition already has to
    # avoid double-counting on every sync.
    statistics = state_data.get("Statistics", {})
    delta_seconds = 0
    if "SpentReadingMinutes" in statistics:
        incoming_seconds = int(statistics["SpentReadingMinutes"]) * 60
        existing = (
            await db.execute(
                select(_EP.time_spent_seconds).where(
                    _EP.user_id == user_id, _EP.edition_id == edition_id
                )
            )
        ).scalar_one_or_none() or 0
        delta_seconds = max(0, incoming_seconds - existing)

    # Kobo's own time-left estimate, when present. We pass it through
    # untouched so the web reader / book detail can display the device's
    # number rather than re-deriving from a pace model.
    remaining_minutes: Optional[int] = None
    if "RemainingTimeMinutes" in statistics:
        try:
            remaining_minutes = max(0, int(statistics["RemainingTimeMinutes"]))
        except (TypeError, ValueError):
            remaining_minutes = None

    device = await _get_or_create_kobo_device(user_id, db)

    # Snapshot the full Kobo state JSON onto DevicePosition.raw_payload
    # so future debugging / multi-device reconciliation can replay the
    # original message. ``write_progress`` only persists this when a
    # ``device_id`` is set, which it always is on the Kobo path.
    import json as _json
    raw_payload = _json.dumps(state_data, separators=(",", ":"))

    await write_progress(
        db,
        user_id=user_id,
        edition=edition,
        cursor_format=cursor_format,
        cursor_value=cursor_value,
        cursor_pct=cursor_pct or 0.0,
        device_id=device.id,
        raw_payload=raw_payload,
        time_spent_delta_seconds=delta_seconds,
        status_hint=status_hint,
        remaining_time_minutes=remaining_minutes,
        timestamp=_utcnow(),
    )

    await db.commit()
    return (
        await db.execute(
            select(_EP).where(_EP.user_id == user_id, _EP.edition_id == edition_id)
        )
    ).scalar_one_or_none()


async def _get_or_create_kobo_device(
    user_id: int,
    db: AsyncSession,
) -> Device:
    """Get or create a generic Kobo device record for a user."""
    stmt = select(Device).where(
        Device.user_id == user_id,
        Device.device_type == "kobo",
    )
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        device = Device(
            user_id=user_id,
            name="Kobo eReader",
            device_type="kobo",
        )
        db.add(device)
        await db.flush()

    return device


# ---------------------------------------------------------------------------
# Book Download — Edition-first
# ---------------------------------------------------------------------------

async def get_download_path(
    book_uuid: str,
    file_format: str,
    db: AsyncSession,
    sync_token: Optional[KoboSyncToken] = None,
) -> Optional[Path]:
    """Get the filesystem path for a file to serve to a Kobo device.

    Checks EditionFile first (new), then falls back to BookFile (legacy).

    When ``sync_token`` is provided, the lookup is scoped to libraries the
    token's user can access — without it, any caller with any UUID would be
    able to download any file in the library.
    """
    accessible_lib_ids: set[int] | None = None
    if sync_token is not None:
        from app.api.auth import get_accessible_library_ids
        from app.models.user import User as _User

        user = await db.get(_User, sync_token.user_id)
        if user is None:
            return None
        accessible_lib_ids = await get_accessible_library_ids(db, user)

    # Try EditionFile via Edition.uuid. We pull the parent Edition's
    # is_fixed_layout flag in the same query so ensure_kepub() can decide
    # whether to skip conversion without an extra round-trip.
    stmt = (
        select(EditionFile, Edition.is_fixed_layout)
        .join(Edition, EditionFile.edition_id == Edition.id)
        .where(
            Edition.uuid == book_uuid,
            EditionFile.format == file_format,
        )
    )
    if accessible_lib_ids is not None:
        stmt = stmt.where(Edition.library_id.in_(accessible_lib_ids))
    result = await db.execute(stmt)
    # Multiple files with the same format can exist (duplicate imports);
    # the first match is safe — all point at the same book.
    row = result.first()
    edition_file = row[0] if row else None
    is_fixed_layout = bool(row[1]) if row else False

    if edition_file:
        from app.config import resolve_path

        # Auto-convert EPUB to KEPUB for better Kobo experience.
        #
        # Two gates here:
        #   1. The device must have asked for KEPUB. If it asked for raw
        #      EPUB/EPUB3 we honour that — running the conversion path
        #      anyway would serve a ``.kepub.epub``-named file in
        #      response to an EPUB request, which is inconsistent with
        #      the format we advertised in ``_build_download_urls``.
        #   2. ``kepubify`` must actually be installed. The fallback in
        #      ``convert_to_kepub`` produces a byte-identical copy of
        #      the source EPUB with a ``.kepub.epub`` name and no Kobo
        #      span wrapping — that's worse than serving the raw EPUB
        #      because the device thinks it's a real KEPUB.
        # Fixed-layout titles always skip conversion; Nickel renders
        # them natively under the EPUB3FL format.
        if file_format.lower() == "kepub" and edition_file.format.lower() == "epub":
            from app.services.kepub import _find_kepubify, ensure_kepub
            if _find_kepubify() is not None:
                try:
                    kepub_path = await ensure_kepub(
                        edition_file, is_fixed_layout=is_fixed_layout
                    )
                    if kepub_path:
                        resolved = Path(resolve_path(kepub_path))
                        if resolved.exists():
                            await db.commit()  # persist kepub_path/hash on edition_file
                            return resolved
                except Exception:
                    pass  # Fall through to original file

        path = Path(resolve_path(edition_file.file_path))
        return path if path.exists() else None

    # Fallback to legacy BookFile
    stmt = (
        select(BookFile)
        .join(Book, BookFile.edition_id == Book.id)
        .where(
            Book.uuid == book_uuid,
            BookFile.format == file_format,
        )
    )
    if accessible_lib_ids is not None:
        stmt = stmt.where(Book.library_id.in_(accessible_lib_ids))
    result = await db.execute(stmt)
    book_file = result.scalar_one_or_none()

    if not book_file:
        return None

    from app.config import resolve_path
    path = Path(resolve_path(book_file.file_path))
    return path if path.exists() else None


# ---------------------------------------------------------------------------
# Sync URL Builder (for settings page)
# ---------------------------------------------------------------------------

def build_sync_url(auth_token: str, base_url: str) -> str:
    """Build the api_endpoint value that users put in their Kobo device config."""
    return f"{base_url}/kobo/{auth_token}"
