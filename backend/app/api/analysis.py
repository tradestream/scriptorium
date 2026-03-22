"""API endpoints for book analysis and analysis templates."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import Book, User
from app.models.analysis import AnalysisTemplate, BookAnalysis
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisTemplateCreate,
    AnalysisTemplateRead,
    AnalysisTemplateUpdate,
    BookAnalysisRead,
    BookAnalysisSummary,
)
from app.services.analysis import run_analysis

from .auth import get_current_user

router = APIRouter()


# --- Book Analysis Endpoints ---

@router.get("/books/{book_id}/analyses", response_model=list[BookAnalysisSummary])
async def list_book_analyses(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all analyses for a book."""
    stmt = (
        select(BookAnalysis)
        .where(BookAnalysis.work_id == book_id)
        .order_by(BookAnalysis.created_at.desc())
    )
    result = await db.execute(stmt)
    analyses = result.scalars().all()
    return [BookAnalysisSummary.model_validate(a) for a in analyses]


@router.get("/books/{book_id}/analyses/{analysis_id}", response_model=BookAnalysisRead)
async def get_book_analysis(
    book_id: int,
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get a specific analysis with full content."""
    stmt = (
        select(BookAnalysis)
        .where(BookAnalysis.id == analysis_id, BookAnalysis.work_id == book_id)
        .options(joinedload(BookAnalysis.template))
    )
    result = await db.execute(stmt)
    analysis = result.unique().scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    return BookAnalysisRead.model_validate(analysis)


@router.post("/books/{book_id}/analyses", response_model=BookAnalysisSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_book_analysis(
    book_id: int,
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Trigger an LLM analysis for a book.

    The analysis runs in the background. Poll the status via GET.
    Returns immediately with status='running'.
    """
    # Verify book exists
    stmt = select(Book).where(Book.id == book_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    # Run analysis (for now, synchronously — will be backgrounded with task queue later)
    analysis = await run_analysis(
        book_id=book_id,
        db=db,
        template_id=request.template_id,
        custom_prompt=request.custom_prompt,
        title=request.title,
    )

    return BookAnalysisSummary.model_validate(analysis)


@router.delete("/books/{book_id}/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book_analysis(
    book_id: int,
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Delete a saved analysis."""
    stmt = select(BookAnalysis).where(
        BookAnalysis.id == analysis_id, BookAnalysis.work_id == book_id
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    await db.delete(analysis)
    await db.commit()


class EsotericReadingUpdate(BaseModel):
    esoteric_reading: Optional[str] = None


@router.patch("/books/{book_id}/analyses/{analysis_id}/esoteric-reading", response_model=BookAnalysisRead)
async def set_esoteric_reading(
    book_id: int,
    analysis_id: int,
    data: EsotericReadingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set or clear the esoteric reading for an analysis. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    result = await db.execute(
        select(BookAnalysis).options(joinedload(BookAnalysis.template)).where(
            BookAnalysis.id == analysis_id, BookAnalysis.work_id == book_id
        )
    )
    analysis = result.unique().scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    analysis.esoteric_reading = data.esoteric_reading
    await db.commit()
    await db.refresh(analysis)
    return analysis


# --- Analysis Template Endpoints ---

@router.get("/analysis-templates", response_model=list[AnalysisTemplateRead])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all available analysis templates."""
    stmt = select(AnalysisTemplate).order_by(
        AnalysisTemplate.is_default.desc(), AnalysisTemplate.name
    )
    result = await db.execute(stmt)
    return [AnalysisTemplateRead.model_validate(t) for t in result.scalars().all()]


@router.get("/analysis-templates/{template_id}", response_model=AnalysisTemplateRead)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get a specific analysis template."""
    stmt = select(AnalysisTemplate).where(AnalysisTemplate.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return AnalysisTemplateRead.model_validate(template)


@router.post("/analysis-templates", response_model=AnalysisTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: AnalysisTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom analysis template."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create templates")

    # If setting as default, unset others
    if data.is_default:
        stmt = select(AnalysisTemplate).where(AnalysisTemplate.is_default == True)
        result = await db.execute(stmt)
        for t in result.scalars().all():
            t.is_default = False

    template = AnalysisTemplate(
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        user_prompt_template=data.user_prompt_template,
        is_default=data.is_default,
        is_builtin=False,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return AnalysisTemplateRead.model_validate(template)


@router.put("/analysis-templates/{template_id}", response_model=AnalysisTemplateRead)
async def update_template(
    template_id: int,
    data: AnalysisTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a custom analysis template."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update templates")

    stmt = select(AnalysisTemplate).where(AnalysisTemplate.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify built-in templates. Create a copy instead.",
        )

    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.system_prompt is not None:
        template.system_prompt = data.system_prompt
    if data.user_prompt_template is not None:
        template.user_prompt_template = data.user_prompt_template
    if data.is_default is not None:
        if data.is_default:
            # Unset other defaults
            unset_stmt = select(AnalysisTemplate).where(
                AnalysisTemplate.is_default == True, AnalysisTemplate.id != template_id
            )
            r = await db.execute(unset_stmt)
            for t in r.scalars().all():
                t.is_default = False
        template.is_default = data.is_default

    await db.commit()
    await db.refresh(template)

    return AnalysisTemplateRead.model_validate(template)


@router.delete("/analysis-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom analysis template."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete templates")

    stmt = select(AnalysisTemplate).where(AnalysisTemplate.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete built-in templates",
        )

    await db.delete(template)
    await db.commit()


# --- Computational (Esoteric) Analysis Endpoints ---

from app.models.analysis import ComputationalAnalysis
from app.services.text_extraction import extract_text_from_book
from app.services.esoteric import (
    EsotericAnalysisConfig,
    run_full_esoteric_analysis,
    detect_loud_silences,
    hunt_contradictions,
    locate_centers,
    analyze_exoteric_esoteric_ratio,
)
import json


class ComputationalAnalysisRequest(BaseModel):
    """Request to run computational esoteric analysis."""
    analysis_type: str = "full"  # full, loud_silence, contradiction, center, exoteric_esoteric, repetition_variation, audience_differentiation, hedging_language, first_last_words, parenthetical_footnote, structural_obscurity, disreputable_mouthpiece
    keywords: list[str] = []
    entities: list[str] = []
    pious_words: list[str] = []
    subversive_words: list[str] = []
    delimiter_pattern: str | None = None

    class Config:
        from_attributes = True


class ComputationalAnalysisRead(BaseModel):
    """Read schema for computational analysis results."""
    id: int
    book_id: int
    analysis_type: str
    results: dict  # Parsed JSON
    config: dict | None = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/books/{book_id}/esoteric", response_model=list[ComputationalAnalysisRead])
async def list_computational_analyses(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all computational esoteric analyses for a book."""
    stmt = (
        select(ComputationalAnalysis)
        .where(ComputationalAnalysis.work_id == book_id)
        .order_by(ComputationalAnalysis.created_at.desc())
    )
    result = await db.execute(stmt)
    analyses = result.scalars().all()

    return [
        ComputationalAnalysisRead(
            id=a.id,
            work_id=a.work_id,
            analysis_type=a.analysis_type,
            results=json.loads(a.results_json),
            config=json.loads(a.config_json) if a.config_json else None,
            status=a.status,
            created_at=a.created_at,
        )
        for a in analyses
    ]


@router.get("/books/{book_id}/esoteric/{analysis_id}", response_model=ComputationalAnalysisRead)
async def get_computational_analysis(
    book_id: int,
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get a specific computational analysis with full results."""
    stmt = select(ComputationalAnalysis).where(
        ComputationalAnalysis.id == analysis_id,
        ComputationalAnalysis.work_id == book_id,
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    return ComputationalAnalysisRead(
        id=analysis.id,
        work_id=analysis.work_id,
        analysis_type=analysis.analysis_type,
        results=json.loads(analysis.results_json),
        config=json.loads(analysis.config_json) if analysis.config_json else None,
        status=analysis.status,
        created_at=analysis.created_at,
    )


@router.post("/books/{book_id}/esoteric", response_model=ComputationalAnalysisRead, status_code=status.HTTP_201_CREATED)
async def run_computational_analysis(
    book_id: int,
    request: ComputationalAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Run computational esoteric analysis on a book.

    Available types:
    - 'full': Run all four tools
    - 'loud_silence': Detect where keywords conspicuously vanish
    - 'contradiction': Track entity sentiment dissonance
    - 'center': Find the physical center of the text
    - 'exoteric_esoteric': Measure pious vs. subversive language ratio
    """
    # Verify book exists and extract text
    stmt = select(Book).where(Book.id == book_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    text = await extract_text_from_book(book, db)

    # Build config
    config = EsotericAnalysisConfig(
        keywords=request.keywords or EsotericAnalysisConfig().keywords,
        entities=request.entities,
        pious_words=set(request.pious_words) if request.pious_words else None,
        subversive_words=set(request.subversive_words) if request.subversive_words else None,
        delimiter_pattern=request.delimiter_pattern,
    )

    # Run analysis
    try:
        if request.analysis_type == "full":
            results = run_full_esoteric_analysis(text, config)
        elif request.analysis_type == "loud_silence":
            r = detect_loud_silences(text, config.keywords, config.delimiter_pattern, config.silence_threshold)
            results = r.to_dict()
        elif request.analysis_type == "contradiction":
            if not config.entities:
                raise HTTPException(status_code=400, detail="Entities required for contradiction analysis")
            r = hunt_contradictions(text, config.entities, config.delimiter_pattern, config.context_window)
            results = r.to_dict()
        elif request.analysis_type == "center":
            r = locate_centers(text, config.delimiter_pattern, config.center_window_lines)
            results = r.to_dict()
        elif request.analysis_type == "exoteric_esoteric":
            r = analyze_exoteric_esoteric_ratio(text, config.pious_words, config.subversive_words, config.delimiter_pattern)
            results = r.to_dict()
        elif request.analysis_type == "repetition_variation":
            from app.services.esoteric import detect_repetition_with_variation
            r = detect_repetition_with_variation(text, config.keywords, config.delimiter_pattern, config.context_window)
            results = r.to_dict()
        elif request.analysis_type == "audience_differentiation":
            from app.services.esoteric import detect_audience_differentiation
            r = detect_audience_differentiation(text, config.delimiter_pattern, config.context_window)
            results = r.to_dict()
        elif request.analysis_type == "hedging_language":
            from app.services.esoteric import detect_hedging_language
            r = detect_hedging_language(text, config.delimiter_pattern, config.context_window)
            results = r.to_dict()
        elif request.analysis_type == "self_reference":
            from app.services.esoteric import detect_self_reference
            r = detect_self_reference(text, config.delimiter_pattern, config.context_window)
            results = r.to_dict()
        elif request.analysis_type == "section_proportion":
            from app.services.esoteric import analyze_section_proportions
            r = analyze_section_proportions(text, config.keywords, config.delimiter_pattern)
            results = r.to_dict()
        elif request.analysis_type == "epigraph":
            from app.services.esoteric import extract_epigraphs
            r = extract_epigraphs(text)
            results = r.to_dict()
        elif request.analysis_type == "conditional_language":
            from app.services.esoteric import detect_conditional_language
            r = detect_conditional_language(text, config.delimiter_pattern, config.context_window)
            results = r.to_dict()
        elif request.analysis_type == "emphasis_quotation":
            from app.services.esoteric import extract_emphasis_markers
            r = extract_emphasis_markers(text, config.delimiter_pattern)
            results = r.to_dict()
        elif request.analysis_type == "first_last_words":
            from app.services.esoteric import extract_first_last_words
            r = extract_first_last_words(text, config.delimiter_pattern)
            results = r.to_dict()
        elif request.analysis_type == "parenthetical_footnote":
            from app.services.esoteric import extract_parentheticals
            r = extract_parentheticals(text, config.delimiter_pattern)
            results = r.to_dict()
        elif request.analysis_type == "structural_obscurity":
            from app.services.esoteric import detect_structural_obscurity
            r = detect_structural_obscurity(text, config.keywords, config.delimiter_pattern)
            results = r.to_dict()
        elif request.analysis_type == "disreputable_mouthpiece":
            from app.services.esoteric import detect_disreputable_mouthpieces
            r = detect_disreputable_mouthpieces(text, config.delimiter_pattern, config.context_window)
            results = r.to_dict()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown analysis type: {request.analysis_type}")

        status_val = "completed"
    except HTTPException:
        raise
    except Exception as e:
        results = {"error": str(e)}
        status_val = "failed"

    # Persist
    config_dict = {
        "keywords": config.keywords,
        "entities": config.entities,
        "delimiter_pattern": config.delimiter_pattern,
    }

    record = ComputationalAnalysis(
        book_id=book_id,
        analysis_type=request.analysis_type,
        config_json=json.dumps(config_dict),
        results_json=json.dumps(results, default=str),
        status=status_val,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return ComputationalAnalysisRead(
        id=record.id,
        work_id=record.work_id,
        analysis_type=record.analysis_type,
        results=results,
        config=config_dict,
        status=record.status,
        created_at=record.created_at,
    )


@router.delete("/books/{book_id}/esoteric/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_computational_analysis(
    book_id: int,
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Delete a saved computational analysis."""
    stmt = select(ComputationalAnalysis).where(
        ComputationalAnalysis.id == analysis_id,
        ComputationalAnalysis.work_id == book_id,
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    await db.delete(analysis)
    await db.commit()


# ── Per-book esoteric enablement ──────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional
from datetime import datetime as _datetime


class EsotericToggle(_BaseModel):
    enabled: bool


@router.patch("/books/{book_id}/esoteric-enabled", response_model=dict)
async def set_esoteric_enabled(
    book_id: int,
    data: EsotericToggle,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle esoteric analysis availability for a book. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    book.esoteric_enabled = data.enabled
    await db.commit()
    return {"book_id": book_id, "esoteric_enabled": book.esoteric_enabled}


@router.post("/authors/{author_id}/enable-esoteric", response_model=dict)
async def enable_esoteric_for_author(
    author_id: int,
    data: EsotericToggle,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable/disable esoteric analysis for all books by an author. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    from sqlalchemy.orm import joinedload as _jl
    from app.models.book import Author
    result = await db.execute(
        select(Author).options(_jl(Author.books)).where(Author.id == author_id)
    )
    author = result.unique().scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    for b in author.books:
        b.esoteric_enabled = data.enabled
    await db.commit()
    return {"author_id": author_id, "books_updated": len(author.books), "esoteric_enabled": data.enabled}


# ── Per-book prompt configs ───────────────────────────────────────────────────

from app.models.analysis import BookPromptConfig


class PromptConfigUpsert(_BaseModel):
    template_id: _Optional[int] = None
    custom_system_prompt: _Optional[str] = None
    custom_user_prompt: _Optional[str] = None
    notes: _Optional[str] = None


class PromptConfigRead(_BaseModel):
    id: int
    book_id: int
    template_id: _Optional[int] = None
    custom_system_prompt: _Optional[str] = None
    custom_user_prompt: _Optional[str] = None
    notes: _Optional[str] = None
    created_at: _datetime
    updated_at: _datetime
    template_name: _Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/books/{book_id}/prompt-configs", response_model=list[PromptConfigRead])
async def list_prompt_configs(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all per-book prompt overrides."""
    from sqlalchemy.orm import joinedload as _jl
    result = await db.execute(
        select(BookPromptConfig)
        .options(_jl(BookPromptConfig.template))
        .where(BookPromptConfig.work_id == book_id)
        .order_by(BookPromptConfig.created_at)
    )
    configs = result.unique().scalars().all()
    return [
        PromptConfigRead(
            id=c.id, work_id=c.work_id, template_id=c.template_id,
            custom_system_prompt=c.custom_system_prompt,
            custom_user_prompt=c.custom_user_prompt,
            notes=c.notes, created_at=c.created_at, updated_at=c.updated_at,
            template_name=c.template.name if c.template else None,
        )
        for c in configs
    ]


@router.put("/books/{book_id}/prompt-configs", response_model=PromptConfigRead)
async def upsert_prompt_config(
    book_id: int,
    data: PromptConfigUpsert,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Create or update a per-book prompt override for a template."""
    bk_result = await db.execute(select(Book).where(Book.id == book_id))
    if not bk_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    stmt = select(BookPromptConfig).where(
        BookPromptConfig.work_id == book_id,
        BookPromptConfig.template_id == data.template_id,
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config:
        if data.custom_system_prompt is not None:
            config.custom_system_prompt = data.custom_system_prompt
        if data.custom_user_prompt is not None:
            config.custom_user_prompt = data.custom_user_prompt
        if data.notes is not None:
            config.notes = data.notes
    else:
        config = BookPromptConfig(
            book_id=book_id, template_id=data.template_id,
            custom_system_prompt=data.custom_system_prompt,
            custom_user_prompt=data.custom_user_prompt, notes=data.notes,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)

    tname = None
    if config.template_id:
        from sqlalchemy.orm import joinedload as _jl2
        r2 = await db.execute(
            select(BookPromptConfig).options(_jl2(BookPromptConfig.template)).where(BookPromptConfig.id == config.id)
        )
        cfg2 = r2.unique().scalar_one()
        tname = cfg2.template.name if cfg2.template else None

    return PromptConfigRead(
        id=config.id, work_id=config.work_id, template_id=config.template_id,
        custom_system_prompt=config.custom_system_prompt,
        custom_user_prompt=config.custom_user_prompt,
        notes=config.notes, created_at=config.created_at, updated_at=config.updated_at,
        template_name=tname,
    )


@router.delete("/books/{book_id}/prompt-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_config(
    book_id: int,
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Delete a per-book prompt override."""
    result = await db.execute(
        select(BookPromptConfig).where(BookPromptConfig.id == config_id, BookPromptConfig.work_id == book_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    await db.delete(config)
    await db.commit()


# ── Text extraction preview ────────────────────────────────────────────────────

class TextPreviewResponse(_BaseModel):
    book_id: int
    char_count: int
    word_count: int
    preview: str       # First ~2000 chars of optimized text
    truncated: bool    # Whether the full text was truncated for the LLM


@router.get("/books/{book_id}/text-preview", response_model=TextPreviewResponse)
async def get_text_preview(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Return a preview of the LLM-optimized text that would be sent for analysis.

    Useful for verifying extraction quality and debugging prompt issues
    before triggering a full (potentially expensive) AI analysis.
    """
    stmt = select(Book).where(Book.id == book_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    try:
        full_text = await extract_text_from_book(book, db, llm_optimize=True)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    PREVIEW_CHARS = 2000
    return TextPreviewResponse(
        book_id=book_id,
        char_count=len(full_text),
        word_count=len(full_text.split()),
        preview=full_text[:PREVIEW_CHARS],
        truncated=len(full_text) > PREVIEW_CHARS,
    )
