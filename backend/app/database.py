"""Database engine + session factory.

The single source of truth is ``_engine`` — every session created by
``_session_factory`` uses the same underlying connection pool. SQLite
PRAGMAs are per-connection, so we hook them via a SQLAlchemy ``connect``
event listener on the sync engine. ``init_db`` no longer creates and
disposes a separate engine for setup.
"""
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()


def _attach_sqlite_pragmas(sync_engine: Engine) -> None:
    """Set SQLite PRAGMAs on every new connection.

    SQLite PRAGMAs (``foreign_keys``, ``journal_mode``, ``synchronous``)
    are per-connection. Configuring them once on a setup engine has no
    effect on the runtime pool's connections. The ``connect`` event
    fires for every fresh DBAPI connection the pool opens, so this is
    the only way to enforce them across the lifetime of the app.

    Skipped for non-SQLite backends so the same module works if we ever
    move to Postgres.
    """
    if not str(sync_engine.url).startswith("sqlite"):
        return

    @event.listens_for(sync_engine, "connect")
    def _set_pragmas(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


def _build_engine():
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    # ``sync_engine`` is the underlying DBAPI engine that the async
    # wrapper drives — that's where SQLAlchemy's connect event fires.
    _attach_sqlite_pragmas(engine.sync_engine)
    return engine


# Single module-level engine. Both init_db (one-time setup) and the
# request-scoped session factory share it so PRAGMAs apply uniformly.
_engine = _build_engine()
_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_engine():
    """Return the shared application engine."""
    return _engine


def get_session_factory():
    """Return the shared session factory."""
    return _session_factory


async def init_db() -> None:
    """One-time startup: ensure the FTS5 index exists.

    PRAGMAs are now applied via the connect-event listener on
    ``_engine``; this function only does the schema-side setup that
    needs a connection (FTS5 virtual table + triggers).
    """
    from app.services.search import ensure_fts

    async with _engine.begin() as conn:
        await ensure_fts(conn)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Close database connections."""
    await _engine.dispose()
