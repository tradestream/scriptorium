#!/usr/bin/env python3
"""
ESOTERIC WRITING ANALYZER
==========================
A computational toolkit for detecting potential esoteric writing techniques
in philosophical, religious, and literary texts.

Based on the methods described by:
  - Leo Strauss (Persecution and the Art of Writing, 1952)
  - Arthur Melzer (Philosophy Between the Lines, 2014)
  - Maimonides (Guide for the Perplexed, Introduction)
  - Francis Bacon (The Advancement of Learning, 1605)
  - The Pythagorean/Kabbalistic numerological traditions
  - Stanley Rosen (Hermeneutics as Politics; The Limits of Analysis;
    The Elusiveness of the Ordinary; Plato's Symposium)
  - Seth Benardete (Freedom and the Human Person; The Bow and the Lyre)
  - Leon Kass (Freedom and the Human Person)

METHODS DETECTED:
  1.  Contradiction Analysis — semantic tension between passages
  2.  Central Placement Analysis — where key ideas cluster in the structure
  3.  Numerological Analysis — chapter counts, gematria, isopsephy, structural numbers
  4.  Silence & Omission Analysis — expected topics conspicuously absent
  5.  Repetition & Emphasis Mapping — excessive praise or unusual frequency
  6.  Structural Symmetry (Chiastic/Ring) — mirror structures hiding a center
  7.  Sentiment Inversion Detection — potential irony markers
  8.  Digression Detection — passages that deviate from surrounding context
  9.  Lexical Density Mapping — where the author writes most carefully
  10. Acrostic & Telestic Detection — hidden messages in first/last letters
  11. Hapax Legomena Analysis — words used exactly once as deliberate signals
  12. Voice/Persona Consistency — detecting multiple speakers (Kierkegaard method)
  13. Register Analysis — rhetorical vs dialectical vs demonstrative tiers (Averroes)
  14. Logos/Mythos Transition Detection — genre shifts signaling limits of reason (Plato)
  15. Commentary Divergence Analysis — where commentary departs from source
  16. Polysemy Detection — words operating across multiple semantic domains (Dante)
  17. Aphoristic Fragmentation — compression, mask-shifts, self-contradiction (Nietzsche)
  18. Trapdoor Detection — local inconsistencies planted to force deeper reading (Benardete)
  19. Dyadic Structure — conjunctive/disjunctive twos, phantom images, eidetic analysis (Benardete)
  20. Periagoge Detection — structural reversal/turning, pathei mathos (Benardete/Plato)
  21. Logos-Ergon / Speech-Deed Analysis — mismatch between what is said and done (Benardete)
  22. Onomastic / Etymological Analysis — names as structural keys (Benardete)
  23. Recognition Structure — concealment-test-reveal pattern (Benardete)
  24. Nomos-Physis / Convention-Nature Analysis — natural vs cultural (Herodotean)
  25. Impossible Arithmetic / Poetic Dialectic — productive impossibilities (Benardete)
  26. Rhetoric of Concealment — hidden design beneath surface disorder (Rosen on Montesquieu)
  27. Transcendental Ambiguity — unresolved double meanings serving philosophy (Rosen on Kant)
  28. Rhetoric of Frankness — performative transparency as concealment (Rosen)
  29. Intuition-Analysis Dialectic — appeal to non-discursive knowing (Rosen, The Limits of Analysis)
  30. Logographic Necessity — dramatic/formal constraints as philosophical content (Benardete)
  31. Theological Disavowal — theology disguised as philosophy (Rosen)
  32. Defensive Writing — preemptive rebuttals and excessive qualification (Rosen/Strauss)
  33. Nature-Freedom Oscillation — systematic alternation between necessity and freedom (Rosen)
  34. Postmodern Misreading Vulnerability — what deconstruction exploits vs. misses (Rosen)
  35. Dramatic Context Analysis — speaker identity, audience, and setting as meaning (Rosen/Symposium)
  36. Speech Sequencing — successive speeches building, contradicting, transforming (Rosen/Symposium)
  37. Philosophical Comedy — serious content delivered through comic form (Rosen/Symposium)
  38. Daimonic Mediation — intermediate beings/concepts bridging opposites (Rosen/Symposium)
  39. Medicinal Rhetoric — speech adapted to the condition of the listener (Rosen/Symposium)
  40. Poetry-Philosophy Dialectic — the ancient quarrel and its productive tension (Rosen/Symposium)
  41. Aspiration-Achievement Gap — permanent gap between desire and possession (Rosen/Symposium)
  42. Synoptic Requirement — text demanding wider corpus knowledge (Rosen/Symposium)

Usage:
  analyzer = EsotericAnalyzer()
  analyzer.load_text("path/to/text.txt")           # or analyzer.load_text_string("...")
  report = analyzer.full_analysis()
  analyzer.export_report("analysis_report.md")

  # For comparing esoteric vs exoteric layers:
  comparison = analyzer.compare_layers()

  # For generating the LLM prompt:
  prompt = analyzer.generate_llm_prompt()
"""

import re
import math
import json
import statistics
from collections import Counter, defaultdict
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

# ---------------------------------------------------------------------------
# NUMEROLOGICAL TABLES
# ---------------------------------------------------------------------------

# Hebrew gematria (standard / mispar hechrachi)
GEMATRIA_TABLE = {
    'א': 1,   'ב': 2,   'ג': 3,   'ד': 4,   'ה': 5,
    'ו': 6,   'ז': 7,   'ח': 8,   'ט': 9,   'י': 10,
    'כ': 20,  'ך': 20,  'ל': 30,  'מ': 40,  'ם': 40,
    'נ': 50,  'ן': 50,  'ס': 60,  'ע': 70,  'פ': 80,
    'ף': 80,  'צ': 90,  'ץ': 90,  'ק': 100, 'ר': 200,
    'ש': 300, 'ת': 400,
}

# Greek isopsephy (Milesian numeral system)
ISOPSEPHY_TABLE = {
    'α': 1,   'β': 2,   'γ': 3,   'δ': 4,   'ε': 5,
    'ϛ': 6,   'ζ': 7,   'η': 8,   'θ': 9,   'ι': 10,
    'κ': 20,  'λ': 30,  'μ': 40,  'ν': 50,  'ξ': 60,
    'ο': 70,  'π': 80,  'ϟ': 90,  'ρ': 100, 'σ': 200,
    'ς': 200, 'τ': 300, 'υ': 400, 'φ': 500, 'χ': 600,
    'ψ': 700, 'ω': 800, 'ϡ': 900,
}

# Latin letter-number mapping (A=1, B=2, ... Z=26) for simple English analysis
LATIN_TABLE = {chr(i): i - 96 for i in range(97, 123)}

# Symbolically significant numbers across traditions
SIGNIFICANT_NUMBERS = {
    1:    "Unity, the One, the Monad (Pythagorean/Neoplatonic)",
    2:    "Dyad, division, the feminine, matter (Pythagorean)",
    3:    "Triad, harmony, the masculine, the Trinity (Pythagorean/Christian)",
    4:    "Tetractys, cosmic completeness (Pythagorean)",
    5:    "Pentad, marriage of 2+3, the human (Pythagorean); Pentateuch",
    6:    "Harmony, creation (6 days); perfect number",
    7:    "Sacred completeness (7 days, 7 planets, 7 liberal arts)",
    8:    "New beginning, resurrection (Christian); octave",
    9:    "Completion of the single digits; 3×3",
    10:   "Decad, perfection, the Tetractys sum (1+2+3+4); Ten Commandments; Sefirot",
    12:   "Cosmic order (12 tribes, 12 apostles, 12 zodiac signs)",
    13:   "Transgression, rebellion; 13 attributes of mercy (Jewish); death/rebirth",
    18:   "Chai (life) in gematria (חי = 8+10)",
    22:   "Letters of the Hebrew alphabet; paths on the Tree of Life",
    26:   "YHWH in gematria (10+5+6+5); Strauss on Machiavelli",
    28:   "Second perfect number (1+2+4+7+14)",
    32:   "Paths of wisdom (10 Sefirot + 22 letters); 32 Rules of Rabbi Eliezer",
    36:   "Double-chai (36 righteous ones / Lamed-Vav Tzadikim)",
    40:   "Trial, testing, purification (40 days flood, desert, Lent)",
    42:   "Name of God (Kabbalistic 42-letter name); 6×7",
    49:   "7×7, completeness squared; Jubilee eve; gates of understanding",
    50:   "Jubilee, freedom, Pentecost",
    70:   "Fullness of nations (70 nations); Sanhedrin",
    72:   "Names of God (Shemhamphorasch); 6×12",
    99:   "Near-perfection, the threshold",
    100:  "Fullness, completeness of a cycle",
    108:  "Sacred in Hindu/Buddhist traditions; 12×9",
    142:  "Chapters in Machiavelli's Discourses (= Livy's 141 books + 1)",
    216:  "One proposed value of Plato's Nuptial Number; 6³",
    318:  "Abraham's servants / gematria of Eliezer",
    666:  "Number of the Beast (Revelation); isopsephy of Nero Caesar",
}


# ---------------------------------------------------------------------------
# CORE ANALYZER CLASS
# ---------------------------------------------------------------------------

class EsotericAnalyzer:
    """
    Computational analysis engine for detecting esoteric writing techniques.

    The analyzer works by segmenting a text into structural units (chapters,
    sections, paragraphs) and applying a battery of quantitative tests
    corresponding to historically documented esoteric methods.

    Each test returns:
      - A numerical score (0.0–1.0) indicating strength of the signal
      - Specific textual evidence (passages, locations, patterns)
      - The esoteric method being tested and its historical precedent
    """

    def __init__(self):
        self.raw_text: str = ""
        self.title: str = ""
        self.chapters: list[dict] = []        # [{title, text, index, sentences, words}]
        self.paragraphs: list[str] = []
        self.sentences: list[str] = []
        self.words: list[str] = []
        self.stop_words = set(stopwords.words('english'))
        self.results: dict = {}
        self.expected_topics: list[str] = []   # user-supplied for silence analysis
        self.reference_texts: dict = {}        # {label: text} for source comparison

    # ------------------------------------------------------------------
    # TEXT LOADING
    # ------------------------------------------------------------------

    def load_text(self, filepath: str, title: str = ""):
        """Load text from a file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            self.raw_text = f.read()
        self.title = title or filepath.split('/')[-1]
        self._parse()

    def load_text_string(self, text: str, title: str = "Untitled"):
        """Load text directly from a string."""
        self.raw_text = text
        self.title = title
        self._parse()

    def set_expected_topics(self, topics: list[str]):
        """Set topics the text would be expected to address (for silence analysis)."""
        self.expected_topics = [t.lower() for t in topics]

    def add_reference_text(self, label: str, text: str):
        """Add a source text for distortion/comparison analysis."""
        self.reference_texts[label] = text

    def _parse(self):
        """Segment text into chapters, paragraphs, sentences, words."""
        # --- Chapters: detect common heading patterns ---
        chapter_pattern = r'(?:^|\n)(?:CHAPTER|Chapter|BOOK|Book|PART|Part|SECTION|Section)\s+[IVXLCDM\d]+[.:)]?\s*[^\n]*'
        splits = re.split(chapter_pattern, self.raw_text)
        headings = re.findall(chapter_pattern, self.raw_text)

        if len(headings) >= 2:
            self.chapters = []
            for i, heading in enumerate(headings):
                text = splits[i + 1] if i + 1 < len(splits) else ""
                sents = sent_tokenize(text)
                wrds = word_tokenize(text.lower())
                self.chapters.append({
                    'title': heading.strip(),
                    'text': text.strip(),
                    'index': i,
                    'sentences': sents,
                    'words': [w for w in wrds if w.isalpha()],
                })
        else:
            # No chapter markers: treat double-newline blocks as sections
            blocks = re.split(r'\n\s*\n', self.raw_text)
            blocks = [b.strip() for b in blocks if b.strip()]
            # Group into ~equal chunks if many small blocks
            chunk_size = max(1, len(blocks) // max(10, 1))
            self.chapters = []
            for i in range(0, len(blocks), max(chunk_size, 1)):
                chunk_text = "\n\n".join(blocks[i:i + chunk_size])
                sents = sent_tokenize(chunk_text)
                wrds = word_tokenize(chunk_text.lower())
                self.chapters.append({
                    'title': f"Section {i // max(chunk_size, 1) + 1}",
                    'text': chunk_text,
                    'index': len(self.chapters),
                    'sentences': sents,
                    'words': [w for w in wrds if w.isalpha()],
                })

        self.paragraphs = [p.strip() for p in re.split(r'\n\s*\n', self.raw_text) if p.strip()]
        self.sentences = sent_tokenize(self.raw_text)
        all_words = word_tokenize(self.raw_text.lower())
        self.words = [w for w in all_words if w.isalpha()]

    # ------------------------------------------------------------------
    # METHOD 1: CONTRADICTION ANALYSIS
    # ------------------------------------------------------------------

    def analyze_contradictions(self) -> dict:
        """
        METHOD: Contradiction Analysis
        PRECEDENT: Maimonides (7th cause), Strauss (the less emphatic statement
                   is likelier to be the author's true view), Al-Farabi (soul
                   immortality across works).

        Technique: Uses TF-IDF cosine similarity to find topically similar
        passages, then checks for sentiment/polarity inversion between them.
        High topical similarity + opposing sentiment = potential contradiction.
        """
        if len(self.paragraphs) < 3:
            return {'score': 0, 'evidence': [], 'method': 'Contradiction Analysis'}

        # Build TF-IDF matrix over paragraphs
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=5000,
            min_df=1,
            max_df=0.95,
        )
        try:
            tfidf = vectorizer.fit_transform(self.paragraphs)
        except ValueError:
            return {'score': 0, 'evidence': [], 'method': 'Contradiction Analysis'}

        sim_matrix = cosine_similarity(tfidf)

        # Negation and opposition markers
        negation_words = {
            'not', 'no', 'never', 'neither', 'nor', 'nothing', 'nowhere',
            'hardly', 'scarcely', 'barely', 'without', 'cannot', "can't",
            "don't", "doesn't", "didn't", "won't", "wouldn't", "shouldn't",
            "couldn't", "isn't", "aren't", "wasn't", "weren't",
        }
        opposition_words = {
            'but', 'however', 'yet', 'nevertheless', 'nonetheless',
            'although', 'contrary', 'opposite', 'whereas', 'instead',
            'rather', 'despite', 'notwithstanding', 'conversely',
        }

        def negation_density(text: str) -> float:
            words = word_tokenize(text.lower())
            if not words:
                return 0.0
            neg_count = sum(1 for w in words if w in negation_words)
            opp_count = sum(1 for w in words if w in opposition_words)
            return (neg_count + opp_count * 0.5) / len(words)

        contradictions = []
        n = len(self.paragraphs)
        for i in range(n):
            for j in range(i + 1, n):
                sim = sim_matrix[i, j]
                if sim > 0.25:  # topically related
                    neg_i = negation_density(self.paragraphs[i])
                    neg_j = negation_density(self.paragraphs[j])
                    neg_diff = abs(neg_i - neg_j)

                    if neg_diff > 0.02:
                        score = sim * neg_diff * 10
                        contradictions.append({
                            'paragraph_a': i + 1,
                            'paragraph_b': j + 1,
                            'topical_similarity': round(sim, 3),
                            'negation_differential': round(neg_diff, 4),
                            'tension_score': round(min(score, 1.0), 3),
                            'excerpt_a': self.paragraphs[i][:200] + "...",
                            'excerpt_b': self.paragraphs[j][:200] + "...",
                        })

        contradictions.sort(key=lambda x: x['tension_score'], reverse=True)
        top = contradictions[:15]

        overall = min(1.0, sum(c['tension_score'] for c in top) / max(len(top), 1))

        return {
            'score': round(overall, 3),
            'evidence': top,
            'method': 'Contradiction Analysis',
            'precedent': 'Maimonides 7th cause; Strauss on the less emphatic statement; Al-Farabi on the soul',
            'interpretation': (
                'High scores indicate passages that discuss the same topic but with '
                'inverted polarity. Per Strauss, in a genuine contradiction the more '
                'hidden or less emphatic formulation is likelier to represent the '
                "author's true position."
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 2: CENTRAL PLACEMENT ANALYSIS
    # ------------------------------------------------------------------

    def analyze_central_placement(self, key_terms: Optional[list[str]] = None) -> dict:
        """
        METHOD: Central Placement Analysis
        PRECEDENT: Strauss on Plato's Republic (philosopher-king at geometric center),
                   Strauss on Machiavelli's Discourses (radical chapters at center),
                   the general principle that heterodox ideas hide in the middle.

        Technique: Divides the text into positional quintiles (0-20%, 20-40%, 40-60%,
        60-80%, 80-100%) and measures where key philosophical terms, hedging language,
        and semantically dense passages cluster.
        """
        if not self.sentences:
            return {'score': 0, 'evidence': [], 'method': 'Central Placement'}

        # Default key terms that often mark philosophical claims
        if not key_terms:
            key_terms = [
                'truth', 'true', 'truly', 'nature', 'natural', 'reason',
                'soul', 'god', 'divine', 'justice', 'good', 'evil',
                'freedom', 'liberty', 'virtue', 'knowledge', 'wisdom',
                'death', 'immortal', 'eternal', 'power', 'law',
                'secret', 'hidden', 'conceal', 'reveal', 'mystery',
                'appear', 'seem', 'surface', 'beneath', 'beyond',
            ]

        key_terms_lower = set(t.lower() for t in key_terms)
        n = len(self.sentences)
        quintiles = {0: [], 1: [], 2: [], 3: [], 4: []}

        for i, sent in enumerate(self.sentences):
            q = min(4, int((i / n) * 5))
            words = word_tokenize(sent.lower())
            key_count = sum(1 for w in words if w in key_terms_lower)
            if words:
                density = key_count / len(words)
                quintiles[q].append((density, i, sent))

        # Average density per quintile
        avg_density = {}
        for q in range(5):
            if quintiles[q]:
                avg_density[q] = statistics.mean(d for d, _, _ in quintiles[q])
            else:
                avg_density[q] = 0.0

        labels = {0: "Opening (0-20%)", 1: "Early (20-40%)", 2: "CENTER (40-60%)",
                  3: "Late (60-80%)", 4: "Closing (80-100%)"}

        # Score: how much does the center exceed the periphery?
        center = avg_density[2]
        periphery = statistics.mean([avg_density[0], avg_density[1], avg_density[3], avg_density[4]])
        ratio = center / periphery if periphery > 0 else 0
        score = min(1.0, max(0, (ratio - 1.0)))  # 0 if center ≤ periphery

        # Top sentences from center
        center_sents = sorted(quintiles[2], key=lambda x: x[0], reverse=True)[:5]

        return {
            'score': round(score, 3),
            'quintile_densities': {labels[q]: round(avg_density[q], 5) for q in range(5)},
            'center_ratio_to_periphery': round(ratio, 3),
            'top_center_sentences': [
                {'sentence_index': idx, 'density': round(d, 4), 'text': s[:200]}
                for d, idx, s in center_sents
            ],
            'method': 'Central Placement Analysis',
            'precedent': "Strauss on Republic's center; Machiavelli's central chapters",
            'interpretation': (
                'A ratio > 1.0 means key philosophical terms cluster more heavily '
                'in the center of the work than at the edges. Scores above 0.3 are '
                'noteworthy. The center is where casual readers are least attentive '
                'and where esoteric writers historically place their most radical claims.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 3: NUMEROLOGICAL ANALYSIS
    # ------------------------------------------------------------------

    def analyze_numerology(self) -> dict:
        """
        METHOD: Numerological Analysis
        PRECEDENT: Pythagorean number symbolism, Hebrew gematria, Greek isopsephy,
                   Strauss on Machiavelli's 142 chapters and patterns of 13/26,
                   Plato's Nuptial Number.

        Technique: Counts structural units (chapters, paragraphs, sentences, words)
        and checks them against a table of symbolically significant numbers. Also
        examines ratios, factors, and patterns.
        """
        counts = {
            'chapters': len(self.chapters),
            'paragraphs': len(self.paragraphs),
            'sentences': len(self.sentences),
            'words': len(self.words),
        }

        # Check each count against significant numbers
        hits = []
        for label, count in counts.items():
            if count in SIGNIFICANT_NUMBERS:
                hits.append({
                    'unit': label,
                    'count': count,
                    'significance': SIGNIFICANT_NUMBERS[count],
                })
            # Check factors
            for sig_num, meaning in SIGNIFICANT_NUMBERS.items():
                if sig_num > 1 and count > sig_num and count % sig_num == 0:
                    hits.append({
                        'unit': label,
                        'count': count,
                        'divisible_by': sig_num,
                        'quotient': count // sig_num,
                        'significance': f"Divisible by {sig_num}: {meaning}",
                    })

        # Chapter word counts — look for patterns
        chapter_word_counts = [len(ch['words']) for ch in self.chapters]
        chapter_patterns = {}
        if chapter_word_counts:
            chapter_patterns = {
                'counts': chapter_word_counts,
                'mean': round(statistics.mean(chapter_word_counts), 1),
                'median': round(statistics.median(chapter_word_counts), 1),
                'stdev': round(statistics.stdev(chapter_word_counts), 1) if len(chapter_word_counts) > 1 else 0,
            }
            # Identify outlier chapters (much longer or shorter than average)
            if len(chapter_word_counts) > 2:
                mean = statistics.mean(chapter_word_counts)
                std = statistics.stdev(chapter_word_counts) if statistics.stdev(chapter_word_counts) > 0 else 1
                outliers = []
                for i, wc in enumerate(chapter_word_counts):
                    z = (wc - mean) / std
                    if abs(z) > 1.5:
                        outliers.append({
                            'chapter': i + 1,
                            'title': self.chapters[i]['title'],
                            'word_count': wc,
                            'z_score': round(z, 2),
                            'note': 'Unusually LONG' if z > 0 else 'Unusually SHORT',
                        })
                chapter_patterns['outlier_chapters'] = outliers

        # Gematria/Isopsephy of the title
        title_numerology = {}
        if self.title:
            latin_val = sum(LATIN_TABLE.get(c, 0) for c in self.title.lower() if c.isalpha())
            title_numerology['latin_sum'] = latin_val
            if latin_val in SIGNIFICANT_NUMBERS:
                title_numerology['latin_significance'] = SIGNIFICANT_NUMBERS[latin_val]
            # Check for Hebrew/Greek characters in title
            hebrew_val = sum(GEMATRIA_TABLE.get(c, 0) for c in self.title)
            if hebrew_val > 0:
                title_numerology['hebrew_gematria'] = hebrew_val
                if hebrew_val in SIGNIFICANT_NUMBERS:
                    title_numerology['hebrew_significance'] = SIGNIFICANT_NUMBERS[hebrew_val]
            greek_val = sum(ISOPSEPHY_TABLE.get(c, 0) for c in self.title.lower())
            if greek_val > 0:
                title_numerology['greek_isopsephy'] = greek_val
                if greek_val in SIGNIFICANT_NUMBERS:
                    title_numerology['greek_significance'] = SIGNIFICANT_NUMBERS[greek_val]

        score = min(1.0, len(hits) * 0.1)

        return {
            'score': round(score, 3),
            'structural_counts': counts,
            'significant_number_hits': hits[:20],
            'chapter_word_count_patterns': chapter_patterns,
            'title_numerology': title_numerology,
            'method': 'Numerological Analysis',
            'precedent': (
                "Pythagorean number symbolism; Hebrew gematria; Greek isopsephy; "
                "Strauss on Machiavelli's 142 chapters and the number 26 (YHWH); "
                "Plato's Nuptial Number"
            ),
            'interpretation': (
                'Significant-number hits do not prove esotericism by themselves. '
                'They become meaningful when combined with other signals — e.g., '
                'if the number of chapters matches a symbolically loaded number AND '
                'the central chapter contains the most radical content.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 4: SILENCE & OMISSION ANALYSIS
    # ------------------------------------------------------------------

    def analyze_silence(self) -> dict:
        """
        METHOD: Silence & Omission Analysis
        PRECEDENT: Strauss on Machiavelli's silences; Plato's conspicuous omissions;
                   the general principle that what is NOT said can be as significant
                   as what IS said.

        Technique: Given a list of expected topics (user-supplied or derived from
        the text's genre), checks which topics are absent or dramatically
        underrepresented relative to what the text does discuss.
        """
        if not self.expected_topics:
            return {
                'score': 0,
                'evidence': [],
                'method': 'Silence & Omission Analysis',
                'note': 'No expected topics provided. Call set_expected_topics() with a list of topics this text would be expected to address.',
            }

        text_lower = self.raw_text.lower()
        word_freq = Counter(self.words)
        total_words = len(self.words)

        topic_presence = {}
        for topic in self.expected_topics:
            # Check both exact word and as substring
            topic_words = topic.lower().split()
            exact_count = sum(word_freq.get(tw, 0) for tw in topic_words)
            substring_count = text_lower.count(topic.lower())
            combined = max(exact_count, substring_count)
            frequency = combined / total_words if total_words > 0 else 0
            topic_presence[topic] = {
                'occurrences': combined,
                'frequency': round(frequency, 6),
                'status': 'ABSENT' if combined == 0 else ('RARE' if frequency < 0.0005 else 'PRESENT'),
            }

        absent = [t for t, v in topic_presence.items() if v['status'] == 'ABSENT']
        rare = [t for t, v in topic_presence.items() if v['status'] == 'RARE']

        score = min(1.0, (len(absent) * 0.3 + len(rare) * 0.1))

        return {
            'score': round(score, 3),
            'topic_analysis': topic_presence,
            'absent_topics': absent,
            'rare_topics': rare,
            'method': 'Silence & Omission Analysis',
            'precedent': "Strauss on Machiavelli's theological silences; Plato's omissions",
            'interpretation': (
                'Absent or rare topics are significant only when the genre, declared '
                'subject, and historical context would lead a reader to EXPECT their '
                "discussion. A political treatise's silence on divine right, or a "
                "theological work's silence on a particular doctrine, is the kind of "
                'omission that may constitute a negative argument.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 5: REPETITION & EMPHASIS MAPPING
    # ------------------------------------------------------------------

    def analyze_repetition(self) -> dict:
        """
        METHOD: Repetition & Emphasis Mapping
        PRECEDENT: Strauss on "excessive or conspicuous praise" as a signal of
                   disagreement — the author who praises orthodoxy too loudly may
                   be protesting too much.

        Technique: Identifies words and phrases with unusually high frequency
        relative to the text's baseline, especially evaluative/praise terms.
        Tracks where emphasis clusters spatially.
        """
        # Evaluative and praise vocabulary
        praise_words = {
            'excellent', 'noble', 'divine', 'sacred', 'holy', 'pious',
            'virtuous', 'glorious', 'magnificent', 'admirable', 'sublime',
            'wonderful', 'worthy', 'honorable', 'great', 'good', 'best',
            'perfect', 'wise', 'beautiful', 'just', 'righteous', 'blessed',
            'praiseworthy', 'venerable', 'revered', 'illustrious',
        }
        hedge_words = {
            'perhaps', 'maybe', 'possibly', 'seemingly', 'apparently',
            'it seems', 'one might say', 'it appears', 'as it were',
            'so to speak', 'in a manner', 'as they say',
        }

        word_freq = Counter(self.words)
        total = len(self.words)

        # Top repeated content words (excluding stopwords)
        content_words = {w: c for w, c in word_freq.items()
                         if w not in self.stop_words and len(w) > 3}
        top_repeated = sorted(content_words.items(), key=lambda x: x[1], reverse=True)[:30]

        # Praise density per chapter
        praise_by_chapter = []
        for ch in self.chapters:
            ch_words = ch['words']
            if not ch_words:
                continue
            praise_count = sum(1 for w in ch_words if w in praise_words)
            hedge_count = sum(1 for w in ch_words if w in hedge_words)
            praise_density = praise_count / len(ch_words)
            hedge_density = hedge_count / len(ch_words)
            praise_by_chapter.append({
                'chapter': ch['index'] + 1,
                'title': ch['title'],
                'praise_density': round(praise_density, 5),
                'hedge_density': round(hedge_density, 5),
                'praise_count': praise_count,
                'hedge_count': hedge_count,
            })

        # Overall praise density
        overall_praise = sum(1 for w in self.words if w in praise_words) / total if total > 0 else 0
        overall_hedge = sum(1 for w in self.words if w in hedge_words) / total if total > 0 else 0

        # Find chapters with praise density > 2× average (suspicious emphasis)
        if praise_by_chapter:
            avg_praise = statistics.mean(p['praise_density'] for p in praise_by_chapter)
            suspicious = [p for p in praise_by_chapter
                          if avg_praise > 0 and p['praise_density'] > 2 * avg_praise]
        else:
            avg_praise = 0
            suspicious = []

        score = min(1.0, len(suspicious) * 0.15 + (overall_praise * 50))

        return {
            'score': round(score, 3),
            'top_repeated_words': top_repeated[:20],
            'overall_praise_density': round(overall_praise, 5),
            'overall_hedge_density': round(overall_hedge, 5),
            'praise_by_chapter': praise_by_chapter,
            'suspiciously_emphatic_chapters': suspicious,
            'method': 'Repetition & Emphasis Mapping',
            'precedent': 'Strauss on excessive/conspicuous praise as a signal of disagreement',
            'interpretation': (
                'Chapters with unusually high praise density relative to the text\'s '
                'average may signal what Strauss called "protesting too much." High '
                'hedge-word density in combination suggests the author is qualifying '
                'claims they do not fully endorse.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 6: STRUCTURAL SYMMETRY (CHIASTIC / RING COMPOSITION)
    # ------------------------------------------------------------------

    def analyze_symmetry(self) -> dict:
        """
        METHOD: Structural Symmetry / Ring Composition
        PRECEDENT: Mary Douglas (Thinking in Circles), Plato's dialogues,
                   biblical ring compositions, Homeric chiasmus.
                   In ring/chiastic structures, the most important content
                   occupies the pivot (center) — the "turning point."

        Technique: Compares the first half of the work's chapters to the
        reversed second half using TF-IDF cosine similarity. High symmetry
        between chapter i and chapter (n-1-i) suggests ring composition.
        """
        if len(self.chapters) < 4:
            return {'score': 0, 'evidence': [], 'method': 'Structural Symmetry'}

        texts = [ch['text'] for ch in self.chapters]
        n = len(texts)

        vectorizer = TfidfVectorizer(stop_words='english', max_features=3000)
        try:
            tfidf = vectorizer.fit_transform(texts)
        except ValueError:
            return {'score': 0, 'evidence': [], 'method': 'Structural Symmetry'}

        sim_matrix = cosine_similarity(tfidf)

        # Compare mirror pairs: chapter i with chapter (n-1-i)
        pairs = []
        half = n // 2
        for i in range(half):
            j = n - 1 - i
            if i != j:
                sim = sim_matrix[i, j]
                pairs.append({
                    'chapter_a': i + 1,
                    'chapter_b': j + 1,
                    'title_a': self.chapters[i]['title'],
                    'title_b': self.chapters[j]['title'],
                    'mirror_similarity': round(float(sim), 3),
                })

        # Average adjacent similarity (how similar each chapter is to its neighbor)
        adjacent_sims = []
        for i in range(n - 1):
            adjacent_sims.append(float(sim_matrix[i, i + 1]))
        avg_adjacent = statistics.mean(adjacent_sims) if adjacent_sims else 0

        # Average mirror similarity
        mirror_sims = [p['mirror_similarity'] for p in pairs]
        avg_mirror = statistics.mean(mirror_sims) if mirror_sims else 0

        # Ring composition score: mirror similarity should be notably higher
        # than what you'd expect from random chapter pairs
        all_pairs_sim = []
        for i in range(n):
            for j in range(i + 1, n):
                all_pairs_sim.append(float(sim_matrix[i, j]))
        avg_all = statistics.mean(all_pairs_sim) if all_pairs_sim else 0

        ratio = avg_mirror / avg_all if avg_all > 0 else 0
        score = min(1.0, max(0, (ratio - 1.0) * 2))

        return {
            'score': round(score, 3),
            'mirror_pairs': pairs,
            'avg_mirror_similarity': round(avg_mirror, 3),
            'avg_adjacent_similarity': round(avg_adjacent, 3),
            'avg_all_pairs_similarity': round(avg_all, 3),
            'mirror_to_baseline_ratio': round(ratio, 3),
            'method': 'Structural Symmetry / Ring Composition',
            'precedent': (
                "Mary Douglas on ring composition; Platonic dialogue structure; "
                "biblical chiasmus; the principle that the pivot/center of a "
                "ring structure carries the most important content"
            ),
            'interpretation': (
                'A mirror-to-baseline ratio above 1.2 suggests the text may have '
                'ring or chiastic structure. In such structures, the CENTER — the '
                'pivot point that the ring surrounds — is where the author places '
                'the essential but often most heterodox content.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 7: SENTIMENT INVERSION / IRONY DETECTION
    # ------------------------------------------------------------------

    def analyze_irony(self) -> dict:
        """
        METHOD: Sentiment Inversion Detection
        PRECEDENT: Socratic irony; Strauss on the gap between surface praise
                   and underlying critique; Kierkegaard on irony as indirect
                   communication.

        Technique: Identifies sentences with mixed or inverted sentiment signals —
        praise vocabulary combined with negation or qualification, or positive
        framing of negative content.
        """
        irony_markers = []
        praise_set = {
            'excellent', 'noble', 'divine', 'sacred', 'holy', 'pious',
            'virtuous', 'glorious', 'admirable', 'wise', 'great', 'good',
            'perfect', 'beautiful', 'just', 'wonderful', 'magnificent',
        }
        negation_set = {
            'not', 'no', 'never', 'hardly', 'scarcely', 'barely',
            'without', 'cannot', "can't", "don't", "doesn't",
        }
        qualifier_set = {
            'perhaps', 'maybe', 'seemingly', 'apparently', 'supposedly',
            'so-called', 'alleged', 'professed', 'ostensibly', 'nominally',
        }

        for i, sent in enumerate(self.sentences):
            words = set(word_tokenize(sent.lower()))
            has_praise = bool(words & praise_set)
            has_negation = bool(words & negation_set)
            has_qualifier = bool(words & qualifier_set)

            if has_praise and (has_negation or has_qualifier):
                irony_markers.append({
                    'sentence_index': i + 1,
                    'text': sent[:250],
                    'praise_words': list(words & praise_set),
                    'negation_words': list(words & negation_set),
                    'qualifier_words': list(words & qualifier_set),
                    'type': 'Praised concept + negation' if has_negation else 'Praised concept + qualification',
                })

        score = min(1.0, len(irony_markers) / max(len(self.sentences) * 0.05, 1))

        return {
            'score': round(score, 3),
            'irony_markers': irony_markers[:20],
            'total_markers': len(irony_markers),
            'method': 'Sentiment Inversion / Irony Detection',
            'precedent': 'Socratic irony; Strauss on surface praise concealing critique; Kierkegaard on indirect communication',
            'interpretation': (
                'Sentences combining praise vocabulary with negation or qualification '
                'may signal irony — the author says something positive while subtly '
                'undermining it. This is computationally approximate; true irony '
                'detection requires contextual understanding beyond what NLP can provide.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 8: DIGRESSION DETECTION
    # ------------------------------------------------------------------

    def analyze_digressions(self) -> dict:
        """
        METHOD: Digression Detection
        PRECEDENT: Strauss on unusual examples that don't fit the stated argument;
                   Maimonides' scattered chapters; Bacon on the aphoristic method.

        Technique: Measures the topical coherence of each paragraph/section with
        its neighbors. Passages with low similarity to their context may be
        deliberate digressions carrying hidden significance.
        """
        if len(self.paragraphs) < 5:
            return {'score': 0, 'evidence': [], 'method': 'Digression Detection'}

        vectorizer = TfidfVectorizer(stop_words='english', max_features=3000)
        try:
            tfidf = vectorizer.fit_transform(self.paragraphs)
        except ValueError:
            return {'score': 0, 'evidence': [], 'method': 'Digression Detection'}

        sim_matrix = cosine_similarity(tfidf)
        n = len(self.paragraphs)

        # For each paragraph, compute average similarity to neighbors (window of 2)
        coherence_scores = []
        for i in range(n):
            neighbors = []
            for j in range(max(0, i - 2), min(n, i + 3)):
                if i != j:
                    neighbors.append(sim_matrix[i, j])
            local_coherence = statistics.mean(neighbors) if neighbors else 0
            coherence_scores.append(local_coherence)

        # Find paragraphs with notably low local coherence (digressions)
        if len(coherence_scores) > 2:
            mean_coh = statistics.mean(coherence_scores)
            std_coh = statistics.stdev(coherence_scores) if statistics.stdev(coherence_scores) > 0 else 0.01
            digressions = []
            for i, coh in enumerate(coherence_scores):
                z = (coh - mean_coh) / std_coh
                if z < -1.0:
                    position_pct = round((i / n) * 100, 1)
                    digressions.append({
                        'paragraph_index': i + 1,
                        'position_in_text': f"{position_pct}%",
                        'local_coherence': round(coh, 3),
                        'z_score': round(z, 2),
                        'excerpt': self.paragraphs[i][:250] + "...",
                    })
        else:
            digressions = []

        score = min(1.0, len(digressions) * 0.1)

        return {
            'score': round(score, 3),
            'digressions': digressions[:15],
            'total_digressions': len(digressions),
            'method': 'Digression Detection',
            'precedent': "Strauss on unusual examples; Maimonides' scattered chapters; Bacon's aphoristic method",
            'interpretation': (
                'Paragraphs with low local coherence — topically distant from their '
                'immediate neighbors — may be deliberate digressions. In the esoteric '
                'tradition, digressions often carry the real argument: the author '
                'embeds a crucial point in an apparently irrelevant aside.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 9: LEXICAL DENSITY MAPPING
    # ------------------------------------------------------------------

    def analyze_lexical_density(self) -> dict:
        """
        METHOD: Lexical Density Mapping
        PRECEDENT: Melzer on literal reading — the esoteric author writes most
                   carefully at the most important moments. Unusual lexical density
                   (high type-token ratio, rare vocabulary) signals heightened
                   authorial attention.

        Technique: Computes type-token ratio and average word length per chapter/
        section, identifying where the author's prose is most compressed and
        carefully constructed.
        """
        chapter_density = []
        for ch in self.chapters:
            words = ch['words']
            if not words:
                continue
            types = set(words)
            ttr = len(types) / len(words) if words else 0
            avg_word_len = statistics.mean(len(w) for w in words)
            rare_words = [w for w in types if w not in self.stop_words and len(w) > 8]
            chapter_density.append({
                'chapter': ch['index'] + 1,
                'title': ch['title'],
                'word_count': len(words),
                'unique_words': len(types),
                'type_token_ratio': round(ttr, 4),
                'avg_word_length': round(avg_word_len, 2),
                'rare_word_count': len(rare_words),
                'rare_word_sample': rare_words[:10],
            })

        if len(chapter_density) > 1:
            ttrs = [c['type_token_ratio'] for c in chapter_density]
            mean_ttr = statistics.mean(ttrs)
            std_ttr = statistics.stdev(ttrs) if len(ttrs) > 1 else 0.01
            for cd in chapter_density:
                cd['ttr_z_score'] = round((cd['type_token_ratio'] - mean_ttr) / std_ttr, 2) if std_ttr > 0 else 0

            # High-density chapters
            dense_chapters = [c for c in chapter_density if c.get('ttr_z_score', 0) > 1.0]
        else:
            dense_chapters = []

        score = min(1.0, len(dense_chapters) * 0.15)

        return {
            'score': round(score, 3),
            'chapter_density': chapter_density,
            'high_density_chapters': dense_chapters,
            'method': 'Lexical Density Mapping',
            'precedent': "Melzer on literal reading; the esoteric author's heightened care at crucial moments",
            'interpretation': (
                'Chapters with unusually high type-token ratio (many unique words '
                'relative to total) and longer average word length suggest the author '
                'is writing with heightened precision. When these chapters coincide '
                'with central placement or contradiction signals, the convergence '
                'strengthens the case for deliberate esotericism.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 10: ACROSTIC & TELESTIC DETECTION
    # ------------------------------------------------------------------

    def analyze_acrostics(self) -> dict:
        """
        METHOD: Acrostic & Telestic Detection
        PRECEDENT: 14 alphabetic acrostics in the Hebrew Bible (Psalms, Proverbs,
                   Lamentations, Nahum); medieval Jewish liturgical poetry;
                   classical Latin acrostics (Virgil, Aeneid); Renaissance
                   steganography.

        Technique: Extracts the first letter of each sentence, paragraph, and
        chapter, and the last letter of each, then checks for:
          - Alphabetic sequences (A-B-C... or Hebrew aleph-bet order)
          - Recognizable words or names spelled out
          - Repeated patterns or palindromes
          - Statistical deviation from expected letter frequencies
        """
        results_data = {}

        # --- Sentence-level acrostic ---
        sent_first_letters = ""
        sent_last_letters = ""
        for sent in self.sentences:
            words = [w for w in word_tokenize(sent) if w.isalpha()]
            if words:
                sent_first_letters += words[0][0].lower()
                sent_last_letters += words[-1][-1].lower()

        # --- Paragraph-level acrostic ---
        para_first_letters = ""
        para_last_letters = ""
        for para in self.paragraphs:
            words = [w for w in word_tokenize(para) if w.isalpha()]
            if words:
                para_first_letters += words[0][0].lower()
                para_last_letters += words[-1][-1].lower()

        # --- Chapter-level acrostic ---
        ch_first_letters = ""
        ch_last_letters = ""
        for ch in self.chapters:
            words = ch['words']
            if words:
                ch_first_letters += words[0][0].lower()
                ch_last_letters += words[-1][-1].lower()

        def find_patterns(letter_seq: str, label: str) -> list:
            """Search a letter sequence for meaningful patterns."""
            findings = []
            if len(letter_seq) < 3:
                return findings

            # Check for alphabetic runs (3+ consecutive letters in order)
            for i in range(len(letter_seq) - 2):
                run_len = 1
                for j in range(i + 1, len(letter_seq)):
                    if ord(letter_seq[j]) == ord(letter_seq[j - 1]) + 1:
                        run_len += 1
                    else:
                        break
                if run_len >= 3:
                    run = letter_seq[i:i + run_len]
                    findings.append({
                        'type': 'alphabetic_run',
                        'position': i,
                        'length': run_len,
                        'sequence': run,
                        'source': label,
                    })

            # Check for recognizable short words (3-8 letters) via sliding window
            common_signal_words = {
                'god', 'die', 'sin', 'law', 'war', 'man', 'lie', 'eye',
                'one', 'two', 'end', 'key', 'why', 'who', 'all', 'nil',
                'love', 'hate', 'true', 'lies', 'soul', 'mind', 'free',
                'hide', 'veil', 'mask', 'dead', 'evil', 'good', 'king',
                'fool', 'wise', 'fire', 'dark', 'self', 'void', 'fear',
                'hope', 'fate', 'lord', 'name', 'truth', 'death', 'light',
                'power', 'slave', 'false', 'secret', 'hidden', 'nature',
                'reason', 'divine',
            }
            for word_len in range(3, min(9, len(letter_seq) + 1)):
                for i in range(len(letter_seq) - word_len + 1):
                    candidate = letter_seq[i:i + word_len]
                    if candidate in common_signal_words:
                        findings.append({
                            'type': 'word_found',
                            'position': i,
                            'word': candidate,
                            'source': label,
                        })

            # Check for palindromes (4+ letters)
            for plen in range(4, min(12, len(letter_seq) + 1)):
                for i in range(len(letter_seq) - plen + 1):
                    sub = letter_seq[i:i + plen]
                    if sub == sub[::-1]:
                        findings.append({
                            'type': 'palindrome',
                            'position': i,
                            'sequence': sub,
                            'length': plen,
                            'source': label,
                        })

            # Letter frequency deviation from English baseline
            english_freq = {
                'e': 0.127, 't': 0.091, 'a': 0.082, 'o': 0.075, 'i': 0.070,
                'n': 0.067, 's': 0.063, 'h': 0.061, 'r': 0.060, 'd': 0.043,
                'l': 0.040, 'c': 0.028, 'u': 0.028, 'm': 0.024, 'w': 0.024,
                'f': 0.022, 'g': 0.020, 'y': 0.020, 'p': 0.019, 'b': 0.015,
                'v': 0.010, 'k': 0.008, 'j': 0.002, 'x': 0.002, 'q': 0.001,
                'z': 0.001,
            }
            if len(letter_seq) >= 10:
                observed = Counter(letter_seq)
                total = len(letter_seq)
                chi_sq = 0
                for letter, expected_freq in english_freq.items():
                    observed_count = observed.get(letter, 0)
                    expected_count = expected_freq * total
                    if expected_count > 0:
                        chi_sq += (observed_count - expected_count) ** 2 / expected_count
                findings.append({
                    'type': 'frequency_analysis',
                    'chi_squared': round(chi_sq, 2),
                    'source': label,
                    'note': 'High chi-squared suggests non-random letter distribution in initial/final letters',
                })

            return findings

        all_findings = []
        all_findings.extend(find_patterns(sent_first_letters, "sentence_acrostic"))
        all_findings.extend(find_patterns(sent_last_letters, "sentence_telestic"))
        all_findings.extend(find_patterns(para_first_letters, "paragraph_acrostic"))
        all_findings.extend(find_patterns(para_last_letters, "paragraph_telestic"))
        all_findings.extend(find_patterns(ch_first_letters, "chapter_acrostic"))
        all_findings.extend(find_patterns(ch_last_letters, "chapter_telestic"))

        word_findings = [f for f in all_findings if f['type'] == 'word_found']
        alpha_findings = [f for f in all_findings if f['type'] == 'alphabetic_run']
        palindrome_findings = [f for f in all_findings if f['type'] == 'palindrome']

        score = min(1.0, len(word_findings) * 0.2 + len(alpha_findings) * 0.15 + len(palindrome_findings) * 0.1)

        return {
            'score': round(score, 3),
            'letter_sequences': {
                'sentence_acrostic': sent_first_letters[:100],
                'sentence_telestic': sent_last_letters[:100],
                'paragraph_acrostic': para_first_letters[:100],
                'paragraph_telestic': para_last_letters[:100],
                'chapter_acrostic': ch_first_letters,
                'chapter_telestic': ch_last_letters,
            },
            'words_found': word_findings,
            'alphabetic_runs': alpha_findings,
            'palindromes': palindrome_findings,
            'all_findings': all_findings[:25],
            'method': 'Acrostic & Telestic Detection',
            'precedent': (
                'Hebrew Bible alphabetic acrostics (Psalms, Lamentations); '
                'medieval Jewish liturgical poetry; classical Latin acrostics '
                '(Virgil); Renaissance steganography'
            ),
            'interpretation': (
                'Words spelled out by first or last letters of sequential sentences, '
                'paragraphs, or chapters may be deliberate steganographic signals. '
                'Alphabetic runs suggest intentional ordering. Non-random letter '
                'frequency distributions in acrostic positions suggest the author '
                'constrained word choice to encode a pattern. NOTE: short texts '
                'produce many false positives — findings are significant primarily '
                'in longer, carefully composed works.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 11: HAPAX LEGOMENA ANALYSIS
    # ------------------------------------------------------------------

    def analyze_hapax_legomena(self) -> dict:
        """
        METHOD: Hapax Legomena Analysis
        PRECEDENT: Biblical scholarship on words appearing once in the Hebrew
                   Bible (e.g., 1,500+ hapax legomena in the OT); the principle
                   that in a carefully composed text, a word used exactly once
                   may be a deliberate signal or marker.

        Technique: Identifies all words appearing exactly once, measures their
        density per chapter, and checks whether hapax legomena cluster at
        structurally significant positions (center, beginning, end).
        """
        word_freq = Counter(self.words)
        hapax = {w for w, c in word_freq.items() if c == 1 and w not in self.stop_words and len(w) > 3}
        dis_legomena = {w for w, c in word_freq.items() if c == 2 and w not in self.stop_words and len(w) > 3}

        total_content = len([w for w in self.words if w not in self.stop_words and len(w) > 3])
        hapax_ratio = len(hapax) / total_content if total_content > 0 else 0

        # Hapax per chapter — where do unique words cluster?
        hapax_by_chapter = []
        for ch in self.chapters:
            ch_words = [w for w in ch['words'] if w not in self.stop_words and len(w) > 3]
            ch_hapax = [w for w in ch_words if w in hapax]
            density = len(ch_hapax) / len(ch_words) if ch_words else 0
            hapax_by_chapter.append({
                'chapter': ch['index'] + 1,
                'title': ch['title'],
                'hapax_count': len(ch_hapax),
                'content_words': len(ch_words),
                'hapax_density': round(density, 4),
                'sample_hapax': ch_hapax[:10],
            })

        # Positional analysis — do hapax cluster at the center?
        n = len(self.sentences)
        hapax_positions = {'opening': 0, 'early': 0, 'center': 0, 'late': 0, 'closing': 0}
        hapax_pos_totals = {'opening': 0, 'early': 0, 'center': 0, 'late': 0, 'closing': 0}
        labels_map = {0: 'opening', 1: 'early', 2: 'center', 3: 'late', 4: 'closing'}
        for i, sent in enumerate(self.sentences):
            q = min(4, int((i / max(n, 1)) * 5))
            label = labels_map[q]
            words = [w.lower() for w in word_tokenize(sent) if w.isalpha() and len(w) > 3]
            hapax_in_sent = [w for w in words if w in hapax]
            hapax_positions[label] += len(hapax_in_sent)
            hapax_pos_totals[label] += len(words)

        positional_density = {}
        for label in hapax_positions:
            total = hapax_pos_totals[label]
            positional_density[label] = round(hapax_positions[label] / total, 4) if total > 0 else 0

        # Semantic weight of hapax — are they philosophically loaded?
        philosophical_terms = {
            'truth', 'being', 'essence', 'nature', 'soul', 'god', 'divine',
            'reason', 'justice', 'virtue', 'freedom', 'knowledge', 'wisdom',
            'death', 'immortal', 'eternal', 'power', 'law', 'good', 'evil',
            'beauty', 'love', 'existence', 'substance', 'form', 'matter',
            'spirit', 'mind', 'cosmos', 'creation', 'revelation', 'prophecy',
            'sacred', 'profane', 'hidden', 'secret', 'mystery', 'veil',
        }
        philosophical_hapax = [w for w in hapax if w in philosophical_terms]

        score = min(1.0, hapax_ratio * 2 + len(philosophical_hapax) * 0.05)

        return {
            'score': round(score, 3),
            'total_hapax': len(hapax),
            'total_dis_legomena': len(dis_legomena),
            'hapax_ratio': round(hapax_ratio, 4),
            'hapax_by_chapter': hapax_by_chapter,
            'positional_density': positional_density,
            'philosophical_hapax': philosophical_hapax,
            'sample_hapax': sorted(hapax)[:40],
            'method': 'Hapax Legomena Analysis',
            'precedent': (
                'Biblical scholarship (1,500+ hapax legomena in the Hebrew Bible); '
                'the principle that in carefully composed texts, words used exactly '
                'once may serve as deliberate markers or signals'
            ),
            'interpretation': (
                'A high hapax ratio suggests a text with unusual lexical range. '
                'When hapax legomena cluster at the structural center or carry '
                'philosophical weight, they may be deliberate markers — words '
                'the author chose specifically for a single critical moment. '
                'Philosophically loaded hapax (e.g., a key term used only once) '
                'deserve especially close attention.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 12: VOICE / PERSONA CONSISTENCY (KIERKEGAARD METHOD)
    # ------------------------------------------------------------------

    def analyze_voice_consistency(self) -> dict:
        """
        METHOD: Voice / Persona Consistency Analysis
        PRECEDENT: Kierkegaard's pseudonymous authorship (Johannes Climacus,
                   Anti-Climacus, Judge William, etc.); Plato's dialogue characters;
                   Nietzsche's multiple voices (Zarathustra, Dionysus, the free spirit).

        Technique: Segments the text into chapters/sections and computes a stylistic
        fingerprint for each (vocabulary profile, sentence length distribution,
        punctuation patterns, hedging frequency). Sections with sharply divergent
        fingerprints may indicate different "voices" or personae — the author
        shifting registers to communicate indirectly.
        """
        if len(self.chapters) < 3:
            return {'score': 0, 'evidence': [], 'method': 'Voice / Persona Consistency'}

        chapter_profiles = []
        for ch in self.chapters:
            words = ch['words']
            sents = ch['sentences']
            if not words or not sents:
                continue

            # Average sentence length
            sent_lengths = [len(word_tokenize(s)) for s in sents]
            avg_sent_len = statistics.mean(sent_lengths) if sent_lengths else 0
            sent_len_std = statistics.stdev(sent_lengths) if len(sent_lengths) > 1 else 0

            # Punctuation density
            text = ch['text']
            question_density = text.count('?') / len(sents) if sents else 0
            exclamation_density = text.count('!') / len(sents) if sents else 0
            semicolon_density = text.count(';') / len(sents) if sents else 0
            dash_density = (text.count('—') + text.count('--')) / len(sents) if sents else 0

            # First-person vs third-person pronouns
            first_person = sum(1 for w in words if w in {'i', 'me', 'my', 'mine', 'we', 'us', 'our'})
            third_person = sum(1 for w in words if w in {'he', 'she', 'it', 'they', 'him', 'her', 'them', 'his', 'its', 'their'})
            fp_ratio = first_person / len(words) if words else 0
            tp_ratio = third_person / len(words) if words else 0

            # Hedging / certainty language
            hedge_words = {'perhaps', 'maybe', 'possibly', 'seemingly', 'apparently', 'might', 'could'}
            certainty_words = {'certainly', 'surely', 'undoubtedly', 'clearly', 'obviously', 'must', 'always', 'never'}
            hedge_count = sum(1 for w in words if w in hedge_words)
            certainty_count = sum(1 for w in words if w in certainty_words)

            # Type-token ratio
            ttr = len(set(words)) / len(words) if words else 0

            profile = {
                'chapter': ch['index'] + 1,
                'title': ch['title'],
                'avg_sentence_length': round(avg_sent_len, 1),
                'sentence_length_std': round(sent_len_std, 1),
                'question_density': round(question_density, 3),
                'exclamation_density': round(exclamation_density, 3),
                'semicolon_density': round(semicolon_density, 3),
                'dash_density': round(dash_density, 3),
                'first_person_ratio': round(fp_ratio, 4),
                'third_person_ratio': round(tp_ratio, 4),
                'hedge_count': hedge_count,
                'certainty_count': certainty_count,
                'type_token_ratio': round(ttr, 4),
            }
            chapter_profiles.append(profile)

        # Compute pairwise stylistic distance between chapters
        if len(chapter_profiles) < 2:
            return {'score': 0, 'evidence': [], 'method': 'Voice / Persona Consistency'}

        features = ['avg_sentence_length', 'question_density', 'exclamation_density',
                     'semicolon_density', 'dash_density', 'first_person_ratio',
                     'third_person_ratio', 'type_token_ratio']

        # Normalize features
        feature_matrix = []
        for p in chapter_profiles:
            feature_matrix.append([p[f] for f in features])
        feature_matrix = np.array(feature_matrix)

        # Z-score normalize
        means = feature_matrix.mean(axis=0)
        stds = feature_matrix.std(axis=0)
        stds[stds == 0] = 1
        normalized = (feature_matrix - means) / stds

        # Pairwise Euclidean distance
        from sklearn.metrics.pairwise import euclidean_distances
        dist_matrix = euclidean_distances(normalized)

        # Identify voice shifts: chapters with high average distance from neighbors
        voice_shifts = []
        n = len(chapter_profiles)
        avg_distances = []
        for i in range(n):
            neighbors = []
            if i > 0:
                neighbors.append(dist_matrix[i, i - 1])
            if i < n - 1:
                neighbors.append(dist_matrix[i, i + 1])
            avg_dist = statistics.mean(neighbors) if neighbors else 0
            avg_distances.append(avg_dist)

        if len(avg_distances) > 2:
            mean_dist = statistics.mean(avg_distances)
            std_dist = statistics.stdev(avg_distances) if statistics.stdev(avg_distances) > 0 else 0.01
            for i, d in enumerate(avg_distances):
                z = (d - mean_dist) / std_dist
                if z > 1.0:
                    voice_shifts.append({
                        'chapter': chapter_profiles[i]['chapter'],
                        'title': chapter_profiles[i]['title'],
                        'stylistic_distance': round(d, 3),
                        'z_score': round(z, 2),
                        'profile': chapter_profiles[i],
                    })

        # Overall voice consistency score (inverse: high inconsistency = high esoteric signal)
        overall_variance = statistics.mean(avg_distances) if avg_distances else 0
        score = min(1.0, overall_variance / 3.0)

        return {
            'score': round(score, 3),
            'chapter_profiles': chapter_profiles,
            'voice_shifts': voice_shifts,
            'overall_stylistic_variance': round(overall_variance, 3),
            'method': 'Voice / Persona Consistency Analysis',
            'precedent': (
                "Kierkegaard's pseudonymous authorship; Plato's dialogue characters; "
                "Nietzsche's multiple voices; the principle that a single 'author' "
                "speaking in detectably different voices may be communicating indirectly"
            ),
            'interpretation': (
                'Chapters with sharply different stylistic profiles from their neighbors '
                'may indicate the author shifting "voice" or persona. In the Kierkegaardian '
                'tradition, this signals indirect communication: the author distributes '
                'different (and potentially contradictory) positions across different voices '
                'to prevent the reader from simply appropriating a doctrine. High overall '
                'variance suggests a polyphonic text.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 13: REGISTER ANALYSIS (AVERROES THREE-TIER METHOD)
    # ------------------------------------------------------------------

    def analyze_register(self) -> dict:
        """
        METHOD: Three-Tier Register Analysis
        PRECEDENT: Averroes (Ibn Rushd), Decisive Treatise — three levels of
                   communication: rhetorical (persuasive imagery for masses),
                   dialectical (theological argument for scholars), demonstrative
                   (strict philosophical proof for philosophers).

        Technique: Classifies sentences into three registers based on vocabulary
        and syntactic markers, then maps which register dominates each section
        and whether the text shifts between registers.
        """
        # Vocabulary markers for each register
        rhetorical_markers = {
            'imagine', 'picture', 'story', 'parable', 'like', 'as',
            'beautiful', 'glorious', 'wonderful', 'terrible', 'fear',
            'hope', 'love', 'hate', 'heart', 'feel', 'believe',
            'pray', 'worship', 'holy', 'sacred', 'blessed', 'cursed',
            'heaven', 'hell', 'angel', 'demon', 'miracle', 'sign',
            'reward', 'punishment', 'obey', 'command', 'duty',
        }
        dialectical_markers = {
            'argument', 'objection', 'reply', 'therefore', 'hence',
            'follows', 'granted', 'denied', 'distinction', 'contrary',
            'moreover', 'furthermore', 'nevertheless', 'however',
            'tradition', 'authority', 'scripture', 'doctrine', 'opinion',
            'probable', 'likely', 'plausible', 'reasonable', 'common',
            'accepted', 'orthodox', 'interpretation', 'commentator',
        }
        demonstrative_markers = {
            'necessarily', 'impossible', 'contradiction', 'proof',
            'demonstrate', 'syllogism', 'premise', 'conclusion',
            'definition', 'axiom', 'principle', 'universal', 'particular',
            'essence', 'substance', 'cause', 'effect', 'necessary',
            'contingent', 'sufficient', 'condition', 'entails', 'implies',
            'qed', 'thus', 'formal', 'logical', 'valid', 'invalid',
            'abstract', 'concrete', 'genus', 'species', 'differentia',
        }

        sentence_registers = []
        for i, sent in enumerate(self.sentences):
            words = set(w.lower() for w in word_tokenize(sent) if w.isalpha())
            r_count = len(words & rhetorical_markers)
            d_count = len(words & dialectical_markers)
            p_count = len(words & demonstrative_markers)

            total = r_count + d_count + p_count
            if total == 0:
                dominant = 'neutral'
            elif r_count >= d_count and r_count >= p_count:
                dominant = 'rhetorical'
            elif d_count >= r_count and d_count >= p_count:
                dominant = 'dialectical'
            else:
                dominant = 'demonstrative'

            sentence_registers.append({
                'index': i,
                'dominant_register': dominant,
                'rhetorical': r_count,
                'dialectical': d_count,
                'demonstrative': p_count,
            })

        # Aggregate per chapter
        chapter_registers = []
        for ch in self.chapters:
            ch_sents = ch['sentences']
            r_total = d_total = p_total = 0
            for sent in ch_sents:
                words = set(w.lower() for w in word_tokenize(sent) if w.isalpha())
                r_total += len(words & rhetorical_markers)
                d_total += len(words & dialectical_markers)
                p_total += len(words & demonstrative_markers)

            total = r_total + d_total + p_total
            if total == 0:
                dominant = 'neutral'
                r_pct = d_pct = p_pct = 0
            else:
                r_pct = round(r_total / total, 3)
                d_pct = round(d_total / total, 3)
                p_pct = round(p_total / total, 3)
                if r_total >= d_total and r_total >= p_total:
                    dominant = 'rhetorical'
                elif d_total >= r_total and d_total >= p_total:
                    dominant = 'dialectical'
                else:
                    dominant = 'demonstrative'

            chapter_registers.append({
                'chapter': ch['index'] + 1,
                'title': ch['title'],
                'dominant_register': dominant,
                'rhetorical_pct': r_pct,
                'dialectical_pct': d_pct,
                'demonstrative_pct': p_pct,
            })

        # Count register transitions (shifts between dominant registers)
        transitions = []
        for i in range(1, len(chapter_registers)):
            if chapter_registers[i]['dominant_register'] != chapter_registers[i - 1]['dominant_register']:
                transitions.append({
                    'from_chapter': chapter_registers[i - 1]['chapter'],
                    'to_chapter': chapter_registers[i]['chapter'],
                    'from_register': chapter_registers[i - 1]['dominant_register'],
                    'to_register': chapter_registers[i]['dominant_register'],
                })

        # Multi-tier presence: does the text operate on multiple levels?
        register_set = set(cr['dominant_register'] for cr in chapter_registers if cr['dominant_register'] != 'neutral')
        multi_tier = len(register_set) >= 2

        score = min(1.0, len(transitions) * 0.1 + (0.3 if multi_tier else 0))

        return {
            'score': round(score, 3),
            'chapter_registers': chapter_registers,
            'register_transitions': transitions,
            'registers_present': list(register_set),
            'multi_tier': multi_tier,
            'method': 'Three-Tier Register Analysis (Averroes Method)',
            'precedent': (
                "Averroes (Ibn Rushd), Decisive Treatise: three classes of men require "
                "three modes of communication — rhetorical (persuasive imagery), "
                "dialectical (theological argument), demonstrative (philosophical proof). "
                "It is 'forbidden' to share demonstrative interpretation with those "
                "capable only of rhetorical understanding."
            ),
            'interpretation': (
                'A text operating across multiple registers may be addressing different '
                'audiences simultaneously. Transitions from rhetorical to demonstrative '
                'register may mark the boundary between exoteric and esoteric content. '
                'Sections in demonstrative register embedded within a predominantly '
                'rhetorical text are especially significant — they may be the moments '
                'where the author speaks to the philosophical reader alone.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 14: LOGOS / MYTHOS TRANSITION DETECTION (PLATO METHOD)
    # ------------------------------------------------------------------

    def analyze_logos_mythos(self) -> dict:
        """
        METHOD: Logos / Mythos Transition Detection
        PRECEDENT: Plato's dialogues, where shifts from discursive argument (logos)
                   to narrative myth (mythos) signal the boundary where reason
                   reaches its limit and the author resorts to indirect, symbolic
                   communication. Also applicable to any text that alternates
                   between argumentative and narrative modes.

        Technique: Classifies passages as logos (argumentative) or mythos (narrative)
        based on vocabulary, tense, and syntactic markers, then identifies
        transition points.
        """
        logos_markers = {
            'therefore', 'because', 'since', 'thus', 'hence', 'follows',
            'implies', 'entails', 'argument', 'proof', 'demonstrate',
            'reason', 'rational', 'logical', 'conclude', 'premise',
            'necessary', 'sufficient', 'if', 'then', 'either', 'or',
            'granted', 'denied', 'objection', 'definition', 'analysis',
            'consider', 'examine', 'distinguish', 'true', 'false',
        }
        mythos_markers = {
            'once', 'story', 'tale', 'told', 'say', 'said', 'spoke',
            'went', 'came', 'saw', 'heard', 'dream', 'vision', 'image',
            'imagine', 'picture', 'like', 'resembled', 'appeared',
            'wandered', 'journey', 'cave', 'river', 'mountain', 'sea',
            'descended', 'ascended', 'born', 'died', 'father', 'mother',
            'god', 'goddess', 'hero', 'monster', 'dragon', 'gift',
            'curse', 'fate', 'prophecy', 'oracle', 'myth', 'legend',
            'parable', 'allegory', 'fable', 'symbol', 'shadow', 'light',
            'fire', 'water', 'earth', 'sky', 'underworld', 'chariot',
        }

        # Classify each paragraph
        para_modes = []
        for i, para in enumerate(self.paragraphs):
            words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            logos_count = len(words & logos_markers)
            mythos_count = len(words & mythos_markers)

            if logos_count > mythos_count:
                mode = 'logos'
            elif mythos_count > logos_count:
                mode = 'mythos'
            else:
                mode = 'mixed'

            para_modes.append({
                'paragraph': i + 1,
                'mode': mode,
                'logos_score': logos_count,
                'mythos_score': mythos_count,
            })

        # Detect transitions
        transitions = []
        for i in range(1, len(para_modes)):
            prev = para_modes[i - 1]['mode']
            curr = para_modes[i]['mode']
            if prev != curr and prev != 'mixed' and curr != 'mixed':
                position_pct = round((i / len(para_modes)) * 100, 1)
                transitions.append({
                    'paragraph': i + 1,
                    'position': f"{position_pct}%",
                    'from': prev,
                    'to': curr,
                    'excerpt': self.paragraphs[i][:200],
                })

        # Identify mythos passages embedded in logos-dominant text (or vice versa)
        total_logos = sum(1 for p in para_modes if p['mode'] == 'logos')
        total_mythos = sum(1 for p in para_modes if p['mode'] == 'mythos')
        total_mixed = sum(1 for p in para_modes if p['mode'] == 'mixed')

        dominant = 'logos' if total_logos >= total_mythos else 'mythos'
        embedded = 'mythos' if dominant == 'logos' else 'logos'
        embedded_passages = [p for p in para_modes if p['mode'] == embedded]

        score = min(1.0, len(transitions) * 0.1 + len(embedded_passages) * 0.05)

        return {
            'score': round(score, 3),
            'paragraph_modes': para_modes,
            'transitions': transitions[:15],
            'mode_counts': {'logos': total_logos, 'mythos': total_mythos, 'mixed': total_mixed},
            'dominant_mode': dominant,
            'embedded_passages': [{'paragraph': p['paragraph'], 'mode': p['mode']} for p in embedded_passages],
            'method': 'Logos / Mythos Transition Detection',
            'precedent': (
                "Plato's dialogue transitions from argument to myth (Cave allegory, "
                "Allegory of Er, Allegory of the Charioteer); the principle that "
                "the shift to mythos signals the boundary of what reason can directly "
                "demonstrate — the author resorts to indirect, symbolic communication"
            ),
            'interpretation': (
                'Transitions from logos to mythos mark moments where the author '
                'shifts from direct argument to indirect, symbolic communication. '
                'In Plato, these are precisely the passages that carry the deepest '
                'philosophical content — truths that resist propositional statement '
                'and require imagistic expression. Mythos passages embedded in a '
                'predominantly logos text deserve special interpretive attention.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 15: COMMENTARY DIVERGENCE ANALYSIS
    # ------------------------------------------------------------------

    def analyze_commentary_divergence(self) -> dict:
        """
        METHOD: Commentary Divergence Analysis
        PRECEDENT: Al-Farabi, Averroes, and Aquinas writing "commentaries" on
                   Aristotle that are vehicles for their own philosophy; Spinoza
                   decoding Ibn Ezra; the commentary form as concealment.

        Technique: If reference texts (sources being commented upon) have been
        provided, measures where the commentary's vocabulary and emphasis diverge
        most sharply from the source — indicating where the commentator is
        importing their own ideas under cover of explication.
        """
        if not self.reference_texts:
            return {
                'score': 0,
                'evidence': [],
                'method': 'Commentary Divergence Analysis',
                'note': ('No reference texts provided. Call add_reference_text(label, text) '
                         'to add the source(s) being commented upon.'),
            }

        divergences = []
        for label, ref_text in self.reference_texts.items():
            # Build vocabulary profiles
            ref_words = [w.lower() for w in word_tokenize(ref_text) if w.isalpha() and w not in self.stop_words]
            ref_freq = Counter(ref_words)
            ref_total = len(ref_words)

            # Compare each chapter of the commentary to the reference
            for ch in self.chapters:
                ch_words = [w for w in ch['words'] if w not in self.stop_words]
                ch_freq = Counter(ch_words)
                ch_total = len(ch_words)

                if not ch_total or not ref_total:
                    continue

                # Words in commentary NOT in reference (novel vocabulary)
                novel_words = set(ch_freq.keys()) - set(ref_freq.keys())
                novel_ratio = len(novel_words) / len(set(ch_freq.keys())) if ch_freq else 0

                # TF-IDF similarity between chapter and reference
                vectorizer = TfidfVectorizer(stop_words='english', max_features=2000)
                try:
                    tfidf = vectorizer.fit_transform([ch['text'], ref_text])
                    sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
                except ValueError:
                    sim = 0

                divergence_score = (1 - sim) * novel_ratio

                divergences.append({
                    'chapter': ch['index'] + 1,
                    'title': ch['title'],
                    'reference': label,
                    'similarity_to_source': round(float(sim), 3),
                    'novel_vocabulary_ratio': round(novel_ratio, 3),
                    'divergence_score': round(divergence_score, 3),
                    'top_novel_words': sorted(novel_words)[:15],
                })

        divergences.sort(key=lambda x: x['divergence_score'], reverse=True)
        top_divergent = divergences[:10]

        overall = statistics.mean(d['divergence_score'] for d in divergences) if divergences else 0
        score = min(1.0, overall * 5)

        return {
            'score': round(score, 3),
            'divergences': top_divergent,
            'all_divergences': divergences,
            'method': 'Commentary Divergence Analysis',
            'precedent': (
                "Al-Farabi, Averroes, Aquinas using the commentary form to advance "
                "their own philosophy under cover of 'explaining' Aristotle; Spinoza "
                "decoding Ibn Ezra; the commentary as concealment"
            ),
            'interpretation': (
                'Chapters where the commentary diverges most sharply from its source — '
                'introducing novel vocabulary, shifting emphasis, or departing topically — '
                'are the passages where the commentator is most likely importing their '
                'own ideas. When a commentary says "Aristotle means X" using vocabulary '
                'Aristotle never used, the commentator may really be saying "I believe X."'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 16: POLYSEMY DETECTION (DANTE FOUR-LEVELS METHOD)
    # ------------------------------------------------------------------

    def analyze_polysemy(self) -> dict:
        """
        METHOD: Polysemy Detection
        PRECEDENT: Dante's four levels of meaning (Convivio, Letter to Can Grande):
                   literal, allegorical, moral, anagogical. Also the Kabbalistic
                   PaRDeS method (Peshat, Remez, Derash, Sod) and Origen's three
                   levels (somatic, psychic, pneumatic).

        Technique: Identifies words and passages that operate across multiple
        semantic domains simultaneously — physical/spiritual, historical/typological,
        ethical/eschatological. High polysemy density suggests the text is designed
        to be read on multiple levels.
        """
        # Semantic domain wordlists
        domains = {
            'physical': {
                'body', 'earth', 'stone', 'water', 'fire', 'bread', 'wine',
                'blood', 'bone', 'flesh', 'seed', 'tree', 'fruit', 'root',
                'mountain', 'valley', 'river', 'sea', 'sun', 'moon', 'star',
                'hand', 'eye', 'foot', 'path', 'road', 'gate', 'door',
                'house', 'city', 'wall', 'tower', 'field', 'garden',
            },
            'spiritual': {
                'soul', 'spirit', 'divine', 'sacred', 'holy', 'grace',
                'redemption', 'salvation', 'sin', 'virtue', 'heaven',
                'hell', 'angel', 'demon', 'prayer', 'meditation', 'faith',
                'revelation', 'prophecy', 'vision', 'enlightenment',
                'transcendence', 'eternal', 'immortal', 'blessed',
            },
            'political': {
                'king', 'ruler', 'citizen', 'law', 'justice', 'power',
                'authority', 'freedom', 'slavery', 'republic', 'tyranny',
                'democracy', 'war', 'peace', 'order', 'rebellion',
                'obedience', 'command', 'right', 'duty', 'consent',
                'sovereignty', 'state', 'nation', 'people', 'ruler',
            },
            'philosophical': {
                'truth', 'being', 'essence', 'existence', 'nature', 'reason',
                'knowledge', 'wisdom', 'opinion', 'appearance', 'reality',
                'form', 'matter', 'substance', 'cause', 'good', 'beauty',
                'one', 'many', 'whole', 'part', 'universal', 'particular',
            },
        }

        # Words that appear in 2+ domain lists (inherently polysemous in this context)
        all_domain_words = {}
        for domain, words in domains.items():
            for w in words:
                if w not in all_domain_words:
                    all_domain_words[w] = []
                all_domain_words[w].append(domain)
        multi_domain_words = {w: doms for w, doms in all_domain_words.items() if len(doms) >= 2}

        # Count domain co-presence per paragraph
        polysemous_paragraphs = []
        for i, para in enumerate(self.paragraphs):
            words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            domains_present = set()
            domain_counts = {d: 0 for d in domains}
            polysemous_words_found = []

            for word in words:
                for domain, domain_words in domains.items():
                    if word in domain_words:
                        domains_present.add(domain)
                        domain_counts[domain] += 1
                if word in multi_domain_words:
                    polysemous_words_found.append(word)

            if len(domains_present) >= 3:
                polysemous_paragraphs.append({
                    'paragraph': i + 1,
                    'domains_present': list(domains_present),
                    'domain_count': len(domains_present),
                    'domain_scores': {d: c for d, c in domain_counts.items() if c > 0},
                    'polysemous_words': polysemous_words_found,
                    'excerpt': para[:200],
                })

        # Words in the text that exist in multiple domains
        text_word_set = set(self.words)
        cross_domain_in_text = {w: doms for w, doms in multi_domain_words.items() if w in text_word_set}

        # Overall polysemy score
        polysemy_ratio = len(polysemous_paragraphs) / len(self.paragraphs) if self.paragraphs else 0
        score = min(1.0, polysemy_ratio * 3 + len(cross_domain_in_text) * 0.02)

        return {
            'score': round(score, 3),
            'polysemous_paragraphs': polysemous_paragraphs[:15],
            'total_multi_domain_paragraphs': len(polysemous_paragraphs),
            'cross_domain_words_in_text': {w: doms for w, doms in list(cross_domain_in_text.items())[:20]},
            'polysemy_ratio': round(polysemy_ratio, 4),
            'method': 'Polysemy Detection (Dante Four-Levels Method)',
            'precedent': (
                "Dante's four levels (literal, allegorical, moral, anagogical) from "
                "the Convivio and Letter to Can Grande; the Kabbalistic PaRDeS method "
                "(Peshat/Remez/Derash/Sod); Origen's three levels (somatic/psychic/pneumatic)"
            ),
            'interpretation': (
                'Paragraphs operating across 3+ semantic domains simultaneously are '
                'candidates for multi-level reading. Words that bridge physical and '
                'spiritual domains (e.g., "light," "path," "fire") may function as '
                'hinges between literal and allegorical readings. High polysemy density '
                'suggests a text designed to reward reading at multiple levels — precisely '
                "the structure Dante, Origen, and the Kabbalists described."
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 17: APHORISTIC FRAGMENTATION (NIETZSCHE MASK METHOD)
    # ------------------------------------------------------------------

    def analyze_aphoristic_fragmentation(self) -> dict:
        """
        METHOD: Aphoristic Fragmentation Analysis
        PRECEDENT: Nietzsche's mask theory (BGE §40: "Every profound spirit needs
                   a mask"); his aphoristic style in Human, All Too Human, Beyond
                   Good and Evil, Twilight of the Idols; Pythagorean symbola;
                   Bacon's aphoristic method.

        Technique: Measures the degree of thematic fragmentation — how rapidly
        the text shifts topics between adjacent paragraphs/sentences. Highly
        fragmented texts (many rapid topic shifts) suggest the aphoristic
        method: compressed, enigmatic fragments that resist systematic
        interpretation and require the reader to supply connections.
        Also detects self-referential "mask" language.
        """
        # Mask / concealment vocabulary
        mask_words = {
            'mask', 'veil', 'hide', 'hidden', 'conceal', 'concealed',
            'disguise', 'cloak', 'cover', 'surface', 'beneath', 'behind',
            'appear', 'appearance', 'seeming', 'seem', 'pretend', 'pretense',
            'secret', 'mystery', 'enigma', 'riddle', 'puzzle', 'cipher',
            'decode', 'encrypt', 'obscure', 'shadow', 'depth', 'deeper',
            'between the lines', 'indirect', 'oblique', 'hint', 'allude',
            'suggest', 'intimate', 'insinuate', 'imply', 'unspoken',
        }

        # Self-referential writing language
        meta_words = {
            'write', 'written', 'writing', 'reader', 'read', 'book',
            'chapter', 'page', 'author', 'text', 'discourse', 'treatise',
            'communicate', 'express', 'say', 'said', 'speak', 'spoken',
            'silence', 'silent', 'unsaid', 'understand', 'misunderstand',
            'interpret', 'interpretation', 'meaning', 'sense',
        }

        # Count mask and meta vocabulary
        mask_count = sum(1 for w in self.words if w in mask_words)
        meta_count = sum(1 for w in self.words if w in meta_words)
        total = len(self.words)
        mask_density = mask_count / total if total > 0 else 0
        meta_density = meta_count / total if total > 0 else 0

        # Fragmentation: average topical similarity between adjacent paragraphs
        if len(self.paragraphs) >= 3:
            vectorizer = TfidfVectorizer(stop_words='english', max_features=2000)
            try:
                tfidf = vectorizer.fit_transform(self.paragraphs)
                sim_matrix = cosine_similarity(tfidf)
                adjacent_sims = []
                for i in range(len(self.paragraphs) - 1):
                    adjacent_sims.append(float(sim_matrix[i, i + 1]))
                avg_adjacent = statistics.mean(adjacent_sims) if adjacent_sims else 0
                fragmentation = 1 - avg_adjacent  # High fragmentation = low adjacent similarity

                # Find the sharpest breaks
                sharp_breaks = []
                if len(adjacent_sims) > 2:
                    mean_sim = statistics.mean(adjacent_sims)
                    std_sim = statistics.stdev(adjacent_sims) if statistics.stdev(adjacent_sims) > 0 else 0.01
                    for i, sim in enumerate(adjacent_sims):
                        z = (sim - mean_sim) / std_sim
                        if z < -1.0:
                            sharp_breaks.append({
                                'between_paragraphs': f"{i + 1} and {i + 2}",
                                'similarity': round(sim, 3),
                                'z_score': round(z, 2),
                            })
            except ValueError:
                fragmentation = 0
                sharp_breaks = []
                avg_adjacent = 0
        else:
            fragmentation = 0
            sharp_breaks = []
            avg_adjacent = 0

        # Paragraph length variance (aphoristic texts have highly variable paragraph length)
        para_lengths = [len(word_tokenize(p)) for p in self.paragraphs]
        if len(para_lengths) > 1:
            length_cv = statistics.stdev(para_lengths) / statistics.mean(para_lengths) if statistics.mean(para_lengths) > 0 else 0
        else:
            length_cv = 0

        # Find sentences with mask/meta vocabulary
        mask_sentences = []
        for i, sent in enumerate(self.sentences):
            words = set(w.lower() for w in word_tokenize(sent) if w.isalpha())
            mask_hits = words & mask_words
            meta_hits = words & meta_words
            if len(mask_hits) >= 2 or (mask_hits and meta_hits):
                mask_sentences.append({
                    'sentence_index': i + 1,
                    'text': sent[:250],
                    'mask_words': list(mask_hits),
                    'meta_words': list(meta_hits),
                })

        score = min(1.0, fragmentation * 0.5 + mask_density * 30 + meta_density * 10 + length_cv * 0.1)

        return {
            'score': round(score, 3),
            'fragmentation_index': round(fragmentation, 3),
            'avg_adjacent_similarity': round(avg_adjacent, 3),
            'sharp_breaks': sharp_breaks[:10],
            'paragraph_length_cv': round(length_cv, 3),
            'mask_vocabulary_density': round(mask_density, 5),
            'meta_vocabulary_density': round(meta_density, 5),
            'mask_sentences': mask_sentences[:10],
            'method': 'Aphoristic Fragmentation Analysis (Nietzsche Mask Method)',
            'precedent': (
                "Nietzsche BGE §40: 'Every profound spirit needs a mask'; "
                "the aphoristic style of Human All Too Human, BGE, Twilight; "
                "Pythagorean symbola; Bacon's aphoristic method; "
                "the principle that compressed, enigmatic fragments force "
                "the reader to actively reconstruct the argument"
            ),
            'interpretation': (
                'High fragmentation (low adjacent-paragraph similarity) combined '
                'with mask/concealment vocabulary suggests a text that deliberately '
                'resists systematic reading. Sharp topical breaks between paragraphs '
                'force the reader to supply connections the author has withheld. '
                'Self-referential "mask" language — where the author discusses '
                'concealment, surfaces, or the act of writing itself — may be '
                'metacommentary on the text\'s own esoteric structure.'
            ),
        }

    # ------------------------------------------------------------------
    # BENARDETE METHODS (from "The Argument of the Action")
    # ------------------------------------------------------------------

    def analyze_trapdoors(self) -> dict:
        """
        METHOD: Trapdoor Detection
        PRECEDENT: Seth Benardete's concept of "trapdoors" — intentional flaws
                   in the apparent argument that induce the reader to "drop beneath
                   the surface to uncover the source of movement that reveals the
                   real argument" (Burger & Davis, Introduction, p. xi).

        Unlike global contradiction analysis (which detects semantic tension between
        distant passages), trapdoor analysis detects LOCAL impossibilities and
        narrative inconsistencies within short windows — temporal impossibilities,
        factual self-contradictions, logical non-sequiturs signaled by hedging
        near strong claims — that a careful reader would notice as deliberately
        planted flaws.

        Technique:
        1. Temporal impossibility: detect impossible time references within narrative
        2. Local self-contradiction: within small windows, detect claim + negation
        3. Hedging near absolutes: confident claims immediately qualified/undercut
        4. Premise-conclusion mismatch: premises that don't actually support conclusions
        """
        # 1. Hedging near absolutes — a trapdoor signature
        absolute_markers = {
            'all', 'every', 'always', 'never', 'none', 'certainly', 'undoubtedly',
            'obviously', 'clearly', 'indisputably', 'unquestionably', 'absolutely',
            'must', 'necessarily', 'proven', 'established', 'beyond doubt',
            'no one denies', 'everyone agrees', 'it is certain', 'without exception',
        }
        hedge_markers = {
            'perhaps', 'maybe', 'possibly', 'might', 'could', 'seems', 'appears',
            'apparently', 'arguably', 'supposedly', 'one might say', 'in a sense',
            'so to speak', 'as it were', 'not entirely', 'not quite', 'almost',
            'nearly', 'somewhat', 'rather', 'fairly', 'to some extent',
            'it is not clear', 'one wonders', 'it remains to be seen',
            'however', 'yet', 'but', 'although', 'though', 'nevertheless',
            'notwithstanding', 'on the other hand', 'admittedly',
        }

        trapdoor_candidates = []
        window = 3  # Check sentences within this window for hedge-near-absolute

        for i, sent in enumerate(self.sentences):
            words_lower = sent.lower()
            has_absolute = any(m in words_lower for m in absolute_markers)
            if has_absolute:
                # Check if nearby sentences hedge or qualify
                start = max(0, i - window)
                end = min(len(self.sentences), i + window + 1)
                nearby_hedges = []
                for j in range(start, end):
                    if j == i:
                        continue
                    nearby_lower = self.sentences[j].lower()
                    hedges_found = [h for h in hedge_markers if h in nearby_lower]
                    if hedges_found:
                        nearby_hedges.append({
                            'sentence_index': j + 1,
                            'hedges': hedges_found[:3],
                        })
                if nearby_hedges:
                    trapdoor_candidates.append({
                        'type': 'hedge_near_absolute',
                        'absolute_sentence_index': i + 1,
                        'absolute_text': sent[:200],
                        'nearby_hedges': nearby_hedges,
                        'position_in_text': round(i / max(len(self.sentences), 1), 3),
                    })

        # 2. Local self-contradiction: within small sentence windows
        local_contradictions = []
        negation_words = {'not', 'no', 'never', 'neither', 'nor', 'nothing',
                          'nowhere', 'hardly', 'scarcely', 'barely', 'deny',
                          'denied', 'denies', 'impossible', 'false', 'untrue'}

        for i in range(len(self.sentences) - 2):
            s1_words = set(w.lower() for w in word_tokenize(self.sentences[i]) if w.isalpha())
            s1_content = s1_words - self.stop_words
            s1_neg = bool(s1_words & negation_words)

            for j in range(i + 1, min(i + 4, len(self.sentences))):
                s2_words = set(w.lower() for w in word_tokenize(self.sentences[j]) if w.isalpha())
                s2_content = s2_words - self.stop_words
                s2_neg = bool(s2_words & negation_words)

                # Same topic (high content overlap) but opposite polarity
                overlap = len(s1_content & s2_content)
                if overlap >= 3 and s1_neg != s2_neg:
                    local_contradictions.append({
                        'type': 'local_self_contradiction',
                        'sentence_a': i + 1,
                        'sentence_b': j + 1,
                        'text_a': self.sentences[i][:150],
                        'text_b': self.sentences[j][:150],
                        'shared_content': list(s1_content & s2_content)[:5],
                        'position': round(i / max(len(self.sentences), 1), 3),
                    })

        # 3. Non-sequitur markers: conclusion language without adequate premises
        conclusion_markers = {
            'therefore', 'thus', 'hence', 'consequently', 'it follows',
            'we conclude', 'this proves', 'this shows', 'accordingly',
            'so we see', 'from this it is clear', 'q.e.d.',
        }
        non_sequitur_candidates = []
        for i, sent in enumerate(self.sentences):
            words_lower = sent.lower()
            has_conclusion = any(m in words_lower for m in conclusion_markers)
            if has_conclusion and i >= 2:
                # Check if preceding sentences actually provided premises
                # (very rough heuristic: do preceding sentences share key nouns?)
                conclusion_nouns = set(w.lower() for w in word_tokenize(sent)
                                       if w.isalpha() and w.lower() not in self.stop_words
                                       and len(w) > 3)
                premise_nouns = set()
                for k in range(max(0, i - 3), i):
                    premise_nouns |= set(w.lower() for w in word_tokenize(self.sentences[k])
                                         if w.isalpha() and w.lower() not in self.stop_words
                                         and len(w) > 3)
                shared = conclusion_nouns & premise_nouns
                if len(shared) < 2:
                    non_sequitur_candidates.append({
                        'type': 'potential_non_sequitur',
                        'conclusion_sentence': i + 1,
                        'text': sent[:200],
                        'shared_with_premises': list(shared),
                        'position': round(i / max(len(self.sentences), 1), 3),
                    })

        total_trapdoors = len(trapdoor_candidates) + len(local_contradictions) + len(non_sequitur_candidates)
        density = total_trapdoors / max(len(self.sentences), 1)

        score = min(1.0, density * 50 + len(local_contradictions) * 0.05)

        return {
            'score': round(score, 3),
            'total_trapdoors': total_trapdoors,
            'hedge_near_absolute': trapdoor_candidates[:15],
            'local_contradictions': local_contradictions[:15],
            'non_sequiturs': non_sequitur_candidates[:10],
            'trapdoor_density': round(density, 5),
            'method': 'Trapdoor Detection (Benardete Method)',
            'precedent': (
                "Benardete's concept of 'trapdoors' — intentional flaws in the "
                "apparent argument that induce the reader to drop beneath the surface. "
                "Burger & Davis: 'an intentional flaw in the flow of the apparent "
                "argument — Plato's trapdoor — induces us to drop beneath the surface "
                "to uncover the source of movement that reveals the real argument.' "
                "This method detects local inconsistencies (as opposed to global "
                "contradictions): hedged absolutes, nearby negation reversals, and "
                "conclusions without adequate premises."
            ),
            'interpretation': (
                'Trapdoors are locally planted inconsistencies that a careful reader '
                'notices as impossible — temporal impossibilities, claims immediately '
                'undercut, conclusions that do not follow from their premises. Unlike '
                'global contradictions (which may reflect different aspects of a complex '
                'position), trapdoors are deliberately placed to force the attentive '
                'reader to look deeper. The density of hedge-near-absolute patterns '
                'is especially diagnostic: an author who confidently asserts X and then '
                'immediately qualifies it is signaling the reader to question X.'
            ),
        }

    def analyze_dyadic_structure(self) -> dict:
        """
        METHOD: Dyadic Structure Analysis (Conjunctive/Disjunctive Two)
        PRECEDENT: Seth Benardete's distinction between "conjunctive two" and
                   "disjunctive two" — adapted from Plato's use of myth vs. logos.

        Conjunctive two: two seemingly independent elements presented together
        as if their conjunction requires external explanation (myth, narrative).
        Disjunctive two: two elements that are mutually determining parts of a
        single whole — their apparent independence is an illusion.

        The movement from conjunctive to disjunctive is the philosophical
        "turn" (periagoge) at the heart of Platonic dialectic.

        Technique: Detect binary opposition pairs in the text (X and Y, X or Y,
        X vs Y), track whether they converge later, and measure the text's
        overall binary-opposition density as a marker of dialectical structure.
        """
        # Binary opposition markers
        opposition_patterns = [
            r'\b(\w+)\s+(?:and|or|versus|vs\.?|against|rather than)\s+(\w+)',
            r'\b(?:between|either)\s+(\w+)\s+(?:and|or)\s+(\w+)',
            r'\b(\w+)\s+(?:is not|are not|cannot be|differs from|opposes)\s+(\w+)',
        ]

        # Collect binary pairs across the text
        binary_pairs = []
        pair_positions = defaultdict(list)
        for i, para in enumerate(self.paragraphs):
            for pattern in opposition_patterns:
                matches = re.finditer(pattern, para.lower())
                for m in matches:
                    pair = tuple(sorted([m.group(1), m.group(2)]))
                    if pair[0] != pair[1] and all(len(w) > 2 for w in pair):
                        binary_pairs.append(pair)
                        pair_positions[pair].append(i)

        # Count recurring pairs (same opposition mentioned in multiple locations)
        pair_counts = Counter(binary_pairs)
        recurring_pairs = [(pair, count) for pair, count in pair_counts.items() if count >= 2]
        recurring_pairs.sort(key=lambda x: -x[1])

        # Check for convergence: do pair terms appear in same sentence later?
        convergence_markers = []
        for pair, positions in pair_positions.items():
            if len(positions) >= 2:
                # Check if in later occurrences the terms collapse
                first_pos = positions[0]
                for later_pos in positions[1:]:
                    if later_pos > first_pos + 2:  # Must be significantly later
                        later_text = self.paragraphs[later_pos].lower()
                        # Check for unity/identity language near the pair
                        unity_words = {'same', 'one', 'identical', 'united',
                                       'inseparable', 'both', 'together',
                                       'cannot be separated', 'are one',
                                       'turns out to be', 'proves to be',
                                       'is really', 'nothing but', 'whole'}
                        has_unity = any(w in later_text for w in unity_words)
                        if has_unity:
                            convergence_markers.append({
                                'pair': list(pair),
                                'first_position': first_pos + 1,
                                'convergence_position': later_pos + 1,
                                'convergence_excerpt': self.paragraphs[later_pos][:200],
                            })

        # Eidetic analysis markers: parts-wholes language
        eidetic_vocab = {
            'whole', 'part', 'parts', 'wholes', 'unity', 'manifold',
            'one', 'many', 'same', 'other', 'being', 'becoming',
            'appearance', 'reality', 'surface', 'depth', 'form', 'matter',
            'eidos', 'idea', 'image', 'original', 'copy', 'phantom',
            'shadow', 'reflection', 'dyad', 'monad', 'triad',
        }
        eidetic_count = sum(1 for w in self.words if w in eidetic_vocab)
        eidetic_density = eidetic_count / max(len(self.words), 1)

        # Phantom image detection: where the text discusses split appearances
        phantom_vocab = {
            'phantom', 'phantasm', 'image', 'apparition', 'ghost',
            'double', 'split', 'divided', 'fractured', 'mask',
            'disguise', 'semblance', 'seeming', 'mirage', 'illusion',
            'deceptive', 'misleading', 'distorted', 'mirror',
        }
        phantom_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            phantom_hits = para_words & phantom_vocab
            if len(phantom_hits) >= 2:
                phantom_passages.append({
                    'paragraph': i + 1,
                    'phantom_terms': list(phantom_hits),
                    'excerpt': para[:200],
                })

        total_pairs = len(binary_pairs)
        binary_density = total_pairs / max(len(self.paragraphs), 1)

        score = min(1.0, (
            binary_density * 0.2 +
            len(recurring_pairs) * 0.05 +
            len(convergence_markers) * 0.1 +
            eidetic_density * 20 +
            len(phantom_passages) * 0.03
        ))

        return {
            'score': round(score, 3),
            'total_binary_pairs': total_pairs,
            'binary_pair_density': round(binary_density, 3),
            'recurring_pairs': [{'pair': list(p), 'count': c} for p, c in recurring_pairs[:15]],
            'convergence_markers': convergence_markers[:10],
            'eidetic_vocabulary_density': round(eidetic_density, 5),
            'phantom_passages': phantom_passages[:10],
            'method': 'Dyadic Structure Analysis (Benardete Conjunctive/Disjunctive Two)',
            'precedent': (
                "Benardete's distinction between 'conjunctive two' (mythical pairing "
                "of independent elements) and 'disjunctive two' (necessary relation "
                "between mutually determining parts of a whole). The movement from "
                "conjunctive to disjunctive is the philosophical turn (periagoge) "
                "at the heart of Platonic dialectic. Also incorporates Benardete's "
                "'eidetic analysis' (account of being revealing parts parading as "
                "wholes) and 'phantom images' (split appearances hiding a single reality)."
            ),
            'interpretation': (
                'Binary oppositions are the scaffolding of dialectical argument. A high '
                'density of recurring pairs that later converge signals the conjunctive-'
                'to-disjunctive movement characteristic of Platonic dialogue: what began '
                'as two independent entities is revealed to be two aspects of a single '
                'thing. Phantom image passages — where the text explicitly discusses split '
                'appearances, doubles, or distorted mirrors — are especially significant '
                'as metacommentary on the text\'s own dialectical structure.'
            ),
        }

    def analyze_periagoge(self) -> dict:
        """
        METHOD: Periagoge (Structural Reversal/Turning) Detection
        PRECEDENT: Benardete's concept of periagoge — the conversion or "turning"
                   that every Platonic dialogue reproduces in itself (cf. the Cave
                   allegory, Republic 514a-521b). Also: pathei mathos (learning
                   through suffering/error) from Aeschylus Agamemnon 177.

        The periagoge structure: the text leads the reader to a conclusion in
        the first half, then undermines, inverts, or deepens that conclusion in
        the second half. The reader must undergo the error to understand the truth.

        Technique:
        1. Compare key vocabulary between first and second halves
        2. Detect claim-inversion: assertions in the first half negated in the second
        3. Measure the "reversal index" — how much the second half contradicts the first
        4. Track evaluative language (good/bad, true/false) polarity shifts
        """
        if len(self.paragraphs) < 4:
            return {'score': 0, 'method': 'Periagoge Detection', 'note': 'Text too short'}

        mid = len(self.paragraphs) // 2
        first_half = ' '.join(self.paragraphs[:mid])
        second_half = ' '.join(self.paragraphs[mid:])

        # 1. Vocabulary comparison between halves
        fh_words = [w.lower() for w in word_tokenize(first_half) if w.isalpha() and w.lower() not in self.stop_words]
        sh_words = [w.lower() for w in word_tokenize(second_half) if w.isalpha() and w.lower() not in self.stop_words]

        fh_freq = Counter(fh_words)
        sh_freq = Counter(sh_words)

        # Words that shift dramatically in frequency
        all_words = set(fh_freq.keys()) | set(sh_freq.keys())
        freq_shifts = []
        for word in all_words:
            f1 = fh_freq.get(word, 0) / max(len(fh_words), 1)
            f2 = sh_freq.get(word, 0) / max(len(sh_words), 1)
            if max(f1, f2) > 0.0005:  # Only track words with meaningful frequency
                shift = abs(f2 - f1)
                if shift > 0.001:
                    freq_shifts.append({
                        'word': word,
                        'first_half_freq': round(f1, 5),
                        'second_half_freq': round(f2, 5),
                        'shift': round(shift, 5),
                        'direction': 'increases' if f2 > f1 else 'decreases',
                    })
        freq_shifts.sort(key=lambda x: -x['shift'])

        # 2. Evaluative polarity comparison
        positive_words = {
            'good', 'true', 'beautiful', 'noble', 'just', 'wise', 'virtue',
            'excellent', 'best', 'perfect', 'divine', 'sacred', 'blessed',
            'right', 'correct', 'proper', 'worthy', 'admirable', 'praise',
        }
        negative_words = {
            'bad', 'false', 'ugly', 'base', 'unjust', 'foolish', 'vice',
            'terrible', 'worst', 'imperfect', 'corrupt', 'profane', 'cursed',
            'wrong', 'incorrect', 'improper', 'unworthy', 'shameful', 'blame',
        }

        fh_pos = sum(1 for w in fh_words if w in positive_words)
        fh_neg = sum(1 for w in fh_words if w in negative_words)
        sh_pos = sum(1 for w in sh_words if w in positive_words)
        sh_neg = sum(1 for w in sh_words if w in negative_words)

        fh_polarity = (fh_pos - fh_neg) / max(fh_pos + fh_neg, 1)
        sh_polarity = (sh_pos - sh_neg) / max(sh_pos + sh_neg, 1)
        polarity_shift = sh_polarity - fh_polarity

        # 3. Reversal detection: sentences in second half that negate first-half claims
        # Build a set of key first-half claims (sentences with assertion markers)
        assertion_markers = {'is', 'are', 'must', 'should', 'always', 'never'}
        negation_markers = {'not', 'no', 'never', 'neither', 'cannot', 'impossible',
                            'false', 'wrong', 'deny', 'denies', 'fails', 'failed'}

        first_half_sents = sent_tokenize(first_half)
        second_half_sents = sent_tokenize(second_half)

        reversals = []
        for i, fh_sent in enumerate(first_half_sents):
            fh_content = set(w.lower() for w in word_tokenize(fh_sent)
                             if w.isalpha() and w.lower() not in self.stop_words and len(w) > 3)
            if len(fh_content) < 3:
                continue
            for j, sh_sent in enumerate(second_half_sents):
                sh_words_set = set(w.lower() for w in word_tokenize(sh_sent) if w.isalpha())
                sh_content = sh_words_set - self.stop_words
                overlap = fh_content & sh_content
                has_negation = bool(sh_words_set & negation_markers)
                if len(overlap) >= 3 and has_negation:
                    reversals.append({
                        'first_half_sentence': fh_sent[:150],
                        'second_half_sentence': sh_sent[:150],
                        'shared_terms': list(overlap)[:5],
                        'first_position': round(i / max(len(first_half_sents), 1), 3),
                        'second_position': round(j / max(len(second_half_sents), 1), 3),
                    })

        # 4. Turning-point language detection
        turning_vocab = {
            'however', 'but', 'yet', 'nevertheless', 'on the contrary',
            'in truth', 'in reality', 'actually', 'in fact', 'really',
            'turn', 'turning', 'reverse', 'invert', 'conversion', 'transform',
            'overcome', 'transcend', 'sublate', 'aufheben', 'periagoge',
            'second sailing', 'begin again', 'reconsider', 'on reflection',
        }
        # Count turning vocabulary in the middle third
        third = len(self.paragraphs) // 3
        middle_third = ' '.join(self.paragraphs[third:2*third])
        middle_words = [w.lower() for w in word_tokenize(middle_third) if w.isalpha()]
        turning_count = sum(1 for w in middle_words if w in turning_vocab)
        turning_density = turning_count / max(len(middle_words), 1)

        reversal_index = len(reversals) / max(len(first_half_sents), 1)
        score = min(1.0, (
            abs(polarity_shift) * 0.5 +
            reversal_index * 10 +
            turning_density * 30 +
            len(freq_shifts[:10]) * 0.01
        ))

        return {
            'score': round(score, 3),
            'polarity_shift': round(polarity_shift, 3),
            'first_half_polarity': round(fh_polarity, 3),
            'second_half_polarity': round(sh_polarity, 3),
            'reversal_count': len(reversals),
            'reversal_index': round(reversal_index, 5),
            'reversals': reversals[:10],
            'vocabulary_shifts': freq_shifts[:20],
            'turning_vocabulary_density': round(turning_density, 5),
            'method': 'Periagoge Detection (Benardete Structural Reversal)',
            'precedent': (
                "Benardete's periagoge — the conversion or 'turning' reproduced in "
                "every Platonic dialogue (cf. Cave allegory, Republic 514a-521b); "
                "Aeschylus's pathei mathos (Agamemnon 177); Aristotle's complex plot "
                "with reversal (peripeteia) and recognition (anagnorisis). The text "
                "leads the reader through an error that must be undergone before the "
                "truth can emerge. The second half inverts or deepens the first half's "
                "conclusions — not merely contradicting them but revealing the hidden "
                "necessity behind the original error."
            ),
            'interpretation': (
                'A text exhibiting periagoge structure leads the reader to a conclusion '
                'in its first half that is undermined, inverted, or radically deepened '
                'in the second half. A positive polarity shift means the text moves from '
                'critique to affirmation; a negative shift from affirmation to critique. '
                'High reversal counts (same-topic sentences with opposite polarity) signal '
                'that the text literally takes back what it first asserted. Turning '
                'vocabulary concentrated at the structural center marks the point of '
                'periagoge — the philosophical "turn" analogous to the cave-dweller\'s '
                'wrenching from shadow to light.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 21: LOGOS-ERGON (SPEECH-DEED) ANALYSIS
    # ------------------------------------------------------------------

    def analyze_logos_ergon(self) -> dict:
        """
        METHOD: Logos-Ergon (Speech-Deed) Analysis
        PRECEDENT: Benardete's central discovery that in Platonic dialogues and
                   Greek poetry there is an "argument IN the action" distinct from
                   the stated argument. From Encounters & Reflections: "I didn't
                   understand that there was in fact an argument IN the action."
                   Also: Herodotus's method of embedding arguments in stories
                   ("the argument is in the evidence and not imposed on it").
                   Socrates' Second Sailing introduction: "burstlike" vs.
                   "filamentlike" arguments; "the unexpected break and the
                   unexpected join in arguments."

        Technique:
        1. Detect speech-act markers vs. action markers in proximity
        2. Identify passages where what is SAID contradicts what is DONE/DESCRIBED
        3. Track the ratio of speech-framing to action-framing vocabulary
        4. Detect "burstlike" (sudden) vs. "filamentlike" (gradual) argument shifts
        """
        if len(self.sentences) < 10:
            return {'score': 0, 'method': 'Logos-Ergon Analysis', 'note': 'Text too short'}

        speech_markers = {
            'says', 'said', 'claims', 'claimed', 'argues', 'argued', 'asserts',
            'asserted', 'maintains', 'maintained', 'declares', 'declared',
            'states', 'stated', 'contends', 'insists', 'professes', 'teaches',
            'taught', 'proposes', 'proposed', 'speaks', 'spoke', 'tells', 'told',
            'replies', 'replied', 'answers', 'answered', 'asks', 'asked',
            'believes', 'believed', 'thinks', 'thought', 'holds', 'opinion',
        }
        action_markers = {
            'does', 'did', 'goes', 'went', 'acts', 'acted', 'performs',
            'performed', 'makes', 'made', 'takes', 'took', 'gives', 'gave',
            'comes', 'came', 'leaves', 'left', 'turns', 'turned', 'runs',
            'ran', 'sits', 'sat', 'stands', 'stood', 'walks', 'walked',
            'fights', 'fought', 'kills', 'killed', 'strikes', 'struck',
            'seizes', 'seized', 'flees', 'fled', 'enters', 'entered',
            'departs', 'departed', 'moves', 'moved', 'compels', 'compelled',
        }

        # Track speech-act and action densities per paragraph
        speech_paras = []
        action_paras = []
        mismatches = []

        for i, para in enumerate(self.paragraphs):
            words = [w.lower() for w in word_tokenize(para) if w.isalpha()]
            if len(words) < 10:
                continue
            speech_count = sum(1 for w in words if w in speech_markers)
            action_count = sum(1 for w in words if w in action_markers)
            speech_density = speech_count / len(words)
            action_density = action_count / len(words)
            speech_paras.append(speech_density)
            action_paras.append(action_density)

            # Detect paragraphs with BOTH high speech and high action (potential mismatch)
            if speech_density > 0.01 and action_density > 0.01:
                mismatches.append({
                    'paragraph_index': i,
                    'speech_density': round(speech_density, 4),
                    'action_density': round(action_density, 4),
                    'excerpt': para[:200],
                })

        # Detect "burstlike" argument shifts — sudden topic changes between adjacent paragraphs
        burstlike_shifts = 0
        filamentlike_shifts = 0
        for i in range(1, len(self.paragraphs)):
            prev_words = set(w.lower() for w in word_tokenize(self.paragraphs[i-1])
                             if w.isalpha() and w.lower() not in self.stop_words and len(w) > 3)
            curr_words = set(w.lower() for w in word_tokenize(self.paragraphs[i])
                             if w.isalpha() and w.lower() not in self.stop_words and len(w) > 3)
            if not prev_words or not curr_words:
                continue
            overlap = len(prev_words & curr_words) / max(len(prev_words | curr_words), 1)
            if overlap < 0.05:
                burstlike_shifts += 1
            elif 0.05 <= overlap < 0.20:
                filamentlike_shifts += 1

        avg_speech = sum(speech_paras) / max(len(speech_paras), 1)
        avg_action = sum(action_paras) / max(len(action_paras), 1)
        speech_action_ratio = avg_speech / max(avg_action, 0.0001)
        mismatch_rate = len(mismatches) / max(len(self.paragraphs), 1)

        score = min(1.0, (
            mismatch_rate * 5 +
            min(1.0, burstlike_shifts / max(len(self.paragraphs), 1) * 10) * 0.3 +
            min(1.0, abs(1 - speech_action_ratio) * 0.3) +
            (0.2 if len(mismatches) > 5 else 0)
        ))

        return {
            'score': round(score, 3),
            'method': 'Logos-Ergon (Speech-Deed) Analysis (Benardete)',
            'speech_action_ratio': round(speech_action_ratio, 3),
            'mismatch_count': len(mismatches),
            'mismatch_rate': round(mismatch_rate, 4),
            'burstlike_shifts': burstlike_shifts,
            'filamentlike_shifts': filamentlike_shifts,
            'mismatches': mismatches[:10],
            'precedent': (
                "Benardete's discovery that Platonic dialogues contain an 'argument IN "
                "the action' irreducible to propositional summary. From Encounters: 'I "
                "didn't understand that there was in fact an argument IN the action.' "
                "Also: Herodotus's embedding of universal arguments in particular stories; "
                "Benardete's distinction between 'burstlike' and 'filamentlike' arguments "
                "(Socrates' Second Sailing, Introduction). The method detects where speech "
                "and action co-occur (potential for dramatic irony) and where arguments "
                "shift suddenly (burstlike) vs. gradually (filamentlike)."
            ),
            'interpretation': (
                'High mismatch counts indicate passages where speech-framing and action-framing '
                'co-occur — potential sites of dramatic irony where what is SAID contradicts '
                'or complicates what is DONE. High burstlike shift counts indicate sudden '
                'argument breaks (counterexamples, digressions); high filamentlike counts '
                'indicate periagogic/conversive arguments where premises are gradually deformed.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 22: ONOMASTIC / ETYMOLOGICAL ANALYSIS
    # ------------------------------------------------------------------

    def analyze_onomastic(self) -> dict:
        """
        METHOD: Onomastic (Name-Meaning) and Etymological Analysis
        PRECEDENT: Benardete's sustained attention to name-meanings as structural
                   keys. From The Bow and the Lyre: "Odysseus's name designates two
                   things, knowledge and lameness" (on Oedipus); "Odysseus has two
                   names... both are significant names, but they apparently signify
                   utterly different things. The plot of the Odyssey connects them."
                   From Encounters: the outis/metis pun as the key to Odysseus's
                   self-understanding. From Herodotean Inquiries: Herodotus's use
                   of significant names (Gyges, Candaules, Croesus).

        Technique:
        1. Detect proper nouns and their frequency distributions
        2. Identify etymological commentary (passages discussing name origins)
        3. Track name-puns and double-naming patterns
        4. Measure density of naming/calling vocabulary
        """
        if len(self.sentences) < 10:
            return {'score': 0, 'method': 'Onomastic Analysis', 'note': 'Text too short'}

        # Vocabulary for etymological/onomastic passages
        naming_vocab = {
            'name', 'named', 'names', 'naming', 'called', 'call', 'calls',
            'meaning', 'means', 'signifies', 'signify', 'designates', 'designate',
            'etymology', 'etymological', 'derives', 'derived', 'origin',
            'cognate', 'root', 'literally', 'properly', 'so-called',
            'translated', 'translation', 'pun', 'wordplay', 'double meaning',
            'homonym', 'epithet', 'title', 'alias', 'nickname',
        }

        # Detect proper nouns (capitalized words not at sentence start, > 1 char)
        proper_nouns = Counter()
        naming_passages = []

        for i, sent in enumerate(self.sentences):
            words = word_tokenize(sent)
            # Track proper nouns
            for j, w in enumerate(words):
                if j > 0 and w[0:1].isupper() and w.isalpha() and len(w) > 1:
                    proper_nouns[w] += 1

            # Detect etymological commentary
            sent_lower = sent.lower()
            sent_words = set(w.lower() for w in words if w.isalpha())
            naming_hits = sent_words & naming_vocab
            if len(naming_hits) >= 2 or ('name' in sent_lower and any(
                w in sent_lower for w in ['means', 'signif', 'called', 'designat'])):
                naming_passages.append({
                    'sentence_index': i,
                    'naming_terms': list(naming_hits),
                    'excerpt': sent[:200],
                })

        # Detect multiple-naming: proper nouns that appear with different referent patterns
        # (e.g., "Odysseus" and "No One" referring to same entity)
        top_names = proper_nouns.most_common(30)

        # Calculate naming density across the text
        all_words = [w.lower() for w in self.words if w.isalpha()]
        naming_count = sum(1 for w in all_words if w in naming_vocab)
        naming_density = naming_count / max(len(all_words), 1)

        # Proper noun diversity relative to text length
        pn_diversity = len(proper_nouns) / max(len(all_words) / 100, 1)  # per 100 words

        score = min(1.0, (
            naming_density * 50 +
            min(1.0, len(naming_passages) / max(len(self.sentences) / 20, 1)) * 0.3 +
            min(1.0, pn_diversity * 0.1) * 0.2
        ))

        return {
            'score': round(score, 3),
            'method': 'Onomastic / Etymological Analysis (Benardete)',
            'naming_density': round(naming_density, 5),
            'naming_passage_count': len(naming_passages),
            'naming_passages': naming_passages[:10],
            'proper_noun_count': len(proper_nouns),
            'top_proper_nouns': top_names[:20],
            'proper_noun_diversity': round(pn_diversity, 3),
            'precedent': (
                "Benardete's attention to name-meanings as structural keys in Greek poetry "
                "and Platonic dialogues. Oedipus's name = knowledge + lameness; Odysseus's "
                "two names (Odysseus/Outis) signify utterly different things yet are connected "
                "by the plot; the outis/metis pun encodes the relation of anonymity and mind. "
                "Herodotus's significant names (Gyges = 'covered', Croesus linked to gold). "
                "A high score indicates the text is rich in etymological commentary and "
                "name-based argumentation."
            ),
            'interpretation': (
                'High naming density and many etymological passages suggest the author treats '
                'names as philosophically significant — a hallmark of esoteric writing in the '
                'Platonic-Benardete tradition, where "the surface of things is the heart of '
                'things" and names encode compressed arguments about the nature of their bearers.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 23: RECOGNITION SCENE / CONCEALMENT-TEST-REVEAL
    # ------------------------------------------------------------------

    def analyze_recognition_structure(self) -> dict:
        """
        METHOD: Recognition Scene / Concealment-Test-Reveal Structure Detection
        PRECEDENT: Benardete on the Odyssey: identity is not given but achieved
                   through narrative. Odysseus's concealment, testing, and
                   progressive self-revelation constitutes the plot structure.
                   "Through speech and action it discovers the things that conceal
                   either two in one or one in two" (The Bow and the Lyre, Preface).
                   Also: Aristotle's anagnorisis (Poetics 1452a29-b8) as recognition
                   paired with reversal (peripeteia).

        Technique:
        1. Track concealment vocabulary across the text
        2. Track testing/trial vocabulary
        3. Track revelation/recognition vocabulary
        4. Detect sequential patterns: concealment→test→reveal
        """
        if len(self.sentences) < 10:
            return {'score': 0, 'method': 'Recognition Structure Analysis', 'note': 'Text too short'}

        concealment_vocab = {
            'hide', 'hides', 'hidden', 'hiding', 'conceal', 'conceals', 'concealed',
            'concealing', 'concealment', 'disguise', 'disguised', 'disguises',
            'mask', 'masked', 'masks', 'masking', 'cover', 'covered', 'covering',
            'secret', 'secretly', 'secrecy', 'invisible', 'unseen', 'unknown',
            'anonymous', 'anonymity', 'incognito', 'pretend', 'pretends', 'pretending',
            'impersonate', 'impersonates', 'impersonation', 'cloak', 'cloaked',
            'veil', 'veiled', 'veiling', 'screen', 'screened', 'obscure', 'obscured',
            'suppress', 'suppressed', 'withhold', 'withheld', 'dissemble', 'dissembling',
        }
        testing_vocab = {
            'test', 'tests', 'tested', 'testing', 'trial', 'trials', 'try', 'tries',
            'tried', 'trying', 'prove', 'proves', 'proved', 'proving', 'proof',
            'examine', 'examines', 'examined', 'examination', 'inspect', 'inspected',
            'question', 'questioned', 'questioning', 'challenge', 'challenged',
            'verify', 'verified', 'assess', 'assessed', 'probe', 'probed', 'probing',
            'scrutinize', 'scrutinized', 'investigate', 'investigated',
        }
        revelation_vocab = {
            'reveal', 'reveals', 'revealed', 'revealing', 'revelation', 'disclose',
            'disclosed', 'disclosing', 'disclosure', 'discover', 'discovers',
            'discovered', 'discovering', 'discovery', 'recognize', 'recognizes',
            'recognized', 'recognition', 'unmask', 'unmasked', 'unmasking',
            'uncover', 'uncovered', 'uncovering', 'expose', 'exposed', 'exposing',
            'manifest', 'manifested', 'manifestation', 'show', 'shows', 'shown',
            'showing', 'apparent', 'appear', 'appears', 'appeared', 'appearing',
            'identity', 'identify', 'identified', 'identifying', 'identification',
        }

        # Track density across text thirds
        thirds = [
            self.sentences[:len(self.sentences)//3],
            self.sentences[len(self.sentences)//3:2*len(self.sentences)//3],
            self.sentences[2*len(self.sentences)//3:],
        ]

        phase_densities = []
        for third in thirds:
            all_words_t = []
            for sent in third:
                all_words_t.extend(w.lower() for w in word_tokenize(sent) if w.isalpha())
            total = max(len(all_words_t), 1)
            c = sum(1 for w in all_words_t if w in concealment_vocab) / total
            t = sum(1 for w in all_words_t if w in testing_vocab) / total
            r = sum(1 for w in all_words_t if w in revelation_vocab) / total
            phase_densities.append({'concealment': round(c, 5), 'testing': round(t, 5), 'revelation': round(r, 5)})

        # Check for the ideal pattern: concealment highest in first third, testing in middle, revelation in last
        ideal_pattern = (
            phase_densities[0]['concealment'] >= phase_densities[2]['concealment'] and
            phase_densities[1]['testing'] >= max(phase_densities[0]['testing'], phase_densities[2]['testing']) and
            phase_densities[2]['revelation'] >= phase_densities[0]['revelation']
        )

        # Overall vocabulary presence
        all_words = [w.lower() for w in self.words if w.isalpha()]
        total_words = max(len(all_words), 1)
        c_total = sum(1 for w in all_words if w in concealment_vocab)
        t_total = sum(1 for w in all_words if w in testing_vocab)
        r_total = sum(1 for w in all_words if w in revelation_vocab)
        combined_density = (c_total + t_total + r_total) / total_words

        score = min(1.0, (
            combined_density * 30 +
            (0.3 if ideal_pattern else 0) +
            min(0.3, (c_total + t_total + r_total) / max(len(self.sentences), 1) * 0.5)
        ))

        return {
            'score': round(score, 3),
            'method': 'Recognition Scene / Concealment-Test-Reveal (Benardete)',
            'phase_densities': phase_densities,
            'ideal_pattern_detected': ideal_pattern,
            'concealment_count': c_total,
            'testing_count': t_total,
            'revelation_count': r_total,
            'combined_density': round(combined_density, 5),
            'precedent': (
                "Benardete on the Odyssey: identity is not given but achieved through "
                "narrative. The concealment→test→reveal structure is the deep grammar of "
                "the Odyssey and of Platonic dialogue alike. 'Through speech and action it "
                "discovers the things that conceal either two in one or one in two' (Bow "
                "and the Lyre). Also: Aristotle's anagnorisis — recognition as the pivot "
                "of tragic plot, paired with peripeteia (reversal)."
            ),
            'interpretation': (
                'A text exhibiting the concealment→test→reveal pattern moves from hiddenness '
                'toward disclosure — the narrative structure of both the Odyssey and the '
                'Platonic dialogue. The ideal pattern shows concealment vocabulary concentrated '
                'early, testing in the middle, and revelation at the end. High scores suggest '
                'the text enacts a recognition scene, making the reader undergo the process '
                'of discovery rather than simply being told the conclusion.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 24: NOMOS-PHYSIS (CUSTOM-NATURE) DETECTION
    # ------------------------------------------------------------------

    def analyze_nomos_physis(self) -> dict:
        """
        METHOD: Nomos-Physis (Convention vs. Nature) Detection
        PRECEDENT: Benardete's Herodotean Inquiries: Herodotus's method of
                   "looking at alien customs to reveal one's own." The Gyges/Candaules
                   story as paradigm: eyes vs. ears, shame vs. knowledge, the seen
                   vs. the heard. "To discover the human beneath the infinite disguises
                   of custom." Also: Benardete on the Republic — the noble lie as
                   naturalizing law and legalizing nature. Nomos vs. physis is the
                   fundamental opposition of Greek Enlightenment thought.

        Technique:
        1. Track nomos vocabulary (law, custom, convention, tradition, rule)
        2. Track physis vocabulary (nature, natural, by nature, innate, born)
        3. Measure co-occurrence and opposition patterns
        4. Detect "alien-looking" passages (comparative customs, foreign practices)
        """
        if len(self.sentences) < 10:
            return {'score': 0, 'method': 'Nomos-Physis Analysis', 'note': 'Text too short'}

        nomos_vocab = {
            'law', 'laws', 'lawful', 'unlawful', 'legal', 'illegal',
            'custom', 'customs', 'customary', 'convention', 'conventional',
            'tradition', 'traditional', 'traditions', 'rule', 'rules',
            'regulation', 'established', 'institution', 'institutional',
            'opinion', 'opinions', 'belief', 'beliefs', 'belief',
            'agreed', 'agreement', 'contract', 'oath', 'decree',
            'prohibition', 'forbidden', 'permitted', 'allowed',
            'obey', 'obedience', 'disobey', 'disobedience',
            'shame', 'shameful', 'shameless', 'modesty', 'decency',
            'propriety', 'impropriety', 'acceptable', 'unacceptable',
        }
        physis_vocab = {
            'nature', 'natural', 'naturally', 'natures', 'innate',
            'born', 'birth', 'inborn', 'native', 'inherent',
            'instinct', 'instinctive', 'spontaneous', 'organic',
            'necessary', 'necessity', 'inevitable', 'compel', 'compelled',
            'force', 'forces', 'forced', 'power', 'capacity',
            'body', 'bodies', 'bodily', 'desire', 'desires',
            'passion', 'passions', 'appetite', 'appetites',
            'species', 'kind', 'class', 'genus', 'breed',
        }

        # Track densities across text
        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        nomos_count = sum(1 for w in all_words if w in nomos_vocab)
        physis_count = sum(1 for w in all_words if w in physis_vocab)
        nomos_density = nomos_count / total
        physis_density = physis_count / total

        # Detect co-occurrence in sentences
        co_occurrences = []
        for i, sent in enumerate(self.sentences):
            sent_words = set(w.lower() for w in word_tokenize(sent) if w.isalpha())
            n_hits = sent_words & nomos_vocab
            p_hits = sent_words & physis_vocab
            if n_hits and p_hits:
                co_occurrences.append({
                    'sentence_index': i,
                    'nomos_terms': list(n_hits),
                    'physis_terms': list(p_hits),
                    'excerpt': sent[:200],
                })

        # Detect comparative/alien-looking passages
        comparative_vocab = {
            'barbarian', 'barbarians', 'foreign', 'foreigner', 'foreigners',
            'alien', 'stranger', 'strangers', 'other peoples', 'other nations',
            'compare', 'comparison', 'contrast', 'differ', 'different', 'difference',
            'whereas', 'unlike', 'similar', 'similarly', 'resemble', 'resembles',
            'greek', 'greeks', 'persian', 'persians', 'egyptian', 'egyptians',
            'practice', 'practices', 'rite', 'rites', 'ritual', 'rituals',
            'worship', 'worships', 'worshipped', 'sacrifice', 'sacrifices',
        }
        comparative_count = sum(1 for w in all_words if w in comparative_vocab)
        comparative_density = comparative_count / total

        co_occurrence_rate = len(co_occurrences) / max(len(self.sentences), 1)

        score = min(1.0, (
            (nomos_density + physis_density) * 20 +
            co_occurrence_rate * 10 +
            comparative_density * 15 +
            (0.2 if nomos_count > 10 and physis_count > 10 else 0)
        ))

        return {
            'score': round(score, 3),
            'method': 'Nomos-Physis (Convention vs. Nature) Detection (Benardete/Herodotus)',
            'nomos_density': round(nomos_density, 5),
            'physis_density': round(physis_density, 5),
            'nomos_count': nomos_count,
            'physis_count': physis_count,
            'co_occurrence_count': len(co_occurrences),
            'co_occurrence_rate': round(co_occurrence_rate, 4),
            'comparative_density': round(comparative_density, 5),
            'co_occurrences': co_occurrences[:10],
            'precedent': (
                "Benardete's Herodotean Inquiries: 'To discover the human beneath the "
                "infinite disguises of custom.' Herodotus's method of juxtaposing alien "
                "customs to reveal what is truly natural vs. merely conventional. The "
                "Gyges/Candaules story: the tension between seeing (physis) and hearing "
                "(nomos), between shame (convention) and knowledge (nature). The Republic: "
                "the noble lie 'naturalizes the law' (first part) and 'legalizes nature' "
                "(second part) — showing the inseparability of nomos and physis."
            ),
            'interpretation': (
                'High densities of both nomos and physis vocabulary, especially when '
                'co-occurring, suggest the text is grappling with the nature/convention '
                'distinction central to Greek thought and to esoteric writing. Comparative '
                'passages (looking at alien customs) indicate the Herodotean method of '
                'using the foreign to reveal the problematic character of one\'s own assumptions.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 25: IMPOSSIBLE ARITHMETIC / POETIC DIALECTIC
    # ------------------------------------------------------------------

    def analyze_impossible_arithmetic(self) -> dict:
        """
        METHOD: Impossible Arithmetic / Poetic Dialectic
        PRECEDENT: Benardete's The Bow and the Lyre: "The poet divides what is
                   necessarily one and unites what is necessarily two. He practices
                   his own kind of dialectic in which the truth shows up in two
                   spurious forms." Also: "'It could not be,' Oedipus says, 'that
                   one could be equal to many'" (OT 845). The plot as "disclosure
                   of impossibilities or apparent impossibilities." Socrates' Second
                   Sailing introduction: the paradox that "life no less than death
                   is both one and two."

        Technique:
        1. Detect impossibility language co-occurring with unity/plurality terms
        2. Track one/many, same/different, and arithmetic paradox language
        3. Identify passages with "impossible yet true" structures
        4. Measure density of dialectical impossibility markers
        """
        if len(self.sentences) < 10:
            return {'score': 0, 'method': 'Impossible Arithmetic Analysis', 'note': 'Text too short'}

        impossibility_vocab = {
            'impossible', 'impossibility', 'impossibilities', 'cannot',
            'absurd', 'absurdity', 'paradox', 'paradoxical', 'paradoxes',
            'contradiction', 'contradictory', 'contradicts', 'inconceivable',
            'incompatible', 'incoherent', 'incoherence', 'unintelligible',
            'ridiculous', 'preposterous', 'unthinkable',
        }
        arithmetic_vocab = {
            'one', 'two', 'three', 'many', 'both', 'neither', 'either',
            'same', 'different', 'equal', 'unequal', 'identical', 'other',
            'single', 'double', 'triple', 'whole', 'part', 'parts',
            'unity', 'duality', 'plurality', 'multiplicity',
            'divide', 'divides', 'divided', 'division', 'divisions',
            'unite', 'unites', 'united', 'union', 'unions',
            'separate', 'separates', 'separated', 'separation',
            'combine', 'combines', 'combined', 'combination',
            'split', 'splits', 'merge', 'merges', 'merged',
            'together', 'apart', 'join', 'joins', 'joined',
        }
        impossibility_affirmation = {
            'yet', 'nevertheless', 'nonetheless', 'still', 'even so',
            'and yet', 'but', 'however', 'though', 'although',
            'must', 'must be', 'is', 'proves', 'turns out', 'shows',
        }

        # Track co-occurrences of impossibility + arithmetic
        poetic_dialectic_passages = []
        for i, sent in enumerate(self.sentences):
            sent_words = set(w.lower() for w in word_tokenize(sent) if w.isalpha())
            imp_hits = sent_words & impossibility_vocab
            arith_hits = sent_words & arithmetic_vocab
            if imp_hits and arith_hits:
                poetic_dialectic_passages.append({
                    'sentence_index': i,
                    'impossibility_terms': list(imp_hits),
                    'arithmetic_terms': list(arith_hits),
                    'excerpt': sent[:200],
                })

        # Track "impossible yet true" patterns (impossibility followed by affirmation)
        impossible_yet_true = 0
        for i in range(len(self.sentences) - 1):
            sent_words = set(w.lower() for w in word_tokenize(self.sentences[i]) if w.isalpha())
            next_words = set(w.lower() for w in word_tokenize(self.sentences[i+1]) if w.isalpha())
            if sent_words & impossibility_vocab and next_words & impossibility_affirmation:
                impossible_yet_true += 1

        # Overall densities
        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        imp_density = sum(1 for w in all_words if w in impossibility_vocab) / total
        arith_density = sum(1 for w in all_words if w in arithmetic_vocab) / total
        pd_rate = len(poetic_dialectic_passages) / max(len(self.sentences), 1)

        score = min(1.0, (
            pd_rate * 15 +
            imp_density * 40 +
            arith_density * 5 +
            impossible_yet_true / max(len(self.sentences), 1) * 10
        ))

        return {
            'score': round(score, 3),
            'method': 'Impossible Arithmetic / Poetic Dialectic (Benardete)',
            'impossibility_density': round(imp_density, 5),
            'arithmetic_density': round(arith_density, 5),
            'poetic_dialectic_passage_count': len(poetic_dialectic_passages),
            'poetic_dialectic_rate': round(pd_rate, 5),
            'impossible_yet_true_count': impossible_yet_true,
            'poetic_dialectic_passages': poetic_dialectic_passages[:10],
            'precedent': (
                "Benardete's The Bow and the Lyre: 'The poet divides what is necessarily "
                "one and unites what is necessarily two. He practices his own kind of "
                "dialectic in which the truth shows up in two spurious forms.' The plot "
                "as 'disclosure of impossibilities or apparent impossibilities.' The "
                "Oedipal riddle: 'one could not be equal to many' yet proves to be so. "
                "Socrates' Second Sailing: 'life no less than death is both one and two.'"
            ),
            'interpretation': (
                'High scores indicate the text operates through productive impossibilities — '
                'presenting paradoxes that cannot be resolved propositionally but that the '
                'plot or argument resolves dramatically. This is the hallmark of "poetic '
                'dialectic": truth appearing in the guise of the impossible, the one showing '
                'up as many and the many revealing themselves as one.'
            ),
        }

    def analyze_rhetoric_of_concealment(self) -> dict:
        """Rosen on Montesquieu: Detect rhetoric of concealment — hidden design beneath disorder."""
        concealment_vocab = {
            'conceal', 'hidden', 'beneath', 'disguise', 'mask', 'veil', 'cloak', 'cover',
            'obscure', 'secret', 'design', 'plan', 'architecture', 'deceptive', 'misleading',
            'apparent disorder', 'seeming confusion'
        }
        design_vocab = {
            'design', 'inner plan', 'structure', 'order', 'system', 'deductive',
            'logical progression', 'architecture', 'framework', 'skeleton'
        }
        defensive_vocab = {
            'defensive', 'maneuver', 'charges', 'accusation', 'persecution', 'censorship',
            'caution', 'prudence', 'index'
        }

        para_scores = []
        for para in self.paragraphs:
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            c_hits = len(para_words & concealment_vocab)
            d_hits = len(para_words & design_vocab)
            def_hits = len(para_words & defensive_vocab)
            co_occur = 1.0 if (c_hits > 0 and d_hits > 0) else 0.5 if (c_hits > 0 or d_hits > 0) else 0
            para_scores.append({
                'concealment': c_hits,
                'design': d_hits,
                'defensive': def_hits,
                'co_occurrence_boost': co_occur,
                'combined_score': c_hits + d_hits + def_hits + co_occur,
            })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        c_density = sum(1 for w in all_words if w in concealment_vocab) / total
        d_density = sum(1 for w in all_words if w in design_vocab) / total
        def_density = sum(1 for w in all_words if w in defensive_vocab) / total
        avg_co_occur = sum(p['co_occurrence_boost'] for p in para_scores) / max(len(para_scores), 1)

        score = min(1.0, (
            c_density * 30 + d_density * 25 + def_density * 15 + avg_co_occur * 10
        ))

        return {
            'score': round(score, 3),
            'method': 'Rhetoric of Concealment (Rosen on Montesquieu)',
            'concealment_density': round(c_density, 5),
            'design_density': round(d_density, 5),
            'defensive_density': round(def_density, 5),
            'co_occurrence_boost': round(avg_co_occur, 5),
            'precedent': (
                "Rosen, 'The Elusiveness of the Ordinary': Montesquieu's Spirit of the Laws "
                "conceals a deductive structure beneath a 'somewhat disheveled surface.' The "
                "apparent disorder is a 'rhetoric of concealment.'"
            ),
            'interpretation': (
                'High scores indicate the text employs deliberate surface disorder to conceal '
                'an underlying logical structure. The author announces design while appearing '
                'unsystematic—a defensive strategy distinguishing moderate Enlightenment from '
                'revolutionary esotericism.'
            ),
        }

    def analyze_transcendental_ambiguity(self) -> dict:
        """Rosen on Kant: Detect deliberately unresolved double meanings serving system."""
        ambiguity_markers = {
            'ambiguous', 'ambiguity', 'double meaning', 'two senses', 'equivocal',
            'both', 'and', 'simultaneously', 'paradox', 'tension', 'oscillation'
        }
        resistance_vocab = {
            'cannot be defined', 'resists definition', 'irreducible', 'not reducible',
            'transcends', 'distinction'
        }
        multi_sense = {
            'in one sense', 'in another', 'perspective', 'on the one hand', 'on the other'
        }

        ambig_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            amb_hits = len(para_words & ambiguity_markers)
            res_hits = len(para_words & resistance_vocab)
            multi_hits = len(para_words & multi_sense)
            if amb_hits > 0 or res_hits > 0 or multi_hits > 0:
                ambig_passages.append({
                    'paragraph': i,
                    'ambiguity_markers': amb_hits,
                    'resistance_markers': res_hits,
                    'multi_sense_markers': multi_hits,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        ambig_density = sum(1 for w in all_words if w in ambiguity_markers) / total
        resist_density = sum(1 for w in all_words if w in resistance_vocab) / total
        multi_density = sum(1 for w in all_words if w in multi_sense) / total

        score = min(1.0, (
            ambig_density * 35 + resist_density * 30 + multi_density * 20 +
            len(ambig_passages) / max(len(self.paragraphs), 1) * 15
        ))

        return {
            'score': round(score, 3),
            'method': 'Transcendental Ambiguity (Rosen on Kant)',
            'ambiguity_marker_density': round(ambig_density, 5),
            'resistance_marker_density': round(resist_density, 5),
            'multi_sense_density': round(multi_density, 5),
            'ambiguous_passage_count': len(ambig_passages),
            'ambiguous_passages': ambig_passages[:5],
            'precedent': (
                "Rosen, 'Hermeneutics as Politics': Kant's key terms (freedom, spontaneity, "
                "autonomy) carry deliberately unresolved double meanings. The ambiguity is "
                "'transcendental' because it is a condition of possibility for the system itself."
            ),
            'interpretation': (
                'High scores indicate the text employs productive ambiguity as a structural '
                'feature, not a flaw. Key terms remain equivocal because this ambiguity enables '
                'the philosophical or political argument. The reader must hold multiple senses '
                'in tension rather than collapsing them into univocity.'
            ),
        }

    def analyze_rhetoric_of_frankness(self) -> dict:
        """Rosen: Detect performative transparency as a form of concealment."""
        frankness_markers = {
            'frankly', 'openly', 'honestly', 'candidly', 'confess', 'plainly',
            'clear', 'conceal', 'disguise', 'transparent', 'straightforward'
        }
        self_ref_honesty = {
            'being honest', 'truth is', 'openly', 'make no secret', 'everyone can see'
        }
        enlightenment_daring = {
            'dare', 'courage', 'resolve', 'maturity', 'bold', 'fearless'
        }
        hedging = {
            'perhaps', 'seems', 'one might', 'arguably', 'certain sense', 'in a way'
        }

        frank_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            frank_hits = len(para_words & frankness_markers)
            self_ref = len(para_words & self_ref_honesty)
            dare_hits = len(para_words & enlightenment_daring)
            hedge_hits = len(para_words & hedging)
            performative = 1.5 if (frank_hits > 0 and hedge_hits > 0) else 1.0 if frank_hits > 0 else 0
            if frank_hits > 0:
                frank_passages.append({
                    'paragraph': i,
                    'frankness_markers': frank_hits,
                    'hedging_markers': hedge_hits,
                    'performative_score': performative,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        frank_density = sum(1 for w in all_words if w in frankness_markers) / total
        dare_density = sum(1 for w in all_words if w in enlightenment_daring) / total
        hedge_density = sum(1 for w in all_words if w in hedging) / total
        performative_count = sum(1 for p in frank_passages if p['hedging_markers'] > 0)

        score = min(1.0, (
            frank_density * 30 + dare_density * 20 + hedge_density * 5 +
            performative_count / max(len(frank_passages), 1) * 20
        ))

        return {
            'score': round(score, 3),
            'method': 'Rhetoric of Frankness (Rosen)',
            'frankness_density': round(frank_density, 5),
            'daring_density': round(dare_density, 5),
            'hedging_density': round(hedge_density, 5),
            'frank_passage_count': len(frank_passages),
            'performative_frankness_count': performative_count,
            'frank_passages': frank_passages[:5],
            'precedent': (
                "Rosen, 'Hermeneutics as Politics': Kant's rhetoric of frankness ('dare to know') "
                "is itself rhetorical. Declarations of openness can function as concealment by "
                "deflecting attention from what remains hidden. The frank author says 'I am hiding "
                "nothing'—which is itself a form of hiding."
            ),
            'interpretation': (
                'High scores indicate the author uses performative transparency as a strategy. '
                'Passages declaring frankness that are simultaneously hedged suggest ironic '
                'self-awareness: the author announces honesty while actually concealing. This is '
                'a sophisticated defensive maneuver appropriate to texts under potential scrutiny.'
            ),
        }

    def analyze_intuition_analysis_dialectic(self) -> dict:
        """Rosen, The Limits of Analysis: Appeal to non-discursive knowing."""
        intuition_vocab = {
            'intuition', 'intuitive', 'see', 'seeing', 'vision', 'grasp', 'apprehend',
            'perceive', 'self-evident', 'immediately', 'pre-analytical', 'pre-theoretical',
            'given', 'anschauung'
        }
        analysis_limit = {
            'cannot be analyzed', 'limits of analysis', 'cannot be defined', 'indefinable',
            'primitive', 'logically simple', 'hint', 'cannot be formalized', 'resists formalization'
        }
        looking_metaphors = {
            'look at', 'look into', 'gaze', 'contemplate', 'insight', 'see', 'vision'
        }
        reflexive = {
            'concept of concept', 'definition of definition', 'analysis of analysis',
            'knowledge of knowledge'
        }

        int_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            int_hits = len(para_words & intuition_vocab)
            lim_hits = len(para_words & analysis_limit)
            look_hits = len(para_words & looking_metaphors)
            refl_hits = len(para_words & reflexive)
            if int_hits > 0 or lim_hits > 0:
                int_passages.append({
                    'paragraph': i,
                    'intuition_markers': int_hits,
                    'limit_markers': lim_hits,
                    'looking_markers': look_hits,
                    'reflexive_markers': refl_hits,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        int_density = sum(1 for w in all_words if w in intuition_vocab) / total
        lim_density = sum(1 for w in all_words if w in analysis_limit) / total
        refl_density = sum(1 for w in all_words if w in reflexive) / total

        score = min(1.0, (
            int_density * 25 + lim_density * 30 + refl_density * 35 +
            len(int_passages) / max(len(self.paragraphs), 1) * 10
        ))

        return {
            'score': round(score, 3),
            'method': 'Intuition-Analysis Dialectic (Rosen)',
            'intuition_density': round(int_density, 5),
            'analysis_limit_density': round(lim_density, 5),
            'reflexive_density': round(refl_density, 5),
            'intuitive_passage_count': len(int_passages),
            'intuitive_passages': int_passages[:5],
            'precedent': (
                "Rosen, 'The Limits of Analysis': All analysis depends on prior intuition "
                "(non-discursive 'seeing'). The concept of 'concept' cannot itself be defined "
                "conceptually. Frege acknowledged 'hints' (Winke) for logically simple primitives "
                "that cannot be analyzed further."
            ),
            'interpretation': (
                'High scores indicate the text acknowledges its own limits—the author appeals to '
                'direct seeing, intuition, or primitive terms that resist further analysis. This '
                'appeal to the non-discursive marks a boundary of rational argument and signals '
                'that certain truths are pre-analytical or require contemplative seeing.'
            ),
        }

    def analyze_logographic_necessity(self) -> dict:
        """Benardete: Dramatic/formal constraints carry philosophical content."""
        constraint_vocab = {
            'conditions for', 'constraints', 'necessity', 'had to be', 'could not be otherwise',
            'required', 'demanded', 'forced', 'inevitable', 'dramatic necessity'
        }
        form_content = {
            'form carries', 'structure reveals', 'shows rather', 'enacts', 'dramatizes',
            'performs', 'embodies', 'the form', 'the structure'
        }
        narrative_vocab = {
            'dialogue', 'interlocutor', 'dramatic', 'scene', 'setting', 'character',
            'plot', 'narrative', 'dialogue form', 'exchange'
        }

        logo_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            const_hits = len(para_words & constraint_vocab)
            form_hits = len(para_words & form_content)
            narr_hits = len(para_words & narrative_vocab)
            if const_hits > 0 or form_hits > 0:
                logo_passages.append({
                    'paragraph': i,
                    'constraint_markers': const_hits,
                    'form_content_markers': form_hits,
                    'narrative_markers': narr_hits,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        const_density = sum(1 for w in all_words if w in constraint_vocab) / total
        form_density = sum(1 for w in all_words if w in form_content) / total
        narr_density = sum(1 for w in all_words if w in narrative_vocab) / total

        score = min(1.0, (
            const_density * 25 + form_density * 35 + narr_density * 20 +
            len(logo_passages) / max(len(self.paragraphs), 1) * 20
        ))

        return {
            'score': round(score, 3),
            'method': 'Logographic Necessity (Benardete)',
            'constraint_density': round(const_density, 5),
            'form_content_density': round(form_density, 5),
            'narrative_density': round(narr_density, 5),
            'logographic_passage_count': len(logo_passages),
            'logographic_passages': logo_passages[:5],
            'precedent': (
                "Benardete (Freedom and the Human Person): 'It is not the arguments in Plato "
                "that convey the truth but the conditions for the arguments that carry the logos. "
                "In the Platonic universe necessity is the teleology.' Dramatic/formal constraints "
                "ARE the philosophical argument."
            ),
            'interpretation': (
                'High scores indicate the text\'s formal features—dialogue structure, dramatic '
                'constraints, narrative necessity—carry philosophical weight. What cannot be said '
                'directly is shown through the form. The condition of possibility for the argument '
                'IS the argument.'
            ),
        }

    def analyze_theological_disavowal(self) -> dict:
        """Rosen: Theology disguised as philosophy through substitution."""
        theological_vocab = {
            'god', 'divine', 'providence', 'creation', 'grace', 'immortality', 'soul',
            'redemption', 'salvation', 'sin', 'sacred', 'holy', 'revelation', 'faith',
            'prayer', 'heaven', 'eternal life', 'blessed', 'damnation'
        }
        philosophical_subs = {
            'first principle', 'ground', 'condition of possibility', 'transcendental',
            'noumenal', 'absolute', 'unconditional', 'postulate', 'regulative idea',
            'necessary presupposition', 'categorical imperative', 'in-itself'
        }
        disavowal_markers = {
            'not theological', 'purely philosophical', 'without recourse to', 'independent of',
            'faith', 'secular', 'rational grounds', 'reason alone'
        }

        theo_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            theo_hits = len(para_words & theological_vocab)
            phil_hits = len(para_words & philosophical_subs)
            disav_hits = len(para_words & disavowal_markers)
            co_occur = 1.5 if (theo_hits > 0 and disav_hits > 0) else 1.0 if theo_hits > 0 else 0
            if theo_hits > 0:
                theo_passages.append({
                    'paragraph': i,
                    'theological_terms': theo_hits,
                    'philosophical_subs_terms': phil_hits,
                    'disavowal_markers': disav_hits,
                    'co_occurrence_boost': co_occur,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        theo_density = sum(1 for w in all_words if w in theological_vocab) / total
        phil_density = sum(1 for w in all_words if w in philosophical_subs) / total
        disav_density = sum(1 for w in all_words if w in disavowal_markers) / total
        avg_co_occur = sum(p['co_occurrence_boost'] for p in theo_passages) / max(len(theo_passages), 1)

        score = min(1.0, (
            theo_density * 25 + phil_density * 20 + disav_density * 30 + avg_co_occur * 15
        ))

        return {
            'score': round(score, 3),
            'method': 'Theological Disavowal (Rosen)',
            'theological_density': round(theo_density, 5),
            'philosophical_substitute_density': round(phil_density, 5),
            'disavowal_density': round(disav_density, 5),
            'theo_passage_count': len(theo_passages),
            'theological_passages': theo_passages[:5],
            'precedent': (
                "Rosen, 'Hermeneutics as Politics': Modern philosophy reproduces theological "
                "structures (God, creation, grace, immortality) through philosophical terminology "
                "without acknowledging religious origins. Kant's 'postulates of practical reason' "
                "are theology in disguise."
            ),
            'interpretation': (
                'High scores indicate theological vocabulary appears in the text, often paired '
                'with claims of purely philosophical (non-theological) content. This suggests the '
                'author is translating theological concepts into philosophical vocabulary—a '
                'strategy common in texts seeking to evade religious censorship or dogmatism.'
            ),
        }

    def analyze_defensive_writing(self) -> dict:
        """Rosen/Strauss: Detect preemptive rebuttals, disclaimers, and excessive qualification."""
        defensive_markers = {
            'i do not mean', 'let no one', 'far be it', 'hasten to add', 'should not be taken',
            'would not wish', 'contrary to', 'i do not wish', 'understand me', 'no such thing'
        }
        orthodox_appeals = {
            'in accordance with', 'tradition teaches', 'as the ancients', 'as the church',
            'as scripture', 'as is well known', 'as everyone', 'no reasonable person',
            'the wise', 'the learned'
        }
        qualification_vocab = {
            'to be sure', 'of course', 'naturally', 'needless to say', 'goes without saying',
            'admittedly', 'granted', 'certainly', 'undoubtedly', 'no doubt'
        }
        preempt_vocab = {
            'one might object', 'some will say', 'it may seem', 'the objection', 'critics will',
            'some argue', 'one might think', 'perhaps it will be objected'
        }

        def_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            def_hits = len(para_words & defensive_markers)
            orth_hits = len(para_words & orthodox_appeals)
            qual_hits = len(para_words & qualification_vocab)
            pree_hits = len(para_words & preempt_vocab)
            total_hits = def_hits + orth_hits + qual_hits + pree_hits
            if total_hits > 0:
                def_passages.append({
                    'paragraph': i,
                    'defensive_markers': def_hits,
                    'orthodox_appeals': orth_hits,
                    'qualifications': qual_hits,
                    'preemptive_rebuttals': pree_hits,
                    'total_defensive_score': total_hits,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        def_density = sum(1 for w in all_words if w in defensive_markers) / total
        orth_density = sum(1 for w in all_words if w in orthodox_appeals) / total
        qual_density = sum(1 for w in all_words if w in qualification_vocab) / total
        pree_density = sum(1 for w in all_words if w in preempt_vocab) / total
        multi_cat = sum(1 for p in def_passages if sum([
            p['defensive_markers']>0, p['orthodox_appeals']>0, p['qualifications']>0, p['preemptive_rebuttals']>0
        ]) > 1) / max(len(def_passages), 1)

        score = min(1.0, (
            def_density * 20 + orth_density * 20 + qual_density * 15 + pree_density * 25 + multi_cat * 20
        ))

        return {
            'score': round(score, 3),
            'method': 'Defensive Writing (Rosen/Strauss)',
            'defensive_density': round(def_density, 5),
            'orthodox_appeal_density': round(orth_density, 5),
            'qualification_density': round(qual_density, 5),
            'preemptive_density': round(pree_density, 5),
            'defensive_passage_count': len(def_passages),
            'multi_category_ratio': round(multi_cat, 5),
            'defensive_passages': def_passages[:5],
            'precedent': (
                "Rosen, 'The Elusiveness of the Ordinary': Montesquieu's preface is a 'defensive "
                "maneuver' against charges of atheism and amoralism. His work was placed on the Index. "
                "The moderate Enlightenment required defensive strategies distinct from revolutionary "
                "esotericism."
            ),
            'interpretation': (
                'High scores indicate the author employs multiple defensive strategies simultaneously: '
                'disclaimers, appeals to orthodoxy, excessive qualification, and preemptive rebuttals. '
                'This defensive layering suggests the text addresses a potentially hostile audience—a '
                'hallmark of texts written under threat of censorship or doctrinal persecution.'
            ),
        }

    def analyze_nature_freedom_oscillation(self) -> dict:
        """Rosen on Montesquieu: Systematic oscillation between necessity and freedom."""
        nature_vocab = {
            'nature', 'natural law', 'determined', 'necessity', 'determined by', 'law of nature',
            'universal', 'invariable', 'fixed', 'regularity', 'instinct', 'mechanism',
            'cause', 'effect', 'natural', 'inevitable', 'necessary'
        }
        freedom_vocab = {
            'freedom', 'free', 'choice', 'will', 'voluntary', 'contingent', 'historical',
            'circumstance', 'diversity', 'culture', 'convention', 'arbitrary', 'open',
            'flexibility', 'autonomy', 'agent'
        }

        # Detect paragraph-level dominance
        nature_paras = []
        freedom_paras = []
        oscillations = 0

        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            nat_count = len(para_words & nature_vocab)
            free_count = len(para_words & freedom_vocab)

            if nat_count > free_count and nat_count > 0:
                nature_paras.append(i)
            elif free_count > nat_count and free_count > 0:
                freedom_paras.append(i)

        # Count alternations
        for i in range(len(self.paragraphs) - 1):
            para_i = set(w.lower() for w in word_tokenize(self.paragraphs[i]) if w.isalpha())
            para_next = set(w.lower() for w in word_tokenize(self.paragraphs[i+1]) if w.isalpha())
            nat_i = len(para_i & nature_vocab)
            free_i = len(para_i & freedom_vocab)
            nat_next = len(para_next & nature_vocab)
            free_next = len(para_next & freedom_vocab)

            if (nat_i > free_i and free_next > nat_next) or (free_i > nat_i and nat_next > free_next):
                oscillations += 1

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        nat_density = sum(1 for w in all_words if w in nature_vocab) / total
        free_density = sum(1 for w in all_words if w in freedom_vocab) / total
        switch_frequency = oscillations / max(len(self.paragraphs) - 1, 1)

        # Detect explicit tension acknowledgments
        tension_detected = False
        for sent in self.sentences:
            sent_words = sent.lower()
            if any(phrase in sent_words for phrase in ['tension', 'paradox', 'freedom and necessity', 'necessity and freedom']):
                tension_detected = True
                break

        score = min(1.0, (
            switch_frequency * 40 + nat_density * 15 + free_density * 15 +
            (1.5 if tension_detected else 1.0) * 10
        ))

        return {
            'score': round(score, 3),
            'method': 'Nature-Freedom Oscillation (Rosen on Montesquieu)',
            'nature_density': round(nat_density, 5),
            'freedom_density': round(free_density, 5),
            'oscillation_frequency': round(switch_frequency, 5),
            'oscillation_count': oscillations,
            'nature_dominant_paragraphs': len(nature_paras),
            'freedom_dominant_paragraphs': len(freedom_paras),
            'explicit_tension_acknowledged': tension_detected,
            'precedent': (
                "Rosen, 'The Elusiveness of the Ordinary': Montesquieu systematically oscillates "
                "between treating human behavior as determined by natural law and as free/open. "
                "This oscillation reflects genuine tension in human nature between necessity and "
                "freedom."
            ),
            'interpretation': (
                'High scores indicate the text alternates between deterministic and freedom-oriented '
                'vocabulary in a systematic pattern. Rather than resolving the tension between nature '
                'and freedom, the author highlights and maintains the oscillation—suggesting both are '
                'necessary and irreducible aspects of the human condition.'
            ),
        }

    # ------------------------------------------------------------------
    # METHOD 34: POSTMODERN MISREADING VULNERABILITY (Rosen)
    # ------------------------------------------------------------------

    def analyze_postmodern_misreading(self) -> dict:
        """
        METHOD: Postmodern Misreading Vulnerability Analysis
        PRECEDENT: Rosen, "Hermeneutics as Politics" and "Plato's Symposium" —
                   Rosen argues that postmodern/deconstructionist reading commits
                   specific hermeneutic errors: (1) importing Heidegger's "metaphysics
                   of presence" critique into texts where it doesn't apply, (2) reducing
                   silence and noetic perception to textuality, (3) dissolving authorial
                   intention into "play of signifiers", (4) treating rhetorical
                   accommodation as evidence of conceptual instability, (5) collapsing
                   the esoteric/exoteric distinction into undecidability.

        Technique: Two-track analysis. Track A identifies features of the text that
        postmodernism would latch onto (paradox, absence, metaphor, "presence"
        language) and predict where misreading is likeliest. Track B identifies
        features that postmodernism would miss (intentional design, audience
        accommodation, esoteric layers, noetic content, formal constraints as
        philosophical content). The ratio between the two produces a "misreading
        vulnerability" score.
        """
        # ---- TRACK A: What postmodernism would latch onto ----
        # Features that invite deconstruction/misreading

        pm_latch_vocab = {
            # presence/absence language postmodernism would seize on
            'presence', 'present', 'absent', 'absence', 'appear', 'appearance',
            'manifest', 'revelation', 'disclosed', 'disclose', 'visible',
            'invisible', 'hidden', 'concealed', 'surface', 'depth',
            # binary oppositions postmodernism would "deconstruct"
            'origin', 'original', 'copy', 'image', 'imitation', 'representation',
            'truth', 'illusion', 'reality', 'appearance', 'being', 'becoming',
            'same', 'other', 'identity', 'difference', 'one', 'many',
            # metaphors of writing/speech postmodernism would privilege
            'writing', 'written', 'text', 'speech', 'voice', 'silence',
            'sign', 'signify', 'meaning', 'interpretation', 'reading',
            # paradox/aporia language
            'paradox', 'contradiction', 'aporia', 'impossible', 'undecidable',
            'cannot be decided', 'indeterminate',
        }

        pm_misread_vocab = {
            # Derrida/Heidegger vocabulary — when found IN the analysis
            # (not in the primary text), signals postmodern reading
            'differance', 'différance', 'trace', 'traces', 'supplement',
            'supplementarity', 'dissemination', 'deconstruction', 'deconstructive',
            'archi-writing', 'logocentrism', 'logocentric', 'phonocentrism',
            'phallogocentrism', 'metaphysics of presence', 'onto-theology',
            'closure', 'under erasure', 'sous rature', 'play of signifiers',
            'iterability', 'undecidability', 'aporia',
        }

        # ---- TRACK B: What postmodernism would miss ----
        # Features Rosen identifies as invisible to postmodern reading

        pm_miss_vocab = {
            # Intentional design vocabulary
            'design', 'intention', 'purpose', 'deliberate', 'carefully',
            'constructed', 'planned', 'arranged', 'architecture', 'structure',
            'author', 'authored', 'composed',
            # Audience accommodation
            'audience', 'reader', 'listener', 'accommodate', 'adapted',
            'adjusted', 'addressed', 'suitable', 'appropriate', 'persuade',
            'medicinal', 'therapeutic', 'pedagogical',
            # Esoteric/exoteric distinction
            'esoteric', 'exoteric', 'concealment', 'caution', 'prudence',
            'persecution', 'censorship', 'dangerous', 'heterodox',
            # Noetic/intuitive perception
            'intuition', 'noetic', 'intellectual perception', 'direct apprehension',
            'insight', 'contemplation', 'recollection', 'anamnesis',
            # Formal constraints as content
            'dramatic', 'dialogue', 'interlocutor', 'character', 'setting',
            'dramatic context', 'formal constraint', 'form carries',
            # Nature/hierarchy
            'nature', 'natural', 'hierarchy', 'rank', 'order', 'eternal',
            'permanent', 'unchanging', 'universal',
        }

        # ---- SCAN TEXT ----
        latch_count = 0
        miss_count = 0
        misread_count = 0
        latch_paras = []
        miss_paras = []
        misread_paras = []

        for i, para in enumerate(self.paragraphs):
            words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            text_lower = para.lower()

            # Count latch-on features
            latch_hits = words & pm_latch_vocab
            # Also check multi-word phrases
            for phrase in ['metaphysics of presence', 'play of signifiers',
                           'cannot be decided', 'under erasure']:
                if phrase in text_lower:
                    latch_hits.add(phrase)

            # Count miss features
            miss_hits = words & pm_miss_vocab
            for phrase in ['intellectual perception', 'direct apprehension',
                           'dramatic context', 'formal constraint', 'form carries']:
                if phrase in text_lower:
                    miss_hits.add(phrase)

            # Count explicit postmodern vocabulary (already present)
            misread_hits = words & pm_misread_vocab
            for phrase in ['metaphysics of presence', 'play of signifiers',
                           'under erasure', 'sous rature', 'archi-writing']:
                if phrase in text_lower:
                    misread_hits.add(phrase)

            if len(latch_hits) >= 3:
                latch_count += 1
                latch_paras.append({
                    'paragraph': i + 1,
                    'latch_terms': list(latch_hits)[:10],
                    'excerpt': para[:200],
                })

            if len(miss_hits) >= 2:
                miss_count += 1
                miss_paras.append({
                    'paragraph': i + 1,
                    'miss_terms': list(miss_hits)[:10],
                    'excerpt': para[:200],
                })

            if misread_hits:
                misread_count += 1
                misread_paras.append({
                    'paragraph': i + 1,
                    'postmodern_terms': list(misread_hits),
                    'excerpt': para[:200],
                })

        n = max(len(self.paragraphs), 1)

        # Vulnerability: high latch-on density + low miss-feature density
        latch_ratio = latch_count / n
        miss_ratio = miss_count / n
        misread_ratio = misread_count / n

        # Vulnerability = features PM would exploit / features PM would miss
        # High score = text is very vulnerable to postmodern misreading
        # (many "deconstructible" features, few signals of intentional design)
        if miss_ratio > 0:
            vulnerability_ratio = latch_ratio / miss_ratio
        else:
            vulnerability_ratio = latch_ratio * 10  # no miss-features = high vulnerability

        # Already-postmodern score: does the text itself use PM vocabulary?
        already_pm = min(1.0, misread_ratio * 5)

        # Overall score: combines vulnerability + already-PM
        score = min(1.0, vulnerability_ratio * 0.3 + already_pm * 0.3 + latch_ratio * 2)

        return {
            'score': round(score, 3),
            'latch_on_density': round(latch_ratio, 4),
            'missed_feature_density': round(miss_ratio, 4),
            'vulnerability_ratio': round(vulnerability_ratio, 3),
            'already_postmodern_density': round(already_pm, 3),
            'latch_paragraphs': latch_paras[:10],
            'miss_paragraphs': miss_paras[:10],
            'postmodern_vocabulary_paragraphs': misread_paras[:10],
            'total_latch_paragraphs': latch_count,
            'total_miss_paragraphs': miss_count,
            'total_postmodern_paragraphs': misread_count,
            'method': 'Postmodern Misreading Vulnerability (Rosen Method)',
            'precedent': (
                "Rosen, 'Hermeneutics as Politics' and 'Plato's Symposium': Postmodern/deconstructionist "
                "reading commits five hermeneutic errors: (1) importing the Heideggerian 'metaphysics of "
                "presence' critique where it does not apply; (2) reducing silence and noetic perception to "
                "textuality; (3) dissolving authorial intention into 'play of signifiers'; (4) treating "
                "rhetorical accommodation as evidence of conceptual instability; (5) collapsing the "
                "esoteric/exoteric distinction into undecidability. Derrida 'does not seem to notice that "
                "there is a pregnant absence here, about to fill itself up with a poetic episteme, to say "
                "nothing of the silence of noetic perception.'"
            ),
            'interpretation': (
                'Track A (latch-on features) measures how much material the text provides for '
                'postmodern "deconstruction" — presence/absence language, binary oppositions, writing '
                'metaphors, paradoxes. Track B (missed features) measures intentional design signals, '
                'audience accommodation, esoteric layering, noetic vocabulary, and formal-constraint-as-'
                'content markers that postmodern reading systematically ignores. High vulnerability ratio '
                'means the text has many deconstructible features but few signals that would correct a '
                'postmodern misreading. A Rosenian reader would recognize that the "deconstructible" '
                'features are DELIBERATE authorial strategies (not conceptual instabilities) precisely '
                'because the missed features reveal intentional design.'
            ),
        }

    def analyze_dramatic_context(self) -> dict:
        """Rosen on Plato's Symposium: Speaker identity, setting, and occasion shape meaning."""
        speaker_vocab = {
            'speaker', 'says', 'replied', 'asked', 'argued', 'claims', 'addresses',
            'audience', 'listener', 'speaker identification', 'uttered', 'remarked'
        }
        setting_vocab = {
            'occasion', 'dinner', 'feast', 'gathering', 'trial', 'assembly', 'symposium',
            'scene', 'dramatic', 'setting', 'venue', 'place', 'location', 'where'
        }
        persona_vocab = {
            'character', 'role', 'mask', 'persona', 'voice', 'perspective', 'position',
            'stands', 'viewpoint', 'stance', 'speaks as', 'assumes'
        }

        dramatic_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            speaker_hits = len(para_words & speaker_vocab)
            setting_hits = len(para_words & setting_vocab)
            persona_hits = len(para_words & persona_vocab)
            combined = speaker_hits + setting_hits + persona_hits
            if combined > 0:
                dramatic_passages.append({
                    'paragraph': i,
                    'speaker_markers': speaker_hits,
                    'setting_markers': setting_hits,
                    'persona_markers': persona_hits,
                    'combined_score': combined,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        speaker_density = sum(1 for w in all_words if w in speaker_vocab) / total
        setting_density = sum(1 for w in all_words if w in setting_vocab) / total
        persona_density = sum(1 for w in all_words if w in persona_vocab) / total

        # Attribution patterns (quoted speech markers)
        attribution_patterns = sum(1 for para in self.paragraphs if 'said' in para.lower() or '"' in para)
        attribution_density = attribution_patterns / max(len(self.paragraphs), 1)

        score = min(1.0, (
            speaker_density * 25 + setting_density * 25 + persona_density * 20 +
            attribution_density * 15 + len(dramatic_passages) / max(len(self.paragraphs), 1) * 15
        ))

        return {
            'score': round(score, 3),
            'method': 'Dramatic Context (Rosen on Plato\'s Symposium)',
            'speaker_vocabulary_density': round(speaker_density, 5),
            'setting_vocabulary_density': round(setting_density, 5),
            'persona_vocabulary_density': round(persona_density, 5),
            'attribution_density': round(attribution_density, 5),
            'dramatic_passage_count': len(dramatic_passages),
            'dramatic_passages': dramatic_passages[:5],
            'precedent': (
                "Rosen, 'Plato's Symposium': Speaker identity, audience composition, setting, "
                "and occasion all shape philosophical meaning. Arguments cannot be separated from "
                "who speaks them, to whom, and under what circumstances."
            ),
            'interpretation': (
                'High scores indicate the text foregrounds dramatic framing as essential to meaning. '
                'Philosophical content is inseparable from speaker, setting, and audience. The reader '
                'must attend to who speaks, where, to whom, and when to grasp the full argument.'
            ),
        }

    def analyze_speech_sequencing(self) -> dict:
        """Rosen on Plato's Symposium: Successive speeches build and transform each other."""
        ordinal_vocab = {
            'first', 'second', 'third', 'next', 'then', 'finally', 'last', 'preceding',
            'following', 'after', 'before', 'earlier', 'later', 'subsequently'
        }
        response_vocab = {
            'responds', 'replies', 'corrects', 'challenges', 'agrees', 'disagrees',
            'builds on', 'transforms', 'surpasses', 'transcends', 'supersedes', 'reverses',
            'reaction', 'response', 'objection', 'counter', 'address'
        }
        progression_vocab = {
            'ascent', 'descent', 'higher', 'lower', 'better', 'worse', 'advance',
            'progress', 'regress', 'culminates', 'culmination', 'peak', 'apex', 'upward',
            'downward', 'elevation', 'decline'
        }

        sequential_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            ordinal_hits = len(para_words & ordinal_vocab)
            response_hits = len(para_words & response_vocab)
            progression_hits = len(para_words & progression_vocab)
            combined = ordinal_hits + response_hits + progression_hits
            if combined > 0:
                sequential_passages.append({
                    'paragraph': i,
                    'ordinal_markers': ordinal_hits,
                    'response_markers': response_hits,
                    'progression_markers': progression_hits,
                    'combined_score': combined,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        ordinal_density = sum(1 for w in all_words if w in ordinal_vocab) / total
        response_density = sum(1 for w in all_words if w in response_vocab) / total
        progression_density = sum(1 for w in all_words if w in progression_vocab) / total

        score = min(1.0, (
            ordinal_density * 20 + response_density * 30 + progression_density * 25 +
            len(sequential_passages) / max(len(self.paragraphs), 1) * 25
        ))

        return {
            'score': round(score, 3),
            'method': 'Speech Sequencing (Rosen on Plato\'s Symposium)',
            'ordinal_density': round(ordinal_density, 5),
            'response_density': round(response_density, 5),
            'progression_density': round(progression_density, 5),
            'sequential_passage_count': len(sequential_passages),
            'sequential_passages': sequential_passages[:5],
            'precedent': (
                "Rosen, 'Plato's Symposium': Successive speeches in a dialogue build, contradict, "
                "or transform each other. The ORDER matters: each speech responds to and modifies "
                "what came before. Later speeches don't simply supersede earlier ones."
            ),
            'interpretation': (
                'High scores indicate the text is fundamentally dialogical and sequential. Understanding '
                'requires tracking the order of arguments and responses. The progression—ascent, descent, '
                'transformation—is not incidental but constitutive of philosophical meaning.'
            ),
        }

    def analyze_philosophical_comedy(self) -> dict:
        """Rosen on Plato's Symposium: Serious philosophy delivered through comic form."""
        comic_vocab = {
            'laugh', 'comic', 'joke', 'jest', 'humor', 'ridicule', 'absurd', 'funny',
            'witty', 'playful', 'ludicrous', 'farce', 'mock', 'parody', 'satire', 'hiccup',
            'belch', 'snore', 'comedy', 'laughter'
        }
        serious_vocab = {
            'truth', 'justice', 'good', 'being', 'essence', 'soul', 'immortality', 'virtue',
            'wisdom', 'knowledge', 'beauty', 'form', 'reality', 'idea', 'serious', 'earnest'
        }
        juxtaposition_vocab = {
            'serious', 'earnest', 'joke', 'play', 'gravity', 'levity', 'laughter', 'tears',
            'both', 'and', 'yet', 'though', 'despite', 'nonetheless', 'simultaneously'
        }

        comic_philosophy_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            comic_hits = len(para_words & comic_vocab)
            serious_hits = len(para_words & serious_vocab)
            juxtaposition_hits = len(para_words & juxtaposition_vocab)

            # High score when both comic and serious appear together
            combo_boost = 2.0 if (comic_hits > 0 and serious_hits > 0) else 1.0
            combined = (comic_hits + serious_hits) * combo_boost + juxtaposition_hits

            if comic_hits > 0 and serious_hits > 0:
                comic_philosophy_passages.append({
                    'paragraph': i,
                    'comic_markers': comic_hits,
                    'serious_markers': serious_hits,
                    'juxtaposition_markers': juxtaposition_hits,
                    'combined_score': combined,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        comic_density = sum(1 for w in all_words if w in comic_vocab) / total
        serious_density = sum(1 for w in all_words if w in serious_vocab) / total
        juxtaposition_density = sum(1 for w in all_words if w in juxtaposition_vocab) / total

        score = min(1.0, (
            comic_density * 20 + serious_density * 25 + juxtaposition_density * 20 +
            len(comic_philosophy_passages) / max(len(self.paragraphs), 1) * 35
        ))

        return {
            'score': round(score, 3),
            'method': 'Philosophical Comedy (Rosen on Plato\'s Symposium)',
            'comic_density': round(comic_density, 5),
            'serious_density': round(serious_density, 5),
            'juxtaposition_density': round(juxtaposition_density, 5),
            'comic_philosophy_passage_count': len(comic_philosophy_passages),
            'comic_philosophy_passages': comic_philosophy_passages[:5],
            'precedent': (
                "Rosen, 'Plato's Symposium': Serious philosophical content delivered through comic "
                "form. The comedy IS the philosophy; reducing to either pure seriousness or pure jest "
                "misses the point. Aristophanes' speech is both the funniest AND contains essential "
                "philosophical content."
            ),
            'interpretation': (
                'High scores indicate comedy is not ornamental but constitutive of philosophical meaning. '
                'The text uses humor as a vehicle for truth, allowing truths that cannot be stated directly. '
                'The reader must learn to laugh while learning.'
            ),
        }

    def analyze_daimonic_mediation(self) -> dict:
        """Rosen on Plato's Symposium: Eros as daimon mediates between mortal and divine."""
        mediation_vocab = {
            'between', 'intermediate', 'mediator', 'daimon', 'demon', 'messenger', 'bridge',
            'link', 'middle', 'neither', 'nor', 'both', 'and', 'participate', 'partake', 'share'
        }
        boundary_vocab = {
            'threshold', 'boundary', 'limit', 'border', 'edge', 'margin', 'horizon', 'liminal',
            'passage', 'crossing', 'transition', 'divide', 'separation', 'junction'
        }
        transformation_vocab = {
            'become', 'transform', 'ascend', 'elevate', 'transcend', 'aspire', 'strive', 'reach',
            'desire', 'longing', 'yearning', 'eros', 'love', 'lack', 'poverty', 'resource',
            'pregnant', 'birth', 'generation'
        }

        daimonic_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            mediation_hits = len(para_words & mediation_vocab)
            boundary_hits = len(para_words & boundary_vocab)
            transformation_hits = len(para_words & transformation_vocab)
            combined = mediation_hits + boundary_hits + transformation_hits
            if combined > 0:
                daimonic_passages.append({
                    'paragraph': i,
                    'mediation_markers': mediation_hits,
                    'boundary_markers': boundary_hits,
                    'transformation_markers': transformation_hits,
                    'combined_score': combined,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        mediation_density = sum(1 for w in all_words if w in mediation_vocab) / total
        boundary_density = sum(1 for w in all_words if w in boundary_vocab) / total
        transformation_density = sum(1 for w in all_words if w in transformation_vocab) / total

        score = min(1.0, (
            mediation_density * 30 + boundary_density * 25 + transformation_density * 25 +
            len(daimonic_passages) / max(len(self.paragraphs), 1) * 20
        ))

        return {
            'score': round(score, 3),
            'method': 'Daimonic Mediation (Rosen on Plato\'s Symposium)',
            'mediation_density': round(mediation_density, 5),
            'boundary_density': round(boundary_density, 5),
            'transformation_density': round(transformation_density, 5),
            'daimonic_passage_count': len(daimonic_passages),
            'daimonic_passages': daimonic_passages[:5],
            'precedent': (
                "Rosen, 'Plato's Symposium': Eros is a daimon, intermediate between mortal and divine. "
                "Philosophy itself is daimonic—it mediates between ignorance and wisdom, between the human "
                "and the divine. Texts deploying intermediate/mediating figures embody this tradition."
            ),
            'interpretation': (
                'High scores indicate the text structures meaning through mediation and intermediate concepts. '
                'Neither/nor and both/and logic prevail. Transformation occurs at boundaries and thresholds. '
                'The reader encounters a middle ground that enables passage between opposites.'
            ),
        }

    def analyze_medicinal_rhetoric(self) -> dict:
        """Rosen on Plato's Symposium: Rhetoric as medicine adapted to the soul."""
        medical_vocab = {
            'medicine', 'heal', 'cure', 'remedy', 'disease', 'illness', 'healthy', 'sick',
            'physician', 'doctor', 'therapy', 'treatment', 'diagnosis', 'prescription', 'dose',
            'poison', 'drug', 'pharmakon', 'symptom', 'pathology'
        }
        pedagogical_vocab = {
            'teach', 'student', 'learn', 'educate', 'instruct', 'lesson', 'pupil', 'guide',
            'mentor', 'prepare', 'initiate', 'accommodate', 'adapt', 'tailor', 'training',
            'education', 'instruction', 'discipline'
        }
        soul_vocab = {
            'soul', 'psyche', 'character', 'temperament', 'disposition', 'nature', 'capacity',
            'readiness', 'worthy', 'unworthy', 'able', 'unable', 'condition', 'state'
        }

        medicinal_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            medical_hits = len(para_words & medical_vocab)
            pedagogical_hits = len(para_words & pedagogical_vocab)
            soul_hits = len(para_words & soul_vocab)
            combined = medical_hits + pedagogical_hits + soul_hits
            if combined > 0:
                medicinal_passages.append({
                    'paragraph': i,
                    'medical_markers': medical_hits,
                    'pedagogical_markers': pedagogical_hits,
                    'soul_vocabulary': soul_hits,
                    'combined_score': combined,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        medical_density = sum(1 for w in all_words if w in medical_vocab) / total
        pedagogical_density = sum(1 for w in all_words if w in pedagogical_vocab) / total
        soul_density = sum(1 for w in all_words if w in soul_vocab) / total

        score = min(1.0, (
            medical_density * 25 + pedagogical_density * 30 + soul_density * 25 +
            len(medicinal_passages) / max(len(self.paragraphs), 1) * 20
        ))

        return {
            'score': round(score, 3),
            'method': 'Medicinal Rhetoric (Rosen on Plato\'s Symposium)',
            'medical_density': round(medical_density, 5),
            'pedagogical_density': round(pedagogical_density, 5),
            'soul_vocabulary_density': round(soul_density, 5),
            'medicinal_rhetoric_passage_count': len(medicinal_passages),
            'medicinal_rhetoric_passages': medicinal_passages[:5],
            'precedent': (
                "Rosen, 'Plato's Symposium': Eryximachus treats rhetoric as medicine; speech must be "
                "adapted to the condition of the listener/patient. Different souls need different speeches. "
                "The philosopher as physician administers truth in measured doses, tailoring form to recipient."
            ),
            'interpretation': (
                'High scores indicate the text deploys rhetoric as therapeutic intervention. Meaning adapts '
                'to audience condition; the same truth requires different formulations for different souls. '
                'The author functions as physician, diagnosing and treating through carefully measured speech.'
            ),
        }

    def analyze_poetry_philosophy_dialectic(self) -> dict:
        """Rosen on Plato's Symposium: Reconciling the ancient quarrel between poetry and philosophy."""
        poetry_vocab = {
            'poem', 'poetry', 'poet', 'verse', 'song', 'sing', 'muse', 'inspiration', 'image',
            'imagination', 'myth', 'story', 'narrative', 'beautiful', 'beauty', 'sublime',
            'tragic', 'tragedy', 'comedy', 'drama', 'art', 'artistic', 'aesthetic', 'craft'
        }
        philosophy_vocab = {
            'reason', 'argument', 'proof', 'logic', 'dialectic', 'definition', 'concept',
            'analysis', 'demonstration', 'syllogism', 'principle', 'hypothesis', 'premise',
            'conclusion', 'refute', 'examine', 'investigate', 'inquiry', 'method', 'truth'
        }
        quarrel_vocab = {
            'quarrel', 'tension', 'rivalry', 'opposition', 'ancient quarrel', 'contest',
            'compete', 'reconcile', 'synthesize', 'unite', 'both', 'together', 'integrate',
            'interdepend', 'complement', 'mutual', 'reciprocal'
        }

        dialectic_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            poetry_hits = len(para_words & poetry_vocab)
            philosophy_hits = len(para_words & philosophy_vocab)
            quarrel_hits = len(para_words & quarrel_vocab)

            # Boost when poetry and philosophy co-occur
            combo_boost = 1.5 if (poetry_hits > 0 and philosophy_hits > 0) else 1.0
            combined = (poetry_hits + philosophy_hits) * combo_boost + quarrel_hits

            if combined > 0:
                dialectic_passages.append({
                    'paragraph': i,
                    'poetry_markers': poetry_hits,
                    'philosophy_markers': philosophy_hits,
                    'quarrel_markers': quarrel_hits,
                    'combined_score': combined,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        poetry_density = sum(1 for w in all_words if w in poetry_vocab) / total
        philosophy_density = sum(1 for w in all_words if w in philosophy_vocab) / total
        quarrel_density = sum(1 for w in all_words if w in quarrel_vocab) / total

        score = min(1.0, (
            poetry_density * 25 + philosophy_density * 25 + quarrel_density * 25 +
            len(dialectic_passages) / max(len(self.paragraphs), 1) * 25
        ))

        return {
            'score': round(score, 3),
            'method': 'Poetry-Philosophy Dialectic (Rosen on Plato\'s Symposium)',
            'poetry_density': round(poetry_density, 5),
            'philosophy_density': round(philosophy_density, 5),
            'quarrel_density': round(quarrel_density, 5),
            'dialectic_passage_count': len(dialectic_passages),
            'dialectic_passages': dialectic_passages[:5],
            'precedent': (
                "Rosen, 'Plato's Symposium': Socrates demands that the same person write both comedy "
                "and tragedy. The ancient quarrel between poetry and philosophy is resolved not by eliminating "
                "one side but by showing their deep interdependence. Texts operating at this intersection embody this."
            ),
            'interpretation': (
                'High scores indicate the text refuses to separate poetic from philosophical meaning. Poetry is not '
                'decoration for philosophy; philosophy is not the essence with poetry as vehicle. Instead, they are '
                'mutually constitutive. The quarrel itself is transcended through dialectical integration.'
            ),
        }

    def analyze_aspiration_achievement_gap(self) -> dict:
        """Rosen on Plato's Symposium: Philosophy as permanent unfulfilled desire."""
        aspiration_vocab = {
            'aspire', 'strive', 'seek', 'desire', 'long', 'yearn', 'hope', 'aim', 'reach',
            'pursue', 'quest', 'dream', 'wish', 'want', 'need', 'lack', 'poverty', 'deficiency',
            'hunger', 'thirst', 'searching', 'seeking', 'striving'
        }
        achievement_vocab = {
            'possess', 'attain', 'achieve', 'arrive', 'complete', 'fulfill', 'grasp', 'hold',
            'have', 'obtain', 'master', 'accomplish', 'succeed', 'triumph', 'full', 'whole',
            'perfect', 'sufficient', 'complete', 'finish', 'end', 'resolution'
        }
        gap_vocab = {
            'gap', 'tension', 'between', 'never', 'always', 'permanent', 'eternal', 'unending',
            'perpetual', 'ongoing', 'cannot', 'impossible', 'incomplete', 'partial', 'approach',
            'approximate', 'asymptotic', 'forever', 'endless', 'unfulfilled'
        }

        aspiration_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            aspiration_hits = len(para_words & aspiration_vocab)
            achievement_hits = len(para_words & achievement_vocab)
            gap_hits = len(para_words & gap_vocab)

            # Unresolved aspiration: aspiration + gap, penalizing if achievement dominates
            unresolved = 1.0 if (aspiration_hits > 0 and gap_hits > 0) else 0.5 if aspiration_hits > 0 else 0
            resolved = 0.3 if achievement_hits > aspiration_hits else 0
            combined = aspiration_hits + gap_hits - resolved

            if aspiration_hits > 0 or gap_hits > 0:
                aspiration_passages.append({
                    'paragraph': i,
                    'aspiration_markers': aspiration_hits,
                    'achievement_markers': achievement_hits,
                    'gap_markers': gap_hits,
                    'unresolved_score': unresolved,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        aspiration_density = sum(1 for w in all_words if w in aspiration_vocab) / total
        achievement_density = sum(1 for w in all_words if w in achievement_vocab) / total
        gap_density = sum(1 for w in all_words if w in gap_vocab) / total

        # Unresolved aspiration ratio: high when gap co-occurs with aspiration, low when achievement dominates
        unresolved_passages = sum(1 for p in aspiration_passages if p['unresolved_score'] > 0.5)
        unresolved_ratio = unresolved_passages / max(len(aspiration_passages), 1)

        score = min(1.0, (
            aspiration_density * 30 + gap_density * 30 - achievement_density * 15 +
            unresolved_ratio * 25
        ))

        return {
            'score': round(score, 3),
            'method': 'Aspiration-Achievement Gap (Rosen on Plato\'s Symposium)',
            'aspiration_density': round(aspiration_density, 5),
            'achievement_density': round(achievement_density, 5),
            'gap_density': round(gap_density, 5),
            'unresolved_aspiration_ratio': round(unresolved_ratio, 5),
            'aspiration_passage_count': len(aspiration_passages),
            'aspiration_passages': aspiration_passages[:5],
            'precedent': (
                "Rosen, 'Plato's Symposium': Eros is desire for what one lacks. Philosophy is permanent "
                "loving of wisdom without possessing it. The gap between aspiration and achievement is not "
                "a defect to overcome but the essential condition of philosophy itself."
            ),
            'interpretation': (
                'High scores indicate the text maintains the tension between desire and fulfillment without '
                'resolving it. Philosophy appears not as achievement but as perpetual striving. The reader '
                'learns that the gap IS the truth, and closure would be philosophical death.'
            ),
        }

    def analyze_synoptic_requirement(self) -> dict:
        """Rosen on Plato's Symposium: Full understanding requires knowledge of wider corpus."""
        cross_reference_vocab = {
            'elsewhere', 'other work', 'as we have seen', 'as i have argued', 'compare', 'cf',
            'see also', 'in the republic', 'in the phaedrus', 'already shown', 'previously',
            'later', 'another place', 'other dialogue', 'other writing', 'earlier', 'reminds',
            'recalls', 'anticipates', 'echoes', 'mentioned', 'noted'
        }
        intertextual_vocab = {
            'allusion', 'reference', 'echo', 'parallel', 'analogy', 'correspond', 'similar',
            'passage', 'compare', 'contrast', 'intertext', 'quotation', 'citation', 'invoke',
            'evoke', 'reference', 'point to', 'gesture toward'
        }
        incompleteness_vocab = {
            'partial', 'incomplete', 'fuller treatment', 'cannot be treated here', 'beyond our scope',
            'on another occasion', 'requires', 'presupposes', 'assumes familiarity', 'reader who knows',
            'further discussion', 'elsewhere explained', 'not here addressed', 'reserved for', 'separate study'
        }

        synoptic_passages = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            cross_ref_hits = len(para_words & cross_reference_vocab)
            intertextual_hits = len(para_words & intertextual_vocab)
            incompleteness_hits = len(para_words & incompleteness_vocab)
            combined = cross_ref_hits + intertextual_hits + incompleteness_hits
            if combined > 0:
                synoptic_passages.append({
                    'paragraph': i,
                    'cross_reference_markers': cross_ref_hits,
                    'intertextual_markers': intertextual_hits,
                    'incompleteness_markers': incompleteness_hits,
                    'combined_score': combined,
                    'excerpt': para[:200],
                })

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        cross_reference_density = sum(1 for w in all_words if w in cross_reference_vocab) / total
        intertextual_density = sum(1 for w in all_words if w in intertextual_vocab) / total
        incompleteness_density = sum(1 for w in all_words if w in incompleteness_vocab) / total

        score = min(1.0, (
            cross_reference_density * 30 + intertextual_density * 25 + incompleteness_density * 25 +
            len(synoptic_passages) / max(len(self.paragraphs), 1) * 20
        ))

        return {
            'score': round(score, 3),
            'method': 'Synoptic Requirement (Rosen on Plato\'s Symposium)',
            'cross_reference_density': round(cross_reference_density, 5),
            'intertextual_density': round(intertextual_density, 5),
            'incompleteness_density': round(incompleteness_density, 5),
            'synoptic_passage_count': len(synoptic_passages),
            'synoptic_passages': synoptic_passages[:5],
            'precedent': (
                "Rosen, 'Plato's Symposium': Full understanding of any dialogue requires knowledge of the "
                "wider Platonic corpus. Rosen constantly cross-references other dialogues. Texts demanding "
                "external knowledge for full comprehension deploy this technique intentionally."
            ),
            'interpretation': (
                'High scores indicate the text cannot be understood in isolation. Its meaning depends on the '
                'reader\'s familiarity with related works. Incompleteness is deliberate: it signals that full '
                'understanding requires synoptic grasp of a larger body of work.'
            ),
        }

    # ------------------------------------------------------------------
    # FULL ANALYSIS
    # ------------------------------------------------------------------

    def full_analysis(self) -> dict:
        """Run all analyses and produce a composite report."""
        self.results = {
            'title': self.title,
            'text_statistics': {
                'total_words': len(self.words),
                'total_sentences': len(self.sentences),
                'total_paragraphs': len(self.paragraphs),
                'total_chapters': len(self.chapters),
            },
            'analyses': {},
        }

        analyses = [
            ('contradiction', self.analyze_contradictions),
            ('central_placement', self.analyze_central_placement),
            ('numerology', self.analyze_numerology),
            ('silence', self.analyze_silence),
            ('repetition', self.analyze_repetition),
            ('symmetry', self.analyze_symmetry),
            ('irony', self.analyze_irony),
            ('digression', self.analyze_digressions),
            ('lexical_density', self.analyze_lexical_density),
            ('acrostic', self.analyze_acrostics),
            ('hapax_legomena', self.analyze_hapax_legomena),
            ('voice_consistency', self.analyze_voice_consistency),
            ('register', self.analyze_register),
            ('logos_mythos', self.analyze_logos_mythos),
            ('commentary_divergence', self.analyze_commentary_divergence),
            ('polysemy', self.analyze_polysemy),
            ('aphoristic_fragmentation', self.analyze_aphoristic_fragmentation),
            ('trapdoor', self.analyze_trapdoors),
            ('dyadic_structure', self.analyze_dyadic_structure),
            ('periagoge', self.analyze_periagoge),
            ('logos_ergon', self.analyze_logos_ergon),
            ('onomastic', self.analyze_onomastic),
            ('recognition_structure', self.analyze_recognition_structure),
            ('nomos_physis', self.analyze_nomos_physis),
            ('impossible_arithmetic', self.analyze_impossible_arithmetic),
            ('rhetoric_of_concealment', self.analyze_rhetoric_of_concealment),
            ('transcendental_ambiguity', self.analyze_transcendental_ambiguity),
            ('rhetoric_of_frankness', self.analyze_rhetoric_of_frankness),
            ('intuition_analysis', self.analyze_intuition_analysis_dialectic),
            ('logographic_necessity', self.analyze_logographic_necessity),
            ('theological_disavowal', self.analyze_theological_disavowal),
            ('defensive_writing', self.analyze_defensive_writing),
            ('nature_freedom_oscillation', self.analyze_nature_freedom_oscillation),
            ('postmodern_misreading', self.analyze_postmodern_misreading),
            ('dramatic_context', self.analyze_dramatic_context),
            ('speech_sequencing', self.analyze_speech_sequencing),
            ('philosophical_comedy', self.analyze_philosophical_comedy),
            ('daimonic_mediation', self.analyze_daimonic_mediation),
            ('medicinal_rhetoric', self.analyze_medicinal_rhetoric),
            ('poetry_philosophy', self.analyze_poetry_philosophy_dialectic),
            ('aspiration_gap', self.analyze_aspiration_achievement_gap),
            ('synoptic_requirement', self.analyze_synoptic_requirement),
        ]

        scores = []
        for name, fn in analyses:
            result = fn()
            self.results['analyses'][name] = result
            scores.append(result.get('score', 0))

        # Composite esoteric probability (weighted)
        # Weights sum to 1.0; rebalanced to accommodate 42 methods total
        # Tier 1 (0.04): core Straussian methods + key Rosen methods
        # Tier 2 (0.03): important structural/hermeneutic methods
        # Tier 3 (0.02): supporting methods and specialized detectors
        weights = {
            'contradiction': 0.04,
            'rhetoric_of_concealment': 0.04,
            'transcendental_ambiguity': 0.04,
            'central_placement': 0.04,
            'silence': 0.04,
            'irony': 0.04,
            'trapdoor': 0.04,
            'dramatic_context': 0.04,
            'postmodern_misreading': 0.04,
            'rhetoric_of_frankness': 0.04,
            'repetition': 0.03,
            'symmetry': 0.03,
            'periagoge': 0.03,
            'logos_ergon': 0.03,
            'intuition_analysis': 0.03,
            'defensive_writing': 0.03,
            'logographic_necessity': 0.03,
            'polysemy': 0.03,
            'speech_sequencing': 0.02,
            'philosophical_comedy': 0.02,
            'daimonic_mediation': 0.02,
            'medicinal_rhetoric': 0.02,
            'poetry_philosophy': 0.02,
            'aspiration_gap': 0.02,
            'synoptic_requirement': 0.02,
            'dyadic_structure': 0.02,
            'nomos_physis': 0.02,
            'nature_freedom_oscillation': 0.02,
            'numerology': 0.02,
            'lexical_density': 0.02,
            'acrostic': 0.01,
            'hapax_legomena': 0.01,
            'voice_consistency': 0.01,
            'register': 0.01,
            'logos_mythos': 0.01,
            'aphoristic_fragmentation': 0.01,
            'onomastic': 0.01,
            'recognition_structure': 0.01,
            'impossible_arithmetic': 0.01,
            'theological_disavowal': 0.01,
            'commentary_divergence': 0.01,
            'digression': 0.01,
        }

        composite = 0
        for i, (name, _) in enumerate(analyses):
            composite += scores[i] * weights.get(name, 0.1)

        self.results['composite_esoteric_score'] = round(min(1.0, composite), 3)
        self.results['score_interpretation'] = self._interpret_composite(composite)

        return self.results

    def _interpret_composite(self, score: float) -> str:
        if score < 0.15:
            return ("LOW — Few computational signals of esotericism detected. "
                    "The text appears relatively straightforward, though this does "
                    "not rule out subtle forms of concealment below computational detection.")
        elif score < 0.35:
            return ("MODERATE — Some signals present. The text shows patterns "
                    "consistent with at least some esoteric techniques. LLM-based "
                    "close reading is recommended to investigate further.")
        elif score < 0.55:
            return ("ELEVATED — Multiple converging signals. The text shows "
                    "statistically notable patterns across several esoteric methods. "
                    "Close reading with attention to contradiction, central placement, "
                    "and structural patterns is strongly recommended.")
        else:
            return ("HIGH — Strong convergence of multiple esoteric signals. "
                    "The text exhibits patterns highly consistent with deliberate "
                    "concealment techniques documented in the historical tradition. "
                    "Detailed close reading and source comparison are essential.")

    # ------------------------------------------------------------------
    # ESOTERIC VS EXOTERIC LAYER COMPARISON
    # ------------------------------------------------------------------

    def compare_layers(self) -> dict:
        """
        Attempt to separate and compare the esoteric and exoteric layers
        of the text based on the computational analysis.

        The "exoteric layer" = the surface: passages with high local coherence,
        conventional sentiment, and standard vocabulary.

        The "esoteric layer" = the depth: passages flagged by contradiction,
        digression, irony, central placement, or unusual density.
        """
        if not self.results:
            self.full_analysis()

        flagged_paragraphs = set()

        # Gather paragraph indices flagged by each method
        contras = self.results['analyses'].get('contradiction', {}).get('evidence', [])
        for c in contras:
            flagged_paragraphs.add(c.get('paragraph_a', 0) - 1)
            flagged_paragraphs.add(c.get('paragraph_b', 0) - 1)

        digressions = self.results['analyses'].get('digression', {}).get('digressions', [])
        for d in digressions:
            flagged_paragraphs.add(d.get('paragraph_index', 0) - 1)

        irony_markers = self.results['analyses'].get('irony', {}).get('irony_markers', [])
        irony_sents = set(m.get('sentence_index', 0) - 1 for m in irony_markers)

        # Flag polysemous paragraphs (multi-domain = multi-level meaning)
        polysemous = self.results['analyses'].get('polysemy', {}).get('polysemous_paragraphs', [])
        for p in polysemous:
            flagged_paragraphs.add(p.get('paragraph', 0) - 1)

        # Flag mythos passages embedded in logos-dominant text
        logos_mythos = self.results['analyses'].get('logos_mythos', {})
        if logos_mythos.get('dominant_mode') == 'logos':
            for ep in logos_mythos.get('embedded_passages', []):
                flagged_paragraphs.add(ep.get('paragraph', 0) - 1)

        # Flag mask/concealment sentences (aphoristic method)
        mask_sents = self.results['analyses'].get('aphoristic_fragmentation', {}).get('mask_sentences', [])
        # Convert sentence indices to approximate paragraph indices
        for ms in mask_sents:
            sent_idx = ms.get('sentence_index', 0) - 1
            approx_para = min(sent_idx * len(self.paragraphs) // max(len(self.sentences), 1),
                              len(self.paragraphs) - 1)
            flagged_paragraphs.add(approx_para)

        # Flag trapdoor passages (Benardete method)
        trapdoor_data = self.results['analyses'].get('trapdoor', {})
        for td in trapdoor_data.get('local_contradictions', []):
            sent_idx = td.get('sentence_a', 1) - 1
            approx_para = min(sent_idx * len(self.paragraphs) // max(len(self.sentences), 1),
                              len(self.paragraphs) - 1)
            flagged_paragraphs.add(approx_para)
        for td in trapdoor_data.get('non_sequiturs', []):
            sent_idx = td.get('conclusion_sentence', 1) - 1
            approx_para = min(sent_idx * len(self.paragraphs) // max(len(self.sentences), 1),
                              len(self.paragraphs) - 1)
            flagged_paragraphs.add(approx_para)

        # Flag phantom image passages (Benardete dyadic method)
        dyadic_data = self.results['analyses'].get('dyadic_structure', {})
        for pp in dyadic_data.get('phantom_passages', []):
            flagged_paragraphs.add(pp.get('paragraph', 1) - 1)

        # Separate layers
        esoteric_passages = []
        exoteric_passages = []
        for i, para in enumerate(self.paragraphs):
            if i in flagged_paragraphs:
                esoteric_passages.append({'index': i + 1, 'text': para[:300]})
            else:
                exoteric_passages.append({'index': i + 1, 'text': para[:300]})

        # Compare vocabulary
        eso_words = []
        exo_words = []
        for i, para in enumerate(self.paragraphs):
            tokens = [w.lower() for w in word_tokenize(para) if w.isalpha() and w.lower() not in self.stop_words]
            if i in flagged_paragraphs:
                eso_words.extend(tokens)
            else:
                exo_words.extend(tokens)

        eso_freq = Counter(eso_words).most_common(30)
        exo_freq = Counter(exo_words).most_common(30)

        # Words distinctive to each layer
        eso_set = set(w for w, _ in eso_freq)
        exo_set = set(w for w, _ in exo_freq)
        eso_distinctive = eso_set - exo_set
        exo_distinctive = exo_set - eso_set

        return {
            'esoteric_layer': {
                'passage_count': len(esoteric_passages),
                'sample_passages': esoteric_passages[:10],
                'top_vocabulary': eso_freq[:15],
                'distinctive_vocabulary': list(eso_distinctive)[:15],
            },
            'exoteric_layer': {
                'passage_count': len(exoteric_passages),
                'sample_passages': exoteric_passages[:5],
                'top_vocabulary': exo_freq[:15],
                'distinctive_vocabulary': list(exo_distinctive)[:15],
            },
            'layer_ratio': round(len(esoteric_passages) / max(len(exoteric_passages), 1), 3),
            'interpretation': (
                'The esoteric layer consists of passages flagged by contradiction, '
                'digression, or irony analyses. The exoteric layer is everything else. '
                'Compare their vocabularies: the esoteric layer often uses more '
                'philosophical, hedging, or negation-heavy language. The layer ratio '
                'indicates what proportion of the text is computationally flagged.'
            ),
        }

    # ------------------------------------------------------------------
    # LLM PROMPT GENERATOR
    # ------------------------------------------------------------------

    def generate_llm_prompt(self) -> str:
        """
        Generate a detailed prompt for an LLM to perform deep esoteric analysis
        beyond what computational methods can detect.

        The prompt is informed by the computational findings and directs the LLM
        to investigate specific passages, apply specific historical methods, and
        produce a structured interpretation.
        """
        if not self.results:
            self.full_analysis()

        # Gather the most significant findings to embed in the prompt
        composite = self.results.get('composite_esoteric_score', 0)
        top_contradictions = self.results['analyses'].get('contradiction', {}).get('evidence', [])[:5]
        center_sents = self.results['analyses'].get('central_placement', {}).get('top_center_sentences', [])
        num_hits = self.results['analyses'].get('numerology', {}).get('significant_number_hits', [])[:5]
        absent_topics = self.results['analyses'].get('silence', {}).get('absent_topics', [])
        irony = self.results['analyses'].get('irony', {}).get('irony_markers', [])[:5]
        digressions = self.results['analyses'].get('digression', {}).get('digressions', [])[:5]
        emphatic_ch = self.results['analyses'].get('repetition', {}).get('suspiciously_emphatic_chapters', [])
        dense_ch = self.results['analyses'].get('lexical_density', {}).get('high_density_chapters', [])
        symmetry = self.results['analyses'].get('symmetry', {})

        # Build computational findings summary
        findings_summary = f"Composite esoteric score: {composite}\n"

        if top_contradictions:
            findings_summary += "\n### Potential Contradictions Detected\n"
            for c in top_contradictions:
                findings_summary += (
                    f"- Paragraphs {c['paragraph_a']} vs {c['paragraph_b']} "
                    f"(similarity: {c['topical_similarity']}, tension: {c['tension_score']})\n"
                    f"  A: \"{c['excerpt_a'][:150]}...\"\n"
                    f"  B: \"{c['excerpt_b'][:150]}...\"\n"
                )

        if center_sents:
            findings_summary += "\n### Key Sentences at the Structural Center\n"
            for s in center_sents:
                findings_summary += f"- [Sentence {s['sentence_index']}]: \"{s['text'][:200]}\"\n"

        if num_hits:
            findings_summary += "\n### Numerological Patterns\n"
            for h in num_hits:
                findings_summary += f"- {h['unit']}: {h['count']} — {h.get('significance', '')}\n"

        if absent_topics:
            findings_summary += f"\n### Conspicuously Absent Topics\n"
            findings_summary += f"- {', '.join(absent_topics)}\n"

        if digressions:
            findings_summary += "\n### Detected Digressions\n"
            for d in digressions:
                findings_summary += (
                    f"- Paragraph {d['paragraph_index']} at {d['position_in_text']} "
                    f"(coherence z-score: {d['z_score']})\n"
                    f"  \"{d['excerpt'][:150]}...\"\n"
                )

        if irony:
            findings_summary += "\n### Potential Irony Markers\n"
            for m in irony:
                findings_summary += f"- [Sentence {m['sentence_index']}]: \"{m['text'][:150]}...\"\n"

        if emphatic_ch:
            findings_summary += "\n### Suspiciously Emphatic Chapters\n"
            for e in emphatic_ch:
                findings_summary += (
                    f"- Chapter {e['chapter']} ({e['title']}): "
                    f"praise density {e['praise_density']}\n"
                )

        mirror_ratio = symmetry.get('mirror_to_baseline_ratio', 0)
        if mirror_ratio > 1.1:
            findings_summary += f"\n### Ring/Chiastic Structure Signal\n"
            findings_summary += f"- Mirror-to-baseline ratio: {mirror_ratio}\n"

        # New method findings
        acrostic_data = self.results['analyses'].get('acrostic', {})
        acrostic_words = acrostic_data.get('words_found', [])
        if acrostic_words:
            findings_summary += "\n### Acrostic/Telestic Patterns\n"
            for w in acrostic_words[:5]:
                findings_summary += f"- Word '{w['word']}' found in {w['source']} at position {w['position']}\n"
            seqs = acrostic_data.get('letter_sequences', {})
            if seqs.get('chapter_acrostic'):
                findings_summary += f"- Chapter first-letters: {seqs['chapter_acrostic']}\n"

        hapax_data = self.results['analyses'].get('hapax_legomena', {})
        phil_hapax = hapax_data.get('philosophical_hapax', [])
        if phil_hapax:
            findings_summary += f"\n### Philosophically Loaded Hapax Legomena\n"
            findings_summary += f"- Words used exactly once: {', '.join(phil_hapax[:10])}\n"

        voice_data = self.results['analyses'].get('voice_consistency', {})
        voice_shifts = voice_data.get('voice_shifts', [])
        if voice_shifts:
            findings_summary += "\n### Voice/Persona Shifts Detected\n"
            for vs in voice_shifts[:5]:
                findings_summary += f"- Chapter {vs['chapter']} ({vs['title']}): stylistic distance z={vs['z_score']}\n"

        register_data = self.results['analyses'].get('register', {})
        register_transitions = register_data.get('register_transitions', [])
        if register_transitions:
            findings_summary += "\n### Register Transitions (Averroes Three-Tier)\n"
            for rt in register_transitions[:5]:
                findings_summary += f"- Ch. {rt['from_chapter']} ({rt['from_register']}) -> Ch. {rt['to_chapter']} ({rt['to_register']})\n"

        lm_data = self.results['analyses'].get('logos_mythos', {})
        lm_transitions = lm_data.get('transitions', [])
        if lm_transitions:
            findings_summary += "\n### Logos/Mythos Transitions\n"
            for lt in lm_transitions[:5]:
                findings_summary += f"- Paragraph {lt['paragraph']} at {lt['position']}: {lt['from']} -> {lt['to']}\n"

        polysemy_data = self.results['analyses'].get('polysemy', {})
        poly_paras = polysemy_data.get('polysemous_paragraphs', [])
        if poly_paras:
            findings_summary += "\n### Multi-Domain (Polysemous) Passages\n"
            for pp in poly_paras[:3]:
                findings_summary += f"- Paragraph {pp['paragraph']}: domains={pp['domains_present']}\n"

        aph_data = self.results['analyses'].get('aphoristic_fragmentation', {})
        mask_sents_prompt = aph_data.get('mask_sentences', [])
        if mask_sents_prompt:
            findings_summary += "\n### Mask/Concealment Self-References\n"
            for ms in mask_sents_prompt[:5]:
                findings_summary += f"- [Sentence {ms['sentence_index']}]: \"{ms['text'][:150]}...\"\n"
        frag_idx = aph_data.get('fragmentation_index', 0)
        if frag_idx > 0.5:
            findings_summary += f"\n### High Aphoristic Fragmentation\n"
            findings_summary += f"- Fragmentation index: {frag_idx}\n"

        # Benardete method findings
        trapdoor_data = self.results['analyses'].get('trapdoor', {})
        local_contras = trapdoor_data.get('local_contradictions', [])
        hedge_abs = trapdoor_data.get('hedge_near_absolute', [])
        non_seqs = trapdoor_data.get('non_sequiturs', [])
        if local_contras or hedge_abs or non_seqs:
            findings_summary += f"\n### Trapdoor Detection (Benardete)\n"
            findings_summary += f"- Total trapdoors: {trapdoor_data.get('total_trapdoors', 0)}\n"
            for lc in local_contras[:3]:
                findings_summary += (f"- Local contradiction: sentences {lc['sentence_a']} vs {lc['sentence_b']}: "
                                     f"\"{lc['text_a'][:100]}...\" vs \"{lc['text_b'][:100]}...\"\n")
            for ha in hedge_abs[:3]:
                findings_summary += f"- Hedged absolute at sentence {ha['absolute_sentence_index']}: \"{ha['absolute_text'][:100]}...\"\n"
            for ns in non_seqs[:3]:
                findings_summary += f"- Non-sequitur at sentence {ns['conclusion_sentence']}: \"{ns['text'][:100]}...\"\n"

        dyadic_data = self.results['analyses'].get('dyadic_structure', {})
        recurring = dyadic_data.get('recurring_pairs', [])
        convergences = dyadic_data.get('convergence_markers', [])
        phantoms = dyadic_data.get('phantom_passages', [])
        if recurring or convergences or phantoms:
            findings_summary += f"\n### Dyadic Structure (Benardete)\n"
            findings_summary += f"- Eidetic vocabulary density: {dyadic_data.get('eidetic_vocabulary_density', 0)}\n"
            for rp in recurring[:5]:
                findings_summary += f"- Recurring binary pair: {rp['pair'][0]}/{rp['pair'][1]} ({rp['count']}x)\n"
            for cm in convergences[:3]:
                findings_summary += f"- Convergence of {cm['pair']}: para {cm['first_position']} -> {cm['convergence_position']}\n"
            for ph in phantoms[:3]:
                findings_summary += f"- Phantom image passage at para {ph['paragraph']}: {ph['phantom_terms']}\n"

        periagoge_data = self.results['analyses'].get('periagoge', {})
        pol_shift = periagoge_data.get('polarity_shift', 0)
        reversals_list = periagoge_data.get('reversals', [])
        if abs(pol_shift) > 0.1 or reversals_list:
            findings_summary += f"\n### Periagoge / Structural Reversal (Benardete)\n"
            findings_summary += f"- Polarity shift (1st->2nd half): {pol_shift}\n"
            findings_summary += f"- Reversal count: {periagoge_data.get('reversal_count', 0)}\n"
            findings_summary += f"- Turning vocabulary density (middle third): {periagoge_data.get('turning_vocabulary_density', 0)}\n"
            for rv in reversals_list[:3]:
                findings_summary += (f"- Reversal: \"{rv['first_half_sentence'][:80]}...\" "
                                     f"-> \"{rv['second_half_sentence'][:80]}...\"\n")

        logos_ergon_data = self.results['analyses'].get('logos_ergon', {})
        if logos_ergon_data.get('mismatch_count', 0) > 0:
            findings_summary += f"\n### Logos-Ergon (Speech-Deed) Analysis\n"
            findings_summary += f"- Speech/action ratio: {logos_ergon_data.get('speech_action_ratio', 0)}\n"
            findings_summary += f"- Speech-action mismatches: {logos_ergon_data.get('mismatch_count', 0)}\n"
            findings_summary += f"- Burstlike argument shifts: {logos_ergon_data.get('burstlike_shifts', 0)}\n"
            findings_summary += f"- Filamentlike argument shifts: {logos_ergon_data.get('filamentlike_shifts', 0)}\n"

        onomastic_data = self.results['analyses'].get('onomastic', {})
        if onomastic_data.get('naming_passage_count', 0) > 0:
            findings_summary += f"\n### Onomastic / Etymological Analysis\n"
            findings_summary += f"- Naming density: {onomastic_data.get('naming_density', 0)}\n"
            findings_summary += f"- Etymological passages: {onomastic_data.get('naming_passage_count', 0)}\n"
            findings_summary += f"- Proper noun diversity: {onomastic_data.get('proper_noun_diversity', 0)}\n"
            for pn in onomastic_data.get('top_proper_nouns', [])[:5]:
                findings_summary += f"- Frequent name: {pn[0]} ({pn[1]}x)\n"

        recog_data = self.results['analyses'].get('recognition_structure', {})
        if recog_data.get('combined_density', 0) > 0.001:
            findings_summary += f"\n### Recognition Scene / Concealment-Test-Reveal\n"
            findings_summary += f"- Ideal pattern detected: {recog_data.get('ideal_pattern_detected', False)}\n"
            findings_summary += f"- Concealment terms: {recog_data.get('concealment_count', 0)}\n"
            findings_summary += f"- Testing terms: {recog_data.get('testing_count', 0)}\n"
            findings_summary += f"- Revelation terms: {recog_data.get('revelation_count', 0)}\n"
            for pd in recog_data.get('phase_densities', []):
                findings_summary += f"  Phase: conceal={pd.get('concealment',0)}, test={pd.get('testing',0)}, reveal={pd.get('revelation',0)}\n"

        nomos_data = self.results['analyses'].get('nomos_physis', {})
        if nomos_data.get('co_occurrence_count', 0) > 0:
            findings_summary += f"\n### Nomos-Physis (Convention vs. Nature)\n"
            findings_summary += f"- Nomos density: {nomos_data.get('nomos_density', 0)}\n"
            findings_summary += f"- Physis density: {nomos_data.get('physis_density', 0)}\n"
            findings_summary += f"- Co-occurrences: {nomos_data.get('co_occurrence_count', 0)}\n"
            findings_summary += f"- Comparative density: {nomos_data.get('comparative_density', 0)}\n"

        imp_arith_data = self.results['analyses'].get('impossible_arithmetic', {})
        if imp_arith_data.get('poetic_dialectic_passage_count', 0) > 0:
            findings_summary += f"\n### Impossible Arithmetic / Poetic Dialectic\n"
            findings_summary += f"- Impossibility density: {imp_arith_data.get('impossibility_density', 0)}\n"
            findings_summary += f"- Arithmetic density: {imp_arith_data.get('arithmetic_density', 0)}\n"
            findings_summary += f"- Poetic dialectic passages: {imp_arith_data.get('poetic_dialectic_passage_count', 0)}\n"
            findings_summary += f"- 'Impossible yet true' patterns: {imp_arith_data.get('impossible_yet_true_count', 0)}\n"

        # New 8 methods
        conc_data = self.results['analyses'].get('rhetoric_of_concealment', {})
        if conc_data.get('concealment_density', 0) > 0.001:
            findings_summary += f"\n### Rhetoric of Concealment (Rosen)\n"
            findings_summary += f"- Concealment density: {conc_data.get('concealment_density', 0)}\n"
            findings_summary += f"- Design density: {conc_data.get('design_density', 0)}\n"
            findings_summary += f"- Defensive density: {conc_data.get('defensive_density', 0)}\n"

        amb_data = self.results['analyses'].get('transcendental_ambiguity', {})
        if amb_data.get('ambiguity_marker_density', 0) > 0.001:
            findings_summary += f"\n### Transcendental Ambiguity (Rosen)\n"
            findings_summary += f"- Ambiguity marker density: {amb_data.get('ambiguity_marker_density', 0)}\n"
            findings_summary += f"- Resistance marker density: {amb_data.get('resistance_marker_density', 0)}\n"
            findings_summary += f"- Ambiguous passages: {amb_data.get('ambiguous_passage_count', 0)}\n"

        frank_data = self.results['analyses'].get('rhetoric_of_frankness', {})
        if frank_data.get('frankness_density', 0) > 0.001:
            findings_summary += f"\n### Rhetoric of Frankness (Rosen)\n"
            findings_summary += f"- Frankness density: {frank_data.get('frankness_density', 0)}\n"
            findings_summary += f"- Performative frankness passages: {frank_data.get('performative_frankness_count', 0)}\n"

        intuit_data = self.results['analyses'].get('intuition_analysis', {})
        if intuit_data.get('intuition_density', 0) > 0.001:
            findings_summary += f"\n### Intuition-Analysis Dialectic (Rosen)\n"
            findings_summary += f"- Intuition density: {intuit_data.get('intuition_density', 0)}\n"
            findings_summary += f"- Analysis limit density: {intuit_data.get('analysis_limit_density', 0)}\n"
            findings_summary += f"- Reflexive impossibility passages: {intuit_data.get('intuitive_passage_count', 0)}\n"

        logo_data = self.results['analyses'].get('logographic_necessity', {})
        if logo_data.get('constraint_density', 0) > 0.001:
            findings_summary += f"\n### Logographic Necessity (Benardete)\n"
            findings_summary += f"- Constraint density: {logo_data.get('constraint_density', 0)}\n"
            findings_summary += f"- Form-content unity passages: {logo_data.get('logographic_passage_count', 0)}\n"

        theo_data = self.results['analyses'].get('theological_disavowal', {})
        if theo_data.get('theological_density', 0) > 0.001:
            findings_summary += f"\n### Theological Disavowal (Rosen)\n"
            findings_summary += f"- Theological term density: {theo_data.get('theological_density', 0)}\n"
            findings_summary += f"- Philosophical substitute density: {theo_data.get('philosophical_substitute_density', 0)}\n"
            findings_summary += f"- Disavowal density: {theo_data.get('disavowal_density', 0)}\n"

        defens_data = self.results['analyses'].get('defensive_writing', {})
        if defens_data.get('defensive_density', 0) > 0.001:
            findings_summary += f"\n### Defensive Writing (Rosen/Strauss)\n"
            findings_summary += f"- Defensive passage count: {defens_data.get('defensive_passage_count', 0)}\n"
            findings_summary += f"- Multi-category defensive ratio: {defens_data.get('multi_category_ratio', 0)}\n"
            findings_summary += f"- Orthodox appeal density: {defens_data.get('orthodox_appeal_density', 0)}\n"

        osc_data = self.results['analyses'].get('nature_freedom_oscillation', {})
        if osc_data.get('oscillation_frequency', 0) > 0.01:
            findings_summary += f"\n### Nature-Freedom Oscillation (Rosen)\n"
            findings_summary += f"- Oscillation frequency: {osc_data.get('oscillation_frequency', 0)}\n"
            findings_summary += f"- Nature-dominant paragraphs: {osc_data.get('nature_dominant_paragraphs', 0)}\n"
            findings_summary += f"- Freedom-dominant paragraphs: {osc_data.get('freedom_dominant_paragraphs', 0)}\n"
            findings_summary += f"- Explicit tension acknowledged: {osc_data.get('explicit_tension_acknowledged', False)}\n"

        pm_data = self.results['analyses'].get('postmodern_misreading', {})
        if pm_data.get('latch_on_density', 0) > 0.01 or pm_data.get('already_postmodern_density', 0) > 0:
            findings_summary += f"\n### Postmodern Misreading Vulnerability (Rosen)\n"
            findings_summary += f"- Latch-on density (deconstructible features): {pm_data.get('latch_on_density', 0)}\n"
            findings_summary += f"- Missed-feature density (intentional design signals): {pm_data.get('missed_feature_density', 0)}\n"
            findings_summary += f"- Vulnerability ratio: {pm_data.get('vulnerability_ratio', 0)}\n"
            findings_summary += f"- Already-postmodern vocabulary density: {pm_data.get('already_postmodern_density', 0)}\n"
            findings_summary += f"- Latch-on paragraphs: {pm_data.get('total_latch_paragraphs', 0)}\n"
            findings_summary += f"- Missed-feature paragraphs: {pm_data.get('total_miss_paragraphs', 0)}\n"

        dc_data = self.results['analyses'].get('dramatic_context', {})
        if dc_data.get('speaker_vocabulary_density', 0) > 0.001:
            findings_summary += f"\n### Dramatic Context (Rosen/Symposium)\n"
            findings_summary += f"- Speaker vocabulary density: {dc_data.get('speaker_vocabulary_density', 0)}\n"
            findings_summary += f"- Setting vocabulary density: {dc_data.get('setting_vocabulary_density', 0)}\n"
            findings_summary += f"- Attribution density: {dc_data.get('attribution_density', 0)}\n"

        ss_data = self.results['analyses'].get('speech_sequencing', {})
        if ss_data.get('ordinal_density', 0) > 0.001:
            findings_summary += f"\n### Speech Sequencing (Rosen/Symposium)\n"
            findings_summary += f"- Ordinal marker density: {ss_data.get('ordinal_density', 0)}\n"
            findings_summary += f"- Response vocabulary density: {ss_data.get('response_density', 0)}\n"
            findings_summary += f"- Progression vocabulary density: {ss_data.get('progression_density', 0)}\n"

        pc_data = self.results['analyses'].get('philosophical_comedy', {})
        if pc_data.get('comic_density', 0) > 0.001:
            findings_summary += f"\n### Philosophical Comedy (Rosen/Symposium)\n"
            findings_summary += f"- Comic vocabulary density: {pc_data.get('comic_density', 0)}\n"
            findings_summary += f"- Serious vocabulary density: {pc_data.get('serious_density', 0)}\n"
            findings_summary += f"- Juxtaposition density: {pc_data.get('juxtaposition_density', 0)}\n"
            findings_summary += f"- Comic-philosophy passages: {len(pc_data.get('comic_philosophy_passages', []))}\n"

        dm_data = self.results['analyses'].get('daimonic_mediation', {})
        if dm_data.get('mediation_density', 0) > 0.001:
            findings_summary += f"\n### Daimonic Mediation (Rosen/Symposium)\n"
            findings_summary += f"- Mediation vocabulary density: {dm_data.get('mediation_density', 0)}\n"
            findings_summary += f"- Boundary vocabulary density: {dm_data.get('boundary_density', 0)}\n"
            findings_summary += f"- Transformation vocabulary density: {dm_data.get('transformation_density', 0)}\n"

        mr_data = self.results['analyses'].get('medicinal_rhetoric', {})
        if mr_data.get('medical_density', 0) > 0.001:
            findings_summary += f"\n### Medicinal Rhetoric (Rosen/Symposium)\n"
            findings_summary += f"- Medical vocabulary density: {mr_data.get('medical_density', 0)}\n"
            findings_summary += f"- Pedagogical vocabulary density: {mr_data.get('pedagogical_density', 0)}\n"
            findings_summary += f"- Soul vocabulary density: {mr_data.get('soul_vocabulary_density', 0)}\n"

        pp_data = self.results['analyses'].get('poetry_philosophy', {})
        if pp_data.get('poetry_density', 0) > 0.001:
            findings_summary += f"\n### Poetry-Philosophy Dialectic (Rosen/Symposium)\n"
            findings_summary += f"- Poetry vocabulary density: {pp_data.get('poetry_density', 0)}\n"
            findings_summary += f"- Philosophy vocabulary density: {pp_data.get('philosophy_density', 0)}\n"
            findings_summary += f"- Quarrel/tension density: {pp_data.get('quarrel_density', 0)}\n"

        ag_data = self.results['analyses'].get('aspiration_gap', {})
        if ag_data.get('aspiration_density', 0) > 0.001:
            findings_summary += f"\n### Aspiration-Achievement Gap (Rosen/Symposium)\n"
            findings_summary += f"- Aspiration vocabulary density: {ag_data.get('aspiration_density', 0)}\n"
            findings_summary += f"- Achievement vocabulary density: {ag_data.get('achievement_density', 0)}\n"
            findings_summary += f"- Gap/tension vocabulary density: {ag_data.get('gap_density', 0)}\n"
            findings_summary += f"- Unresolved aspiration ratio: {ag_data.get('unresolved_aspiration_ratio', 0)}\n"

        syn_data = self.results['analyses'].get('synoptic_requirement', {})
        if syn_data.get('cross_reference_density', 0) > 0.001:
            findings_summary += f"\n### Synoptic Requirement (Rosen/Symposium)\n"
            findings_summary += f"- Cross-reference density: {syn_data.get('cross_reference_density', 0)}\n"
            findings_summary += f"- Intertextual density: {syn_data.get('intertextual_density', 0)}\n"
            findings_summary += f"- Incompleteness marker density: {syn_data.get('incompleteness_density', 0)}\n"

        if absent_topics:
            silence_section = f'The following topics were expected but absent or rare: {", ".join(absent_topics)}.'
        else:
            silence_section = ("No expected topics were provided for silence analysis. Consider: "
                               "given the text's declared subject and historical context, what topics "
                               "would a reader EXPECT to find discussed that are conspicuously absent?")

        prompt = f"""You are a scholar trained in the tradition of esoteric textual interpretation,
drawing on the methods of Leo Strauss ("Persecution and the Art of Writing"), Arthur Melzer
("Philosophy Between the Lines"), and the broader tradition including Maimonides, Al-Farabi,
Francis Bacon, Clement of Alexandria, and the Pythagorean/Kabbalistic numerological traditions.

You are analyzing the following text: "{self.title}"

A computational pre-analysis has been performed and yielded the following findings:

{findings_summary}

---

YOUR TASK: Perform a deep esoteric reading of this text, guided by the computational findings
above but going far beyond them. Proceed through the following stages:

## STAGE 1: LITERAL SURFACE READING
First, describe the text's apparent (exoteric) argument — what it seems to say on the surface.
What is its declared subject, its stated thesis, its overt conclusions? Who is the apparent
intended audience? This literal reading is the FOUNDATION of all esoteric interpretation
(per Melzer: you must take the surface with extreme seriousness before looking beneath it).

## STAGE 2: CONTRADICTION ANALYSIS
Examine the computationally flagged contradictions above. For each:
- Is this a genuine contradiction, or can it be harmonized?
- If genuine: which statement is more emphatic/public, and which is more hidden/qualified?
- Per Strauss: the less emphatic, more hidden statement is likelier to represent the
  author's true view. What does that imply?
- Does this contradiction fall under Maimonides' 5th cause (pedagogical simplification)
  or 7th cause (necessary concealment)?

## STAGE 3: STRUCTURAL ANALYSIS
Examine the text's architecture:
- What is placed at the STRUCTURAL CENTER of the work? (The computational analysis
  flagged specific center sentences — assess their significance.)
- Does the work exhibit RING or CHIASTIC structure? (Mirror ratio: {mirror_ratio})
- Are there numerologically significant structural features? (See findings above.)
- How does the chapter/section structure relate to the argument's movement?

## STAGE 4: SILENCE AND OMISSION
{silence_section}
- Why might the author have omitted these topics?
- Does the silence constitute a "negative argument"?

## STAGE 5: IRONY AND INDIRECT COMMUNICATION
Examine the flagged irony markers and the text's use of:
- Praise combined with qualification or negation
- Characters or voices whose reliability should be questioned
- Dramatic framing that undercuts stated positions
- Passages where the author appears to "protest too much"

## STAGE 6: DIGRESSIONS AND SCATTERED ARGUMENTS
Examine the computationally flagged digressions:
- Do they carry content that, when extracted and reassembled (per Maimonides'
  instruction to "combine scattered chapters"), yields a coherent hidden argument?
- Are the digressions positioned at structurally significant locations?

## STAGE 7: SOURCE ANALYSIS
If the text cites, quotes, or retells sources:
- Are the citations accurate, or has the author subtly distorted them
  (per Strauss on Machiavelli's retelling of David and Goliath)?
- What has been omitted from the source material?
- Do the distortions point in a consistent interpretive direction?

## STAGE 8: VOICE AND PERSONA ANALYSIS (KIERKEGAARD METHOD)
Examine the computationally detected voice/persona shifts:
- Does the text speak in a single consistent voice, or do different sections
  exhibit detectably different stylistic profiles?
- If multiple voices: do they hold contradictory positions (as Kierkegaard's
  pseudonyms do)? Is the reader meant to choose between them, or to recognize
  that no single voice represents the author's position?
- Does the author use characters, fictional speakers, or narrative frames
  to create distance from particular claims?

## STAGE 9: REGISTER ANALYSIS (AVERROES THREE-TIER METHOD)
Examine the computationally detected register transitions:
- Does the text shift between rhetorical (persuasive/imagistic), dialectical
  (argumentative/theological), and demonstrative (strict philosophical proof) modes?
- Where does the demonstrative register appear? Per Averroes, this is where
  the author speaks to the philosophical reader alone.
- Are there passages where the author seems to "dumb down" an argument
  (shifting to rhetorical register) or suddenly become more rigorous
  (shifting to demonstrative)? These transitions may mark the exoteric/esoteric boundary.

## STAGE 10: LOGOS/MYTHOS TRANSITIONS (PLATO METHOD)
Examine the detected shifts between argumentative and narrative/mythic modes:
- Where does the author abandon discursive argument and resort to story,
  myth, allegory, or image?
- Per Plato: these transitions signal the boundary of what reason can directly
  demonstrate. The mythos passages may carry the deepest philosophical content
  precisely BECAUSE it resists propositional statement.
- Do the mythos passages cluster at structurally significant locations?

## STAGE 11: MULTI-LEVEL READING (DANTE/KABBALISTIC METHOD)
Examine the computationally flagged polysemous passages:
- Can key passages be read simultaneously on multiple levels: literal,
  allegorical, moral, and anagogical (Dante) or Peshat/Remez/Derash/Sod (Kabbalah)?
- Are there words that function as hinges between physical and spiritual meaning
  (e.g., "light," "path," "fire," "water")?
- Does the text reward reading at each successive level with a more profound
  but also more dangerous interpretation?

## STAGE 12: MASK AND SELF-REFERENCE (NIETZSCHE METHOD)
Examine the detected mask/concealment vocabulary and self-referential passages:
- Does the author discuss concealment, surfaces, masks, or the act of writing itself?
- Per Nietzsche (BGE 40): "Every profound spirit needs a mask." Does the text
  ANNOUNCE its own concealment while still concealing?
- Is the text's fragmentation (rapid topic shifts, aphoristic compression)
  a deliberate strategy to prevent systematic appropriation of its teaching?

## STAGE 13: ACROSTIC AND STEGANOGRAPHIC PATTERNS
Examine any computationally detected acrostic/telestic patterns:
- Do the first or last letters of sentences, paragraphs, or chapters spell
  words, names, or meaningful sequences?
- Are there numerologically significant patterns in structural counts
  (chapter numbers, sentence counts) that align with gematria, isopsephy,
  or Pythagorean symbolism?

## STAGE 14: TRAPDOOR ANALYSIS (BENARDETE METHOD)
Examine the computationally detected trapdoors — local inconsistencies, hedged absolutes,
and non-sequiturs:
- Are there passages where a confident assertion is immediately qualified or
  undercut? Per Benardete: "an intentional flaw in the flow of the apparent
  argument induces us to drop beneath the surface to uncover the source of
  movement that reveals the real argument."
- Do apparent non-sequiturs (conclusions without adequate premises) signal that
  the stated conclusion is NOT what the argument actually demonstrates?
- Are there "impossible time-frames" or factual impossibilities (as in the
  Gorgias, whose dramatic setting spans the entire Peloponnesian War)?
- When you fall through a trapdoor, what deeper argument do you find beneath it?

## STAGE 15: DYADIC STRUCTURE (BENARDETE METHOD)
Examine the binary oppositions detected in the text:
- Are key pairs (e.g., body/soul, knowledge/opinion, one/many) presented as
  independent entities that later prove to be aspects of a single thing?
- Per Benardete: the movement from "conjunctive two" (mythical pairing of
  independent elements) to "disjunctive two" (mutually determining parts of
  a whole) IS the philosophical turn. Track this movement in the text.
- Do "phantom images" appear — split appearances (like sophist + statesman)
  that hide a single reality (the philosopher)?
- What is the "indeterminate dyad" at work in the text — the one that splits
  off part of itself or lies hidden behind its fractured appearances?

## STAGE 16: PERIAGOGE / STRUCTURAL REVERSAL (BENARDETE METHOD)
Examine whether the text exhibits the periagoge structure:
- Does the second half of the text invert, undermine, or radically deepen
  the conclusions of the first half?
- Per Benardete: every Platonic dialogue "reproduces in itself the conversion
  (periagoge) of the philosopher in the cave." Where is this turning point?
- Is there a "pathei mathos" structure — does the reader NEED to undergo the
  error of the first reading in order to understand the truth of the second?
- If the text were read backwards from the conclusion, would the argument
  appear entirely different from a sequential reading?

## STAGE 17: LOGOS-ERGON / SPEECH-DEED ANALYSIS (BENARDETE METHOD)
Examine the relationship between what is SAID and what is DONE in the text:
- Per Benardete (Encounters & Reflections): "I didn't understand that there was
  in fact an argument IN the action." The stated argument and the dramatic action
  may tell different stories.
- Are there passages where characters or the author SAY one thing while the
  narrative/dramatic context SHOWS something else?
- Track "burstlike" arguments (sudden counterexamples that force immediate
  concession) vs. "filamentlike" arguments (gradual deformation of terms that
  turns the reader around without their noticing).
- Per Benardete (Second Sailing): "the unexpected break and the unexpected join
  in arguments constitute the way of eidetic analysis."

## STAGE 18: ONOMASTIC / ETYMOLOGICAL ANALYSIS (BENARDETE METHOD)
Examine names and their meanings as structural keys:
- Per Benardete (The Bow and the Lyre): "Oedipus's name designates two things,
  knowledge and lameness." "Odysseus has two names... both are significant names,
  but they apparently signify utterly different things. The plot connects them."
- Are character names, place names, or titles philosophically significant?
- Are there puns, double meanings, or etymological commentaries that carry
  argumentative weight beyond mere wordplay?
- Per Benardete: the outis/metis pun encodes the relation of anonymity and mind —
  "the nonparticularization of mind."

## STAGE 19: RECOGNITION SCENE / CONCEALMENT-TEST-REVEAL (BENARDETE METHOD)
Examine whether the text enacts a recognition scene structure:
- Per Benardete on the Odyssey: "Identity is not given but achieved through narrative."
  The concealment→test→reveal pattern is the deep grammar of both epic and dialogue.
- Does the text conceal something that is progressively revealed?
- Are there testing sequences where a character or idea is subjected to trial?
- Per Aristotle (Poetics 1452a): anagnorisis (recognition) paired with peripeteia
  (reversal) produces the most powerful dramatic effect. Does this text pair them?

## STAGE 20: NOMOS-PHYSIS / CONVENTION-NATURE ANALYSIS (HERODOTEAN METHOD)
Examine the text's treatment of the convention/nature distinction:
- Per Benardete (Herodotean Inquiries): Herodotus "must discover the human beneath
  the infinite disguises of custom." His method: look at alien customs to reveal
  the problematic character of one's own.
- Does the text present customs, laws, or conventions alongside natural necessities?
- Does it use the foreign or unfamiliar to defamiliarize what the reader takes
  for granted?
- The Gyges/Candaules paradigm: the tension between eyes (nature/knowledge) and
  ears (convention/report), between shame (nomos) and sight (physis).

## STAGE 21: IMPOSSIBLE ARITHMETIC / POETIC DIALECTIC (BENARDETE METHOD)
Examine the text's use of productive impossibilities:
- Per Benardete (The Bow and the Lyre): "The poet divides what is necessarily one
  and unites what is necessarily two. He practices his own kind of dialectic in
  which the truth shows up in two spurious forms."
- Are there passages that present apparently impossible arithmetic (one = many,
  same = different) that the argument/plot resolves?
- Per Benardete: "The plot is the disclosure of impossibilities or apparent
  impossibilities." Does the text lead the reader through an impossibility
  to a truth that could not have been stated directly?

## STAGE 22: RHETORIC OF CONCEALMENT (ROSEN ON MONTESQUIEU)
Examine the text's rhetoric of concealment:
- Per Rosen: Montesquieu's Spirit of the Laws conceals a deductive structure beneath
  a "somewhat disheveled surface." The apparent disorder is itself rhetorical.
- Does the text announce its own disorderliness or unsystematic character while
  actually being highly structured?
- Are there passages that discuss hidden design, architecture, or structure beneath
  apparent disorder?
- Is there evidence of defensive maneuvering against anticipated charges?

## STAGE 23: TRANSCENDENTAL AMBIGUITY (ROSEN ON KANT)
Examine the text's use of deliberately unresolved ambiguities:
- Per Rosen: Kant's key terms carry double meanings that are NOT resolved because
  the ambiguity IS the philosophical point.
- Are key terms explicitly marked as ambiguous or multi-sensed?
- Does the text refuse to collapse equivocal terms into univocity?
- Are there passages that oscillate between competing interpretations without choosing?

## STAGE 24: RHETORIC OF FRANKNESS (ROSEN)
Examine performative transparency as potential concealment:
- Per Rosen: Declarations of honesty and openness can function as concealment by
  deflecting attention from what remains hidden.
- Where does the author declare frankness, candor, or absence of concealment?
- Do these frank claims co-occur with hedging language in the same paragraphs?
- Is "dare to know" itself part of a rhetorical strategy?

## STAGE 25: INTUITION-ANALYSIS DIALECTIC (ROSEN)
Examine appeals to non-discursive knowing:
- Per Rosen (The Limits of Analysis): All analysis rests on prior intuition—direct seeing.
- Does the text acknowledge limits of what can be formalized or analyzed?
- Are there appeals to self-evident truths, immediate perception, or primitive terms?
- Does the text discuss the impossibility of defining "definition" or analyzing "analysis"?

## STAGE 26: LOGOGRAPHIC NECESSITY (BENARDETE)
Examine whether formal constraints carry philosophical content:
- Per Benardete: "It is not the arguments in Plato that convey the truth but the
  conditions for the arguments that carry the logos."
- Do dialogue form, dramatic setting, or narrative structure seem to carry meaning
  independent of explicit argument?
- Are there passages where form/structure/constraint is discussed as if carrying content?
- Does the text show rather than say?

## STAGE 27: THEOLOGICAL DISAVOWAL (ROSEN)
Examine theology disguised as philosophy:
- Per Rosen: Modern philosophy reproduces theological structures (God, grace, immortality)
  through philosophical terminology.
- Where does theological vocabulary appear?
- Are there explicit disavowals ("not theological, but philosophical")?
- Do philosophical substitutes (postulates, regulative ideas, transcendental conditions)
  appear near theological language?

## STAGE 28: DEFENSIVE WRITING (ROSEN/STRAUSS)
Examine preemptive rebuttals, disclaimers, and excessive qualification:
- Per Rosen on Montesquieu's preface: it is a "defensive maneuver."
- What charges or criticisms does the author anticipate and rebut?
- Are there appeals to orthodoxy, tradition, or the wisdom of the ancients?
- Do multiple defensive strategies cluster together (suggesting genuine threat)?

## STAGE 29: NATURE-FREEDOM OSCILLATION (ROSEN ON MONTESQUIEU)
Examine systematic alternation between necessity and freedom:
- Per Rosen: Montesquieu oscillates between treating behavior as determined by
  natural law and as free/open. This oscillation is the philosophical insight.
- Does the text alternate between nature/necessity-vocabulary and freedom/choice-vocabulary?
- Do these alternations occur at regular structural intervals?
- Does the text acknowledge the tension explicitly?

## STAGE 30: POSTMODERN MISREADING VULNERABILITY (Rosen Method)
Examine how a postmodern/deconstructionist reader would misread this text:
- What features would postmodernism latch onto? (Presence/absence language, binary
  oppositions, paradoxes, writing/speech metaphors, moments of "undecidability"?)
- What features would postmodernism MISS? (Intentional design, audience accommodation,
  esoteric layering, noetic content, formal constraints carrying philosophical meaning?)
- Per Rosen: Derrida "is apparently deaf to two kinds of speech in Plato: the speech of
  poetry or myth, and the speech of silence. He attends to the myths, but he does not hear
  them." What in this text can only be heard, not deconstructed?
- Distinguish between what IS paradoxical/unstable in the text (genuine philosophical
  tension) and what APPEARS paradoxical to a reader who has dissolved authorial intention
  (mere artifact of the postmodern framework).
- Does the text contain features that actively resist postmodern appropriation?

## STAGE 31: DRAMATIC CONTEXT ANALYSIS (Rosen/Symposium)
Examine how speaker identity and dramatic setting shape philosophical meaning:
- WHO is speaking? What are their characteristics, biases, limitations?
- To WHOM? How does audience composition constrain what can be said?
- WHEN and WHERE? How do occasion and setting affect the discourse?
- Per Rosen: "The speeches are not detachable philosophical arguments but dramatic
  performances whose meaning depends on who delivers them and to whom."
- What arguments are enabled or foreclosed by the dramatic situation?

## STAGE 32: SPEECH SEQUENCING AND PROGRESSION (Rosen/Symposium)
Examine how sequential structure carries philosophical meaning:
- Do successive sections/speeches build on, contradict, or transform each other?
- Is there an ascending or descending order? Does the sequence matter?
- Per Rosen: The order of speeches in the Symposium is philosophically meaningful;
  each speech responds to and modifies its predecessor.
- What would be lost if the sections were rearranged?
- Does the final position carry special authority, or does it too get qualified?

## STAGE 33: PHILOSOPHICAL COMEDY (Rosen/Symposium)
Examine the relationship between comedy and philosophy in the text:
- Is serious content delivered through playful, comic, or ironic form?
- Per Rosen: Aristophanes' comic speech about the round people contains essential
  philosophical content about human nature and eros — the comedy IS the philosophy.
- Does the text deploy laughter, absurdity, or wit as philosophical instruments?
- Would reducing the text to either pure seriousness or pure jest lose meaning?

## STAGE 34: DAIMONIC MEDIATION (Rosen/Symposium)
Examine the role of intermediate beings, concepts, or positions:
- Per Rosen/Diotima: Eros is a daimon — neither god nor mortal, but an intermediary.
  Philosophy itself occupies this daimonic middle position between ignorance and wisdom.
- Does the text deploy mediating figures or concepts that bridge opposites?
- Are there "neither/nor" or "both/and" constructions that resist binary classification?
- Does the text itself occupy an intermediate position between genres or discourses?

## STAGE 35: MEDICINAL RHETORIC (Rosen/Symposium)
Examine whether speech is adapted to the condition of the listener:
- Per Rosen/Eryximachus: rhetoric as medicine — different souls need different speeches.
  The philosopher-physician administers truth in measured doses.
- Does the text vary its register, vocabulary, or argument style for different audiences?
- Are there passages that seem to "prepare" the reader for harder truths?
- Is there evidence of graduated disclosure — simpler truths first, harder ones later?
- Does the text acknowledge that some truths are harmful to unprepared listeners?

## STAGE 36: POETRY-PHILOSOPHY DIALECTIC (Rosen/Symposium)
Examine the ancient quarrel between poetry and philosophy:
- Per Rosen: Socrates demands the same person write both comedy and tragedy. The quarrel
  between poetry and philosophy is not resolved by eliminating one side.
- Does the text operate at the intersection of poetic and philosophical discourse?
- Are there moments where the text shifts from argumentative to imaginative modes?
- Does the text use narrative, myth, or image to convey what argument alone cannot?

## STAGE 37: ASPIRATION-ACHIEVEMENT GAP (Rosen/Symposium)
Examine the permanent gap between aspiration and achievement:
- Per Rosen/Diotima: Eros is desire for what one lacks. Philosophy is the permanent
  state of loving wisdom without possessing it. This gap is not a defect.
- Does the text maintain unresolved tensions without forcing closure?
- Are there explicit markers of incompleteness, aspiration, or longing?
- Does the text promise more than it delivers — and is this deliberate?
- Per Rosen: texts that resolve all tensions have lost the philosophical impulse.

## STAGE 38: SYNOPTIC REQUIREMENT (Rosen/Symposium)
Examine whether the text demands knowledge beyond itself for full comprehension:
- Per Rosen: understanding any Platonic dialogue requires knowledge of the wider corpus.
  This cross-referential structure is itself a philosophical technique.
- Does the text make explicit or implicit references to other works?
- Are there arguments that seem incomplete or puzzling without external context?
- Does the text assume prior familiarity with specific traditions or texts?
- Is there evidence of deliberate incompleteness designed to send the reader elsewhere?

## STAGE 39: THE ESOTERIC ARGUMENT
Based on ALL of the above (Stages 1-38), attempt to reconstruct the text's
ESOTERIC argument — the teaching that the careful reader is meant to discover
beneath the surface. Structure your reconstruction as:

1. **The exoteric teaching** (what the text appears to say)
2. **The esoteric teaching** (what the text actually communicates to the careful reader)
3. **The methods of concealment** (which specific techniques from the tradition
   the author employs — name each method and cite the historical precedent from
   this list: Maimonides' 7 causes, Strauss's contradiction principle, Al-Farabi's
   exoteric/esoteric division, Averroes' three tiers, Kierkegaard's indirect
   communication, Nietzsche's mask theory, Dante's four levels, Plato's
   logos/mythos boundary, Bacon's acroamatique method, Pythagorean numerology,
   Kabbalistic gematria, Diderot's cross-references, the commentary form as
   concealment, Rosen's methods: rhetoric of concealment, transcendental ambiguity,
   defensive writing)
4. **The evidence** (the specific textual passages that support this reading)
5. **The motive** (why did the author conceal? Which of Melzer's four types applies:
   defensive, protective, pedagogical, or political esotericism?)
6. **Confidence level** (how strong is the case? What alternative readings exist?)

## STAGE 40: SAFEGUARDS AGAINST OVER-READING
Finally, critically evaluate your own esoteric reading:
- Does it produce a MORE coherent interpretation than the surface reading, or merely
  a different one?
- Is the evidence convergent (multiple methods pointing to the same conclusion) or
  scattered (isolated anomalies)?
- Could the patterns be explained by compositional accident, editorial history, or
  genre conventions rather than deliberate concealment?
- What would DISPROVE your esoteric reading?

---

IMPORTANT METHODOLOGICAL NOTES:
- You are looking for DELIBERATE concealment by a skilled author, not random noise.
- Not every text is esoteric. If the evidence is weak, say so.
- Esoteric reading is "a form of rhetoric" (Melzer), not a mechanical procedure.
- The computational findings are STARTING POINTS, not conclusions.
- Your goal is to help the reader see what a careful, historically informed reader
  would see — not to impose a reading the text does not support.

Please provide the text for analysis, or if it has already been provided, begin your
analysis now.
"""
        return prompt

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def export_report(self, filepath: str):
        """Export the full analysis as a Markdown report."""
        if not self.results:
            self.full_analysis()

        lines = []
        lines.append(f"# Esoteric Writing Analysis: {self.title}")
        lines.append("")
        lines.append(f"**Composite Esoteric Score: {self.results['composite_esoteric_score']}**")
        lines.append(f"")
        lines.append(f"*{self.results['score_interpretation']}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        stats = self.results['text_statistics']
        lines.append("## Text Statistics")
        lines.append(f"- Words: {stats['total_words']:,}")
        lines.append(f"- Sentences: {stats['total_sentences']:,}")
        lines.append(f"- Paragraphs: {stats['total_paragraphs']:,}")
        lines.append(f"- Chapters/Sections: {stats['total_chapters']}")
        lines.append("")

        for name, analysis in self.results['analyses'].items():
            lines.append(f"## {analysis.get('method', name)}")
            lines.append(f"**Score: {analysis.get('score', 0)}**")
            lines.append("")

            if 'precedent' in analysis:
                lines.append(f"*Historical precedent: {analysis['precedent']}*")
                lines.append("")

            if 'interpretation' in analysis:
                lines.append(f"> {analysis['interpretation']}")
                lines.append("")

            # Method-specific evidence rendering
            if name == 'contradiction' and analysis.get('evidence'):
                lines.append("### Top Contradictions")
                for c in analysis['evidence'][:10]:
                    lines.append(f"**Paragraphs {c['paragraph_a']} vs {c['paragraph_b']}** "
                                 f"(tension: {c['tension_score']})")
                    lines.append(f"- A: \"{c['excerpt_a']}\"")
                    lines.append(f"- B: \"{c['excerpt_b']}\"")
                    lines.append("")

            elif name == 'central_placement':
                if 'quintile_densities' in analysis:
                    lines.append("### Key-Term Density by Position")
                    for label, density in analysis['quintile_densities'].items():
                        marker = " ◄◄◄" if "CENTER" in label else ""
                        lines.append(f"- {label}: {density}{marker}")
                    lines.append(f"- Center-to-periphery ratio: {analysis.get('center_ratio_to_periphery', 0)}")
                    lines.append("")
                if analysis.get('top_center_sentences'):
                    lines.append("### Top Sentences at Center")
                    for s in analysis['top_center_sentences']:
                        lines.append(f"- [#{s['sentence_index']}] \"{s['text']}\"")
                    lines.append("")

            elif name == 'numerology':
                if analysis.get('structural_counts'):
                    lines.append("### Structural Counts")
                    for unit, count in analysis['structural_counts'].items():
                        lines.append(f"- {unit}: {count}")
                    lines.append("")
                if analysis.get('significant_number_hits'):
                    lines.append("### Significant Number Matches")
                    for h in analysis['significant_number_hits']:
                        lines.append(f"- {h['unit']} = {h['count']}: {h.get('significance', h.get('divisible_by', ''))}")
                    lines.append("")
                if analysis.get('title_numerology'):
                    lines.append("### Title Numerology")
                    for k, v in analysis['title_numerology'].items():
                        lines.append(f"- {k}: {v}")
                    lines.append("")

            elif name == 'silence':
                if analysis.get('absent_topics'):
                    lines.append(f"### Absent Topics: {', '.join(analysis['absent_topics'])}")
                    lines.append("")
                if analysis.get('rare_topics'):
                    lines.append(f"### Rare Topics: {', '.join(analysis['rare_topics'])}")
                    lines.append("")

            elif name == 'repetition':
                if analysis.get('suspiciously_emphatic_chapters'):
                    lines.append("### Suspiciously Emphatic Chapters")
                    for e in analysis['suspiciously_emphatic_chapters']:
                        lines.append(f"- Ch. {e['chapter']} ({e['title']}): "
                                     f"praise density {e['praise_density']}")
                    lines.append("")

            elif name == 'symmetry':
                if analysis.get('mirror_pairs'):
                    lines.append("### Mirror Pairs (Ring Composition)")
                    for p in analysis['mirror_pairs'][:10]:
                        lines.append(f"- Ch. {p['chapter_a']} ↔ Ch. {p['chapter_b']}: "
                                     f"similarity {p['mirror_similarity']}")
                    lines.append("")

            elif name == 'irony':
                if analysis.get('irony_markers'):
                    lines.append("### Irony Markers")
                    for m in analysis['irony_markers'][:10]:
                        lines.append(f"- [#{m['sentence_index']}] \"{m['text'][:200]}\"")
                        lines.append(f"  Praise: {m['praise_words']}, "
                                     f"Negation: {m['negation_words']}, "
                                     f"Qualifiers: {m['qualifier_words']}")
                    lines.append("")

            elif name == 'digression':
                if analysis.get('digressions'):
                    lines.append("### Detected Digressions")
                    for d in analysis['digressions'][:10]:
                        lines.append(f"- ¶{d['paragraph_index']} at {d['position_in_text']} "
                                     f"(z: {d['z_score']}): \"{d['excerpt'][:200]}\"")
                    lines.append("")

            elif name == 'lexical_density':
                if analysis.get('high_density_chapters'):
                    lines.append("### High-Density Chapters (heightened authorial care)")
                    for c in analysis['high_density_chapters']:
                        lines.append(f"- Ch. {c['chapter']} ({c['title']}): "
                                     f"TTR {c['type_token_ratio']}, z={c.get('ttr_z_score', 0)}")
                    lines.append("")

            elif name == 'acrostic':
                seqs = analysis.get('letter_sequences', {})
                if seqs:
                    lines.append("### Letter Sequences Extracted")
                    for label, seq in seqs.items():
                        if seq:
                            lines.append(f"- **{label}**: `{seq[:80]}`")
                    lines.append("")
                if analysis.get('words_found'):
                    lines.append("### Words Found in Acrostic/Telestic Positions")
                    for w in analysis['words_found'][:10]:
                        lines.append(f"- '{w['word']}' in {w['source']} at position {w['position']}")
                    lines.append("")

            elif name == 'hapax_legomena':
                if analysis.get('philosophical_hapax'):
                    lines.append(f"### Philosophically Loaded Hapax: {', '.join(analysis['philosophical_hapax'])}")
                    lines.append("")
                lines.append(f"- Total hapax legomena: {analysis.get('total_hapax', 0)}")
                lines.append(f"- Hapax ratio: {analysis.get('hapax_ratio', 0)}")
                if analysis.get('positional_density'):
                    lines.append("### Hapax Positional Distribution")
                    for pos, density in analysis['positional_density'].items():
                        marker = " <<<" if pos == 'center' else ""
                        lines.append(f"- {pos}: {density}{marker}")
                lines.append("")

            elif name == 'voice_consistency':
                if analysis.get('voice_shifts'):
                    lines.append("### Detected Voice/Persona Shifts")
                    for vs in analysis['voice_shifts']:
                        lines.append(f"- Ch. {vs['chapter']} ({vs['title']}): "
                                     f"stylistic distance z={vs['z_score']}")
                    lines.append("")
                lines.append(f"- Overall stylistic variance: {analysis.get('overall_stylistic_variance', 0)}")
                lines.append("")

            elif name == 'register':
                if analysis.get('chapter_registers'):
                    lines.append("### Register Profile by Chapter")
                    for cr in analysis['chapter_registers']:
                        lines.append(f"- Ch. {cr['chapter']} ({cr['title']}): **{cr['dominant_register']}** "
                                     f"(rhet:{cr['rhetorical_pct']} dial:{cr['dialectical_pct']} "
                                     f"demo:{cr['demonstrative_pct']})")
                    lines.append("")
                if analysis.get('register_transitions'):
                    lines.append("### Register Transitions")
                    for rt in analysis['register_transitions']:
                        lines.append(f"- Ch. {rt['from_chapter']} ({rt['from_register']}) -> "
                                     f"Ch. {rt['to_chapter']} ({rt['to_register']})")
                    lines.append("")

            elif name == 'logos_mythos':
                mc = analysis.get('mode_counts', {})
                lines.append(f"- Logos paragraphs: {mc.get('logos', 0)}, "
                             f"Mythos: {mc.get('mythos', 0)}, Mixed: {mc.get('mixed', 0)}")
                lines.append(f"- Dominant mode: {analysis.get('dominant_mode', 'unknown')}")
                if analysis.get('transitions'):
                    lines.append("### Logos/Mythos Transitions")
                    for lt in analysis['transitions'][:10]:
                        lines.append(f"- Para {lt['paragraph']} at {lt['position']}: "
                                     f"{lt['from']} -> {lt['to']}")
                lines.append("")

            elif name == 'commentary_divergence':
                if analysis.get('divergences'):
                    lines.append("### Most Divergent Sections")
                    for d in analysis['divergences'][:10]:
                        lines.append(f"- Ch. {d['chapter']} ({d['title']}): "
                                     f"divergence={d['divergence_score']}, "
                                     f"similarity={d['similarity_to_source']}")
                    lines.append("")

            elif name == 'polysemy':
                if analysis.get('polysemous_paragraphs'):
                    lines.append("### Multi-Domain Passages")
                    for pp in analysis['polysemous_paragraphs'][:10]:
                        lines.append(f"- Para {pp['paragraph']}: {pp['domain_count']} domains "
                                     f"({', '.join(pp['domains_present'])})")
                    lines.append("")
                if analysis.get('cross_domain_words_in_text'):
                    lines.append("### Cross-Domain Words")
                    for w, doms in list(analysis['cross_domain_words_in_text'].items())[:10]:
                        lines.append(f"- '{w}': {', '.join(doms)}")
                    lines.append("")

            elif name == 'aphoristic_fragmentation':
                lines.append(f"- Fragmentation index: {analysis.get('fragmentation_index', 0)}")
                lines.append(f"- Mask vocabulary density: {analysis.get('mask_vocabulary_density', 0)}")
                lines.append(f"- Meta vocabulary density: {analysis.get('meta_vocabulary_density', 0)}")
                if analysis.get('mask_sentences'):
                    lines.append("### Mask/Concealment Self-References")
                    for ms in analysis['mask_sentences'][:5]:
                        lines.append(f"- [#{ms['sentence_index']}] \"{ms['text'][:200]}\"")
                if analysis.get('sharp_breaks'):
                    lines.append("### Sharpest Topical Breaks")
                    for sb in analysis['sharp_breaks'][:5]:
                        lines.append(f"- Between paragraphs {sb['between_paragraphs']}: "
                                     f"similarity={sb['similarity']}")
                lines.append("")

            elif name == 'trapdoor':
                lines.append(f"- Total trapdoors detected: {analysis.get('total_trapdoors', 0)}")
                lines.append(f"- Trapdoor density: {analysis.get('trapdoor_density', 0)}")
                if analysis.get('local_contradictions'):
                    lines.append("### Local Self-Contradictions")
                    for lc in analysis['local_contradictions'][:5]:
                        lines.append(f"- Sent. {lc['sentence_a']} vs {lc['sentence_b']}: "
                                     f"shared={lc['shared_content']}")
                if analysis.get('hedge_near_absolute'):
                    lines.append("### Hedged Absolutes")
                    for ha in analysis['hedge_near_absolute'][:5]:
                        lines.append(f"- Sent. {ha['absolute_sentence_index']}: "
                                     f"\"{ha['absolute_text'][:150]}\"")
                if analysis.get('non_sequiturs'):
                    lines.append("### Potential Non-Sequiturs")
                    for ns in analysis['non_sequiturs'][:5]:
                        lines.append(f"- Sent. {ns['conclusion_sentence']}: "
                                     f"\"{ns['text'][:150]}\"")
                lines.append("")

            elif name == 'dyadic_structure':
                lines.append(f"- Total binary pairs: {analysis.get('total_binary_pairs', 0)}")
                lines.append(f"- Binary pair density: {analysis.get('binary_pair_density', 0)}")
                lines.append(f"- Eidetic vocabulary density: {analysis.get('eidetic_vocabulary_density', 0)}")
                if analysis.get('recurring_pairs'):
                    lines.append("### Recurring Binary Oppositions")
                    for rp in analysis['recurring_pairs'][:10]:
                        lines.append(f"- {rp['pair'][0]} / {rp['pair'][1]}: {rp['count']}x")
                if analysis.get('convergence_markers'):
                    lines.append("### Convergence Markers (Conjunctive -> Disjunctive)")
                    for cm in analysis['convergence_markers'][:5]:
                        lines.append(f"- {cm['pair']}: para {cm['first_position']} -> "
                                     f"para {cm['convergence_position']}")
                if analysis.get('phantom_passages'):
                    lines.append("### Phantom Image Passages")
                    for ph in analysis['phantom_passages'][:5]:
                        lines.append(f"- Para {ph['paragraph']}: {ph['phantom_terms']}")
                lines.append("")

            elif name == 'periagoge':
                lines.append(f"- Polarity shift (1st->2nd half): {analysis.get('polarity_shift', 0)}")
                lines.append(f"- 1st half polarity: {analysis.get('first_half_polarity', 0)}")
                lines.append(f"- 2nd half polarity: {analysis.get('second_half_polarity', 0)}")
                lines.append(f"- Reversal count: {analysis.get('reversal_count', 0)}")
                lines.append(f"- Turning vocabulary density: {analysis.get('turning_vocabulary_density', 0)}")
                if analysis.get('reversals'):
                    lines.append("### Detected Reversals")
                    for rv in analysis['reversals'][:5]:
                        lines.append(f"- \"{rv['first_half_sentence'][:100]}...\" -> "
                                     f"\"{rv['second_half_sentence'][:100]}...\"")
                if analysis.get('vocabulary_shifts'):
                    lines.append("### Largest Vocabulary Shifts (1st vs 2nd Half)")
                    for vs in analysis['vocabulary_shifts'][:10]:
                        lines.append(f"- '{vs['word']}': {vs['first_half_freq']} -> "
                                     f"{vs['second_half_freq']} ({vs['direction']})")
                lines.append("")

            elif name == 'logos_ergon':
                lines.append(f"- Speech/action ratio: {analysis.get('speech_action_ratio', 0)}")
                lines.append(f"- Speech-action mismatches: {analysis.get('mismatch_count', 0)}")
                lines.append(f"- Burstlike shifts: {analysis.get('burstlike_shifts', 0)}")
                lines.append(f"- Filamentlike shifts: {analysis.get('filamentlike_shifts', 0)}")
                if analysis.get('mismatches'):
                    lines.append("### Speech-Action Mismatches")
                    for mm in analysis['mismatches'][:5]:
                        lines.append(f"- Para {mm['paragraph_index']}: speech={mm['speech_density']}, action={mm['action_density']}")
                lines.append("")

            elif name == 'onomastic':
                lines.append(f"- Naming density: {analysis.get('naming_density', 0)}")
                lines.append(f"- Etymological passages: {analysis.get('naming_passage_count', 0)}")
                lines.append(f"- Proper noun count: {analysis.get('proper_noun_count', 0)}")
                lines.append(f"- Proper noun diversity: {analysis.get('proper_noun_diversity', 0)}")
                if analysis.get('top_proper_nouns'):
                    lines.append("### Most Frequent Proper Nouns")
                    for pn in analysis['top_proper_nouns'][:15]:
                        lines.append(f"- {pn[0]}: {pn[1]}x")
                if analysis.get('naming_passages'):
                    lines.append("### Etymological/Naming Passages")
                    for np in analysis['naming_passages'][:5]:
                        lines.append(f"- Sent {np['sentence_index']}: {np['excerpt'][:120]}...")
                lines.append("")

            elif name == 'recognition_structure':
                lines.append(f"- Ideal pattern (conceal→test→reveal): {analysis.get('ideal_pattern_detected', False)}")
                lines.append(f"- Concealment terms: {analysis.get('concealment_count', 0)}")
                lines.append(f"- Testing terms: {analysis.get('testing_count', 0)}")
                lines.append(f"- Revelation terms: {analysis.get('revelation_count', 0)}")
                if analysis.get('phase_densities'):
                    lines.append("### Phase Densities (Thirds)")
                    for idx, pd in enumerate(analysis['phase_densities']):
                        third_label = ['First', 'Middle', 'Last'][idx]
                        lines.append(f"- {third_label}: conceal={pd.get('concealment',0)}, "
                                     f"test={pd.get('testing',0)}, reveal={pd.get('revelation',0)}")
                lines.append("")

            elif name == 'nomos_physis':
                lines.append(f"- Nomos density: {analysis.get('nomos_density', 0)}")
                lines.append(f"- Physis density: {analysis.get('physis_density', 0)}")
                lines.append(f"- Co-occurrences: {analysis.get('co_occurrence_count', 0)}")
                lines.append(f"- Comparative density: {analysis.get('comparative_density', 0)}")
                if analysis.get('co_occurrences'):
                    lines.append("### Nomos-Physis Co-occurrence Passages")
                    for co in analysis['co_occurrences'][:5]:
                        lines.append(f"- Sent {co['sentence_index']}: nomos={co['nomos_terms']}, physis={co['physis_terms']}")
                lines.append("")

            elif name == 'impossible_arithmetic':
                lines.append(f"- Impossibility density: {analysis.get('impossibility_density', 0)}")
                lines.append(f"- Arithmetic density: {analysis.get('arithmetic_density', 0)}")
                lines.append(f"- Poetic dialectic passages: {analysis.get('poetic_dialectic_passage_count', 0)}")
                lines.append(f"- 'Impossible yet true' patterns: {analysis.get('impossible_yet_true_count', 0)}")
                if analysis.get('poetic_dialectic_passages'):
                    lines.append("### Poetic Dialectic Passages")
                    for pdp in analysis['poetic_dialectic_passages'][:5]:
                        lines.append(f"- Sent {pdp['sentence_index']}: impossibility={pdp['impossibility_terms']}, "
                                     f"arithmetic={pdp['arithmetic_terms']}")
                lines.append("")

            elif name == 'rhetoric_of_concealment':
                lines.append(f"- Concealment density: {analysis.get('concealment_density', 0)}")
                lines.append(f"- Design density: {analysis.get('design_density', 0)}")
                lines.append(f"- Defensive density: {analysis.get('defensive_density', 0)}")
                lines.append(f"- Co-occurrence boost: {analysis.get('co_occurrence_boost', 0)}")
                lines.append("")

            elif name == 'transcendental_ambiguity':
                lines.append(f"- Ambiguity marker density: {analysis.get('ambiguity_marker_density', 0)}")
                lines.append(f"- Resistance marker density: {analysis.get('resistance_marker_density', 0)}")
                lines.append(f"- Multi-sense density: {analysis.get('multi_sense_density', 0)}")
                lines.append(f"- Ambiguous passage count: {analysis.get('ambiguous_passage_count', 0)}")
                if analysis.get('ambiguous_passages'):
                    lines.append("### Ambiguous Passages")
                    for ap in analysis['ambiguous_passages'][:3]:
                        lines.append(f"- Para {ap['paragraph']}: markers={ap['ambiguity_markers']} "
                                     f"resistance={ap['resistance_markers']}")
                lines.append("")

            elif name == 'rhetoric_of_frankness':
                lines.append(f"- Frankness density: {analysis.get('frankness_density', 0)}")
                lines.append(f"- Daring density: {analysis.get('daring_density', 0)}")
                lines.append(f"- Hedging density: {analysis.get('hedging_density', 0)}")
                lines.append(f"- Performative frankness count: {analysis.get('performative_frankness_count', 0)}")
                if analysis.get('frank_passages'):
                    lines.append("### Performative Frankness Passages")
                    for fp in analysis['frank_passages'][:3]:
                        lines.append(f"- Para {fp['paragraph']}: frank={fp['frankness_markers']} hedge={fp['hedging_markers']}")
                lines.append("")

            elif name == 'intuition_analysis':
                lines.append(f"- Intuition density: {analysis.get('intuition_density', 0)}")
                lines.append(f"- Analysis limit density: {analysis.get('analysis_limit_density', 0)}")
                lines.append(f"- Reflexive density: {analysis.get('reflexive_density', 0)}")
                lines.append(f"- Intuitive passage count: {analysis.get('intuitive_passage_count', 0)}")
                if analysis.get('intuitive_passages'):
                    lines.append("### Intuitive/Pre-analytical Passages")
                    for ip in analysis['intuitive_passages'][:3]:
                        lines.append(f"- Para {ip['paragraph']}: intuition={ip['intuition_markers']} "
                                     f"limits={ip['limit_markers']} reflexive={ip['reflexive_markers']}")
                lines.append("")

            elif name == 'logographic_necessity':
                lines.append(f"- Constraint density: {analysis.get('constraint_density', 0)}")
                lines.append(f"- Form-content density: {analysis.get('form_content_density', 0)}")
                lines.append(f"- Narrative density: {analysis.get('narrative_density', 0)}")
                lines.append(f"- Logographic passage count: {analysis.get('logographic_passage_count', 0)}")
                if analysis.get('logographic_passages'):
                    lines.append("### Form-as-Content Passages")
                    for lp in analysis['logographic_passages'][:3]:
                        lines.append(f"- Para {lp['paragraph']}: constraints={lp['constraint_markers']} "
                                     f"form={lp['form_content_markers']} narrative={lp['narrative_markers']}")
                lines.append("")

            elif name == 'theological_disavowal':
                lines.append(f"- Theological density: {analysis.get('theological_density', 0)}")
                lines.append(f"- Philosophical substitute density: {analysis.get('philosophical_substitute_density', 0)}")
                lines.append(f"- Disavowal density: {analysis.get('disavowal_density', 0)}")
                lines.append(f"- Theological passage count: {analysis.get('theo_passage_count', 0)}")
                if analysis.get('theological_passages'):
                    lines.append("### Theological-Philosophical Passages")
                    for tp in analysis['theological_passages'][:3]:
                        lines.append(f"- Para {tp['paragraph']}: theological={tp['theological_terms']} "
                                     f"disavowal={tp['disavowal_markers']}")
                lines.append("")

            elif name == 'defensive_writing':
                lines.append(f"- Defensive passage count: {analysis.get('defensive_passage_count', 0)}")
                lines.append(f"- Multi-category defensive ratio: {analysis.get('multi_category_ratio', 0)}")
                lines.append(f"- Orthodox appeal density: {analysis.get('orthodox_appeal_density', 0)}")
                lines.append(f"- Preemptive rebuttal density: {analysis.get('preemptive_density', 0)}")
                if analysis.get('defensive_passages'):
                    lines.append("### Defensive Strategy Passages")
                    for dp in analysis['defensive_passages'][:3]:
                        lines.append(f"- Para {dp['paragraph']}: defensive={dp['defensive_markers']} "
                                     f"orthodox={dp['orthodox_appeals']} preempt={dp['preemptive_rebuttals']}")
                lines.append("")

            elif name == 'nature_freedom_oscillation':
                lines.append(f"- Nature density: {analysis.get('nature_density', 0)}")
                lines.append(f"- Freedom density: {analysis.get('freedom_density', 0)}")
                lines.append(f"- Oscillation frequency: {analysis.get('oscillation_frequency', 0)}")
                lines.append(f"- Oscillation count: {analysis.get('oscillation_count', 0)}")
                lines.append(f"- Nature-dominant paras: {analysis.get('nature_dominant_paragraphs', 0)}")
                lines.append(f"- Freedom-dominant paras: {analysis.get('freedom_dominant_paragraphs', 0)}")
                lines.append(f"- Explicit tension acknowledged: {analysis.get('explicit_tension_acknowledged', False)}")
                lines.append("")

            elif name == 'dramatic_context':
                lines.append(f"- Speaker vocabulary density: {analysis.get('speaker_vocabulary_density', 0)}")
                lines.append(f"- Setting vocabulary density: {analysis.get('setting_vocabulary_density', 0)}")
                lines.append(f"- Attribution density: {analysis.get('attribution_density', 0)}")
                if analysis.get('dramatic_passages'):
                    lines.append("### Dramatic Context Passages")
                    for dp in analysis['dramatic_passages'][:5]:
                        lines.append(f"- Para {dp['paragraph']}: speaker={dp.get('speaker_hits', 0)} "
                                     f"setting={dp.get('setting_hits', 0)}")
                lines.append("")

            elif name == 'speech_sequencing':
                lines.append(f"- Ordinal marker density: {analysis.get('ordinal_density', 0)}")
                lines.append(f"- Response vocabulary density: {analysis.get('response_density', 0)}")
                lines.append(f"- Progression vocabulary density: {analysis.get('progression_density', 0)}")
                if analysis.get('sequential_passages'):
                    lines.append("### Sequential Structure Passages")
                    for sp in analysis['sequential_passages'][:5]:
                        lines.append(f"- Para {sp['paragraph']}: ordinal={sp.get('ordinal_hits', 0)} "
                                     f"response={sp.get('response_hits', 0)} progression={sp.get('progression_hits', 0)}")
                lines.append("")

            elif name == 'philosophical_comedy':
                lines.append(f"- Comic vocabulary density: {analysis.get('comic_density', 0)}")
                lines.append(f"- Serious vocabulary density: {analysis.get('serious_density', 0)}")
                lines.append(f"- Juxtaposition density: {analysis.get('juxtaposition_density', 0)}")
                if analysis.get('comic_philosophy_passages'):
                    lines.append("### Comic-Philosophy Passages")
                    for cp in analysis['comic_philosophy_passages'][:5]:
                        lines.append(f"- Para {cp['paragraph']}: comic={cp.get('comic_hits', 0)} "
                                     f"serious={cp.get('serious_hits', 0)}")
                lines.append("")

            elif name == 'daimonic_mediation':
                lines.append(f"- Mediation vocabulary density: {analysis.get('mediation_density', 0)}")
                lines.append(f"- Boundary vocabulary density: {analysis.get('boundary_density', 0)}")
                lines.append(f"- Transformation vocabulary density: {analysis.get('transformation_density', 0)}")
                if analysis.get('daimonic_passages'):
                    lines.append("### Daimonic/Intermediate Passages")
                    for dp in analysis['daimonic_passages'][:5]:
                        lines.append(f"- Para {dp['paragraph']}: mediation={dp.get('mediation_hits', 0)} "
                                     f"boundary={dp.get('boundary_hits', 0)} transform={dp.get('transformation_hits', 0)}")
                lines.append("")

            elif name == 'medicinal_rhetoric':
                lines.append(f"- Medical vocabulary density: {analysis.get('medical_density', 0)}")
                lines.append(f"- Pedagogical vocabulary density: {analysis.get('pedagogical_density', 0)}")
                lines.append(f"- Soul vocabulary density: {analysis.get('soul_vocabulary_density', 0)}")
                if analysis.get('medicinal_rhetoric_passages'):
                    lines.append("### Medicinal Rhetoric Passages")
                    for mp in analysis['medicinal_rhetoric_passages'][:5]:
                        lines.append(f"- Para {mp['paragraph']}: medical={mp.get('medical_hits', 0)} "
                                     f"pedagogical={mp.get('pedagogical_hits', 0)} soul={mp.get('soul_hits', 0)}")
                lines.append("")

            elif name == 'poetry_philosophy':
                lines.append(f"- Poetry vocabulary density: {analysis.get('poetry_density', 0)}")
                lines.append(f"- Philosophy vocabulary density: {analysis.get('philosophy_density', 0)}")
                lines.append(f"- Quarrel/tension density: {analysis.get('quarrel_density', 0)}")
                if analysis.get('dialectic_passages'):
                    lines.append("### Poetry-Philosophy Dialectic Passages")
                    for dp in analysis['dialectic_passages'][:5]:
                        lines.append(f"- Para {dp['paragraph']}: poetry={dp.get('poetry_hits', 0)} "
                                     f"philosophy={dp.get('philosophy_hits', 0)}")
                lines.append("")

            elif name == 'aspiration_gap':
                lines.append(f"- Aspiration vocabulary density: {analysis.get('aspiration_density', 0)}")
                lines.append(f"- Achievement vocabulary density: {analysis.get('achievement_density', 0)}")
                lines.append(f"- Gap/tension vocabulary density: {analysis.get('gap_density', 0)}")
                lines.append(f"- Unresolved aspiration ratio: {analysis.get('unresolved_aspiration_ratio', 0)}")
                if analysis.get('aspiration_passages'):
                    lines.append("### Unresolved Aspiration Passages")
                    for ap in analysis['aspiration_passages'][:5]:
                        lines.append(f"- Para {ap['paragraph']}: aspiration={ap.get('aspiration_hits', 0)} "
                                     f"gap={ap.get('gap_hits', 0)}")
                lines.append("")

            elif name == 'synoptic_requirement':
                lines.append(f"- Cross-reference density: {analysis.get('cross_reference_density', 0)}")
                lines.append(f"- Intertextual density: {analysis.get('intertextual_density', 0)}")
                lines.append(f"- Incompleteness marker density: {analysis.get('incompleteness_density', 0)}")
                if analysis.get('synoptic_passages'):
                    lines.append("### Cross-Reference / Synoptic Passages")
                    for sp in analysis['synoptic_passages'][:5]:
                        lines.append(f"- Para {sp['paragraph']}: cross_ref={sp.get('cross_reference_hits', 0)} "
                                     f"intertextual={sp.get('intertextual_hits', 0)} incomplete={sp.get('incompleteness_hits', 0)}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Esoteric vs Exoteric comparison
        comparison = self.compare_layers()
        lines.append("## Esoteric vs. Exoteric Layer Comparison")
        lines.append(f"- Esoteric (flagged) passages: {comparison['esoteric_layer']['passage_count']}")
        lines.append(f"- Exoteric (surface) passages: {comparison['exoteric_layer']['passage_count']}")
        lines.append(f"- Layer ratio: {comparison['layer_ratio']}")
        lines.append("")

        if comparison['esoteric_layer']['distinctive_vocabulary']:
            lines.append("### Vocabulary Distinctive to Esoteric Layer")
            lines.append(f"{', '.join(comparison['esoteric_layer']['distinctive_vocabulary'])}")
            lines.append("")

        if comparison['exoteric_layer']['distinctive_vocabulary']:
            lines.append("### Vocabulary Distinctive to Exoteric Layer")
            lines.append(f"{', '.join(comparison['exoteric_layer']['distinctive_vocabulary'])}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## LLM Analysis Prompt")
        lines.append("")
        lines.append("The following prompt has been generated for deep esoteric analysis ")
        lines.append("by a large language model. Copy the prompt and provide the text ")
        lines.append("to an LLM for Stage 2 interpretation.")
        lines.append("")
        lines.append("```")
        lines.append(self.generate_llm_prompt())
        lines.append("```")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return filepath


# ---------------------------------------------------------------------------
# STANDALONE GEMATRIA / ISOPSEPHY UTILITIES
# ---------------------------------------------------------------------------

def gematria(word: str) -> int:
    """Compute Hebrew gematria value of a word."""
    return sum(GEMATRIA_TABLE.get(c, 0) for c in word)

def isopsephy(word: str) -> int:
    """Compute Greek isopsephy value of a word."""
    return sum(ISOPSEPHY_TABLE.get(c, 0) for c in word.lower())

def latin_value(word: str) -> int:
    """Compute simple Latin A=1..Z=26 value of a word."""
    return sum(LATIN_TABLE.get(c, 0) for c in word.lower() if c.isalpha())

def find_gematria_matches(value: int, word_list: list[str], system: str = 'hebrew') -> list[str]:
    """Find all words in a list that match a given numerical value."""
    table = {'hebrew': GEMATRIA_TABLE, 'greek': ISOPSEPHY_TABLE, 'latin': LATIN_TABLE}
    calc = table.get(system, LATIN_TABLE)
    matches = []
    for word in word_list:
        val = sum(calc.get(c, 0) for c in word.lower())
        if val == value:
            matches.append(word)
    return matches

def check_significant(number: int) -> Optional[str]:
    """Check if a number has known symbolic significance."""
    return SIGNIFICANT_NUMBERS.get(number)


# ---------------------------------------------------------------------------
# DEMO / CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("ESOTERIC WRITING ANALYZER — Demonstration")
    print("=" * 70)
    print()

    # Demo with a sample text that exhibits several esoteric features
    demo_text = """
Chapter 1: On the Nature of Virtue

Virtue is the highest good. All wise men agree that virtue alone brings happiness.
The pious man is blessed above all others, for he walks in the light of divine truth.
It is noble and excellent to follow the path of tradition, which our ancestors have
consecrated through generations of faithful observance. Let no one question what has
been established by the wisdom of the ages.

Perhaps, however, one might note that the virtuous man does not always prosper.
Indeed, the wicked often flourish while the just suffer. But this apparent injustice
is not truly injustice, for the rewards of virtue are invisible to mortal eyes.

Chapter 2: On the Soul

The soul is immortal. This is the teaching of all the great philosophers, and no
reasonable person would deny it. The divine origin of the soul guarantees its eternal
persistence beyond the death of the body. We must accept this truth with reverence
and humility.

Yet it must be admitted that the arguments for the soul's immortality are not all
of equal strength. Some depend on premises that not every philosopher would grant.
The careful student will notice that certain demonstrations prove less than they
appear to prove, and that the question is perhaps more complex than it first seems.

Chapter 3: On Political Order

The best political order is that which is ruled by the wisest. This has been
the teaching from the most ancient times. The philosopher, having knowledge of
the good, is best suited to govern. Yet no philosopher has ever successfully
governed a city, and the attempt to make philosophy rule has always ended in
tyranny or ridicule.

The practical man knows what the theorist cannot see: that political order
depends not on truth but on opinion, not on wisdom but on consent. The city
does not need philosophers; it needs citizens who believe in the city's gods
and obey its laws. Whether those gods exist is a question the statesman must
never raise in public.

Chapter 4: On the Uses of Concealment

There are truths that benefit all who hear them, and truths that harm those
who are not prepared. The wise teacher does not give the same lesson to every
student. What is medicine for the strong may be poison for the weak.

The ancients understood this well. They spoke in riddles and parables, not
because they lacked clarity, but because clarity itself can be dangerous.
A truth stated plainly to those who cannot bear it produces not enlightenment
but rage. Therefore the wise have always written so as to be understood by
some and not by others.

This practice — of saying one thing while meaning another, or of saying the
same thing in different ways to different audiences — is not dishonesty. It is
the highest form of responsibility. The teacher who destroys his student's
necessary beliefs in the name of truth has taught nothing but destruction.
"""

    analyzer = EsotericAnalyzer()
    analyzer.load_text_string(demo_text, title="On Virtue, Soul, and Political Order")
    analyzer.set_expected_topics([
        "god", "prayer", "afterlife", "creation", "scripture",
        "revelation", "prophecy", "miracles", "sin", "redemption",
    ])

    # Run full analysis
    results = analyzer.full_analysis()

    # Export report
    report_path = "/sessions/sweet-youthful-wright/mnt/scriptorium/demo_analysis_report.md"
    analyzer.export_report(report_path)

    # Print summary
    print(f"Title: {results['title']}")
    print(f"Composite Esoteric Score: {results['composite_esoteric_score']}")
    print(f"Interpretation: {results['score_interpretation']}")
    print()
    print("Individual Method Scores:")
    for name, analysis in results['analyses'].items():
        print(f"  {analysis.get('method', name):45s} → {analysis.get('score', 0)}")
    print()

    # Layer comparison
    comparison = analyzer.compare_layers()
    print(f"Esoteric layer passages: {comparison['esoteric_layer']['passage_count']}")
    print(f"Exoteric layer passages: {comparison['exoteric_layer']['passage_count']}")
    print(f"Layer ratio: {comparison['layer_ratio']}")
    print()

    # Generate LLM prompt
    llm_prompt = analyzer.generate_llm_prompt()
    prompt_path = "/sessions/sweet-youthful-wright/mnt/scriptorium/llm_esoteric_prompt.md"
    with open(prompt_path, 'w') as f:
        f.write("# LLM Prompt for Deep Esoteric Analysis\n\n")
        f.write("Use this prompt with any capable LLM (Claude, GPT-4, etc.) along with the text to be analyzed.\n\n")
        f.write("---\n\n")
        f.write(llm_prompt)

    print(f"Report exported to: {report_path}")
    print(f"LLM prompt exported to: {prompt_path}")
    print()
    print("=" * 70)
    print("To analyze your own text:")
    print("  from esoteric_analyzer import EsotericAnalyzer")
    print('  analyzer = EsotericAnalyzer()')
    print('  analyzer.load_text("your_text.txt")')
    print('  analyzer.set_expected_topics(["topic1", "topic2", ...])')
    print('  results = analyzer.full_analysis()')
    print('  analyzer.export_report("report.md")')
    print('  prompt = analyzer.generate_llm_prompt()')
    print("=" * 70)
