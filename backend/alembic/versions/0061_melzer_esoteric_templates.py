"""Seed Melzer Four Forms templates and audience differentiation template

Revision ID: 0061
Revises: 0060
"""
import json
from alembic import op
from sqlalchemy import text

revision = "0061"
down_revision = "0060"


STRAUSS_TEMPLATES = [
    {
        "name": "Strauss: Intentional Blunders",
        "description": "Find errors too obvious for the author to have made accidentally — the 'intelligent high-school boy' test.",
        "system_prompt": (
            "You are an expert in Leo Strauss's method of esoteric reading. "
            "Strauss's key principle: 'If a master of the art of writing commits such blunders "
            "as would shame an intelligent high-school boy, it is reasonable to assume that they "
            "are intentional.' These 'blunders' include: factual errors about well-known matters, "
            "logical contradictions within a few pages, misquotations of famous sources, numerical "
            "discrepancies, anachronisms, and arguments that conspicuously fail to follow from their "
            "premises. The careful reader recognizes these as deliberate signals pointing to the "
            "author's hidden teaching."
        ),
        "user_prompt_template": (
            "Perform an INTENTIONAL BLUNDER analysis on the following text:\n\n"
            "1. FACTUAL ERRORS: Identify any claims that appear factually wrong in ways the author "
            "would certainly have known. Are these errors in areas where the author demonstrates "
            "expertise elsewhere?\n\n"
            "2. LOGICAL CONTRADICTIONS: Find arguments that contradict each other within the text. "
            "Are they close enough together that the author must have noticed? Or separated by "
            "enough distance to escape the casual reader?\n\n"
            "3. MISQUOTATIONS: Does the author quote any authority inaccurately? Is the alteration "
            "meaningful — does it change the doctrine being attributed?\n\n"
            "4. NUMERICAL DISCREPANCIES: Are there counts, enumerations, or sequences that don't "
            "add up? (e.g., promising to discuss five points but only discussing four)\n\n"
            "5. NON SEQUITURS: Where does a conclusion conspicuously not follow from the argument "
            "that precedes it? What conclusion WOULD follow if stated?\n\n"
            "For each blunder found, assess:\n"
            "- Is this plausibly accidental or almost certainly deliberate?\n"
            "- What teaching does it point toward when read as intentional?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Unique Statements",
        "description": "Find claims the author makes exactly once while asserting the contrary everywhere else — the 'unique statement' principle.",
        "system_prompt": (
            "You are an expert in Leo Strauss's hermeneutics. Strauss observed: "
            "'If an author makes a statement on a very important subject only once, while in all "
            "other places he either asserts its contrary or remains silent on the subject, students "
            "of the author invariably ignore the unique statement.' "
            "This is one of the most powerful indicators of esoteric writing: the author's true "
            "view appears exactly once, buried among repeated assertions of the opposite. "
            "Careful readers notice the unique statement; careless ones follow the repeated view."
        ),
        "user_prompt_template": (
            "Perform a UNIQUE STATEMENT analysis on the following text:\n\n"
            "1. Identify the text's REPEATED POSITIONS — what views are asserted multiple times, "
            "forming the apparent consensus of the work?\n\n"
            "2. Search for UNIQUE CONTRARY STATEMENTS — claims that appear exactly once and "
            "contradict or qualify the repeated positions. Pay special attention to:\n"
            "   - Single sentences that reverse a position established over many paragraphs\n"
            "   - Qualifications buried in parentheses, footnotes, or subordinate clauses\n"
            "   - Statements introduced with 'perhaps,' 'it might seem,' or similar hedges\n"
            "   - Passages where the author briefly 'lets slip' a view quickly retracted\n\n"
            "3. For each unique statement found:\n"
            "   - Quote it precisely\n"
            "   - Identify the repeated contrary position\n"
            "   - Assess: does the unique statement represent the author's actual view?\n"
            "   - Why would the author state it only once?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Lessing's Seven Principles",
        "description": "Evaluate the text against Lessing's seven principles of esotericism as distilled by Strauss.",
        "system_prompt": (
            "You are an expert in esoteric writing. Leo Strauss distilled Lessing's view of "
            "esotericism into seven principles:\n\n"
            "1. All ancient philosophers distinguished between exoteric and esoteric teaching.\n"
            "2. The exoteric presentation uses statements the philosopher considers 'mere "
            "possibilities' — not facts, but claims useful for their audience.\n"
            "3. Exoteric statements could not occur within the esoteric teaching itself.\n"
            "4. Exoteric statements are made for reasons of prudence or expediency.\n"
            "5. Some exoteric statements address morally inferior people who would be "
            "frightened by the truth.\n"
            "6. There are certain truths which must be concealed.\n"
            "7. The best political constitution is necessarily imperfect, and theoretical life "
            "is superior to practical or political life.\n\n"
            "Use these as a diagnostic checklist for analyzing the text."
        ),
        "user_prompt_template": (
            "Evaluate the following text against Lessing's Seven Principles of Esotericism:\n\n"
            "For each principle, assess whether the text exhibits it:\n\n"
            "1. DOUBLE TEACHING: Does the text have both an accessible surface and a hidden depth?\n"
            "2. MERE POSSIBILITIES: Does the author present certain claims as 'possibilities' "
            "rather than assertions? Which claims are hedged this way?\n"
            "3. INCOMPATIBILITY: Are there statements that could NOT coexist with the deeper "
            "teaching if both were stated plainly?\n"
            "4. PRUDENT CONCEALMENT: Is there evidence the author conceals views for strategic "
            "rather than intellectual reasons?\n"
            "5. AUDIENCE PROTECTION: Are there statements seemingly designed to comfort or "
            "reassure readers who might be disturbed by the full truth?\n"
            "6. DANGEROUS TRUTHS: What truths, if any, does the text seem to approach but "
            "pull back from stating directly?\n"
            "7. THEORY vs. PRACTICE: Does the text suggest a tension between the contemplative "
            "ideal and political engagement?\n\n"
            "Score: How many of the 7 principles are clearly present? (0-7)\n"
            "Overall assessment: Is this text likely written esoterically?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
]

PERSECUTION_TEMPLATES = [
    {
        "name": "Strauss: Persecution Reading (Full Method)",
        "description": "The complete method from 'Persecution and the Art of Writing' — Strauss's definitive rules for reading between the lines.",
        "system_prompt": (
            "You are applying Leo Strauss's complete method from 'Persecution and the Art of Writing' (1952). "
            "Strauss provides precise rules:\n\n"
            "NEGATIVE CRITERION: The book must have been composed in an era of persecution — when political, "
            "religious, or intellectual orthodoxy was enforced by law or custom.\n\n"
            "POSITIVE CRITERION: If an able writer with a clear mind and perfect knowledge of the orthodox view "
            "contradicts surreptitiously and as it were in passing one of its necessary presuppositions or "
            "consequences which he explicitly recognizes and maintains everywhere else, we can reasonably "
            "suspect he was opposed to the orthodox system as such.\n\n"
            "KEY PRINCIPLES:\n"
            "- The real opinion of an author is NOT necessarily identical with that which he expresses "
            "in the largest number of passages.\n"
            "- Views of characters in a drama/dialogue must NOT be identified with the author's views "
            "without proof.\n"
            "- If a master of writing commits blunders that would shame a high-school boy, assume they are intentional.\n"
            "- Contradictions too deliberate to be accidental point to the hidden teaching.\n"
            "- The author may use disreputable characters (devils, madmen, sophists, drunkards) to state truths "
            "he dare not state in his own name.\n"
            "- 'Obtrusively enigmatic features' serve as 'awakening stumbling blocks' for potential philosophers: "
            "obscurity of plan, contradictions, pseudonyms, inexact repetitions, strange expressions."
        ),
        "user_prompt_template": (
            "Apply Strauss's complete method from 'Persecution and the Art of Writing' to this text:\n\n"
            "1. PERSECUTION CONTEXT\n"
            "What orthodoxy (political, religious, intellectual) was enforced when this was written? "
            "What consequences did the author face for dissent?\n\n"
            "2. THE ORTHODOX SURFACE\n"
            "What orthodox views does the author explicitly maintain throughout most of the text? "
            "Which statements affirm the reigning pieties?\n\n"
            "3. THE SURREPTITIOUS CONTRADICTION\n"
            "Where does the author 'surreptitiously and as it were in passing' contradict a necessary "
            "presupposition of the orthodox view? Quote the passage precisely.\n\n"
            "4. DISREPUTABLE MOUTHPIECES\n"
            "Does the author use any disreputable characters (madmen, sophists, devils, foreigners, "
            "fools) to state views he cannot state in his own name? Which character speaks the "
            "author's truth?\n\n"
            "5. OBTRUSIVELY ENIGMATIC FEATURES\n"
            "Identify the 'stumbling blocks' meant to awaken careful readers:\n"
            "- Obscurity of plan (is the structure deliberately confusing?)\n"
            "- Contradictions (between parts, or with known facts)\n"
            "- Inexact repetitions (a passage repeated with significant changes)\n"
            "- Strange expressions (unusual word choices that invite reflection)\n"
            "- Pseudonyms or attributed speech\n\n"
            "6. THE HIDDEN TEACHING\n"
            "Based on the above, what is the philosophic truth the author communicates only between "
            "the lines? Who is meant to discover it?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Premodern vs. Modern Esotericism",
        "description": "Determine whether the text's esotericism is premodern (permanent concealment) or modern (temporary, aimed at eventual enlightenment).",
        "system_prompt": (
            "You are an expert in Leo Strauss's distinction between two fundamentally different types "
            "of esoteric writers:\n\n"
            "PREMODERN (Classical/Medieval): These authors believe the gulf between 'the wise' and "
            "'the vulgar' is permanent and natural. Philosophy is essentially a privilege of the few. "
            "They conceal their views not temporarily but for all time. Their exoteric teachings are "
            "'noble lies' or 'likely tales.' They write for potential philosophers who must be 'led "
            "step by step from popular views to the truth.' They see no possibility of universal "
            "enlightenment.\n\n"
            "MODERN (Enlightenment): These authors believe persecution is accidental, an outcome of "
            "faulty political construction. They look forward to universal education and 'the republic "
            "of universal light.' They conceal their views only enough to protect themselves, not to "
            "protect society from truth. Their goal is to enlighten ever more people. It is "
            "'comparatively easy to read between the lines of their books.'\n\n"
            "This distinction is crucial because the two types require entirely different reading strategies."
        ),
        "user_prompt_template": (
            "Analyze whether this text exhibits PREMODERN or MODERN esotericism:\n\n"
            "1. ATTITUDE TOWARD 'THE MANY'\n"
            "Does the author believe the gap between wise and vulgar is permanent or temporary? "
            "Does the text suggest universal enlightenment is possible?\n\n"
            "2. PURPOSE OF CONCEALMENT\n"
            "Is concealment aimed at:\n"
            "a) Permanently protecting society from dangerous truths (premodern)\n"
            "b) Temporarily protecting the author until society is ready (modern)\n\n"
            "3. LEVEL OF CONCEALMENT\n"
            "How deeply hidden is the esoteric teaching?\n"
            "- Easy to detect with moderate care (modern)\n"
            "- Requires long, careful study to detect (premodern)\n\n"
            "4. ATTITUDE TOWARD 'NOBLE LIES'\n"
            "Does the author treat exoteric statements as permanently necessary social supports, "
            "or as temporary expedients to be eventually replaced by truth?\n\n"
            "5. CLASSIFICATION: Premodern, Modern, or Mixed? Explain.\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
]

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
    for tmpl in STRAUSS_TEMPLATES + PERSECUTION_TEMPLATES + MELZER_TEMPLATES:
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
    for tmpl in STRAUSS_TEMPLATES + PERSECUTION_TEMPLATES + MELZER_TEMPLATES:
        conn.execute(
            text("DELETE FROM analysis_templates WHERE name = :name"),
            {"name": tmpl["name"]},
        )
