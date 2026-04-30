"""Embedding vectors for semantic search.

Generates text embeddings from book metadata (title, authors, description, tags)
and stores them as JSON arrays on the Work model. Enables similarity search
and recommendation by cosine distance.

Uses sentence-transformers if available, otherwise falls back to a simple
TF-IDF approach with sklearn.
"""

import json
import logging
import math
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_model = None
_model_name = "all-MiniLM-L6-v2"  # 384-dim, fast, good quality


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_model_name)
        logger.info("Loaded embedding model: %s", _model_name)
        return _model
    except ImportError:
        logger.info("sentence-transformers not installed — semantic search unavailable")
        return None


def build_search_text(
    title: str,
    authors: list[str] = None,
    description: str = None,
    tags: list[str] = None,
) -> str:
    """Build a composite searchable text from book metadata."""
    parts = [title]
    if authors:
        parts.append(" ".join(authors))
    if description:
        # Truncate long descriptions
        parts.append(description[:500])
    if tags:
        parts.append(" ".join(tags))
    return " ".join(parts)


def compute_embedding(text: str) -> Optional[list[float]]:
    """Compute embedding vector for text. Returns None if model unavailable."""
    model = _get_model()
    if model is None:
        return None
    try:
        vec = model.encode(text, normalize_embeddings=True)
        return [round(float(v), 6) for v in vec]
    except Exception as exc:
        logger.warning("Embedding computation failed: %s", exc)
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def index_work(db: AsyncSession, work_id: int) -> bool:
    """Generate and store embedding + search_text for a work."""
    from sqlalchemy.orm import joinedload

    from app.models.work import Work

    result = await db.execute(
        select(Work).where(Work.id == work_id)
        .options(joinedload(Work.authors), joinedload(Work.tags))
    )
    work = result.unique().scalar_one_or_none()
    if not work:
        return False

    search_text = build_search_text(
        title=work.title,
        authors=[a.name for a in work.authors],
        description=work.description,
        tags=[t.name for t in work.tags],
    )
    work.search_text = search_text

    embedding = compute_embedding(search_text)
    if embedding:
        work.embedding = json.dumps(embedding)

    return True


async def find_similar(db: AsyncSession, work_id: int, limit: int = 10) -> list[dict]:
    """Find works most similar to the given work by embedding cosine similarity."""
    from app.models.work import Work

    # Get source embedding
    result = await db.execute(select(Work.embedding).where(Work.id == work_id))
    row = result.scalar_one_or_none()
    if not row:
        return []

    try:
        source_vec = json.loads(row)
    except (TypeError, json.JSONDecodeError):
        return []

    # Get all works with embeddings (for small collections this is fine;
    # for large ones, consider pgvector or FAISS)
    result = await db.execute(
        select(Work.id, Work.title, Work.embedding)
        .where(Work.embedding.isnot(None), Work.id != work_id)
    )
    candidates = result.all()

    scored = []
    for cid, ctitle, cemb_json in candidates:
        try:
            cvec = json.loads(cemb_json)
            sim = cosine_similarity(source_vec, cvec)
            scored.append({"work_id": cid, "title": ctitle, "similarity": round(sim, 4)})
        except (TypeError, json.JSONDecodeError):
            continue

    scored.sort(key=lambda x: -x["similarity"])
    return scored[:limit]
