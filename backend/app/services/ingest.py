"""File ingest service — watches the ingest directory and imports new books."""

import asyncio
import logging
from pathlib import Path

from app.config import get_settings, resolve_path
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
            from watchfiles import Change, awatch

            from app.services.exclude_patterns import build_matcher, is_excluded

            # Ingest isn't tied to a library, so we apply only the
            # built-in defaults plus any ``.scriptoriumignore`` at the
            # ingest root. Recompute on each batch so a fresh
            # ``.scriptoriumignore`` is picked up without restarting.
            async for changes in awatch(str(self.ingest_path), recursive=True):
                if not self.is_running:
                    break
                matcher = build_matcher(self.ingest_path, library_exclude_json=None)
                for change_type, path_str in changes:
                    if change_type in (Change.added, Change.modified):
                        path = Path(path_str)
                        if not (path.is_file() and path.suffix.lower() in BOOK_EXTENSIONS):
                            continue
                        if is_excluded(path, self.ingest_path, matcher):
                            logger.debug("ingest: skipping %s (matched exclude)", path.name)
                            continue
                        await self._ingest_file(path)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Ingest watcher error: %s", exc)

    def _detect_library_from_path(self, file_path: Path) -> str | None:
        """Detect target library from subfolder name.

        If a file is at /data/ingest/Books/mybook.epub, return "Books".
        If at /data/ingest/mybook.epub (root), return None.
        """
        try:
            relative = file_path.relative_to(self.ingest_path)
            parts = relative.parts
            if len(parts) > 1:
                return parts[0]  # subfolder name = library name
        except ValueError:
            pass
        return None

    async def _ingest_file(self, file_path: Path):
        """Import a single file into the appropriate library.

        Library resolution order:
        1. Subfolder name (e.g. /ingest/Books/file.epub → "Books" library)
        2. INGEST_DEFAULT_LIBRARY env var
        3. First active library
        """
        from sqlalchemy import func, select

        from app.database import get_session_factory
        from app.models import Library
        from app.models.ingest import IngestLog
        from app.services.scanner import _hash_file, _import_book

        factory = get_session_factory()
        try:
            async with factory() as db:
                library = None

                # 1. Try subfolder name → library
                subfolder = self._detect_library_from_path(file_path)
                if subfolder:
                    result = await db.execute(
                        select(Library).where(
                            func.lower(Library.name) == subfolder.lower()
                        ).limit(1)
                    )
                    library = result.scalar_one_or_none()
                    if library:
                        logger.debug("Matched subfolder '%s' → library '%s'", subfolder, library.name)

                # 2. Try INGEST_DEFAULT_LIBRARY setting
                if library is None and settings.INGEST_DEFAULT_LIBRARY:
                    result = await db.execute(
                        select(Library).where(
                            func.lower(Library.name) == settings.INGEST_DEFAULT_LIBRARY.lower()
                        ).limit(1)
                    )
                    library = result.scalar_one_or_none()

                # 3. Fall back to first active library
                if library is None:
                    result = await db.execute(
                        select(Library).where(Library.is_active == True)
                        .order_by(Library.id)
                        .limit(1)
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
                from sqlalchemy import select as _sel

                from app.models.system import SystemSettings
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

                result = await _import_book(file_path, file_hash, library, db)
                if result is None:
                    logger.warning("Unsupported format: %s", file_path.name)
                    db.add(IngestLog(filename=file_path.name, status='error', error_message='Unsupported format'))
                    await db.commit()
                    return
                work, edition, edition_file = result
                book = edition  # alias for downstream code
                logger.info("Ingested %s into library '%s'", file_path.name, library.name)
                db.add(IngestLog(filename=file_path.name, status='imported'))
                await db.commit()

                # Broadcast to connected WebSocket clients
                try:
                    from app.services.events import broadcaster
                    await broadcaster.ingest_progress(file_path.name, "imported", edition.id)
                    await broadcaster.book_added(edition.id, work.title, library.id)
                except Exception:
                    pass  # events are non-critical

                # Extract identifiers (ISBN/DOI) from file content
                if book:
                    try:
                        from app.services.identifier_extraction import (
                            extract_identifiers_for_edition,
                        )
                        await extract_identifiers_for_edition(book.id)
                    except Exception:
                        pass  # identifier extraction is non-critical

                # Auto-enrich metadata from external providers (non-blocking)
                if book:
                    try:
                        from sqlalchemy.orm import joinedload as _jl

                        from app.api.books import _apply_enrichment
                        from app.models.edition import Edition
                        from app.models.work import Work
                        from app.services.metadata_enrichment import enrichment_service

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

                # Move file to the library directory, applying naming pattern if enabled.
                #
                # ``library.path`` is stored as a container-side path (e.g.
                # ``/data/library/booklore/books``). When the worker runs on
                # the host, that prefix doesn't exist — translate via
                # PATH_REWRITE to get the host-side destination, do the move,
                # then store the canonical container-side path on the row so
                # other consumers (kobo, reader, etc.) keep seeing one shape.
                lib_container = library.path
                lib_host = resolve_path(lib_container)

                def _to_container(host_path: Path) -> str:
                    s = str(host_path)
                    if lib_host != lib_container and s.startswith(lib_host):
                        return lib_container + s[len(lib_host):]
                    return s

                if naming_enabled and edition:

                    from app.services.naming import build_relative_path
                    pattern = effective_pattern
                    year = None
                    if edition.published_date:
                        try:
                            year = edition.published_date.year if hasattr(edition.published_date, 'year') else int(str(edition.published_date)[:4])
                        except Exception:
                            pass
                    rel = build_relative_path(
                        pattern,
                        title=work.title,
                        authors=[a.name for a in work.authors] if work.authors else [],
                        file_ext=file_path.suffix.lower(),
                        year=year,
                        series=work.series[0].name if work.series else None,
                        language=work.language,
                        publisher=edition.publisher,
                        isbn=edition.isbn,
                    )
                    dest = Path(lib_host) / rel
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
                    from sqlalchemy import select as _select

                    from app.models.edition import EditionFile
                    if file_path.exists():
                        ef_result = await db.execute(
                            _select(EditionFile).where(EditionFile.file_hash == file_hash)
                        )
                        ef = ef_result.scalar_one_or_none()
                        file_path.rename(dest)
                        if ef:
                            ef.file_path = _to_container(dest)
                            ef.filename = dest.name
                            await db.commit()
                else:
                    dest = Path(lib_host) / file_path.name
                    Path(lib_host).mkdir(parents=True, exist_ok=True)
                    if file_path.exists() and not dest.exists():
                        file_path.rename(dest)
                        # Reflect the new location on the row, in container shape.
                        from sqlalchemy import select as _select

                        from app.models.edition import EditionFile
                        ef_result = await db.execute(
                            _select(EditionFile).where(EditionFile.file_hash == file_hash)
                        )
                        ef = ef_result.scalar_one_or_none()
                        if ef:
                            ef.file_path = _to_container(dest)
                            ef.filename = dest.name
                            await db.commit()

                # Pre-emptive KEPUB conversion. Scheduled here (after
                # the move + commit) so the cached kepub_path matches
                # the file's final library location.
                if edition_file is not None and edition is not None:
                    if (edition_file.format or "").lower() == "epub" and not edition.is_fixed_layout:
                        if settings.KEPUB_AUTO_CONVERT:
                            from app.services.kepub import schedule_kepub_conversion
                            schedule_kepub_conversion(edition_file.id)
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

    async def _excluded_in_ingest(self, file_path: Path) -> bool:
        """Defaults + ``.scriptoriumignore`` at the ingest root."""
        from app.services.exclude_patterns import build_matcher, is_excluded
        matcher = build_matcher(self.ingest_path, library_exclude_json=None)
        return is_excluded(file_path, self.ingest_path, matcher)

    async def trigger_scan(self):
        """Process all existing files in the ingest directory immediately.

        Scans root and subdirectories (subfolder name = target library).
        """
        logger.info("Ingest: scanning %s for existing files", self.ingest_path)
        from app.services.exclude_patterns import build_matcher, is_excluded
        matcher = build_matcher(self.ingest_path, library_exclude_json=None)
        for file_path in self.ingest_path.rglob("*"):
            if not (file_path.is_file() and file_path.suffix.lower() in BOOK_EXTENSIONS):
                continue
            if is_excluded(file_path, self.ingest_path, matcher):
                logger.debug("ingest: skipping %s (matched exclude)", file_path.name)
                continue
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
        from sqlalchemy import func, select

        from app.database import get_session_factory
        from app.models.ingest import IngestLog

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
