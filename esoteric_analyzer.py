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
        ]

        scores = []
        for name, fn in analyses:
            result = fn()
            self.results['analyses'][name] = result
            scores.append(result.get('score', 0))

        # Composite esoteric probability (weighted)
        # Weights sum to 1.0; original 9 methods slightly reduced to accommodate new 8
        weights = {
            'contradiction': 0.14,
            'central_placement': 0.10,
            'numerology': 0.06,
            'silence': 0.07,
            'repetition': 0.07,
            'symmetry': 0.06,
            'irony': 0.07,
            'digression': 0.05,
            'lexical_density': 0.04,
            'acrostic': 0.05,
            'hapax_legomena': 0.04,
            'voice_consistency': 0.06,
            'register': 0.05,
            'logos_mythos': 0.05,
            'commentary_divergence': 0.03,
            'polysemy': 0.03,
            'aphoristic_fragmentation': 0.03,
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

## STAGE 14: THE ESOTERIC ARGUMENT
Based on ALL of the above (Stages 1-13), attempt to reconstruct the text's
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
   concealment)
4. **The evidence** (the specific textual passages that support this reading)
5. **The motive** (why did the author conceal? Which of Melzer's four types applies:
   defensive, protective, pedagogical, or political esotericism?)
6. **Confidence level** (how strong is the case? What alternative readings exist?)

## STAGE 15: SAFEGUARDS AGAINST OVER-READING
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
