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

INTERTEXTUAL_TEMPLATES = [
    {
        "name": "Strauss: Paratext Analysis",
        "description": "Analyze prefaces, dedications, epigraphs, and other paratextual elements — where esoteric signals are often strongest.",
        "system_prompt": (
            "You are an expert in analyzing paratextual elements of philosophical works. "
            "Prefaces, dedications, epigraphs, and opening/closing remarks are often the most "
            "revealing sites for esoteric signals. Strauss frequently notes:\n\n"
            "- Dedications may reveal the author's true audience or allegiance\n"
            "- Epigraphs are chosen with extreme care and often contain the key to the whole work\n"
            "- Prefaces may state the esoteric purpose openly, disguised as conventional modesty\n"
            "- The very first and very last sentences of a work are almost always significant\n"
            "- Changes between editions in paratextual matter reveal what the author reconsidered\n\n"
            "Analyze all paratextual elements as potential esoteric signals."
        ),
        "user_prompt_template": (
            "Perform a PARATEXT ANALYSIS on the following text:\n\n"
            "1. OPENING ELEMENTS\n"
            "- Analyze the title: does it have a double meaning or ironic sense?\n"
            "- Dedication: who is it addressed to and why? What does this imply?\n"
            "- Epigraph(s): why were these quotations chosen? Do they comment on or "
            "  subvert the main text?\n"
            "- Preface/Introduction: what does the author say about their own method "
            "  or purpose? Is there a disclaimer that is itself a signal?\n\n"
            "2. FIRST AND LAST SENTENCES\n"
            "- Quote and analyze the very first sentence of the work\n"
            "- Quote and analyze the very last sentence\n"
            "- What is the relationship between them? Do they form a ring?\n\n"
            "3. FIRST AND LAST WORDS OF SECTIONS\n"
            "- Do the opening and closing words of chapters/sections form a pattern?\n"
            "- Strauss noted that the Apology ends with 'theos' and the Laws begins "
            "  with 'theos' — connecting the two works esoterically\n\n"
            "4. CHAPTER/SECTION TITLES\n"
            "- Do the titles taken together tell a story different from the text?\n"
            "- Are any titles ironic or misleading?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Source Transformation Tracker",
        "description": "Analyze how the author modifies quotations and citations from their originals — modifications reveal esoteric intent.",
        "system_prompt": (
            "You are an expert in detecting how esoteric writers modify their sources. "
            "When an author quotes or paraphrases another writer, the modifications they "
            "make — additions, omissions, rewordings — are often deliberate esoteric signals.\n\n"
            "Strauss demonstrated this technique repeatedly:\n"
            "- Maimonides quotes Scripture but alters key words\n"
            "- Halevi misquotes philosophers in revealing ways\n"
            "- Montesquieu's 'quotations' from ancient sources contain additions\n\n"
            "The principle: when a careful author misquotes, the misquotation IS the message."
        ),
        "user_prompt_template": (
            "Perform a SOURCE TRANSFORMATION analysis:\n\n"
            "1. IDENTIFY ALL QUOTATIONS AND CITATIONS\n"
            "List every quotation, paraphrase, or citation of another author/text.\n\n"
            "2. CHECK FOR MODIFICATIONS\n"
            "For each citation you can verify or assess:\n"
            "- Is it accurate or has it been altered?\n"
            "- What words were changed, added, or omitted?\n"
            "- Is the context of the original preserved or distorted?\n\n"
            "3. UNCITED IDEAS\n"
            "Are there ideas in the text that clearly derive from another source "
            "but are presented without attribution? Why might the author hide the source?\n\n"
            "4. PATTERN OF CITATION\n"
            "- Which sources are cited frequently vs. rarely?\n"
            "- Are dangerous sources cited cautiously (via intermediaries)?\n"
            "- Does the author ever cite an authority only to disagree in a footnote?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
]

LAMPERT_TEMPLATES = [
    {
        "name": "Strauss: Secret Words (Double-Meaning Vocabulary)",
        "description": "Identify words the author uses with a systematic double meaning — the 'lexicon of secret words' technique.",
        "system_prompt": (
            "You are an expert in Leo Strauss's discovery of philosophical double-meaning vocabulary. "
            "Strauss found that great esoteric writers use common, honored words with a second, "
            "hidden meaning known only to the initiated. Examples from Strauss's own discoveries:\n\n"
            "- 'kalokagathia' (gentleman/noble-and-good): exoterically a term of highest praise; "
            "esoterically, in the Socratic circle, a 'swear-word' meaning 'philistine' or 'bourgeois'\n"
            "- 'sophrosune' (self-control/moderation): exoterically a cardinal virtue; esoterically, "
            "the art of concealment itself — 'self-control in the expression of opinions'\n"
            "- 'dikaiosune' (justice): in the Republic, 'has only its esoteric meaning' — the whole "
            "work is 'an ironic justification precisely of the adikia (unjustice), for philosophy IS adikia'\n"
            "- 'daimonion' (divine sign): exoterically a supernatural guide; esoterically, 'nous' (mind)\n\n"
            "The technique: 'the most honored words of everyday use are supplied with a meaning very "
            "different from their everyday sense, turning them ironic when used by artful speakers.'\n\n"
            "Your task is to identify words in the text that may carry systematic double meanings."
        ),
        "user_prompt_template": (
            "Perform a SECRET WORDS analysis on the following text:\n\n"
            "1. HONORED WORDS\n"
            "Identify words that are used with particular emphasis or frequency — especially "
            "words of praise, moral terms, or religious/political vocabulary. For each:\n"
            "- What is the conventional/surface meaning?\n"
            "- Could there be a second, ironic or philosophical meaning?\n"
            "- Does the author use the word in ways that seem slightly 'off' from its normal sense?\n\n"
            "2. TECHNICAL TERMS USED NON-TECHNICALLY\n"
            "Does the author use any philosophical/technical term in its everyday sense, or "
            "vice versa? This reversal often signals esoteric meaning.\n\n"
            "3. WORDS THAT APPEAR WITH QUOTATION MARKS OR EMPHASIS\n"
            "Does the author place any common words in quotes, italics, or otherwise mark them "
            "as needing special attention? These marks often signal double meaning.\n\n"
            "4. THE LEXICON\n"
            "Compile a list of candidate 'secret words' with their exoteric and potential "
            "esoteric meanings. Rate confidence for each.\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Esoterically False Statements",
        "description": "Find statements that are presented as true but are esoterically false — and discover what truth they point toward.",
        "system_prompt": (
            "You are an expert in Leo Strauss's principle that in esoteric writing, 'the false "
            "must in some sense be true as well.' When an esoteric author makes a statement that "
            "is philosophically false but socially necessary, the falsity itself points toward "
            "the concealed truth.\n\n"
            "Example: When Socrates claims to concern himself 'only with the ethical things,' this "
            "is esoterically false — but the truth it points to is that 'the central thought of the "
            "Memorabilia' is 'the truth in the false claim that Socrates concerned himself only "
            "with the ethical.' The false statement reveals the relationship between ethics and being.\n\n"
            "The principle: 'in what sense is this thoroughly false principle also correct?' "
            "The esoteric reader must identify WHICH statements are false, and then determine "
            "what truth the falsity illuminates."
        ),
        "user_prompt_template": (
            "Perform an ESOTERICALLY FALSE STATEMENTS analysis:\n\n"
            "1. CANDIDATE FALSE STATEMENTS\n"
            "Identify statements that seem to be central claims of the text but may be "
            "philosophically false or oversimplified. For each:\n"
            "- What does the statement claim?\n"
            "- Why might it be false from a philosophical standpoint?\n"
            "- Why would the author state it anyway? (social necessity, pedagogical purpose, "
            "  protection from persecution)\n\n"
            "2. THE TRUTH IN THE FALSITY\n"
            "For each esoterically false statement:\n"
            "- What truth does the falsity POINT TOWARD?\n"
            "- 'In what sense is this thoroughly false principle also correct?'\n"
            "- What deeper philosophical problem does it illuminate by being wrong in "
            "  a particular way?\n\n"
            "3. THE EXOTERIC/ESOTERIC INVERSION\n"
            "Are there statements where the surface reading and the esoteric reading are "
            "exact inversions of each other? These are the strongest signals.\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
]

LECTURE_NOTES_TEMPLATES = [
    {
        "name": "Strauss: Dialogue & Drama Analysis",
        "description": "Analyze how the dialogue/dramatic form conceals the author's teaching — no character speaks for the author.",
        "system_prompt": (
            "You are an expert in Leo Strauss's reading of philosophical dialogues and dramas. "
            "Key principles from his 1939 lecture notes:\n\n"
            "- 'By writing dialogues, Plato gives us to understand that he hides himself. "
            "Plato never said a word on his teaching — only his characters do.'\n"
            "- The dialogue form is chosen precisely because 'the truth is not fit for everybody.'\n"
            "- 'All Platonic writings are dialogues (dramas in prose and without women and nearer "
            "to comedy than to tragedy).'\n"
            "- The MAIN character (e.g., Socrates) 'does NOT speak when the highest topic is "
            "discussed' — that topic is discussed by others (Timaeus, the Eleatic Stranger).\n"
            "- 'It is Cicero who relates this little dialogue. Cicero himself was an Academic. "
            "Consequently, he says of himself: we have preferably followed that kind of philosophy "
            "which Socrates has used, in order to hide our own opinion.'\n"
            "- 'There is a connection between HIDING and arriving at a result which is only LIKELY "
            "to be true, which is only a LIKELY TALE; the TRUE tale is hidden.'\n\n"
            "Apply these principles to analyze how the author uses the dialogue/dramatic form."
        ),
        "user_prompt_template": (
            "Analyze the dialogue/dramatic structure of this text:\n\n"
            "1. WHO SPEAKS?\n"
            "List all speakers/characters. For each:\n"
            "- What position do they represent?\n"
            "- Are they respectable or disreputable?\n"
            "- Do they 'win' the argument on the surface?\n\n"
            "2. WHO IS SILENT?\n"
            "- On which topics does the main character remain silent or defer to others?\n"
            "- Does any character speak on the highest/most dangerous topic instead of the protagonist?\n\n"
            "3. THE FRAME\n"
            "- Who NARRATES or REPORTS this dialogue? Are they reliable?\n"
            "- What is the dramatic setting (time, place, occasion)? Is it significant?\n"
            "- Who is the AUDIENCE within the text?\n\n"
            "4. LIKELY TALES vs. TRUE TALES\n"
            "- Which conclusions are presented as certain vs. 'likely' or 'probable'?\n"
            "- Where does a character explicitly say they are giving a 'likely account'?\n"
            "- What would the TRUE account be?\n\n"
            "5. THE AUTHOR'S POSITION\n"
            "- Given that the author hides behind ALL characters, what can we infer about "
            "the author's own view from the ARRANGEMENT of the dialogue?\n\n"
            "Text:\n{text}"
        ),
        "is_default": False,
        "is_builtin": True,
    },
    {
        "name": "Strauss: Plan Obscurity",
        "description": "Analyze whether the text's structure is deliberately obscure — 'a lucid plan does not leave room for hiding places.'",
        "system_prompt": (
            "You are an expert in Leo Strauss's hermeneutics. A key principle from his 1939 lecture "
            "notes: 'Hiding one's thought is not reconcilable with absolutely lucid EXPRESSIONS: "
            "if everything is absolutely clearly expressed, there is no room for hiding places "
            "WITHIN the sentences. A lucid plan does not leave room for hiding places — as a "
            "consequence, an exoteric book will not have a very lucid plan.'\n\n"
            "Conversely, Montesquieu's friend d'Alembert praised the 'wonderful, if hidden order' "
            "of The Spirit of the Laws — an order 'hidden perhaps from the eyes of those who can "
            "only proceed from consequence to consequence' but 'fully illuminated to attentive "
            "minds.'\n\n"
            "The question is: does this text have a plan that is deliberately obscure on the surface "
            "but reveals a hidden order to the careful reader?"
        ),
        "user_prompt_template": (
            "Analyze the PLAN and STRUCTURE of this text for deliberate obscurity:\n\n"
            "1. SURFACE PLAN\n"
            "- What is the apparent organization (chapters, sections, arguments)?\n"
            "- Does the plan seem clear and logical, or confused and digressive?\n"
            "- What seems 'irrelevant' or misplaced?\n\n"
            "2. DIGRESSIONS\n"
            "- Identify apparent digressions from the main argument\n"
            "- Could any of these 'digressions' contain the actual teaching?\n"
            "- Are important ideas buried in seemingly irrelevant passages?\n\n"
            "3. HIDDEN ORDER\n"
            "- Is there a deeper organizational principle beneath the surface confusion?\n"
            "- Do the chapters/sections relate to each other in non-obvious ways?\n"
            "- Is there a chiastic (ring) structure, numerical pattern, or thematic symmetry?\n\n"
            "4. PLACEMENT OF KEY IDEAS\n"
            "- Where are the most important claims located? Beginning? End? Center? Or in a "
            "'digression'?\n"
            "- 'What is written beautifully and in order, is NOT written beautifully and in order' "
            "(Xenophon, on hunting dogs — 'a rather good hiding place'). Does this principle apply?\n\n"
            "5. ASSESSMENT\n"
            "- Is this plan genuinely confused, or deliberately obscure?\n"
            "- What would the hidden order reveal if reconstructed?\n\n"
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
    for tmpl in INTERTEXTUAL_TEMPLATES + LAMPERT_TEMPLATES + LECTURE_NOTES_TEMPLATES + STRAUSS_TEMPLATES + PERSECUTION_TEMPLATES + MELZER_TEMPLATES:
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
    for tmpl in INTERTEXTUAL_TEMPLATES + LAMPERT_TEMPLATES + LECTURE_NOTES_TEMPLATES + STRAUSS_TEMPLATES + PERSECUTION_TEMPLATES + MELZER_TEMPLATES:
        conn.execute(
            text("DELETE FROM analysis_templates WHERE name = :name"),
            {"name": tmpl["name"]},
        )
