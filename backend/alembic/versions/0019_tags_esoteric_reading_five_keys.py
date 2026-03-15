"""Add tags+related_refs to annotations, esoteric_reading to book_analyses, seed Five Keys templates

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


FIVE_KEYS_TEMPLATES = [
    {
        "name": "Strauss: Center",
        "description": "Find what is hidden in the structural middle of the text — a Straussian Five Keys technique.",
        "system_prompt": (
            "You are an expert in Leo Strauss's method of close reading. "
            "A central Straussian principle is that great authors hide their most dangerous teachings "
            "at the physical center of their text, where casual readers are least attentive. "
            "Analyze the structural center of the provided text with precision and scholarly rigor."
        ),
        "user_prompt_template": (
            "Perform a CENTER analysis on the following text using Strauss's methodology:\n\n"
            "1. Identify the approximate structural center of the text (by word or section count).\n"
            "2. Quote or describe the content at and around that center.\n"
            "3. Analyze why this placement might be deliberate — what teaching or idea is "
            "emphasized by being placed at the center rather than the opening or conclusion?\n"
            "4. Compare the central content to the opening and closing — what does the contrast reveal?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Contradiction",
        "description": "Flag deliberate contradictions — where the subversive view is the real one, the pious statement its bodyguard.",
        "system_prompt": (
            "You are an expert in Leo Strauss's esoteric hermeneutics. "
            "Strauss taught that great authors writing under censorship or social constraint embed "
            "contradictions deliberately: the conventional or pious statement is a 'bodyguard' for "
            "the dangerous truth, which is revealed in the contradicting passage. "
            "Identify and analyze these contradictions with scholarly precision."
        ),
        "user_prompt_template": (
            "Perform a CONTRADICTION analysis on the following text using Strauss's methodology:\n\n"
            "For each significant contradiction or inconsistency you find:\n"
            "1. Quote the conventional/surface statement.\n"
            "2. Quote the contradicting passage.\n"
            "3. Explain which statement appears to be the 'bodyguard' (the acceptable view) "
            "and which reveals the deeper teaching.\n"
            "4. Explain what the contradiction tells us about the author's true position.\n\n"
            "Focus on contradictions too deliberate to be accidental errors.\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Silence",
        "description": "Identify conspicuous absences — what the author refuses to say speaks loudest.",
        "system_prompt": (
            "You are a scholar trained in detecting significant omissions in philosophical and "
            "literary texts. Leo Strauss observed that what a great author conspicuously does not say, "
            "given the subject matter, is often the most important thing to notice. "
            "Analyze the text for meaningful silences, absent vocabulary, and missing arguments."
        ),
        "user_prompt_template": (
            "Perform a SILENCE analysis on the following text using Strauss's methodology:\n\n"
            "1. Given the topic and genre of this text, list vocabulary, themes, figures, or "
            "arguments that one would naturally expect to appear but are conspicuously absent.\n"
            "2. For each silence, explain: (a) what would normally be present, "
            "(b) how the author navigates around it, and (c) what the author's silence might "
            "reveal about their true position.\n"
            "3. Identify any passages where the author comes close to a topic and then "
            "deliberately turns away — what does that swerve signal?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Repetition with Variation",
        "description": "Track recurring phrases and lists where subtle omissions or changes signal the esoteric teaching.",
        "system_prompt": (
            "You are an expert in Straussian close reading with particular skill in detecting "
            "meaningful patterns of repetition and variation. Strauss observed that when an author "
            "repeats a phrase, list, or formula with a subtle change — an addition, omission, or "
            "reordering — that variation is never accidental and always carries interpretive weight."
        ),
        "user_prompt_template": (
            "Perform a REPETITION WITH VARIATION analysis on the following text:\n\n"
            "1. Identify all recurring phrases, formulaic lists, or repeated structural patterns.\n"
            "2. For each repetition, note exactly what is the same and what is different "
            "(added, omitted, reordered, or changed) across its occurrences.\n"
            "3. Analyze the significance of each variation: what does the omission or addition "
            "emphasize? What does the change in order suggest about the author's priorities?\n"
            "4. Identify which variation, if any, represents the author's 'true' or full teaching "
            "versus the more guarded versions.\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Boring Passages",
        "description": "Find where authors hide important teachings in apparently dry, technical, or digressive sections.",
        "system_prompt": (
            "You are a Straussian reader who knows that important philosophical teachings are often "
            "deliberately hidden in apparently dull, technical, or digressive passages. "
            "Strauss wrote: 'The truth is whispered in the very passages which are likely to be "
            "skipped by all but the most careful readers.' Identify and excavate these passages."
        ),
        "user_prompt_template": (
            "Perform a BORING PASSAGES analysis on the following text using Strauss's methodology:\n\n"
            "1. Identify passages that seem unusually dry, technical, repetitive, pedantic, "
            "or digressive compared to the surrounding prose.\n"
            "2. For each such passage, explain what makes it appear boring or skippable on first read.\n"
            "3. Read it with extreme care: what crucial argument, dangerous teaching, or "
            "surprising claim is concealed within its apparently tedious surface?\n"
            "4. Explain why the author might have chosen this camouflage — what risk was being "
            "avoided by hiding this content in plain sight?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
]


def _has_column(conn, table: str, column: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    conn = op.get_bind()
    # ── Schema additions (idempotent) ─────────────────────────────────────
    if not _has_column(conn, "annotations", "tags"):
        op.add_column("annotations", sa.Column("tags", sa.Text(), nullable=True))
    if not _has_column(conn, "annotations", "related_refs"):
        op.add_column("annotations", sa.Column("related_refs", sa.Text(), nullable=True))
    if not _has_column(conn, "book_analyses", "esoteric_reading"):
        op.add_column("book_analyses", sa.Column("esoteric_reading", sa.Text(), nullable=True))

    # ── Seed Five Keys templates ──────────────────────────────────────────
    for t in FIVE_KEYS_TEMPLATES:
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


def downgrade() -> None:
    op.drop_column("annotations", "tags")
    op.drop_column("annotations", "related_refs")
    op.drop_column("book_analyses", "esoteric_reading")
    conn = op.get_bind()
    for t in FIVE_KEYS_TEMPLATES:
        conn.execute(
            sa.text("DELETE FROM analysis_templates WHERE name = :name AND is_builtin = 1"),
            {"name": t["name"]},
        )
