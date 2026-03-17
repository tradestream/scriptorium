"""Articles API — save, list, sync web articles via Instapaper."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.article import Article, ArticleHighlight, ArticleTag
from app.models.user import User

from .auth import get_current_user

router = APIRouter(prefix="/articles")


# ── Schemas ──────────────────────────────────────────────────────────────────

class ArticleSave(BaseModel):
    url: str
    title: Optional[str] = None
    description: Optional[str] = None


class ArticleRead(BaseModel):
    id: int
    user_id: int
    instapaper_id: Optional[int] = None
    url: str
    title: str
    author: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    word_count: Optional[int] = None
    progress: float = 0.0
    is_starred: bool = False
    is_archived: bool = False
    folder: Optional[str] = None
    saved_at: datetime
    highlight_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class ArticleDetail(ArticleRead):
    markdown_content: Optional[str] = None
    highlights: list[dict] = []


class InstapaperLink(BaseModel):
    username: str
    password: str = ""


class InstapaperStatus(BaseModel):
    linked: bool
    instapaper_username: Optional[str] = None
    has_full_api: bool = False


# ── Instapaper Account Linking ───────────────────────────────────────────────

@router.get("/instapaper/status", response_model=InstapaperStatus)
async def instapaper_status(current_user: User = Depends(get_current_user)):
    """Check if current user has linked their Instapaper account."""
    from app.config import get_settings
    s = get_settings()
    return InstapaperStatus(
        linked=bool(current_user.instapaper_username),
        instapaper_username=current_user.instapaper_username,
        has_full_api=bool(current_user.instapaper_token) and bool(s.INSTAPAPER_CONSUMER_KEY),
    )


@router.post("/instapaper/link")
async def link_instapaper(
    data: InstapaperLink,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link Instapaper account. Validates via Simple API, upgrades to Full API if consumer keys configured."""
    from app.services.instapaper import InstapaperSimpleClient
    from app.config import get_settings

    # Validate credentials via Simple API
    client = InstapaperSimpleClient(data.username, data.password)
    if not await client.authenticate():
        raise HTTPException(status_code=401, detail="Invalid Instapaper credentials")

    current_user.instapaper_username = data.username
    current_user.instapaper_password = data.password

    # Try to upgrade to Full API if consumer keys are available
    s = get_settings()
    if s.INSTAPAPER_CONSUMER_KEY and s.INSTAPAPER_CONSUMER_SECRET:
        try:
            from app.services.instapaper import get_access_token
            token, secret = await get_access_token(data.username, data.password)
            current_user.instapaper_token = token
            current_user.instapaper_secret = secret
        except Exception:
            pass  # Full API not available, Simple API still works

    await db.commit()
    return {"linked": True, "has_full_api": bool(current_user.instapaper_token)}


@router.delete("/instapaper/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_instapaper(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlink Instapaper account."""
    current_user.instapaper_username = None
    current_user.instapaper_password = None
    current_user.instapaper_token = None
    current_user.instapaper_secret = None
    await db.commit()


# ── Articles CRUD ────────────────────────────────────────────────────────────

@router.get("", response_model=list[ArticleRead])
async def list_articles(
    archived: bool = False,
    starred: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's articles."""
    stmt = (
        select(Article)
        .where(Article.user_id == current_user.id)
        .where(Article.is_archived == archived)
    )
    if starred is not None:
        stmt = stmt.where(Article.is_starred == starred)
    stmt = stmt.order_by(Article.saved_at.desc()).limit(limit).offset(skip)

    result = await db.execute(stmt)
    articles = result.scalars().all()

    # Get highlight counts
    out = []
    for a in articles:
        item = ArticleRead.model_validate(a)
        hl_count = await db.scalar(
            select(func.count()).where(ArticleHighlight.article_id == a.id)
        )
        item.highlight_count = hl_count or 0
        out.append(item)
    return out


@router.get("/{article_id}", response_model=ArticleDetail)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single article with content and highlights."""
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
        .options(joinedload(Article.highlights))
    )
    article = result.unique().scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    detail = ArticleDetail.model_validate(article)
    detail.highlights = [
        {"id": h.id, "text": h.text, "note": h.note, "position": h.position}
        for h in article.highlights
    ]

    # Fetch content from Instapaper if not cached
    if not detail.markdown_content and article.instapaper_id and current_user.instapaper_token:
        try:
            from app.services.instapaper import InstapaperClient
            client = InstapaperClient(current_user.instapaper_token, current_user.instapaper_secret)
            html = await client.get_text(article.instapaper_id)
            # Convert HTML to markdown
            try:
                from markdownify import markdownify
                md = markdownify(html, heading_style="ATX")
            except ImportError:
                import re
                md = re.sub(r'<[^>]+>', '', html)
            article.markdown_content = md
            await db.commit()
            detail.markdown_content = md
        except Exception:
            pass

    return detail


@router.post("", response_model=ArticleRead, status_code=status.HTTP_201_CREATED)
async def save_article(
    data: ArticleSave,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a URL as an article. Pushes to Instapaper if linked."""
    from urllib.parse import urlparse
    domain = urlparse(data.url).netloc

    instapaper_id = None
    title = data.title or data.url[:100]
    author = None

    # Push to Instapaper if linked
    if current_user.instapaper_token:
        # Full API — returns bookmark metadata
        try:
            from app.services.instapaper import InstapaperClient
            client = InstapaperClient(current_user.instapaper_token, current_user.instapaper_secret)
            bm = await client.add_bookmark(
                url=data.url,
                title=data.title or "",
                description=data.description or "",
            )
            if bm:
                instapaper_id = bm.get("bookmark_id")
                title = bm.get("title", title)
                author = bm.get("author")
        except Exception:
            pass
    elif current_user.instapaper_username:
        # Simple API — just adds the URL, no metadata returned
        try:
            from app.services.instapaper import InstapaperSimpleClient
            client = InstapaperSimpleClient(current_user.instapaper_username, current_user.instapaper_password or "")
            await client.add(data.url, title=data.title or "")
        except Exception:
            pass

    article = Article(
        user_id=current_user.id,
        instapaper_id=instapaper_id,
        url=data.url,
        title=title,
        author=author,
        description=data.description,
        domain=domain,
        saved_at=datetime.utcnow(),
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)

    item = ArticleRead.model_validate(article)
    item.highlight_count = 0
    return item


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an article. Also deletes from Instapaper if linked."""
    article = (await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
    )).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if article.instapaper_id and current_user.instapaper_token:
        try:
            from app.services.instapaper import InstapaperClient
            client = InstapaperClient(current_user.instapaper_token, current_user.instapaper_secret)
            await client.delete_bookmark(article.instapaper_id)
        except Exception:
            pass

    await db.delete(article)
    await db.commit()


@router.post("/{article_id}/star")
async def star_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = (await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
    )).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    article.is_starred = not article.is_starred

    if article.instapaper_id and current_user.instapaper_token:
        try:
            from app.services.instapaper import InstapaperClient
            client = InstapaperClient(current_user.instapaper_token, current_user.instapaper_secret)
            if article.is_starred:
                await client.star(article.instapaper_id)
            else:
                await client.unstar(article.instapaper_id)
        except Exception:
            pass

    await db.commit()
    return {"starred": article.is_starred}


@router.post("/{article_id}/archive")
async def archive_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = (await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
    )).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    article.is_archived = not article.is_archived

    if article.instapaper_id and current_user.instapaper_token:
        try:
            from app.services.instapaper import InstapaperClient
            client = InstapaperClient(current_user.instapaper_token, current_user.instapaper_secret)
            if article.is_archived:
                await client.archive(article.instapaper_id)
            else:
                await client.unarchive(article.instapaper_id)
        except Exception:
            pass

    await db.commit()
    return {"archived": article.is_archived}


# ── Sync ─────────────────────────────────────────────────────────────────────

@router.post("/sync")
async def sync_from_instapaper(
    current_user: User = Depends(get_current_user),
):
    """Pull bookmarks and highlights from Instapaper into Scriptorium.

    Requires Full API (OAuth tokens). Simple API users can save articles
    but cannot sync back — reading progress syncs when Full API is available.
    """
    if not current_user.instapaper_token:
        if current_user.instapaper_username:
            raise HTTPException(
                status_code=400,
                detail="Sync requires the Full API. Configure INSTAPAPER_CONSUMER_KEY to enable it.",
            )
        raise HTTPException(status_code=400, detail="Instapaper not linked")

    from app.services.instapaper import sync_articles
    result = await sync_articles(current_user.id)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result
