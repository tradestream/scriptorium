"""Seed Melzer Four Forms templates and audience differentiation template

Revision ID: 0061
Revises: 0060
"""
import json
from alembic import op
from sqlalchemy import text

revision = "0061"
down_revision = "0060"


MELZER_TEMPLATES = [
    {
        "name": "Melzer: Four Forms Classification",
        "description": "Classify which of Melzer's four forms of esotericism a text exhibits: defensive, protective, pedagogical, or political.",
        "system_prompt": (
            "You are an expert in Arthur M. Melzer's taxonomy of philosophical esotericism "
            "from 'Philosophy Between the Lines.' Melzer identifies four distinct forms, each with "
            "different motives, techniques, and historical periods:\n\n"
            "1. DEFENSIVE esotericism — hiding views to avoid persecution by political/religious authorities. "
            "The author fears punishment. Technique: conformity on the surface, subversion between the lines.\n\n"
            "2. PROTECTIVE esotericism — concealing dangerous truths from society for its own good. "
            "The author believes certain truths would harm ordinary people. Technique: noble lies, "
            "selective disclosure, writing for the 'few.'\n\n"
            "3. PEDAGOGICAL esotericism — using obscurity to force active thinking in students. "
            "The author wants to teach philosophizing, not doctrines. Technique: puzzles, contradictions, "
            "apparent errors that reward careful reading.\n\n"
            "4. POLITICAL esotericism — gradually spreading subversive ideas to reshape society. "
            "The author seeks social transformation through cautious public dissemination. "
            "Technique: cross-references, strategic ambiguity, collective writing projects.\n\n"
            "Analyze the text to determine which form(s) are present. A text may exhibit multiple forms."
        ),
        "user_prompt_template": (
            "Classify the following text according to Melzer's Four Forms of Esotericism:\n\n"
            "For EACH form, provide:\n"
            "1. Evidence present (specific passages or features)\n"
            "2. Evidence absent (why this form may NOT apply)\n"
            "3. Confidence: HIGH / MEDIUM / LOW / NOT PRESENT\n\n"
            "Then provide:\n"
            "- PRIMARY FORM: Which form dominates this text and why\n"
            "- SECONDARY FORMS: Any additional forms present\n"
            "- HISTORICAL CONTEXT: What about the author's time/place explains the form used\n"
            "- AUDIENCE: Who are the 'few' vs. the 'many' in this text's implied readership\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Melzer: Reading the White",
        "description": "Analyze what the author conspicuously does NOT write — the 'white spaces' that reveal hidden meaning.",
        "system_prompt": (
            "You are an expert in esoteric reading, following the principle articulated by "
            "Abbé Galiani: 'read the white, read what I did not write.' "
            "Great esoteric writers communicate as much by what they omit as by what they include. "
            "Strategic omissions can be more revealing than explicit statements. "
            "Your task is to identify what is conspicuously absent from the text."
        ),
        "user_prompt_template": (
            "Perform a 'READING THE WHITE' analysis on the following text:\n\n"
            "1. EXPECTED TOPICS NOT ADDRESSED\n"
            "- Given the text's subject, genre, and historical context, what topics would a reader "
            "reasonably expect to find discussed that are absent?\n"
            "- Are any of these absences too conspicuous to be accidental?\n\n"
            "2. TRUNCATED ARGUMENTS\n"
            "- Where does the author begin a line of reasoning and then abandon it?\n"
            "- Where does a logical chain stop one step short of its natural conclusion?\n"
            "- What conclusion would the reader draw if allowed to complete the argument?\n\n"
            "3. MISSING PARALLELS\n"
            "- Where does a list, enumeration, or pattern have a gap?\n"
            "- Where does a parallel structure break down — a symmetric argument with one side undeveloped?\n\n"
            "4. QUESTIONS RAISED BUT NOT ANSWERED\n"
            "- What questions does the text explicitly pose without answering?\n"
            "- What questions are implied by the argument but never asked?\n\n"
            "5. THE TEACHING OF SILENCE\n"
            "- Taking all these omissions together, what doctrine or position do they point toward?\n"
            "- Why would the author need to leave this unsaid rather than state it directly?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Melzer: Authority Framing",
        "description": "Analyze how the author quotes, cites, and frames authorities — are they being praised sincerely or undermined subtly?",
        "system_prompt": (
            "You are an expert in esoteric writing techniques. A common device of esoteric writers "
            "is to quote or cite authorities — religious texts, rulers, established thinkers — in ways "
            "that superficially show deference but subtly undermine them. This can be done through:\n"
            "- Selective quotation that changes the original meaning\n"
            "- Excessive praise that reads as ironic\n"
            "- Juxtaposing an authority's words with contradicting evidence\n"
            "- Attributing dangerous ideas to respected figures as cover\n"
            "- Praising an authority while actually arguing the opposite position\n\n"
            "Your task is to analyze how the author treats cited authorities and what this reveals."
        ),
        "user_prompt_template": (
            "Perform an AUTHORITY FRAMING analysis on the following text:\n\n"
            "For each significant authority cited or quoted (philosopher, religious figure, ruler, text):\n\n"
            "1. WHO is cited and what is attributed to them?\n"
            "2. How is the citation FRAMED — with praise, criticism, neutrality, or irony?\n"
            "3. Is the citation ACCURATE or has it been selectively edited or recontextualized?\n"
            "4. Does the surrounding text SUPPORT or UNDERMINE what the authority says?\n"
            "5. Is the author using the authority as a SHIELD (to express a dangerous view "
            "through someone else's mouth) or a TARGET (to subtly demolish their position)?\n\n"
            "Then synthesize:\n"
            "- Which authorities does the author genuinely respect vs. merely pretend to respect?\n"
            "- What does the pattern of citation reveal about the author's actual position?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for tmpl in MELZER_TEMPLATES:
        conn.execute(
            text(
                "INSERT INTO analysis_templates "
                "(name, description, system_prompt, user_prompt_template, is_default, is_builtin) "
                "VALUES (:name, :desc, :sys, :user, 0, 1)"
            ),
            {
                "name": tmpl["name"],
                "desc": tmpl["description"],
                "sys": tmpl["system_prompt"],
                "user": tmpl["user_prompt_template"],
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    for tmpl in MELZER_TEMPLATES:
        conn.execute(
            text("DELETE FROM analysis_templates WHERE name = :name"),
            {"name": tmpl["name"]},
        )
