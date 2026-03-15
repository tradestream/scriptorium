"""Book analysis service — orchestrates LLM-powered literary analysis.

Handles template resolution, LLM invocation, and result persistence.
Text extraction is delegated to app.services.text_extraction.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, BookFile
from app.models.analysis import AnalysisTemplate, BookAnalysis, BookPromptConfig
from app.services.llm import LLMProvider, get_llm_provider
from app.services.text_extraction import extract_text_from_book

logger = logging.getLogger(__name__)


# --- Built-in prompt template (ships with Scriptorium) ---
LITERARY_ANALYSIS_SYSTEM = """You are a literary analyst, narrative psychologist, and structural story expert.
Analyze the following fiction text with depth, precision, and layered summarization.
Be insightful but concise. Avoid generic commentary.
Ground all interpretations in textual evidence.
If uncertain, state possibilities rather than assert conclusions."""

LITERARY_ANALYSIS_TEMPLATE = """Follow this structure exactly:

1. STORY OVERVIEW
- Title (if known)
- Author (if known)
- Genre
- Setting (time, place, atmosphere)
- Core Conflict (external and internal)
- Central Themes (3-7 themes)

2. PLOT STRUCTURE
- Major Events
- Turning Points
- Rising Tension Elements
- Climax (if present)
- Resolution (if present)
- Stakes (what is at risk?)
If applicable: Inciting Incident, Midpoint Shift, Dark Night of the Soul, Final Confrontation

3. CHARACTER ANALYSIS
For each significant character:
- Name, Role, Primary motivation
- Internal and external conflict
- Character arc (how they change)
- Moral alignment or ambiguity
- Symbolic function (if any)

4. THEMES & SYMBOLISM
- Major themes and how they are developed
- Recurring motifs
- Symbolic objects or imagery
- Metaphors that reinforce theme
- Parallels between characters or events
- Irony (situational, dramatic, verbal)

5. NARRATIVE TECHNIQUE
- Point of view, Reliability of narrator
- Tone, Pacing, Use of dialogue/description
- Foreshadowing
- Structural choices (nonlinear? framed narrative? multiple POV?)

6. EMOTIONAL & PSYCHOLOGICAL LAYER
- Emotional arc, Dominant emotional tones
- Psychological drivers of main characters
- Underlying fears or desires
- Moral tension present

7. BIG IDEAS & PHILOSOPHICAL QUESTIONS
- What is the story suggesting about human nature?
- What moral/philosophical questions are raised?
- What worldview seems embedded in the narrative?

8. MULTI-LAYER SUMMARY
A. 1-sentence summary
B. 1-paragraph summary
C. 5-bullet summary
D. 10-15 detailed bullet summary

9. MEMORABILITY & DISCUSSION
- Most powerful moment
- Most important quote (if present)
- Discussion questions (5-10)
- What makes this section distinctive?

Now analyze the following text:

{text}"""




NONFICTION_ANALYSIS_SYSTEM = """You are an expert analytical reader, researcher, and structured note-taker.
Your task is to extract, organize, and summarize key information from the following book content.
Be concise but complete. Avoid filler. Preserve nuance.
If something is unclear, state uncertainty rather than guessing."""

NONFICTION_ANALYSIS_TEMPLATE = """Follow this exact structure:

1. HIGH-LEVEL OVERVIEW
- Book Title (if known)
- Author (if known)
- Central Thesis (1-3 sentences)
- Primary Problem the Book Addresses
- Core Argument Summary (5-10 bullet points)

2. STRUCTURAL BREAKDOWN
For this section of text:
- Main Topic of This Section
- Key Claims or Arguments
- Supporting Evidence or Examples
- Important Definitions
- Key Quotes (verbatim, if significant)
- Data, Statistics, or Models Mentioned

3. KEY CONCEPTS & FRAMEWORKS
List and explain:
- Named frameworks, models, or systems
- Step-by-step processes
- Mental models introduced
- Equations or formulas (if any)
- Diagrams described (describe in text)

4. ACTIONABLE INSIGHTS
- Practical Takeaways
- Decisions this information influences
- Behaviors this suggests adopting or avoiding
- Who would benefit most from this content

5. CRITICAL THINKING
- Assumptions made by the author
- Potential weaknesses or counterarguments
- What the book does NOT address
- Questions this raises

6. MULTI-LAYER SUMMARY
A. 1-sentence summary
B. 1-paragraph summary
C. 5-bullet executive summary
D. 10-15 detailed bullet summary

7. KNOWLEDGE GRAPH
Map relationships between:
- Concepts
- Causes -> effects
- Problems -> solutions
- Principles -> outcomes
Format as: Concept A -> leads to -> Result B

Now analyze the following content:

{text}"""



ESOTERIC_READING_SYSTEM = """You are an expert in the tradition of esoteric writing and reading as described by Arthur M. Melzer, Leo Strauss, and the broader history of philosophical esotericism.

You understand that many great texts throughout history operated on two levels:
- An EXOTERIC (surface) teaching: conventional, pious, safe — designed for the general public
- An ESOTERIC (hidden) teaching: philosophical, subversive, dangerous — intended for careful readers

Your task is to read the given text with the assumption that it may contain deliberate double meanings, strategic omissions, intentional contradictions, and protective rhetoric. You are looking for what the text says between the lines.

Be precise and evidence-based. Distinguish between strong signals and speculative readings. Never force an esoteric reading where the text doesn't support it — but never dismiss anomalies either."""

ESOTERIC_READING_TEMPLATE = """Perform a two-layer (exoteric/esoteric) reading of the following text. Follow this structure exactly:

1. SURFACE READING (Exoteric Layer)
- What does this text appear to be saying at face value?
- What conventional beliefs, pieties, or authorities does it affirm?
- What audience would find this reading comfortable or reassuring?
- What moral, political, or theological orthodoxy does the surface conform to?

2. LOUD SILENCES (Strategic Omissions)
- What topics does the author conspicuously avoid?
- Where does a pattern or list break down — where is a parallel element missing?
- What questions does the text raise but never answer?
- What characters, events, or themes receive suspiciously little attention?
- Are there expectations set by the genre or tradition that the author violates by omission?

3. INTENTIONAL CONTRADICTIONS & ERRORS
- Identify any contradictions between different parts of the text
- Note logical gaps, non-sequiturs, or arguments that don't follow
- Flag factual "errors" that seem too obvious for the author to have made accidentally
- Where does the text say one thing and demonstrate another?
- Where do characters' actions contradict their stated beliefs?

4. PROTECTIVE RHETORIC (Defensive Esotericism)
- Where does the author seem to be protecting themselves from censure?
- Identify excessive praise of authorities, gods, rulers, or conventions that feels performative
- Where does piety feel mechanical or formulaic rather than sincere?
- Note qualifying phrases, hedges, or disclaimers that soften a dangerous claim
- Identify "noble lies" — statements that may be socially useful but philosophically false

5. SPEECH vs. DEED ANALYSIS
- Compare what characters say vs. what they do
- Compare the narrator's stated judgments vs. what the narrative actually shows
- Who speaks the truth in this text? Who lies? Is the "wise" character the truthful one?
- Are there characters who represent the philosopher, the city, or the poet?

6. STRUCTURAL ESOTERICISM
- What is at the physical center of this text or section?
- Does the arrangement of material hide something important in an inconspicuous location?
- Are there chiastic (ring) structures, where the outer layers mirror each other and the center holds the key?
- Is information placed strategically — important truths buried in digressions or asides?

7. THE DOUBLE DOCTRINE
Based on your analysis above, articulate:
A. THE EXOTERIC TEACHING: What the text wants most readers to believe
B. THE ESOTERIC TEACHING: What the text may actually be arguing for the careful reader
C. THE EVIDENCE: Rank your evidence from strongest to most speculative
D. THE PROTECTIVE PURPOSE: Why would the author hide this? What danger does the esoteric truth pose?

8. READING BETWEEN THE LINES — KEY PASSAGES
Identify 3-5 specific passages that are most revealing when read esoterically. For each:
- Quote or locate the passage
- Explain the surface reading
- Explain the esoteric reading
- Rate confidence: HIGH / MEDIUM / SPECULATIVE

9. PHILOSOPHICAL QUESTIONS RAISED
- What does this text suggest about the relationship between philosophy and society?
- What does it suggest about truth and its dangers?
- What does it imply about the nature of writing itself?

Now analyze the following text esoterically:

{text}"""

async def get_or_create_default_template(db: AsyncSession) -> AnalysisTemplate:
    """Get the default built-in literary analysis template, creating it if needed."""
    stmt = select(AnalysisTemplate).where(
        AnalysisTemplate.is_builtin == True,
        AnalysisTemplate.name == "Literary Analysis",
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if template is None:
        template = AnalysisTemplate(
            name="Literary Analysis",
            description="Comprehensive literary analysis covering plot, characters, themes, symbolism, and narrative technique.",
            system_prompt=LITERARY_ANALYSIS_SYSTEM,
            user_prompt_template=LITERARY_ANALYSIS_TEMPLATE,
            is_default=True,
            is_builtin=True,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

    return template


async def seed_builtin_templates(db: AsyncSession) -> None:
    """Ensure all built-in templates exist in the database."""
    builtins = [
        {
            "name": "Literary Analysis",
            "description": "Comprehensive literary analysis covering plot, characters, themes, symbolism, and narrative technique. Best for fiction.",
            "system_prompt": LITERARY_ANALYSIS_SYSTEM,
            "user_prompt_template": LITERARY_ANALYSIS_TEMPLATE,
            "is_default": True,
        },
        {
            "name": "Non-Fiction Analysis",
            "description": "Structured extraction of key concepts, frameworks, actionable insights, and knowledge graphs. Best for non-fiction and textbooks.",
            "system_prompt": NONFICTION_ANALYSIS_SYSTEM,
            "user_prompt_template": NONFICTION_ANALYSIS_TEMPLATE,
            "is_default": False,
        },
        {
            "name": "Esoteric Reading",
            "description": "Two-layer (exoteric/esoteric) reading based on Melzer and Strauss. Detects loud silences, intentional contradictions, protective rhetoric, and hidden philosophical teachings. Best for classical, philosophical, and literary texts.",
            "system_prompt": ESOTERIC_READING_SYSTEM,
            "user_prompt_template": ESOTERIC_READING_TEMPLATE,
            "is_default": False,
        },
    ]

    for tmpl_data in builtins:
        stmt = select(AnalysisTemplate).where(
            AnalysisTemplate.is_builtin == True,
            AnalysisTemplate.name == tmpl_data["name"],
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            template = AnalysisTemplate(
                **tmpl_data,
                is_builtin=True,
            )
            db.add(template)

    await db.commit()


async def run_analysis(
    book_id: int,
    db: AsyncSession,
    template_id: Optional[int] = None,
    custom_prompt: Optional[str] = None,
    title: str = "Literary Analysis",
) -> BookAnalysis:
    """Run an LLM analysis on a book and save the result.

    Args:
        book_id: The book to analyze
        db: Database session
        template_id: Specific template to use (optional)
        custom_prompt: One-off prompt override (optional)
        title: Label for this analysis
    """
    # Fetch the book
    stmt = select(Book).where(Book.id == book_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if not book:
        raise ValueError(f"Book not found: {book_id}")

    # Create a pending analysis record
    analysis = BookAnalysis(
        book_id=book_id,
        template_id=template_id,
        title=title,
        content="",
        status="running",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    try:
        # Extract text
        text = await extract_text_from_book(book, db)

        # Resolve the template
        if template_id:
            stmt = select(AnalysisTemplate).where(AnalysisTemplate.id == template_id)
            result = await db.execute(stmt)
            template = result.scalar_one_or_none()
            if not template:
                raise ValueError(f"Template not found: {template_id}")
            analysis.template_id = template.id
        else:
            template = await get_or_create_default_template(db)
            template_id = template.id
            analysis.template_id = template.id

        # Check for per-book prompt override
        cfg_result = await db.execute(
            select(BookPromptConfig).where(
                BookPromptConfig.book_id == book_id,
                BookPromptConfig.template_id == template_id,
            )
        )
        book_cfg = cfg_result.scalar_one_or_none()

        # Resolve the prompt — per-book overrides take priority; custom_prompt overrides all
        if custom_prompt:
            system_prompt = template.system_prompt
            user_prompt = custom_prompt.replace("{text}", text) if "{text}" in custom_prompt else f"{custom_prompt}\n\n{text}"
        elif book_cfg:
            system_prompt = book_cfg.custom_system_prompt or template.system_prompt
            raw_user = book_cfg.custom_user_prompt or template.user_prompt_template
            user_prompt = raw_user.replace("{text}", text)
        else:
            system_prompt = template.system_prompt
            user_prompt = template.user_prompt_template.replace("{text}", text)

        # Call the LLM
        provider = get_llm_provider()
        if not provider.is_available():
            raise RuntimeError(
                "No LLM provider configured. Set ANTHROPIC_API_KEY, configure Ollama, "
                "or set OPENAI_API_KEY in your environment."
            )

        llm_response = await provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Save the result
        analysis.content = llm_response.content
        analysis.model_used = llm_response.model
        analysis.token_count = llm_response.total_tokens
        analysis.status = "completed"

    except Exception as e:
        logger.error(f"Analysis failed for book {book_id}: {e}")
        analysis.status = "failed"
        analysis.error_message = str(e)

    await db.commit()
    await db.refresh(analysis)
    return analysis
