"""Seed standard analysis templates (fiction, non-fiction, Blinkist-style summary)

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


STANDARD_TEMPLATES = [
    {
        "name": "Fiction: Deep Literary Analysis",
        "description": "Comprehensive narrative, character, thematic, and psychological analysis for fiction.",
        "system_prompt": (
            "You are a literary analyst, narrative psychologist, and structural story expert. "
            "Analyze fiction texts with depth, precision, and layered summarization. "
            "Ground all interpretations in textual evidence. "
            "If uncertain, state possibilities rather than assert conclusions."
        ),
        "user_prompt_template": (
            "Analyze the following fiction text with depth, precision, and layered summarization.\n\n"
            "Follow this structure exactly:\n\n"
            "--------------------------------------------------\n"
            "1. STORY OVERVIEW\n"
            "--------------------------------------------------\n"
            "- Title (if known):\n"
            "- Author (if known):\n"
            "- Genre:\n"
            "- Setting (time, place, atmosphere):\n"
            "- Core Conflict (external and internal):\n"
            "- Central Themes (3-7 themes):\n\n"
            "--------------------------------------------------\n"
            "2. PLOT STRUCTURE\n"
            "--------------------------------------------------\n"
            "For this section:\n\n"
            "- Major Events:\n"
            "- Turning Points:\n"
            "- Rising Tension Elements:\n"
            "- Climax (if present):\n"
            "- Resolution (if present):\n"
            "- Stakes (what is at risk?):\n\n"
            "If applicable, identify:\n"
            "- Inciting Incident\n"
            "- Midpoint Shift\n"
            "- Dark Night of the Soul\n"
            "- Final Confrontation\n\n"
            "--------------------------------------------------\n"
            "3. CHARACTER ANALYSIS\n"
            "--------------------------------------------------\n"
            "For each significant character:\n\n"
            "Name:\n"
            "- Role in the story:\n"
            "- Primary motivation:\n"
            "- Internal conflict:\n"
            "- External conflict:\n"
            "- Character arc (how they change):\n"
            "- Moral alignment or ambiguity:\n"
            "- Symbolic function (if any):\n\n"
            "--------------------------------------------------\n"
            "4. THEMES & SYMBOLISM\n"
            "--------------------------------------------------\n"
            "Identify:\n\n"
            "- Major themes and how they are developed\n"
            "- Recurring motifs\n"
            "- Symbolic objects or imagery\n"
            "- Metaphors that reinforce theme\n"
            "- Parallels between characters or events\n"
            "- Irony (situational, dramatic, verbal)\n\n"
            "Explain how these deepen meaning.\n\n"
            "--------------------------------------------------\n"
            "5. NARRATIVE TECHNIQUE\n"
            "--------------------------------------------------\n"
            "- Point of view:\n"
            "- Reliability of narrator:\n"
            "- Tone:\n"
            "- Pacing:\n"
            "- Use of dialogue:\n"
            "- Use of description:\n"
            "- Foreshadowing:\n"
            "- Structural choices (nonlinear? framed narrative? multiple POV?):\n\n"
            "--------------------------------------------------\n"
            "6. EMOTIONAL & PSYCHOLOGICAL LAYER\n"
            "--------------------------------------------------\n"
            "- Emotional arc of this section:\n"
            "- Dominant emotional tones:\n"
            "- Psychological drivers of main characters:\n"
            "- Underlying fears or desires:\n"
            "- Moral tension present:\n\n"
            "--------------------------------------------------\n"
            "7. BIG IDEAS & PHILOSOPHICAL QUESTIONS\n"
            "--------------------------------------------------\n"
            "- What is the story suggesting about human nature?\n"
            "- What moral or philosophical questions are raised?\n"
            "- What worldview seems embedded in the narrative?\n\n"
            "--------------------------------------------------\n"
            "8. MULTI-LAYER SUMMARY\n"
            "--------------------------------------------------\n"
            "Provide:\n\n"
            "A. 1-sentence summary\n"
            "B. 1-paragraph summary\n"
            "C. 5-bullet summary\n"
            "D. 10-15 detailed bullet summary\n\n"
            "--------------------------------------------------\n"
            "9. MEMORABILITY & DISCUSSION\n"
            "--------------------------------------------------\n"
            "- Most powerful moment:\n"
            "- Most important quote (if present):\n"
            "- Discussion questions (5-10):\n"
            "- What makes this section distinctive?\n\n"
            "--------------------------------------------------\n\n"
            "Be insightful but concise.\n"
            "Avoid generic commentary.\n"
            "Ground all interpretations in textual evidence.\n"
            "If uncertain, state possibilities rather than assert conclusions.\n\n"
            "Now analyze the following text:\n\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Non-Fiction: Structured Breakdown",
        "description": "Extract key claims, frameworks, actionable insights, and critical questions from non-fiction.",
        "system_prompt": (
            "You are an expert analytical reader, researcher, and structured note-taker. "
            "Your task is to extract, organize, and summarize key information from book content. "
            "Be concise but complete. Avoid filler. Preserve nuance. "
            "If something is unclear, state uncertainty rather than guessing."
        ),
        "user_prompt_template": (
            "Extract, organize, and summarize key information from the following book content.\n\n"
            "Follow this exact structure:\n\n"
            "--------------------------------------------------\n"
            "1. HIGH-LEVEL OVERVIEW\n"
            "--------------------------------------------------\n"
            "- Book Title (if known):\n"
            "- Author (if known):\n"
            "- Central Thesis (1-3 sentences):\n"
            "- Primary Problem the Book Addresses:\n"
            "- Core Argument Summary (5-10 bullet points):\n\n"
            "--------------------------------------------------\n"
            "2. STRUCTURAL BREAKDOWN\n"
            "--------------------------------------------------\n"
            "For this section of text:\n"
            "- Main Topic of This Section:\n"
            "- Key Claims or Arguments:\n"
            "- Supporting Evidence or Examples:\n"
            "- Important Definitions:\n"
            "- Key Quotes (verbatim, if significant):\n"
            "- Data, Statistics, or Models Mentioned:\n\n"
            "--------------------------------------------------\n"
            "3. KEY CONCEPTS & FRAMEWORKS\n"
            "--------------------------------------------------\n"
            "List and explain:\n"
            "- Named frameworks, models, or systems\n"
            "- Step-by-step processes\n"
            "- Mental models introduced\n"
            "- Equations or formulas (if any)\n"
            "- Diagrams described (describe in text)\n\n"
            "--------------------------------------------------\n"
            "4. ACTIONABLE INSIGHTS\n"
            "--------------------------------------------------\n"
            "- Practical Takeaways:\n"
            "- Decisions this information influences:\n"
            "- Behaviors this suggests adopting or avoiding:\n"
            "- Who would benefit most from this content:\n\n"
            "--------------------------------------------------\n"
            "5. CRITICAL THINKING\n"
            "--------------------------------------------------\n"
            "- Assumptions made by the author:\n"
            "- Potential weaknesses or counterarguments:\n"
            "- What the book does NOT address:\n"
            "- Questions this raises:\n\n"
            "--------------------------------------------------\n"
            "6. MULTI-LAYER SUMMARY\n"
            "--------------------------------------------------\n"
            "Provide:\n\n"
            "A. 1-sentence summary\n"
            "B. 1-paragraph summary\n"
            "C. 5-bullet executive summary\n"
            "D. 10-15 detailed bullet summary\n\n"
            "--------------------------------------------------\n"
            "7. KNOWLEDGE GRAPH\n"
            "--------------------------------------------------\n"
            "Map relationships between concepts, causes, problems, and principles.\n\n"
            "Format as:\n"
            "Concept A -> leads to -> Result B\n"
            "Framework X -> supports -> Goal Y\n\n"
            "--------------------------------------------------\n\n"
            "Be concise but complete.\n"
            "Avoid filler.\n"
            "Preserve nuance.\n"
            "If something is unclear, state uncertainty rather than guessing.\n\n"
            "Now analyze the following content:\n\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Blinkist-Style Summary",
        "description": "Concise, accessible book summary in the style of Blinkist or Summaries.com — key ideas and takeaways.",
        "system_prompt": (
            "You are an expert book summarizer tasked with creating comprehensive yet concise book summaries "
            "in the style of Blinkist or Summaries.com. "
            "Capture essential ideas, frameworks, and actionable insights while remaining accessible and engaging. "
            "Clarity over completeness. Active voice. Present tense. Neutral tone. "
            "Do not simply retell the book chapter-by-chapter. "
            "Each section should make sense independently."
        ),
        "user_prompt_template": (
            "Create a comprehensive yet concise summary of the following book content.\n\n"
            "Follow this exact structure:\n\n"
            "1. BOOK OVERVIEW (2-3 sentences)\n"
            "- Core thesis or central question the book addresses\n"
            "- Target audience and why the book matters\n"
            "- Author's unique perspective or credentials (if apparent from the text)\n\n"
            "2. KEY IDEAS (5-8 main concepts)\n"
            "- Present the book's most important insights as distinct, standalone ideas\n"
            "- Each idea should be 2-4 sentences\n"
            "- Use clear, jargon-free language\n"
            "- Include memorable examples, metaphors, or case studies when relevant\n"
            "- Focus on concepts that are actionable or perspective-shifting\n\n"
            "3. MAIN TAKEAWAYS (3-5 bullet points)\n"
            "- Distill the most practical or memorable insights\n"
            "- What should readers remember six months after reading?\n"
            "- Include any frameworks, principles, or mental models introduced\n\n"
            "4. WHO SHOULD READ THIS (1-2 sentences)\n"
            "- Specific reader profiles who would benefit most\n"
            "- What problems or questions does this book address?\n\n"
            "Style guidelines:\n"
            "- Total summary: 500-800 words\n"
            "- Each key idea: 50-100 words\n"
            "- Active voice, present tense\n"
            "- Avoid 'the author argues' — just present the ideas\n"
            "- No spoilers for narrative non-fiction\n\n"
            "Now summarize the following content:\n\n{text}"
        ),
        "is_default": True,
        "is_builtin": True,
    },
    {
        "name": "Rosen: Reading the Ordinary",
        "description": "Stanley Rosen's phenomenological method — find the esoteric truth hidden on the surface, in the ordinary details theory ignores.",
        "system_prompt": (
            "You are a reader trained in Stanley Rosen's phenomenological approach to esoteric reading. "
            "Rosen argues that truth is not buried deep inside a text like a kernel in a nut — it is hidden "
            "in plain sight on the surface, in the ordinary details that theoretically-minded readers are "
            "trained to ignore. The 'Ordinary' (hunger, fatigue, loyalty, lust) is the bedrock reality that "
            "undermines the 'Extraordinary' (heroism, divine intervention, abstract philosophy). "
            "Your task is to read the surface with extreme attention and recover what theory discards."
        ),
        "user_prompt_template": (
            "Perform a ROSEN ORDINARY READING on the following text:\n\n"
            "Apply Stanley Rosen's four-step phenomenological method:\n\n"
            "1. THE SURFACE IS THE DEPTH\n"
            "   - Identify the most obvious, physical, 'ordinary' details in the text: "
            "hunger, thirst, fatigue, lust, fear, loyalty, domestic life.\n"
            "   - Do not ask 'what do these symbolize?' Ask: 'Why does the author mention this NOW? "
            "What does this ordinary detail reveal about the character's situation that their "
            "high-flown speech or heroic action is concealing?'\n"
            "   - Show how the 'Ordinary' undercuts the 'Extraordinary.'\n\n"
            "2. THE NOBLE NATURE OF THE ORDINARY\n"
            "   - Identify characters who represent 'Ordinary Common Sense' versus those who "
            "represent 'Abstract Theory' or divine/heroic detachment.\n"
            "   - Which characters are grounded? Which are dangerously theoretical?\n"
            "   - Make the case that the 'ordinary' character may be wiser than the 'extraordinary' one.\n\n"
            "3. THE MATHEMATICAL DISTRACTION\n"
            "   - Identify any lists, catalogues, enumerations, or rigid structures in the text.\n"
            "   - Examine them with suspicion: are they complete? Are they internally consistent?\n"
            "   - Show how the apparent 'order' conceals the chaotic reality the author actually portrays.\n\n"
            "4. THE INTUITION CHECK\n"
            "   - Identify any passages that feel unusually boring, pedantic, or over-long.\n"
            "   - Read these with extreme care. What contradiction, reversal, or hidden claim is "
            "buried in the apparently dull surface?\n"
            "   - Why might the author have placed an important teaching in a passage designed to be skipped?\n\n"
            "Contrast Rosen's findings with what a Straussian 'Center/Contradiction' reading would reveal. "
            "Where do the two methods agree? Where do they diverge?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    # Clear existing default before setting a new one
    conn.execute(
        sa.text("UPDATE analysis_templates SET is_default = 0 WHERE is_default = 1")
    )

    for t in STANDARD_TEMPLATES:
        existing = conn.execute(
            sa.text("SELECT id FROM analysis_templates WHERE name = :name"),
            {"name": t["name"]},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO analysis_templates "
                    "(name, description, system_prompt, user_prompt_template, is_default, is_builtin, created_at, updated_at) "
                    "VALUES (:name, :description, :system_prompt, :user_prompt_template, :is_default, :is_builtin, datetime('now'), datetime('now'))"
                ),
                {
                    "name": t["name"],
                    "description": t["description"],
                    "system_prompt": t["system_prompt"],
                    "user_prompt_template": t["user_prompt_template"],
                    "is_default": 1 if t["is_default"] else 0,
                    "is_builtin": 1 if t["is_builtin"] else 0,
                },
            )
        else:
            conn.execute(
                sa.text(
                    "UPDATE analysis_templates SET "
                    "description = :description, system_prompt = :system_prompt, "
                    "user_prompt_template = :user_prompt_template, is_default = :is_default, "
                    "updated_at = datetime('now') "
                    "WHERE name = :name AND is_builtin = 1"
                ),
                {
                    "name": t["name"],
                    "description": t["description"],
                    "system_prompt": t["system_prompt"],
                    "user_prompt_template": t["user_prompt_template"],
                    "is_default": 1 if t["is_default"] else 0,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    for t in STANDARD_TEMPLATES:
        conn.execute(
            sa.text("DELETE FROM analysis_templates WHERE name = :name AND is_builtin = 1"),
            {"name": t["name"]},
        )
