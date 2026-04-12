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

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import Book, BookFile, Edition, EditionFile, Library, User, UserEdition, Work
from app.models.progress import (
    Device,
    KoboBookState,
    KoboShelfArchive,
    KoboSyncedBook,
    KoboSyncToken,
    KoboTokenShelf,
    ReadProgress,
)
from app.models.shelf import Shelf, ShelfBook

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
    """Generate a new Kobo sync auth token for a user."""
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
        for sid in shelf_ids:
            db.add(KoboTokenShelf(token_id=sync_token.id, shelf_id=sid))

    await db.commit()
    await db.refresh(sync_token)
    return sync_token


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


async def revoke_sync_token(token_id: int, db: AsyncSession) -> bool:
    """Revoke (deactivate) a sync token."""
    stmt = select(KoboSyncToken).where(KoboSyncToken.id == token_id)
    result = await db.execute(stmt)
    sync_token = result.scalar_one_or_none()
    if sync_token:
        sync_token.is_active = False
        await db.commit()
        return True
    return False


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
    resources["tag_items"] = f"{kobo_base}/v1/library/tags/{{TagId}}/Items"
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
        # Incremental: only books changed since last sync
        stmt = stmt.where(Edition.updated_at > sync_token.books_last_modified)
    else:
        # Initial sync: exclude books already sent (KoboSyncedBooks lookup)
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

    # Load KoboBookStates for these editions
    edition_ids = [e.id for e in editions]
    states_map: dict[int, KoboBookState] = {}
    if edition_ids:
        states_result = await db.execute(
            select(KoboBookState).where(
                KoboBookState.user_id == user_id,
                KoboBookState.edition_id.in_(edition_ids),
            )
        )
        for state in states_result.scalars().all():
            states_map[state.edition_id] = state

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

        state = states_map.get(edition.id)
        entry = _build_edition_entry(
            edition=edition,
            edition_file=epub_file,
            state=state,
            auth_token=sync_token.token,
            base_url=base_url,
            is_new=edition_is_new,
        )
        items.append(entry)

    # ── Separate ChangedReadingState for books whose state changed but
    # whose Edition record did not (so they aren't in `editions` above).
    # CWA L340-353: only emit ChangedReadingState when the book is NOT in
    # the current entitlement batch, otherwise the device sees duplicates.
    if is_incremental and sync_token.reading_state_last_modified is not None:
        batch_edition_ids = set(edition_ids)
        # Synced editions for this token
        synced_ids_result = await db.execute(
            select(KoboSyncedBook.edition_id).where(
                KoboSyncedBook.sync_token_id == sync_token.id
            )
        )
        synced_ids = {row[0] for row in synced_ids_result}
        candidate_ids = synced_ids - batch_edition_ids
        if candidate_ids:
            extra_states_result = await db.execute(
                select(KoboBookState, Edition.uuid)
                .join(Edition, Edition.id == KoboBookState.edition_id)
                .where(
                    KoboBookState.user_id == user_id,
                    KoboBookState.edition_id.in_(candidate_ids),
                    KoboBookState.updated_at > sync_token.reading_state_last_modified,
                )
            )
            for state, uuid in extra_states_result:
                items.append(
                    {"ChangedReadingState": {"ReadingState": _build_reading_state(uuid, state)}}
                )

    # ── Removal detection: books previously synced that are now gone
    # (deleted or no longer match the token's filter). CWA/grimmory use
    # snapshot tables; we do a lighter diff: any KoboSyncedBook rows whose
    # Edition no longer exists become ChangedEntitlement + IsRemoved=true.
    # Only run on incremental syncs — on first sync there is no prior
    # snapshot to diff against.
    if is_incremental:
        orphan_result = await db.execute(
            select(KoboSyncedBook)
            .outerjoin(Edition, Edition.id == KoboSyncedBook.edition_id)
            .where(
                KoboSyncedBook.sync_token_id == sync_token.id,
                Edition.id.is_(None),
            )
        )
        orphans = list(orphan_result.scalars().all())
        for orphan in orphans:
            # We no longer have the Edition to get a uuid from, and the
            # device only needs the entitlement id we originally sent.
            # Store the uuid on KoboSyncedBook? For now, skip removal of
            # rows with no Edition — the bookkeeping loss is acceptable.
            await db.delete(orphan)

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
    """Build the DownloadUrls list, preferring KEPUB exclusively when present.

    Matches CWA cps/kobo.py L49 + L584-603:
      KOBO_FORMATS = {"KEPUB": ["KEPUB"], "EPUB": ["EPUB3", "EPUB"]}
    For each source file, emit one DownloadUrls entry per advertised
    kobo_format. EPUB sources emit TWO entries (EPUB3 and EPUB) pointing
    at the same /download/epub URL — Nickel picks one based on firmware
    capability. Without the EPUB3 advertisement some firmware versions
    decline to auto-download the entitlement.

    DrmType is intentionally omitted (CWA kobo.py L601 comments it as
    "Not required"). Including `DrmType: "None"` can cause Nickel's
    ContentUrl.setDrmType() to reject the entitlement.
    """
    kobo_formats = {"kepub": ["KEPUB"], "epub": ["EPUB3", "EPUB"]}
    kepubs = [f for f in edition_files if f.format.lower() == "kepub"]
    candidates = kepubs if kepubs else [
        f for f in edition_files if f.format.lower() == "epub"
    ]
    urls = []
    for f in candidates:
        fmt_key = f.format.lower()
        for kobo_format in kobo_formats.get(fmt_key, []):
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
    state: Optional[KoboBookState],
    auth_token: str,
    base_url: str,
    is_new: bool = True,
) -> dict:
    """Build a single Kobo library sync entry for an Edition."""
    kobo_base = f"{base_url}/kobo/{auth_token}"
    work = edition.work

    author_list: list[str] = []
    if work and work.authors:
        author_list = [a.name for a in work.authors]

    series_name = None
    series_number = None
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
        entry[envelope_key]["BookMetadata"]["Series"] = {
            "Name": series_name,
            "Number": str(series_number) if series_number else "0",
            "NumberFloat": float(series_number) if series_number else 0.0,
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
        if state:
            entry[envelope_key]["ReadingState"] = _build_reading_state(edition.uuid, state)
        else:
            entry[envelope_key]["ReadingState"] = _build_empty_reading_state(
                edition.uuid, edition.created_at
            )

    return entry


def _build_book_entry(
    book: Book,
    book_file: BookFile,
    state: Optional[KoboBookState],
    auth_token: str,
    base_url: str,
    is_new: bool = True,
) -> dict:
    """Legacy: build a Kobo entry from a Book record (used until migration 0034)."""
    kobo_base = f"{base_url}/kobo/{auth_token}"

    author_list: list[str] = []
    if book.authors:
        author_list = [a.name for a in book.authors]

    series_name = None
    series_number = None
    if book.series:
        series_name = book.series[0].name

    envelope_key = "NewEntitlement" if is_new else "ChangedEntitlement"

    entry: dict[str, Any] = {
        envelope_key: {
            "BookEntitlement": {
                "Accessibility": "Full",
                "ActivePeriod": {"From": _kobo_timestamp(book.created_at)},
                "Created": _kobo_timestamp(book.created_at),
                "CrossRevisionId": book.uuid,
                "Id": book.uuid,
                "IsHiddenFromArchive": False,
                "IsLocked": False,
                "IsRemoved": False,
                "LastModified": _kobo_timestamp(book.updated_at),
                "OriginCategory": "Imported",
                "RevisionId": book.uuid,
                "Status": "Active",
            },
            "BookMetadata": {
                "Categories": ["00000000-0000-0000-0000-000000000001"],
                "ContributorRoles": [{"Name": name} for name in author_list],
                "Contributors": author_list,
                "CoverImageId": (
                    f"{book.uuid}-{book.cover_hash}" if book.cover_hash else None
                ),
                "CrossRevisionId": book.uuid,
                "CurrentDisplayPrice": {"CurrencyCode": "USD", "TotalAmount": 0},
                "CurrentLoveDisplayPrice": {"TotalAmount": 0},
                "Description": book.description or "",
                "DownloadUrls": _build_download_urls(book, book.files or [], kobo_base),
                "EntitlementId": book.uuid,
                "IsEligibleForKoboLove": False,
                "IsInternetArchive": False,
                "IsPreOrder": False,
                "IsSocialEnabled": True,
                "Language": book.language or "en",
                "PhoneticPronunciations": {},
                "PublicationDate": _kobo_timestamp(book.published_date),
                "Publisher": {"Imprint": "", "Name": ""},
                "RevisionId": book.uuid,
                "Title": book.title,
                "WorkId": book.uuid,
            },
        }
    }

    if series_name:
        entry[envelope_key]["BookMetadata"]["Series"] = {
            "Name": series_name,
            "Number": str(series_number) if series_number else "0",
            "NumberFloat": float(series_number) if series_number else 0.0,
            "Id": series_name,
        }

    if state and is_new:
        entry[envelope_key]["ReadingState"] = _build_reading_state(book.uuid, state)

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


def _build_reading_state(entity_uuid: str, state: KoboBookState) -> dict:
    """Build the Kobo ReadingState object from our stored state."""
    status_info = {
        "LastModified": _kobo_timestamp(state.updated_at),
        "Status": state.status,
        "TimesStartedReading": state.times_started_reading,
    }
    # Add timestamp fields that BookLore includes
    if state.updated_at:
        status_info["LastTimeStartedReading"] = _kobo_timestamp(state.updated_at)
    if state.status == "Finished" and state.updated_at:
        status_info["LastTimeFinished"] = _kobo_timestamp(state.updated_at)

    return {
        "EntitlementId": entity_uuid,
        "Created": _kobo_timestamp(state.created_at),
        "LastModified": _kobo_timestamp(state.updated_at),
        "PriorityTimestamp": _kobo_timestamp(state.updated_at),
        "StatusInfo": status_info,
        "Statistics": {
            "LastModified": _kobo_timestamp(state.updated_at),
            "SpentReadingMinutes": state.time_spent_reading // 60,
            "RemainingTimeMinutes": 0,
        },
        "CurrentBookmark": {
            "LastModified": _kobo_timestamp(state.updated_at),
            "ContentSourceProgressPercent": state.content_source_progress,
            "Location": {
                "Source": state.content_id or "",
                "Type": "KoboSpan",
                "Value": f"spine#{state.spine_index}",
            },
            "ProgressPercent": state.content_source_progress,
        },
    }


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
) -> Optional[KoboBookState]:
    """Process a reading state update from a Kobo device.

    Looks up by UUID (which is identical on both Edition and Book rows during
    the transition period). Prefers Edition; falls back to Book.
    Updates KoboBookState and UserEdition (the canonical user reading state).
    """
    # Edition and Book are the same model (alias), so a single lookup is
    # sufficient. Accept either a UUID string or a numeric id — older
    # Scriptorium releases served Kobo entitlements with numeric ids as
    # the EntitlementId, and those are still cached on user devices.
    edition = await _find_edition_by_any_id(book_uuid, db)

    if edition is None:
        logger.warning("Reading state update for unknown UUID: %s", book_uuid)
        return None

    edition_id = edition.id

    # Upsert KoboBookState
    state_stmt = select(KoboBookState).where(
        KoboBookState.user_id == user_id,
        KoboBookState.edition_id == edition_id,
    )
    state_result = await db.execute(state_stmt)
    kobo_state = state_result.scalar_one_or_none()

    if not kobo_state:
        # Explicitly initialize numeric fields — the SQLAlchemy column
        # defaults don't apply to the Python object until after flush,
        # and downstream code (e.g. _sync_to_user_edition) may read them
        # before the session commits.
        kobo_state = KoboBookState(
            user_id=user_id,
            edition_id=edition_id,
            status="ReadyToRead",
            times_started_reading=0,
            current_page=0,
            time_spent_reading=0,
            content_source_progress=0.0,
            spine_index=0,
        )
        db.add(kobo_state)

    status_info = state_data.get("StatusInfo", {})
    if "Status" in status_info:
        kobo_state.status = status_info["Status"]
    if "TimesStartedReading" in status_info:
        kobo_state.times_started_reading = status_info["TimesStartedReading"]

    statistics = state_data.get("Statistics", {})
    if "SpentReadingMinutes" in statistics:
        kobo_state.time_spent_reading = statistics["SpentReadingMinutes"] * 60

    bookmark = state_data.get("CurrentBookmark", {})

    is_finished = kobo_state.status == "Finished"
    if not is_finished:
        if "ContentSourceProgressPercent" in bookmark:
            kobo_state.content_source_progress = bookmark["ContentSourceProgressPercent"]
        elif "ProgressPercent" in bookmark:
            kobo_state.content_source_progress = bookmark["ProgressPercent"]

        location = bookmark.get("Location", {})
        if location.get("Source"):
            kobo_state.content_id = location["Source"]
        val = location.get("Value", "")
        if val.startswith("spine#"):
            try:
                kobo_state.spine_index = int(val[6:])
            except ValueError:
                pass
    else:
        kobo_state.content_source_progress = 100.0

    kobo_state.updated_at = _utcnow()

    # Sync to UserEdition (canonical). The legacy ReadProgress sync path
    # was removed — its schema diverged from the helper's expectations
    # (no device_id column) and UserEdition is the authoritative table.
    await _sync_to_user_edition(user_id=user_id, edition_id=edition_id, kobo_state=kobo_state, db=db)

    await db.commit()
    await db.refresh(kobo_state)
    return kobo_state


async def _sync_to_user_edition(
    user_id: int,
    edition_id: int,
    kobo_state: KoboBookState,
    db: AsyncSession,
) -> None:
    """Sync Kobo reading state into the UserEdition table."""
    from app.models.edition import UserEdition

    stmt = select(UserEdition).where(
        UserEdition.user_id == user_id,
        UserEdition.edition_id == edition_id,
    )
    result = await db.execute(stmt)
    ue = result.scalar_one_or_none()

    if not ue:
        ue = UserEdition(user_id=user_id, edition_id=edition_id)
        db.add(ue)

    status_map = {
        "ReadyToRead": "want_to_read",
        "Reading": "reading",
        "Finished": "completed",
    }
    ue.status = status_map.get(kobo_state.status, "reading")
    ue.percentage = kobo_state.content_source_progress
    ue.current_page = kobo_state.current_page
    if kobo_state.total_pages:
        ue.total_pages = kobo_state.total_pages
    ue.last_opened = _utcnow()

    if ue.status == "completed" and not ue.completed_at:
        ue.completed_at = _utcnow()
    if (kobo_state.times_started_reading or 0) > 0 and not ue.started_at:
        ue.started_at = _utcnow()


async def _sync_to_read_progress(
    user_id: int,
    book_id: int,
    kobo_state: KoboBookState,
    db: AsyncSession,
) -> None:
    """Legacy: sync Kobo reading state into ReadProgress (kept for transition)."""
    stmt = select(ReadProgress).where(
        ReadProgress.user_id == user_id,
        ReadProgress.edition_id == book_id,
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    if not progress:
        device = await _get_or_create_kobo_device(user_id, db)
        progress = ReadProgress(
            user_id=user_id,
            edition_id=book_id,
            device_id=device.id,
        )
        db.add(progress)

    status_map = {
        "ReadyToRead": "reading",
        "Reading": "reading",
        "Finished": "completed",
    }
    progress.status = status_map.get(kobo_state.status, "reading")
    progress.percentage = kobo_state.content_source_progress
    progress.current_page = kobo_state.current_page
    if kobo_state.total_pages:
        progress.total_pages = kobo_state.total_pages
    progress.last_opened = _utcnow()

    if progress.status == "completed" and not progress.completed_at:
        progress.completed_at = _utcnow()
    if kobo_state.times_started_reading > 0 and not progress.started_at:
        progress.started_at = _utcnow()


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
) -> Optional[Path]:
    """Get the filesystem path for a file to serve to a Kobo device.

    Checks EditionFile first (new), then falls back to BookFile (legacy).
    """
    # Try EditionFile via Edition.uuid
    stmt = (
        select(EditionFile)
        .join(Edition, EditionFile.edition_id == Edition.id)
        .where(
            Edition.uuid == book_uuid,
            EditionFile.format == file_format,
        )
    )
    result = await db.execute(stmt)
    # Use scalars().first() instead of scalar_one_or_none() because some
    # editions have multiple files with the same format (e.g. duplicate
    # imports). Taking the first match is safe — all point to the same book.
    edition_file = result.scalars().first()

    if edition_file:
        from app.config import resolve_path

        # Auto-convert EPUB to KEPUB for better Kobo experience
        if file_format.lower() in ("epub", "kepub") and edition_file.format.lower() == "epub":
            try:
                from app.services.kepub import ensure_kepub
                kepub_path = await ensure_kepub(edition_file)
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
