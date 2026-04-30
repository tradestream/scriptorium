"""Instapaper API client — Simple API + Full OAuth 1.0a.

Two tiers:
- Simple API (always available): authenticate + add bookmarks via Basic Auth.
  No consumer key needed. Enough to save articles that sync to Kobo.
- Full API (when consumer keys configured): list bookmarks, sync progress,
  import highlights, manage folders. Requires OAuth 1.0a xAuth tokens.

Each user stores instapaper_username/password for Simple API,
and optionally instapaper_token/secret for Full API.
"""

import hashlib
import hmac
import logging
import time
import urllib.parse

import httpx

from app.config import get_settings

logger = logging.getLogger("scriptorium.instapaper")

API_BASE = "https://www.instapaper.com"


# ── Simple API (Basic Auth) ─────────────────────────────────────────────────

class InstapaperSimpleClient:
    """Instapaper Simple API — authenticate and add URLs via Basic Auth."""

    def __init__(self, username: str, password: str = ""):
        self.username = username
        self.password = password

    async def authenticate(self) -> bool:
        """Verify credentials. Returns True if valid."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{API_BASE}/api/authenticate",
                auth=(self.username, self.password),
            )
            return r.status_code == 200

    async def add(self, url: str, title: str = "", selection: str = "") -> bool:
        """Add a URL to the user's Instapaper. Returns True on success (201)."""
        params: dict = {"url": url}
        if title:
            params["title"] = title
        if selection:
            params["selection"] = selection

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{API_BASE}/api/add",
                params=params,
                auth=(self.username, self.password),
            )
            return r.status_code == 201
settings = get_settings()


# ── OAuth 1.0a Signing ──────────────────────────────────────────────────────

def _nonce() -> str:
    import secrets
    return secrets.token_hex(16)


def _sign(method: str, url: str, params: dict, consumer_secret: str, token_secret: str = "") -> str:
    """Generate OAuth 1.0a HMAC-SHA1 signature."""
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(params.items())
    )
    base_string = f"{method.upper()}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(sorted_params, safe='')}"
    signing_key = f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(token_secret, safe='')}"
    sig = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    import base64
    return base64.b64encode(sig).decode()


def _oauth_params(consumer_key: str) -> dict:
    return {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": _nonce(),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
    }


# ── Client ───────────────────────────────────────────────────────────────────

class InstapaperClient:
    """Instapaper API client for a specific user."""

    def __init__(self, oauth_token: str, oauth_secret: str):
        self.consumer_key = settings.INSTAPAPER_CONSUMER_KEY or ""
        self.consumer_secret = settings.INSTAPAPER_CONSUMER_SECRET or ""
        self.oauth_token = oauth_token
        self.oauth_secret = oauth_secret

    async def _request(self, method: str, path: str, params: dict | None = None) -> list | dict:
        """Make a signed OAuth 1.0a request to Instapaper."""
        url = f"{API_BASE}{path}"
        all_params = _oauth_params(self.consumer_key)
        all_params["oauth_token"] = self.oauth_token
        if params:
            all_params.update(params)

        all_params["oauth_signature"] = _sign(method, url, all_params, self.consumer_secret, self.oauth_secret)

        async with httpx.AsyncClient(timeout=15) as client:
            if method.upper() == "GET":
                r = await client.get(url, params=all_params)
            else:
                r = await client.post(url, data=all_params)

            if r.status_code == 403:
                raise PermissionError("Instapaper authentication failed")
            r.raise_for_status()
            return r.json()

    # ── Bookmarks ────────────────────────────────────────────────────────────

    async def list_bookmarks(self, folder: str = "unread", limit: int = 100) -> list[dict]:
        """List bookmarks in a folder. Returns bookmark objects."""
        result = await self._request("POST", "/api/1/bookmarks/list", {
            "folder_id": folder,
            "limit": str(limit),
            "have": "",
        })
        # Response is a list of mixed types: user, bookmarks, highlights
        return [item for item in result if item.get("type") == "bookmark"]

    async def add_bookmark(self, url: str, title: str = "", description: str = "", folder_id: str = "") -> dict:
        """Save a URL to Instapaper. Returns the bookmark object."""
        params: dict = {"url": url}
        if title:
            params["title"] = title
        if description:
            params["description"] = description
        if folder_id:
            params["folder_id"] = folder_id

        result = await self._request("POST", "/api/1/bookmarks/add", params)
        bookmarks = [item for item in result if item.get("type") == "bookmark"]
        return bookmarks[0] if bookmarks else {}

    async def get_text(self, bookmark_id: int) -> str:
        """Get the processed text-view HTML of a bookmark."""
        url = f"{API_BASE}/api/1/bookmarks/get_text"
        all_params = _oauth_params(self.consumer_key)
        all_params["oauth_token"] = self.oauth_token
        all_params["bookmark_id"] = str(bookmark_id)
        all_params["oauth_signature"] = _sign("POST", url, all_params, self.consumer_secret, self.oauth_secret)

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, data=all_params)
            r.raise_for_status()
            return r.text

    async def update_read_progress(self, bookmark_id: int, progress: float, progress_timestamp: int | None = None) -> dict:
        """Update reading progress (0.0 to 1.0)."""
        params = {
            "bookmark_id": str(bookmark_id),
            "progress": str(progress),
            "progress_timestamp": str(progress_timestamp or int(time.time())),
        }
        result = await self._request("POST", "/api/1/bookmarks/update_read_progress", params)
        bookmarks = [item for item in result if item.get("type") == "bookmark"]
        return bookmarks[0] if bookmarks else {}

    async def star(self, bookmark_id: int) -> dict:
        result = await self._request("POST", "/api/1/bookmarks/star", {"bookmark_id": str(bookmark_id)})
        bookmarks = [item for item in result if item.get("type") == "bookmark"]
        return bookmarks[0] if bookmarks else {}

    async def unstar(self, bookmark_id: int) -> dict:
        result = await self._request("POST", "/api/1/bookmarks/unstar", {"bookmark_id": str(bookmark_id)})
        bookmarks = [item for item in result if item.get("type") == "bookmark"]
        return bookmarks[0] if bookmarks else {}

    async def archive(self, bookmark_id: int) -> dict:
        result = await self._request("POST", "/api/1/bookmarks/archive", {"bookmark_id": str(bookmark_id)})
        bookmarks = [item for item in result if item.get("type") == "bookmark"]
        return bookmarks[0] if bookmarks else {}

    async def unarchive(self, bookmark_id: int) -> dict:
        result = await self._request("POST", "/api/1/bookmarks/unarchive", {"bookmark_id": str(bookmark_id)})
        bookmarks = [item for item in result if item.get("type") == "bookmark"]
        return bookmarks[0] if bookmarks else {}

    async def delete_bookmark(self, bookmark_id: int) -> None:
        await self._request("POST", "/api/1/bookmarks/delete", {"bookmark_id": str(bookmark_id)})

    # ── Highlights ───────────────────────────────────────────────────────────

    async def list_highlights(self, bookmark_id: int) -> list[dict]:
        """List highlights for a bookmark."""
        result = await self._request("GET", f"/api/1.1/bookmarks/{bookmark_id}/highlights")
        return result if isinstance(result, list) else []

    # ── Folders ──────────────────────────────────────────────────────────────

    async def list_folders(self) -> list[dict]:
        result = await self._request("POST", "/api/1/folders/list")
        return [item for item in result if item.get("type") == "folder"]

    # ── Account ──────────────────────────────────────────────────────────────

    async def verify_credentials(self) -> dict:
        result = await self._request("POST", "/api/1/account/verify_credentials")
        users = [item for item in result if item.get("type") == "user"]
        return users[0] if users else {}


# ── xAuth Token Acquisition ─────────────────────────────────────────────────

async def get_access_token(username: str, password: str) -> tuple[str, str]:
    """Obtain OAuth access token via xAuth.

    Returns (oauth_token, oauth_token_secret).
    """
    consumer_key = settings.INSTAPAPER_CONSUMER_KEY
    consumer_secret = settings.INSTAPAPER_CONSUMER_SECRET
    if not consumer_key or not consumer_secret:
        raise ValueError("Instapaper consumer credentials not configured")

    url = f"{API_BASE}/api/1/oauth/access_token"
    params = _oauth_params(consumer_key)
    params["x_auth_username"] = username
    params["x_auth_password"] = password
    params["x_auth_mode"] = "client_auth"

    params["oauth_signature"] = _sign("POST", url, params, consumer_secret)

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, data=params)
        if r.status_code == 401:
            raise PermissionError("Invalid Instapaper credentials")
        r.raise_for_status()

        # Response is URL-encoded: oauth_token=xxx&oauth_token_secret=yyy
        parsed = dict(urllib.parse.parse_qsl(r.text))
        return parsed["oauth_token"], parsed["oauth_token_secret"]


# ── Sync Service ─────────────────────────────────────────────────────────────

async def sync_articles(user_id: int) -> dict:
    """Pull bookmarks from Instapaper and sync into the articles table.

    Imports new bookmarks, updates progress on existing ones, imports highlights.
    Returns counts of created/updated/highlights.
    """
    from urllib.parse import urlparse

    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.article import Article, ArticleHighlight
    from app.models.user import User

    factory = get_session_factory()
    async with factory() as db:
        user = await db.get(User, user_id)
        if not user or not user.instapaper_token:
            return {"error": "Instapaper not linked"}

        client = InstapaperClient(user.instapaper_token, user.instapaper_secret)

        created = 0
        updated = 0
        highlights_imported = 0

        # Sync unread + archived
        for folder in ["unread", "archive"]:
            try:
                bookmarks = await client.list_bookmarks(folder=folder, limit=500)
            except Exception as exc:
                logger.warning("Instapaper list failed for user %d folder %s: %s", user_id, folder, exc)
                continue

            for bm in bookmarks:
                bm_id = bm.get("bookmark_id")
                if not bm_id:
                    continue

                existing = (await db.execute(
                    select(Article).where(Article.instapaper_id == bm_id)
                )).scalar_one_or_none()

                bm_url = bm.get("url", "")
                domain = urlparse(bm_url).netloc if bm_url else None

                if existing:
                    # Update progress and state
                    existing.progress = bm.get("progress", existing.progress)
                    if bm.get("progress_timestamp"):
                        from datetime import datetime
                        existing.progress_timestamp = datetime.fromtimestamp(bm["progress_timestamp"])
                    existing.is_starred = bool(bm.get("starred", "0") != "0")
                    existing.is_archived = folder == "archive"
                    existing.title = bm.get("title", existing.title)
                    updated += 1
                else:
                    # Create new article
                    from datetime import datetime
                    saved_ts = bm.get("time")
                    saved_at = datetime.fromtimestamp(saved_ts) if saved_ts else datetime.utcnow()

                    article = Article(
                        user_id=user_id,
                        instapaper_id=bm_id,
                        instapaper_hash=bm.get("hash"),
                        url=bm_url,
                        title=bm.get("title", bm_url[:100]),
                        author=bm.get("author"),
                        description=bm.get("description"),
                        domain=domain,
                        word_count=None,
                        progress=bm.get("progress", 0.0),
                        is_starred=bool(bm.get("starred", "0") != "0"),
                        is_archived=folder == "archive",
                        folder=None if folder == "unread" else folder,
                        saved_at=saved_at,
                    )
                    db.add(article)
                    await db.flush()
                    created += 1

                    # Import highlights
                    try:
                        hl_list = await client.list_highlights(bm_id)
                        for hl in hl_list:
                            hl_id = hl.get("highlight_id")
                            if hl_id:
                                exists = (await db.execute(
                                    select(ArticleHighlight).where(
                                        ArticleHighlight.instapaper_highlight_id == hl_id
                                    )
                                )).scalar_one_or_none()
                                if not exists:
                                    db.add(ArticleHighlight(
                                        article_id=article.id,
                                        instapaper_highlight_id=hl_id,
                                        text=hl.get("text", ""),
                                        note=hl.get("note"),
                                        position=hl.get("position"),
                                    ))
                                    highlights_imported += 1
                    except Exception:
                        pass  # highlights are non-critical

        await db.commit()

    return {"created": created, "updated": updated, "highlights": highlights_imported}
