import asyncio
import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api import kobo_device_router, koreader_router, opds_router, router
from app.config import get_settings
from app.database import close_db, init_db
from app.middleware import AccessLogMiddleware, SecurityHeadersMiddleware
from app.services.events import broadcaster
from app.services.ingest import ingest_service

settings = get_settings()


def _rate_limit_key(request: Request) -> str | None:
    """Rate limit key function — exempt Kobo sync paths.

    Kobo devices make many rapid requests during sync; rate limiting
    breaks the protocol. Return None to skip rate limiting for /kobo/ paths.
    """
    if request.url.path.startswith("/kobo/"):
        return None
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key, default_limits=["300/minute"])

# Structured logging configuration
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },
        "root": {"handlers": ["console"], "level": "INFO"},
        "loggers": {
            "scriptorium": {"level": "INFO", "propagate": True},
            "uvicorn.access": {"level": "WARNING", "propagate": False},  # suppress uvicorn's own access log
        },
    }
)
logger = logging.getLogger("scriptorium")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Scriptorium backend...")

    # Create required directories
    Path(settings.LIBRARY_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.INGEST_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.CONFIG_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.COVERS_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.MARKDOWN_PATH).mkdir(parents=True, exist_ok=True)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Load DB-backed enrichment key overrides into memory
    try:
        from app.database import get_session_factory
        from app.models.system import SystemSettings
        from app.services.metadata_enrichment import apply_enrichment_key_overrides
        from sqlalchemy import select as _sel
        _factory = get_session_factory()
        async with _factory() as _db:
            _ss = await _db.scalar(_sel(SystemSettings).where(SystemSettings.id == 1))
            if _ss:
                apply_enrichment_key_overrides({
                    "HARDCOVER_API_KEY": _ss.hardcover_api_key,
                    "COMICVINE_API_KEY": _ss.comicvine_api_key,
                    "GOOGLE_BOOKS_API_KEY": _ss.google_books_api_key,
                    "ISBNDB_API_KEY": _ss.isbndb_api_key,
                    "AMAZON_COOKIE": _ss.amazon_cookie,
                    "LIBRARYTHING_API_KEY": _ss.librarything_api_key,
                })
        logger.info("Enrichment key overrides loaded from DB")
    except Exception as _e:
        logger.warning("Could not load enrichment key overrides: %s", _e)

    # Start file watcher + scan existing files in ingest folder
    await ingest_service.start_watcher()
    logger.info("Ingest service started")
    # Delay startup scan to avoid race with other workers; use a lock file
    async def _deferred_scan():
        import tempfile, os
        lock = Path(tempfile.gettempdir()) / "scriptorium_ingest_scan.lock"
        try:
            # Only one worker gets the lock
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            await asyncio.sleep(2)  # let other workers start first
            await ingest_service.trigger_scan()
        except FileExistsError:
            pass  # another worker already scanning
        finally:
            try:
                lock.unlink(missing_ok=True)
            except Exception:
                pass
    asyncio.create_task(_deferred_scan())

    # One-shot KEPUB backfill — convert every existing EPUB the first
    # time this build runs against an existing library. After it
    # completes successfully (or partially — see _run_bulk_kepub), the
    # ``system_settings.kepub_backfill_done`` flag flips so we don't
    # re-queue every restart. Gated on KEPUB_AUTO_CONVERT so households
    # that don't want pre-conversion can opt out.
    async def _deferred_kepub_backfill():
        import tempfile, os
        from app.config import get_settings as _gs
        if not _gs().KEPUB_AUTO_CONVERT:
            return
        lock = Path(tempfile.gettempdir()) / "scriptorium_kepub_backfill.lock"
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            return  # another worker handling it
        try:
            # Wait until after the ingest scan has had a chance to
            # settle; backfill is opportunistic, not urgent.
            await asyncio.sleep(10)

            from app.database import get_session_factory
            from app.models.system import SystemSettings
            from app.models.edition import Edition, EditionFile
            from app.services.background_jobs import create_job, get_active_job
            from app.api.admin import _run_bulk_kepub
            from sqlalchemy import select, func

            factory = get_session_factory()
            async with factory() as db:
                ss = await db.scalar(select(SystemSettings).where(SystemSettings.id == 1))
                if ss is not None and ss.kepub_backfill_done:
                    return
                stmt = (
                    select(EditionFile.id)
                    .join(Edition, EditionFile.edition_id == Edition.id)
                    .where(EditionFile.format == "epub")
                    .where(EditionFile.kepub_path.is_(None))
                    .where(Edition.is_fixed_layout.is_(False))
                )
                ef_ids = [row[0] for row in (await db.execute(stmt)).all()]

            if not ef_ids:
                # Nothing to do — flip the flag so we don't re-query
                # this on every restart of an all-converted library.
                async with factory() as db:
                    ss = await db.scalar(select(SystemSettings).where(SystemSettings.id == 1))
                    if ss is None:
                        ss = SystemSettings(id=1, kepub_backfill_done=True)
                        db.add(ss)
                    else:
                        ss.kepub_backfill_done = True
                    await db.commit()
                return

            # Don't double-queue if an admin already kicked one.
            if await get_active_job("bulk_kepub") is not None:
                return

            job_id, _ = await create_job("bulk_kepub", len(ef_ids))
            logger.info(
                "Auto-kicking KEPUB backfill: %d EPUB(s) need conversion (job %s)",
                len(ef_ids), job_id,
            )
            asyncio.create_task(_run_bulk_kepub(job_id, ef_ids))
        finally:
            try:
                lock.unlink(missing_ok=True)
            except Exception:
                pass

    asyncio.create_task(_deferred_kepub_backfill())

    yield

    # Shutdown
    logger.info("Shutting down Scriptorium backend...")
    await ingest_service.stop_watcher()
    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Scriptorium",
        description="Self-hosted book and comics library server",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Security headers (outermost so they're on every response)
    app.add_middleware(SecurityHeadersMiddleware)

    # Structured access logging
    app.add_middleware(AccessLogMiddleware)

    # CORS middleware for SvelteKit dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(router)

    # Kobo device sync router (mounted at root, not under /api/v1)
    # Kobo devices expect: /kobo/{auth_token}/v1/...
    app.include_router(kobo_device_router)

    # OPDS catalog (mounted at root: /opds/...)
    # E-readers expect /opds/catalog, /opds/search, etc.
    app.include_router(opds_router)

    # KOReader kosync (mounted at root: /api/ko/...)
    # KOReader Progress Sync plugin expects /api/ko/users/auth etc.
    app.include_router(koreader_router)

    # Static file serving for covers
    covers_path = Path(settings.COVERS_PATH)
    covers_path.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/covers",
        StaticFiles(directory=str(covers_path)),
        name="covers",
    )

    # Health check endpoint
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "service": "Scriptorium"}

    # WebSocket endpoint — real-time library events
    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        """WebSocket endpoint for real-time library events.

        Clients receive JSON messages:
          {"type": "book_added",       "data": {"id": 1, "title": "...", "library_id": 1}}
          {"type": "ingest_progress",  "data": {"filename": "...", "status": "imported", "book_id": 1}}
          {"type": "library_scan_done","data": {"library_id": 1, "added": 5, "updated": 2}}
        """
        await broadcaster.connect(websocket)
        try:
            while True:
                # Keep the connection alive; clients don't send messages
                await websocket.receive_text()
        except WebSocketDisconnect:
            await broadcaster.disconnect(websocket)

    # SSE endpoint — lighter alternative to WebSocket with heartbeat
    @app.get("/api/v1/events/stream")
    async def sse_events(request: Request):
        """Server-Sent Events endpoint for real-time library updates.

        Sends a heartbeat every 15 seconds to keep the connection alive.
        Lighter than WebSocket — no bidirectional channel needed.
        """
        import json as _json
        from starlette.responses import StreamingResponse

        async def event_generator():
            queue: asyncio.Queue = asyncio.Queue()

            # Register this SSE client with the broadcaster
            async def on_event(event_type: str, data: dict):
                await queue.put({"type": event_type, **data})

            broadcaster.sse_clients.append(on_event)
            try:
                while True:
                    try:
                        # Wait up to 15s for an event; send heartbeat if timeout
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"data: {_json.dumps(event)}\n\n"
                    except asyncio.TimeoutError:
                        # Heartbeat — keeps the connection alive through proxies
                        yield ": heartbeat\n\n"

                    # Check if client disconnected
                    if await request.is_disconnected():
                        break
            finally:
                broadcaster.sse_clients.remove(on_event)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
