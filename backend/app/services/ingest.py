"""File ingest service — watches the ingest directory and imports new books."""

import asyncio
import logging
from pathlib import Path

from app.config import get_settings
from app.services.scanner import BOOK_EXTENSIONS

logger = logging.getLogger("scriptorium.ingest")

settings = get_settings()


class IngestService:
    """Watches the ingest directory and pipes new book files into the library scanner."""

    def __init__(self):
        self.ingest_path = Path(settings.INGEST_PATH)
        self.library_path = Path(settings.LIBRARY_PATH)
        self.is_running = False
        self._task: asyncio.Task | None = None

    async def start_watcher(self):
        """Start background watchfiles task monitoring the ingest directory."""
        self.ingest_path.mkdir(parents=True, exist_ok=True)
        self.is_running = True
        self._task = asyncio.create_task(self._watch_loop(), name="ingest-watcher")
        logger.info("Ingest watcher started on %s", self.ingest_path)

    async def stop_watcher(self):
        """Cancel the watcher task cleanly."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Ingest watcher stopped")

    async def _watch_loop(self):
        """Inner loop: use watchfiles to detect new/modified files."""
        try:
            from watchfiles import awatch, Change

            async for changes in awatch(str(self.ingest_path)):
                if not self.is_running:
                    break
                for change_type, path_str in changes:
                    if change_type in (Change.added, Change.modified):
                        path = Path(path_str)
                        if path.is_file() and path.suffix.lower() in BOOK_EXTENSIONS:
                            await self._ingest_file(path)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Ingest watcher error: %s", exc)

    async def _ingest_file(self, file_path: Path):
        """Import a single file from the ingest directory into the default library."""
        from app.database import get_session_factory
        from app.models import Library
        from app.models.ingest import IngestLog
        from app.services.scanner import _import_book, _hash_file
        from sqlalchemy import select

        factory = get_session_factory()
        try:
            async with factory() as db:
                # Find or create a default "Ingest" library
                result = await db.execute(
                    select(Library).where(Library.name == "Ingest").limit(1)
                )
                library = result.scalar_one_or_none()

                if library is None:
                    # Fall back to the first active library
                    result = await db.execute(
                        select(Library).where(Library.is_active == True).limit(1)
                    )
                    library = result.scalar_one_or_none()

                if library is None:
                    logger.warning("No library found to ingest '%s' into", file_path.name)
                    db.add(IngestLog(
                        filename=file_path.name,
                        status='error',
                        error_message='No library found to ingest into',
                    ))
                    await db.commit()
                    return

                # Load system settings for naming priority resolution
                from app.models.system import SystemSettings
                from sqlalchemy import select as _sel
                ss_result = await db.execute(_sel(SystemSettings).where(SystemSettings.id == 1))
                sys_settings = ss_result.scalar_one_or_none()

                # Determine naming_enabled and effective pattern (priority: library > system DB > env)
                from app.services.naming import DEFAULT_PATTERN
                naming_enabled = (
                    sys_settings.naming_enabled if sys_settings is not None
                    else settings.LIBRARY_NAMING_ENABLED
                )
                effective_pattern = (
                    library.naming_pattern  # per-library override (highest priority)
                    or (sys_settings.naming_pattern if sys_settings is not None else None)
                    or settings.LIBRARY_NAMING_PATTERN
                    or DEFAULT_PATTERN
                )

                file_hash = _hash_file(file_path)
                from app.models import BookFile
                existing = await db.scalar(
                    select(BookFile.id).where(BookFile.file_hash == file_hash).limit(1)
                )
                if existing:
                    logger.debug("Skipping duplicate: %s", file_path.name)
                    db.add(IngestLog(filename=file_path.name, status='duplicate'))
                    await db.commit()
                    return

                book = await _import_book(file_path, file_hash, library, db)
                logger.info("Ingested %s into library '%s'", file_path.name, library.name)
                db.add(IngestLog(filename=file_path.name, status='imported'))
                await db.commit()

                # Broadcast to connected WebSocket clients
                try:
                    from app.services.events import broadcaster
                    book_id = book.id if book else None
                    await broadcaster.ingest_progress(file_path.name, "imported", book_id)
                    if book:
                        await broadcaster.book_added(book.id, book.title, library.id)
                except Exception:
                    pass  # events are non-critical

                # Extract identifiers (ISBN/DOI) from file content
                if book:
                    try:
                        from app.services.identifier_extraction import extract_identifiers_for_edition
                        await extract_identifiers_for_edition(book.id)
                    except Exception:
                        pass  # identifier extraction is non-critical

                # Auto-enrich metadata from external providers (non-blocking)
                if book:
                    try:
                        from app.services.metadata_enrichment import enrichment_service
                        from app.api.books import _apply_enrichment
                        from sqlalchemy.orm import joinedload as _jl
                        from app.models.edition import Edition
                        from app.models.work import Work

                        ed_result = await db.execute(
                            select(Edition).where(Edition.id == book.id)
                            .options(_jl(Edition.work).options(_jl(Work.authors), _jl(Work.tags)))
                        )
                        edition = ed_result.unique().scalar_one_or_none()
                        if edition:
                            work = edition.work
                            author_names = [a.name for a in work.authors] if work.authors else []
                            file_ext = file_path.suffix.lower()
                            enriched = await enrichment_service.enrich(
                                work.title, author_names, edition.isbn, file_extension=file_ext
                            )
                            if enriched:
                                await _apply_enrichment(db, edition, work, enriched, force=False)
                                await db.commit()
                                logger.info("Auto-enriched '%s' from metadata providers", work.title)
                    except Exception as enrich_exc:
                        logger.debug("Auto-enrich failed for %s: %s", file_path.name, enrich_exc)

                # Generate cached markdown (non-blocking, non-critical)
                if book:
                    try:
                        from app.services.markdown import generate_markdown
                        await generate_markdown(book.id)
                    except Exception:
                        pass  # markdown generation is non-critical

                # Move file to the library directory, applying naming pattern if enabled
                if naming_enabled and book:
                    from app.services.naming import build_relative_path
                    from datetime import datetime as _dt
                    pattern = effective_pattern
                    year = None
                    if book.published_date:
                        try:
                            year = book.published_date.year if hasattr(book.published_date, 'year') else int(str(book.published_date)[:4])
                        except Exception:
                            pass
                    rel = build_relative_path(
                        pattern,
                        title=book.title,
                        authors=[a.name for a in book.authors],
                        file_ext=file_path.suffix.lower(),
                        year=year,
                        series=book.series[0].name if book.series else None,
                        language=book.language,
                        publisher=book.publisher,
                        isbn=book.isbn,
                    )
                    dest = Path(library.path) / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    # Avoid clobbering an existing file
                    if dest.exists():
                        stem, ext = dest.stem, dest.suffix
                        for n in range(2, 100):
                            candidate = dest.with_name(f"{stem} ({n}){ext}")
                            if not candidate.exists():
                                dest = candidate
                                break
                    # Update the stored file_path to the new location
                    from app.models import BookFile
                    from sqlalchemy import select as _select
                    bf_result = await db.execute(_select(BookFile).where(BookFile.file_hash == file_hash))
                    bf = bf_result.scalar_one_or_none()
                    file_path.rename(dest)
                    if bf:
                        bf.file_path = str(dest)
                        bf.filename = dest.name
                        await db.commit()
                else:
                    dest = Path(library.path) / file_path.name
                    if not dest.exists():
                        file_path.rename(dest)
        except Exception as exc:
            logger.error("Error processing %s: %s", file_path.name, exc)
            try:
                async with factory() as db:
                    db.add(IngestLog(
                        filename=file_path.name,
                        status='error',
                        error_message=str(exc),
                    ))
                    await db.commit()
            except Exception as log_exc:
                logger.error("Ingest: failed to log error for %s: %s", file_path.name, log_exc)

    async def trigger_scan(self):
        """Process all existing files in the ingest directory immediately."""
        logger.info("Ingest: scanning %s for existing files", self.ingest_path)
        for file_path in self.ingest_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in BOOK_EXTENSIONS:
                await self._ingest_file(file_path)

    async def get_ingest_status(self):
        """Return current ingest service status."""
        pending = [
            f.name
            for f in self.ingest_path.iterdir()
            if f.is_file() and f.suffix.lower() in BOOK_EXTENSIONS
        ] if self.ingest_path.exists() else []
        return {
            "is_running": self.is_running,
            "ingest_path": str(self.ingest_path),
            "pending_files": len(pending),
            "pending_names": pending[:20],  # cap for response size
        }

    async def get_history(self, skip: int = 0, limit: int = 50) -> dict:
        """Return paginated ingest log entries from the database."""
        from app.database import get_session_factory
        from app.models.ingest import IngestLog
        from sqlalchemy import select, func

        factory = get_session_factory()
        async with factory() as db:
            total = await db.scalar(select(func.count(IngestLog.id)))
            result = await db.execute(
                select(IngestLog).order_by(IngestLog.created_at.desc()).offset(skip).limit(limit)
            )
            items = result.scalars().all()
            return {"items": items, "total": total or 0, "skip": skip, "limit": limit}


# Global instance
ingest_service = IngestService()
