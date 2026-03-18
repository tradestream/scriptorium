"""Kobo annotation sync — receives Koblime-style pushes from device.

Handles:
- Ingesting raw Bookmark table rows from the Kobo device
- Smart merge: only update if device data is newer (prevents data loss on book removal)
- Auto-mapping VolumeID → Scriptorium edition
- Converting Kobo bookmarks to Scriptorium Annotation model
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kobo_bookmark import KoboBookmark, KoboContentMap

logger = logging.getLogger(__name__)


async def resolve_volume_id(volume_id: str, db: AsyncSession) -> Optional[int]:
    """Map a Kobo VolumeID to a Scriptorium edition_id.

    Kobo VolumeIDs look like:
    - "file:///mnt/onboard/KePub/My Book.kepub.epub" (sideloaded)
    - "file:///mnt/onboard/My Book.epub"
    - A content hash / UUID for store-purchased books

    We try:
    1. Cached mapping in kobo_content_map
    2. Match by filename against edition_files
    3. Match by UUID
    """
    # 1. Check cache
    result = await db.execute(
        select(KoboContentMap.edition_id).where(KoboContentMap.volume_id == volume_id)
    )
    cached = result.scalar_one_or_none()
    if cached:
        return cached

    # 2. Try matching by filename
    from app.models.edition import Edition, EditionFile
    filename = volume_id.split("/")[-1] if "/" in volume_id else volume_id
    # Strip .kepub.epub → .epub for matching
    filename_clean = filename.replace(".kepub.epub", ".epub")

    if filename_clean:
        file_result = await db.execute(
            select(EditionFile.edition_id)
            .where(EditionFile.filename.ilike(f"%{filename_clean}%"))
            .limit(1)
        )
        edition_id = file_result.scalar_one_or_none()
        if edition_id:
            db.add(KoboContentMap(volume_id=volume_id, edition_id=edition_id))
            return edition_id

    # 3. Try matching by UUID (some ContentIDs are UUIDs)
    uuid_result = await db.execute(
        select(Edition.id).where(Edition.uuid == volume_id).limit(1)
    )
    edition_id = uuid_result.scalar_one_or_none()
    if edition_id:
        db.add(KoboContentMap(volume_id=volume_id, edition_id=edition_id))
        return edition_id

    return None


async def sync_bookmarks(
    user_id: int,
    bookmarks: list[dict],
    device_id: Optional[str],
    db: AsyncSession,
) -> dict:
    """Ingest a batch of Kobo Bookmark table rows.

    Smart merge: only update if the incoming data is newer (date_modified).
    When a book is removed from Kobo, it zeroes out data — we detect this
    by checking if the new record has less content than the existing one.

    Returns: {"created": int, "updated": int, "skipped": int, "mapped": int}
    """
    created = 0
    updated = 0
    skipped = 0
    mapped = 0

    for bm in bookmarks:
        bookmark_id = bm.get("BookmarkID") or bm.get("bookmark_id", "")
        if not bookmark_id:
            skipped += 1
            continue

        volume_id = bm.get("VolumeID") or bm.get("volume_id", "")

        # Parse dates
        date_created = _parse_date(bm.get("DateCreated") or bm.get("date_created"))
        date_modified = _parse_date(bm.get("DateModified") or bm.get("date_modified"))

        text = bm.get("Text") or bm.get("text")
        annotation = bm.get("Annotation") or bm.get("annotation")

        # Check for existing bookmark
        result = await db.execute(
            select(KoboBookmark).where(
                KoboBookmark.user_id == user_id,
                KoboBookmark.bookmark_id == bookmark_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Smart merge: don't let a blank record overwrite a populated one
            # (Kobo zeros data when a book is removed from the device)
            existing_has_content = bool(existing.text or existing.annotation)
            incoming_has_content = bool(text or annotation)

            if existing_has_content and not incoming_has_content:
                # Device sent blank data — book was probably removed. Skip.
                skipped += 1
                continue

            # Only update if incoming is newer
            if existing.date_modified and date_modified:
                if date_modified <= existing.date_modified:
                    skipped += 1
                    continue

            # Update existing
            existing.text = text
            existing.annotation = annotation
            existing.start_container_path = bm.get("StartContainerPath") or bm.get("start_container_path")
            existing.start_container_child_index = bm.get("StartContainerChildIndex") or bm.get("start_container_child_index")
            existing.start_offset = bm.get("StartOffset") or bm.get("start_offset")
            existing.end_container_path = bm.get("EndContainerPath") or bm.get("end_container_path")
            existing.end_container_child_index = bm.get("EndContainerChildIndex") or bm.get("end_container_child_index")
            existing.end_offset = bm.get("EndOffset") or bm.get("end_offset")
            existing.extra_annotation_data = bm.get("ExtraAnnotationData") or bm.get("extra_annotation_data")
            existing.date_modified = date_modified
            existing.device_id = device_id
            existing.synced_at = datetime.utcnow()
            updated += 1
        else:
            # Resolve edition
            edition_id = await resolve_volume_id(volume_id, db) if volume_id else None
            if edition_id:
                mapped += 1

            new_bm = KoboBookmark(
                user_id=user_id,
                edition_id=edition_id,
                bookmark_id=bookmark_id,
                volume_id=volume_id,
                text=text,
                annotation=annotation,
                start_container_path=bm.get("StartContainerPath") or bm.get("start_container_path"),
                start_container_child_index=bm.get("StartContainerChildIndex") or bm.get("start_container_child_index"),
                start_offset=bm.get("StartOffset") or bm.get("start_offset"),
                end_container_path=bm.get("EndContainerPath") or bm.get("end_container_path"),
                end_container_child_index=bm.get("EndContainerChildIndex") or bm.get("end_container_child_index"),
                end_offset=bm.get("EndOffset") or bm.get("end_offset"),
                extra_annotation_data=bm.get("ExtraAnnotationData") or bm.get("extra_annotation_data"),
                date_created=date_created,
                date_modified=date_modified,
                device_id=device_id,
            )
            db.add(new_bm)
            created += 1

    await db.commit()

    # Also create Scriptorium Annotation records for new highlights/notes
    annotations_created = await _create_annotations(user_id, db)

    logger.info(
        "Kobo bookmark sync: created=%d updated=%d skipped=%d mapped=%d annotations=%d",
        created, updated, skipped, mapped, annotations_created,
    )
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "mapped": mapped,
        "annotations_created": annotations_created,
    }


async def _create_annotations(user_id: int, db: AsyncSession) -> int:
    """Convert KoboBookmarks into Scriptorium Annotations (if not already linked)."""
    from app.models.annotation import Annotation

    # Find Kobo bookmarks with text (highlights/annotations) that have an edition
    # but don't have a corresponding Annotation yet
    result = await db.execute(
        select(KoboBookmark).where(
            KoboBookmark.user_id == user_id,
            KoboBookmark.edition_id.isnot(None),
            KoboBookmark.text.isnot(None),
            KoboBookmark.text != "",
        )
    )
    kobo_bms = result.scalars().all()

    # Get existing annotations for this user (by edition + location to dedup)
    existing_result = await db.execute(
        select(Annotation.edition_id, Annotation.location, Annotation.source)
        .where(Annotation.user_id == user_id, Annotation.source == "kobo")
    )
    existing_keys = set((r[0], r[1]) for r in existing_result.all())

    count = 0
    for bm in kobo_bms:
        location = bm.start_container_path or f"kobo:{bm.bookmark_id}"
        key = (bm.edition_id, location)
        if key in existing_keys:
            continue

        ann_type = "highlight" if not bm.annotation else "note"
        ann = Annotation(
            user_id=user_id,
            edition_id=bm.edition_id,
            type=ann_type,
            content=bm.annotation or bm.text,
            location=location,
            chapter=None,
            color="yellow",
            source="kobo",
        )
        db.add(ann)
        existing_keys.add(key)
        count += 1

    if count:
        await db.commit()

    return count


def _parse_date(val) -> Optional[datetime]:
    """Parse a date from Kobo's format (ISO string or unix timestamp)."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        return datetime.utcfromtimestamp(val)
    try:
        # Kobo uses ISO format with or without Z
        return datetime.fromisoformat(str(val).replace("Z", "+00:00").replace("+00:00", ""))
    except (ValueError, TypeError):
        return None
