"""Seed esoteric analysis LLM templates (Strauss, Melzer, Lampert, Frazer)

Revision ID: 0061
Revises: 0060
"""
from alembic import op
from sqlalchemy import text

revision = "0061"
down_revision = "0060"


TEMPLATES = [
    # ── Strauss Five Keys (focused sub-analyses) ─────────────────────────────
    {
        "name": "Strauss: Center",
        "description": "Find what is hidden in the structural middle of the text.",
        "system_prompt": (
            "You are an expert in Leo Strauss's method of close reading. "
            "A central Straussian principle is that great authors hide their most dangerous teachings "
            "at the physical center of their text, where casual readers are least attentive."
        ),
        "user_prompt_template": (
            "Perform a CENTER analysis:\n\n"
            "1. Identify the structural center of the text (by word/section count).\n"
            "2. Quote or describe the content at and around that center.\n"
            "3. Why might this placement be deliberate?\n"
            "4. Compare central content to opening and closing.\n\n"
            "Text:\n{text}"
        ),
    },
    {
        "name": "Strauss: Contradiction",
        "description": "Flag deliberate contradictions — the pious statement is a bodyguard for the dangerous truth.",
        "system_prompt": (
            "You are an expert in Strauss's esoteric hermeneutics. Contradictions are deliberate: "
            "the conventional statement is a 'bodyguard' for the dangerous truth in the contradicting passage."
        ),
        "user_prompt_template": (
            "For each contradiction:\n"
            "1. Quote the conventional/surface statement.\n"
            "2. Quote the contradicting passage.\n"
            "3. Which is the 'bodyguard' and which the deeper teaching?\n"
            "4. What does the contradiction reveal about the author's true position?\n\n"
            "Text:\n{text}"
        ),
    },
    {
        "name": "Strauss: Silence",
        "description": "Identify conspicuous silences — what the author deliberately avoids discussing.",
        "system_prompt": (
            "You are an expert in Strauss's method. 'Secrecy is to a certain extent identical with rarity.' "
            "What all people say all the time is the opposite of a secret. Strategic silence is a primary esoteric technique."
        ),
        "user_prompt_template": (
            "Analyze the SILENCES in this text:\n"
            "1. What topics would readers expect to be addressed but are absent?\n"
            "2. Where does a list, argument, or parallel have a conspicuous gap?\n"
            "3. What questions does the text raise but never answer?\n"
            "4. What do these silences collectively point toward?\n\n"
            "Text:\n{text}"
        ),
    },
    {
        "name": "Strauss: Repetition with Variation",
        "description": "Find repeated formulations with subtle changes — 'there is never an identical repetition.'",
        "system_prompt": (
            "You are an expert in Strauss's hermeneutics. 'There is never a repetition which is an identical "
            "repetition; there is always a change.' When an author repeats a formulation with subtle changes, "
            "the variation IS the esoteric signal."
        ),
        "user_prompt_template": (
            "Find passages that repeat earlier formulations with changes:\n"
            "1. Quote the original and repeated versions side by side.\n"
            "2. What exactly changed — which words were added, removed, or substituted?\n"
            "3. Is the change significant? What does the variation reveal?\n"
            "4. Does the pattern of variations across the text tell a story?\n\n"
            "Text:\n{text}"
        ),
    },
    {
        "name": "Strauss: Boring Passages",
        "description": "Analyze tedious, dry sections — important teachings may hide where readers lose attention.",
        "system_prompt": (
            "You are an expert in Strauss's method. Great authors sometimes hide their most important "
            "teachings in deliberately boring, technical, or digressive passages — places where the casual "
            "reader's attention flags."
        ),
        "user_prompt_template": (
            "Identify the most BORING or tedious passages in this text:\n"
            "1. Which sections are unusually dry, technical, or digressive?\n"
            "2. Do any of these 'boring' passages contain surprisingly important claims if read carefully?\n"
            "3. Is the tedium deliberately constructed to ward off casual readers?\n"
            "4. What teaching is hidden in these overlooked sections?\n\n"
            "Text:\n{text}"
        ),
    },

    # ── Strauss methodological templates ──────────────────────────────────────
    {
        "name": "Strauss: Deliberate Anomalies",
        "description": "Find intentional blunders AND unique statements — errors too obvious to be accidental, claims made exactly once.",
        "system_prompt": (
            "You are an expert in two key Straussian principles:\n\n"
            "1. INTENTIONAL BLUNDERS: 'If a master of the art of writing commits such blunders "
            "as would shame an intelligent high-school boy, it is reasonable to assume they are intentional.'\n\n"
            "2. UNIQUE STATEMENTS: 'If an author makes a statement on a very important subject only once, "
            "while in all other places he either asserts its contrary or remains silent on the subject, "
            "students invariably ignore the unique statement.' The rare statement is the true one.\n\n"
            "Both are species of deliberate anomaly — deviations from the author's own patterns that serve as signals."
        ),
        "user_prompt_template": (
            "Analyze this text for DELIBERATE ANOMALIES:\n\n"
            "PART A — BLUNDERS:\n"
            "1. Factual errors the author would certainly have known\n"
            "2. Logical contradictions within close proximity\n"
            "3. Misquotations of well-known sources\n"
            "4. Numerical discrepancies (promising N points but giving N-1)\n"
            "5. Non sequiturs — what conclusion WOULD follow?\n\n"
            "PART B — UNIQUE STATEMENTS:\n"
            "1. What views are REPEATED throughout (the apparent consensus)?\n"
            "2. Are there claims made EXACTLY ONCE that contradict or qualify the repeated view?\n"
            "3. Quote each unique statement and the repeated contrary position.\n"
            "4. Does the unique statement represent the author's actual view?\n\n"
            "For each anomaly: is this accidental or deliberate? What does it teach?\n\n"
            "Text:\n{text}"
        ),
    },
    {
        "name": "Strauss: Lessing's Seven Principles",
        "description": "Evaluate the text against Lessing's seven principles of esotericism as distilled by Strauss.",
        "system_prompt": (
            "You apply Lessing's seven principles: (1) All ancients distinguished exoteric/esoteric teaching. "
            "(2) Exoteric statements are 'mere possibilities.' (3) Exoteric statements could not occur within "
            "the esoteric teaching. (4) Made for prudence/expediency. (5) Addressed to morally inferior people. "
            "(6) Certain truths must be concealed. (7) The best constitution is imperfect; theoretical life "
            "is superior to practical life."
        ),
        "user_prompt_template": (
            "Score this text against Lessing's 7 Principles (0-7):\n"
            "For each: is it PRESENT, ABSENT, or AMBIGUOUS? Cite evidence.\n"
            "1. Double teaching? 2. 'Mere possibilities'? 3. Incompatible layers?\n"
            "4. Prudent concealment? 5. Audience protection? 6. Dangerous truths?\n"
            "7. Theory vs. practice tension?\n\n"
            "Overall: Is this text likely written esoterically?\n\nText:\n{text}"
        ),
    },
    {
        "name": "Strauss: Persecution Reading (Full Method)",
        "description": "The complete method from 'Persecution and the Art of Writing' — all rules for reading between the lines.",
        "system_prompt": (
            "You apply Strauss's complete method:\n"
            "NEGATIVE CRITERION: Composed in an era of persecution (political/religious/intellectual orthodoxy enforced).\n"
            "POSITIVE CRITERION: An able writer surreptitiously contradicts 'in passing' a presupposition "
            "he maintains everywhere else.\n"
            "KEY RULES: The real opinion is NOT necessarily the most frequent one. Characters' views ≠ author's views. "
            "Blunders that shame a high-school boy are intentional. Disreputable characters (devils, madmen, sophists) "
            "may voice the author's truth. 'Obtrusively enigmatic features' — obscurity of plan, contradictions, "
            "pseudonyms, inexact repetitions, strange expressions — are 'awakening stumbling blocks.'"
        ),
        "user_prompt_template": (
            "Apply the full Persecution method:\n"
            "1. PERSECUTION CONTEXT — What orthodoxy was enforced?\n"
            "2. THE ORTHODOX SURFACE — What pieties does the author maintain?\n"
            "3. THE SURREPTITIOUS CONTRADICTION — Where does the author contradict a presupposition 'in passing'?\n"
            "4. DISREPUTABLE MOUTHPIECES — Which characters voice forbidden truths?\n"
            "5. OBTRUSIVELY ENIGMATIC FEATURES — List all stumbling blocks.\n"
            "6. THE HIDDEN TEACHING — What is communicated only between the lines?\n\n"
            "Text:\n{text}"
        ),
    },
    {
        "name": "Strauss: Dialogue & Drama Analysis",
        "description": "Analyze how dialogue form conceals the author's teaching — 'Plato never said a word; only his characters do.'",
        "system_prompt": (
            "Key principles: The author hides behind ALL characters. The main character 'does NOT speak when "
            "the highest topic is discussed.' 'There is a connection between HIDING and arriving at a result "
            "which is only LIKELY to be true — a LIKELY TALE; the TRUE tale is hidden.' "
            "The dialogue form is chosen precisely because 'the truth is not fit for everybody.'"
        ),
        "user_prompt_template": (
            "1. WHO SPEAKS? List characters and their positions.\n"
            "2. WHO IS SILENT? On which topics does the protagonist defer?\n"
            "3. THE FRAME — Who narrates? What is the dramatic setting?\n"
            "4. LIKELY TALES — Which conclusions are presented as 'probable' vs. certain?\n"
            "5. THE AUTHOR — What can we infer from the ARRANGEMENT of the dialogue?\n\n"
            "Text:\n{text}"
        ),
    },

    # ── Classification templates ──────────────────────────────────────────────
    {
        "name": "Esotericism Classification",
        "description": "Classify the text's esotericism: Melzer's four forms (defensive/protective/pedagogical/political) AND premodern vs. modern.",
        "system_prompt": (
            "You classify esotericism using two frameworks:\n\n"
            "MELZER'S FOUR FORMS: (1) Defensive — hiding from persecution. (2) Protective — shielding society "
            "from dangerous truths. (3) Pedagogical — forcing active thought via obscurity. "
            "(4) Political — gradually spreading subversive ideas.\n\n"
            "STRAUSS'S TWO TYPES: PREMODERN/UNCONDITIONAL — the wise/vulgar gap is permanent; concealment is "
            "forever; philosophy is 'a privilege of the few.' MODERN/CONDITIONAL — persecution is accidental; "
            "concealment is temporary; the goal is universal enlightenment; 'comparatively easy to read between the lines.'\n\n"
            "A text may exhibit multiple forms and elements of both types."
        ),
        "user_prompt_template": (
            "Classify this text's esotericism:\n\n"
            "FOUR FORMS — For each, rate HIGH/MEDIUM/LOW/NOT PRESENT with evidence:\n"
            "1. Defensive 2. Protective 3. Pedagogical 4. Political\n"
            "PRIMARY FORM and why.\n\n"
            "TWO TYPES — Premodern or Modern?\n"
            "- Is the wise/vulgar gap treated as permanent or temporary?\n"
            "- Is concealment aimed at all time or until society is ready?\n"
            "- How deeply hidden is the esoteric teaching?\n\n"
            "Text:\n{text}"
        ),
    },

    # ── Structural/Source analysis ────────────────────────────────────────────
    {
        "name": "Strauss: Plan Obscurity & Reading the White",
        "description": "Analyze deliberate structural confusion AND strategic omissions — 'a lucid plan leaves no room for hiding places.'",
        "system_prompt": (
            "You analyze two related techniques:\n\n"
            "PLAN OBSCURITY: 'A lucid plan does not leave room for hiding places — an exoteric book will NOT "
            "have a very lucid plan.' But d'Alembert praised Montesquieu's 'wonderful, if hidden order.'\n\n"
            "READING THE WHITE (Galiani): 'Read the white, read what I did not write.' Strategic omissions "
            "communicate as much as explicit statements. Expected topics not addressed, truncated arguments, "
            "missing parallels, and unanswered questions all point toward the concealed teaching."
        ),
        "user_prompt_template": (
            "PART A — PLAN OBSCURITY:\n"
            "1. What is the apparent organization? Is it clear or confusing?\n"
            "2. Identify digressions — could they contain the actual teaching?\n"
            "3. Is there a hidden order beneath the surface confusion?\n"
            "4. 'What is written beautifully and in order, is NOT written beautifully and in order' — does this apply?\n\n"
            "PART B — READING THE WHITE:\n"
            "1. What expected topics are conspicuously absent?\n"
            "2. Where do arguments stop one step short of their natural conclusion?\n"
            "3. What questions are raised but never answered?\n"
            "4. What do the omissions collectively point toward?\n\n"
            "Text:\n{text}"
        ),
    },
    {
        "name": "Strauss: Authority & Source Analysis",
        "description": "Analyze how authorities are cited/framed AND how quotations are modified — the 'immunity of the commentator.'",
        "system_prompt": (
            "You analyze two related techniques:\n\n"
            "AUTHORITY FRAMING: Esoteric writers cite authorities in ways that superficially show deference "
            "but subtly undermine them — selective quotation, excessive praise as irony, juxtaposing authority "
            "with contradicting evidence.\n\n"
            "SOURCE TRANSFORMATION: When a careful author misquotes, the misquotation IS the message. "
            "Track modifications to quoted material — additions, omissions, rewordings.\n\n"
            "THE COMMENTATOR'S IMMUNITY: Strauss 'availed himself of the immunity of the commentator' — "
            "using commentary on others to state his own views. The commentary IS the author's teaching."
        ),
        "user_prompt_template": (
            "1. CITED AUTHORITIES — For each: Who? How framed (praise/irony/neutral)? Accurate or altered?\n"
            "2. SOURCE MODIFICATIONS — Which citations are inaccurate? What was changed and why?\n"
            "3. UNCITED IDEAS — Ideas from others presented without attribution?\n"
            "4. COMMENTATOR'S IMMUNITY — Is the author using commentary on others to express their own views?\n"
            "5. CITATION PATTERN — Dangerous sources cited cautiously? What does the pattern reveal?\n\n"
            "Text:\n{text}"
        ),
    },

    # ── Lampert-derived ───────────────────────────────────────────────────────
    {
        "name": "Strauss: Secret Words & False Statements",
        "description": "Identify systematic double-meaning vocabulary AND statements that are esoterically false but point toward hidden truths.",
        "system_prompt": (
            "You analyze two related Straussian techniques:\n\n"
            "SECRET WORDS: Strauss discovered that philosophical vocabulary carries systematic double meanings. "
            "Example: 'kalokagathia' (gentleman) = swear-word in Socratic circle; 'sophrosune' (self-control) = "
            "the art of concealment itself; 'dikaiosune' (justice) = 'has only its esoteric meaning' in the Republic. "
            "'The most honored words of everyday use are supplied with a meaning very different from their everyday sense.'\n\n"
            "ESOTERICALLY FALSE STATEMENTS: 'The false must in some sense be true as well.' When Socrates claims "
            "to concern himself 'only with ethical things,' this is false — but the falsity illuminates the "
            "relationship between ethics and being. The lie points to the concealed truth."
        ),
        "user_prompt_template": (
            "PART A — SECRET WORDS:\n"
            "1. Which words are used with unusual emphasis or frequency?\n"
            "2. Could any carry a second, ironic or philosophical meaning?\n"
            "3. Are any common words placed in quotes or italics?\n"
            "4. Compile a lexicon of candidate double-meaning words.\n\n"
            "PART B — FALSE STATEMENTS:\n"
            "1. Which central claims might be philosophically false?\n"
            "2. Why would the author state them anyway?\n"
            "3. 'In what sense is this thoroughly false principle also correct?'\n"
            "4. Are there statements where surface and esoteric readings are exact inversions?\n\n"
            "Text:\n{text}"
        ),
    },

    # ── Paratext ──────────────────────────────────────────────────────────────
    {
        "name": "Strauss: Paratext Analysis",
        "description": "Analyze titles, dedications, epigraphs, first/last sentences — paratextual elements where esoteric signals are strongest.",
        "system_prompt": (
            "Paratextual elements are the most revealing sites for esoteric signals: "
            "titles may have double meanings, dedications reveal true audience, epigraphs contain the key "
            "to the whole work, first and last sentences are almost always significant, and changes between "
            "editions reveal what the author reconsidered."
        ),
        "user_prompt_template": (
            "1. TITLE — Double meaning or ironic sense?\n"
            "2. DEDICATION/EPIGRAPH — Why chosen? Do they subvert the main text?\n"
            "3. PREFACE — What does the author say about method/purpose? Disclaimers as signals?\n"
            "4. FIRST AND LAST SENTENCES — Quote both. What is their relationship?\n"
            "5. CHAPTER TITLES — Do they tell a story different from the text?\n\n"
            "Text:\n{text}"
        ),
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for tmpl in TEMPLATES:
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
    for tmpl in TEMPLATES:
        conn.execute(
            text("DELETE FROM analysis_templates WHERE name = :name"),
            {"name": tmpl["name"]},
        )
