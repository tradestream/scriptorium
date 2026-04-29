from fastapi import APIRouter

from app.api import (
    admin, analysis, annotations, api_keys, articles, audiobookshelf, auth, books, cross_analysis,
    loose_leaves, browse, collections, devices, duplicates, editions, export, goals, ingest, kobo,
    libraries, locations, marginalia, metadata, notebooks, opds, progress, read_sessions,
    reading_lists, search, shelves, stats, story_arcs, sync, tts, users, works,
)

router = APIRouter(prefix="/api/v1")

# Include all API routers
router.include_router(auth.router, tags=["auth"])
router.include_router(works.router, tags=["works"])
router.include_router(editions.router, tags=["editions"])
router.include_router(books.router, tags=["books"])
router.include_router(libraries.router, tags=["libraries"])
router.include_router(browse.router, tags=["browse"])
router.include_router(shelves.router, tags=["shelves"])
router.include_router(collections.router, tags=["collections"])
router.include_router(annotations.router, tags=["annotations"])
router.include_router(read_sessions.router, tags=["read-sessions"])
router.include_router(reading_lists.router, tags=["reading-lists"])
router.include_router(duplicates.router, tags=["duplicates"])
router.include_router(api_keys.router, tags=["api-keys"])
router.include_router(search.router, tags=["search"])
router.include_router(ingest.router, tags=["ingest"])
router.include_router(analysis.router, tags=["analysis"])
router.include_router(cross_analysis.router, tags=["cross-analysis"])
router.include_router(progress.router, tags=["progress"])
router.include_router(admin.router, tags=["admin"])
router.include_router(users.router, tags=["users"])
router.include_router(devices.router, tags=["devices"])
router.include_router(metadata.router, tags=["metadata"])
router.include_router(marginalia.router, tags=["marginalia"])
router.include_router(export.router, tags=["export"])
router.include_router(stats.router, tags=["stats"])
router.include_router(notebooks.router, tags=["notebooks"])
router.include_router(loose_leaves.router, tags=["loose-leaves"])
router.include_router(goals.router, tags=["goals"])
router.include_router(locations.router, tags=["locations"])
router.include_router(articles.router, tags=["articles"])
router.include_router(audiobookshelf.router, tags=["audiobookshelf"])
router.include_router(story_arcs.router, tags=["story-arcs"])
router.include_router(tts.router, tags=["tts"])
router.include_router(kobo.kobo_management_router)

# Routers mounted at app root (not under /api/v1):

# Kobo device sync: /kobo/{token}/v1/...
kobo_device_router = kobo.kobo_device_router

# OPDS catalog: /opds/catalog, /opds/search, etc.
opds_router = opds.router

# KOReader kosync-compatible: /api/ko/users/..., /api/ko/syncs/...
koreader_router = sync.router

__all__ = ["router", "kobo_device_router", "opds_router", "koreader_router"]
