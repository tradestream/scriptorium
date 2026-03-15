"""WebSocket event broadcast service.

All real-time events (ingest progress, library scans, book additions) go
through this module. Components publish events; the WebSocket endpoint
subscribes and fans them out to connected browser clients.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("scriptorium.events")


class EventBroadcaster:
    """Manages active WebSocket connections and broadcasts events to all of them."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.debug("WebSocket client connected (%d total)", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            try:
                self._connections.remove(ws)
            except ValueError:
                pass
        logger.debug("WebSocket client disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, event_type: str, data: Any) -> None:
        """Send a JSON event to all connected clients.

        Dead connections are silently removed.
        """
        if not self._connections:
            return

        message = json.dumps({"type": event_type, "data": data})
        dead: list[WebSocket] = []

        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self._connections.remove(ws)
                    except ValueError:
                        pass

    # ── Typed event helpers ────────────────────────────────────────────────

    async def book_added(self, book_id: int, title: str, library_id: int) -> None:
        await self.broadcast("book_added", {"id": book_id, "title": title, "library_id": library_id})

    async def ingest_progress(self, filename: str, status: str, book_id: int | None = None) -> None:
        await self.broadcast("ingest_progress", {"filename": filename, "status": status, "book_id": book_id})

    async def library_scan_done(self, library_id: int, added: int, updated: int) -> None:
        await self.broadcast("library_scan_done", {"library_id": library_id, "added": added, "updated": updated})

    async def enrich_progress(self, job_id: str, done: int, total: int, current: str, status: str) -> None:
        await self.broadcast("enrich_progress", {
            "job_id": job_id, "done": done, "total": total, "current": current, "status": status,
        })


# Module-level singleton used across the application
broadcaster = EventBroadcaster()
