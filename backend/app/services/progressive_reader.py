"""Progressive Sequential Reader — reads a book chapter-by-chapter like a human.

Instead of static whole-text analysis, this builds understanding progressively:
- Tracks claims, expectations, and contradictions as they develop
- Detects the moment of periagoge (the turning) as it happens
- Builds a running knowledge base that accumulates through the reading
- Produces a reading journal recording how understanding evolves

Inspired by Benardete's "argument of the action" — the meaning emerges
through the sequence, not from a static overview.
"""

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Claim:
    """A claim or assertion detected in the text."""
    text: str
    chapter: int
    position: float  # 0.0 to 1.0 through the book
    key_terms: set = field(default_factory=set)
    is_hedged: bool = False
    is_emphatic: bool = False


@dataclass
class Expectation:
    """An expectation set up by the text — a topic or question raised but not yet addressed."""
    topic: str
    raised_at_chapter: int
    fulfilled_at_chapter: Optional[int] = None
    is_silence: bool = False  # True if never fulfilled


@dataclass
class ChapterSnapshot:
    """Computational analysis of a single chapter in context of what came before."""
    chapter_num: int
    chapter_title: str
    text_length: int

    # Per-chapter metrics
    hedging_density: float = 0.0
    certainty_density: float = 0.0
    praise_density: float = 0.0
    negation_density: float = 0.0
    question_density: float = 0.0
    lexical_density: float = 0.0

    # Progressive detection
    new_claims: list = field(default_factory=list)
    contradictions_found: list = field(default_factory=list)
    expectations_raised: list = field(default_factory=list)
    expectations_fulfilled: list = field(default_factory=list)
    voice_shift_from_previous: float = 0.0
    register_tier: str = ""  # rhetorical/dialectical/demonstrative
    logos_or_mythos: str = ""

    # Cumulative scores at this point
    cumulative_contradiction_count: int = 0
    cumulative_hedging_trend: str = ""  # "increasing", "stable", "decreasing"
    periagoge_signal: float = 0.0  # How much this chapter reverses prior trajectory

    # Key terms introduced for the first time
    new_vocabulary: list = field(default_factory=list)
    # Key terms that disappear after being prominent
    disappeared_terms: list = field(default_factory=list)


# Word sets for detection
_HEDGE = {'perhaps', 'maybe', 'possibly', 'seemingly', 'apparently', 'might', 'could',
           'seems', 'appears', 'arguably', 'one might', 'it may be'}
_CERTAINTY = {'certainly', 'surely', 'undoubtedly', 'clearly', 'obviously', 'must',
              'always', 'never', 'proven', 'established', 'beyond doubt', 'necessarily'}
_PRAISE = {'excellent', 'noble', 'divine', 'sacred', 'virtuous', 'glorious',
           'admirable', 'wise', 'great', 'perfect', 'beautiful', 'just'}
_NEGATION = {'not', 'no', 'never', 'neither', 'nor', 'nothing', 'cannot',
             'deny', 'denies', 'false', 'impossible', 'wrong'}
_LOGOS = {'therefore', 'thus', 'hence', 'consequently', 'follows', 'proof',
          'necessarily', 'logically', 'demonstrably', 'reason', 'argument'}
_MYTHOS = {'story', 'tale', 'myth', 'legend', 'oracle', 'prophecy', 'dream',
           'vision', 'gods', 'hero', 'divine', 'sacred', 'ancient'}
_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
    'with', 'by', 'from', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
    'this', 'that', 'these', 'those', 'it', 'its', 'he', 'she', 'they', 'we',
    'you', 'not', 'no', 'if', 'then', 'than', 'as', 'so',
}


def _words(text: str) -> list[str]:
    return re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())


def _content_words(text: str) -> set[str]:
    return set(w for w in _words(text) if w not in _STOPWORDS)


def _density(text_words: list[str], target_set: set[str]) -> float:
    if not text_words:
        return 0.0
    return sum(1 for w in text_words if w in target_set) / len(text_words)


def split_into_chapters(text: str) -> list[tuple[str, str]]:
    """Split text into (title, body) pairs for progressive reading.

    Strategy: use markdown H1 headings as chapter markers.
    If that produces too many tiny chapters (junk headings from PDF),
    fall back to splitting into ~equal sections by paragraph count.
    """
    # Try markdown heading split first
    parts = re.split(r'^(#\s+.+)$', text, flags=re.MULTILINE)

    if len(parts) > 2:
        chapters = []
        i = 0
        if parts[0].strip() and len(parts[0].strip()) > 200:
            chapters.append(("Introduction", parts[0].strip()))
            i = 1
        while i < len(parts) - 1:
            title = parts[i].strip().lstrip('#').strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if body and len(body) > 200:  # Only valid if body has substance
                chapters.append((title[:80], body))
            elif chapters and body:
                # Merge short chapter into previous
                prev_title, prev_body = chapters[-1]
                chapters[-1] = (prev_title, prev_body + "\n\n" + body)
            i += 2

        # Check quality: if we got good chapters, use them
        if chapters and all(len(b) > 500 for _, b in chapters):
            return chapters

    # Fallback: split into ~equal sections by double-newline paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 30]

    if not paragraphs:
        return [("Full Text", text)]

    # Target ~10 sections, each at least 1000 chars
    target_sections = min(max(len(paragraphs) // 20, 5), 20)
    chunk_size = max(len(paragraphs) // target_sections, 3)

    chapters = []
    for i in range(0, len(paragraphs), chunk_size):
        chunk_paras = paragraphs[i:i + chunk_size]
        body = '\n\n'.join(chunk_paras)
        # Use first significant sentence as title
        first_sent = re.split(r'[.!?]', chunk_paras[0])[0].strip()
        title = first_sent[:60] + "..." if len(first_sent) > 60 else first_sent
        section_num = len(chapters) + 1
        chapters.append((f"Section {section_num}: {title}", body))

    return chapters


class ProgressiveReader:
    """Reads a book chapter-by-chapter, building progressive understanding."""

    def __init__(self):
        self.snapshots: list[ChapterSnapshot] = []
        self.all_claims: list[Claim] = []
        self.expectations: list[Expectation] = []
        self.global_term_freq: Counter = Counter()
        self.chapter_term_freqs: list[Counter] = []
        self.hedging_history: list[float] = []
        self.polarity_history: list[float] = []  # positive - negative ratio
        self.cumulative_vocab: set[str] = set()

    def read(self, text: str) -> dict:
        """Perform a full progressive reading of the text.

        Returns a reading journal with per-chapter snapshots and a synthesis.
        """
        chapters = split_into_chapters(text)
        total_chapters = len(chapters)

        for i, (title, body) in enumerate(chapters):
            if not body or len(body.strip()) < 50:
                continue
            snapshot = self._read_chapter(i, title, body, total_chapters)
            self.snapshots.append(snapshot)

        # Post-reading analysis
        journal = self._synthesize()
        return journal

    def _read_chapter(self, chapter_num: int, title: str, body: str,
                      total_chapters: int) -> ChapterSnapshot:
        """Analyze one chapter in context of everything read so far."""
        words = _words(body)
        content = _content_words(body)
        position = chapter_num / max(total_chapters, 1)

        # Basic metrics
        hedge_d = _density(words, _HEDGE)
        cert_d = _density(words, _CERTAINTY)
        praise_d = _density(words, _PRAISE)
        neg_d = _density(words, _NEGATION)
        q_d = body.count('?') / max(len(re.split(r'[.!?]+', body)), 1)
        lex_d = len(set(words)) / max(len(words), 1)

        # Track term frequencies
        ch_freq = Counter(w for w in words if w not in _STOPWORDS)
        self.chapter_term_freqs.append(ch_freq)
        self.global_term_freq.update(ch_freq)

        # New vocabulary — words appearing for the first time
        new_vocab = list(content - self.cumulative_vocab)[:20]
        self.cumulative_vocab.update(content)

        # Disappeared terms — prominent in previous chapters, absent here
        disappeared = []
        if len(self.chapter_term_freqs) >= 3:
            prev_common = set()
            for prev_freq in self.chapter_term_freqs[-3:-1]:
                prev_common.update(w for w, c in prev_freq.most_common(30))
            absent_now = prev_common - set(ch_freq.keys()) - _STOPWORDS
            disappeared = list(absent_now)[:10]

        # Detect claims (sentences with assertion markers)
        sents = re.split(r'[.!?]+', body)
        sents = [s.strip() for s in sents if len(s.strip()) > 20]
        new_claims = []
        for sent in sents:
            s_words = set(_words(sent))
            is_hedged = bool(s_words & _HEDGE)
            is_emphatic = bool(s_words & _CERTAINTY)
            if is_emphatic or (len(s_words & _content_words(sent)) > 5):
                claim = Claim(
                    text=sent[:150],
                    chapter=chapter_num,
                    position=position,
                    key_terms=s_words - _STOPWORDS,
                    is_hedged=is_hedged,
                    is_emphatic=is_emphatic,
                )
                new_claims.append(claim)

        # Detect contradictions with PREVIOUS claims
        contradictions = []
        for new_claim in new_claims:
            for old_claim in self.all_claims:
                # Same topic (shared key terms)
                shared = new_claim.key_terms & old_claim.key_terms
                if len(shared) < 3:
                    continue
                # Opposite polarity (one negated, other not)
                new_neg = bool(set(_words(new_claim.text)) & _NEGATION)
                old_neg = bool(set(_words(old_claim.text)) & _NEGATION)
                if new_neg != old_neg:
                    contradictions.append({
                        "old_chapter": old_claim.chapter,
                        "old_text": old_claim.text[:100],
                        "new_text": new_claim.text[:100],
                        "shared_terms": list(shared)[:5],
                        "distance_chapters": chapter_num - old_claim.chapter,
                    })

        self.all_claims.extend(new_claims[:20])  # Keep manageable

        # Voice shift from previous chapter
        voice_shift = 0.0
        if self.snapshots:
            prev = self.snapshots[-1]
            voice_shift = (
                abs(hedge_d - prev.hedging_density) +
                abs(cert_d - prev.certainty_density) +
                abs(q_d - prev.question_density) +
                abs(lex_d - prev.lexical_density)
            )

        # Register tier
        logos_score = _density(words, _LOGOS)
        mythos_score = _density(words, _MYTHOS)
        if logos_score > mythos_score * 1.5:
            register = "demonstrative"
            lm = "logos"
        elif mythos_score > logos_score * 1.5:
            register = "rhetorical"
            lm = "mythos"
        else:
            register = "dialectical"
            lm = "mixed"

        # Hedging trend
        self.hedging_history.append(hedge_d)
        if len(self.hedging_history) >= 3:
            recent = self.hedging_history[-3:]
            if recent[-1] > recent[0] * 1.3:
                hedge_trend = "increasing"
            elif recent[-1] < recent[0] * 0.7:
                hedge_trend = "decreasing"
            else:
                hedge_trend = "stable"
        else:
            hedge_trend = "insufficient data"

        # Periagoge signal — how much does this chapter reverse the prior trajectory?
        pos_words = {'good', 'true', 'noble', 'just', 'wise', 'beautiful', 'right', 'virtue'}
        neg_words = {'bad', 'false', 'base', 'unjust', 'foolish', 'ugly', 'wrong', 'vice'}
        pos = _density(words, pos_words)
        neg = _density(words, neg_words)
        polarity = pos - neg
        self.polarity_history.append(polarity)

        periagoge = 0.0
        if len(self.polarity_history) >= 3:
            prev_avg = sum(self.polarity_history[:-1]) / len(self.polarity_history[:-1])
            if prev_avg != 0:
                periagoge = abs(polarity - prev_avg) / max(abs(prev_avg), 0.001)

        snapshot = ChapterSnapshot(
            chapter_num=chapter_num,
            chapter_title=title,
            text_length=len(body),
            hedging_density=round(hedge_d, 5),
            certainty_density=round(cert_d, 5),
            praise_density=round(praise_d, 5),
            negation_density=round(neg_d, 5),
            question_density=round(q_d, 4),
            lexical_density=round(lex_d, 4),
            new_claims=[{"text": c.text, "hedged": c.is_hedged, "emphatic": c.is_emphatic}
                        for c in new_claims[:5]],
            contradictions_found=contradictions[:5],
            voice_shift_from_previous=round(voice_shift, 4),
            register_tier=register,
            logos_or_mythos=lm,
            cumulative_contradiction_count=sum(len(s.contradictions_found) for s in self.snapshots) + len(contradictions),
            cumulative_hedging_trend=hedge_trend,
            periagoge_signal=round(periagoge, 4),
            new_vocabulary=new_vocab[:10],
            disappeared_terms=disappeared[:10],
        )

        return snapshot

    def _synthesize(self) -> dict:
        """Produce the final reading journal from all snapshots."""
        if not self.snapshots:
            return {"error": "No chapters to analyze"}

        # Find the turning point (maximum periagoge signal)
        turning_point = max(self.snapshots, key=lambda s: s.periagoge_signal)

        # Find voice shifts
        major_shifts = sorted(self.snapshots, key=lambda s: s.voice_shift_from_previous, reverse=True)[:5]

        # Track hedging trajectory
        hedging_arc = [(s.chapter_num, s.hedging_density) for s in self.snapshots]

        # Total contradictions
        all_contradictions = []
        for s in self.snapshots:
            for c in s.contradictions_found:
                all_contradictions.append({**c, "detected_at_chapter": s.chapter_num})

        # Polarity arc
        polarity_arc = [(s.chapter_num, self.polarity_history[i] if i < len(self.polarity_history) else 0)
                        for i, s in enumerate(self.snapshots)]

        # Register shifts
        register_sequence = [(s.chapter_num, s.register_tier) for s in self.snapshots]
        register_shifts = []
        for i in range(1, len(register_sequence)):
            if register_sequence[i][1] != register_sequence[i-1][1]:
                register_shifts.append({
                    "at_chapter": register_sequence[i][0],
                    "from": register_sequence[i-1][1],
                    "to": register_sequence[i][1],
                })

        # Expectations that were never fulfilled (loud silences)
        # Terms that appeared prominently early then vanished
        early_terms = set()
        late_terms = set()
        mid = len(self.chapter_term_freqs) // 2
        for freq in self.chapter_term_freqs[:max(mid, 1)]:
            early_terms.update(w for w, c in freq.most_common(20))
        for freq in self.chapter_term_freqs[max(mid, 1):]:
            late_terms.update(w for w, c in freq.most_common(20))

        abandoned_topics = list((early_terms - late_terms) - _STOPWORDS)[:15]
        introduced_late = list((late_terms - early_terms) - _STOPWORDS)[:15]

        return {
            "total_chapters_read": len(self.snapshots),
            "total_claims_tracked": len(self.all_claims),
            "total_contradictions": len(all_contradictions),

            "turning_point": {
                "chapter": turning_point.chapter_num,
                "title": turning_point.chapter_title,
                "periagoge_signal": turning_point.periagoge_signal,
                "interpretation": "Maximum polarity reversal — the philosophical 'turning' (periagoge)",
            },

            "major_voice_shifts": [
                {"chapter": s.chapter_num, "title": s.chapter_title,
                 "shift": s.voice_shift_from_previous}
                for s in major_shifts if s.voice_shift_from_previous > 0.01
            ],

            "contradictions": all_contradictions[:20],

            "hedging_arc": hedging_arc,
            "polarity_arc": polarity_arc,
            "register_shifts": register_shifts,

            "abandoned_topics": abandoned_topics,
            "introduced_late": introduced_late,

            "chapter_snapshots": [
                {
                    "chapter": s.chapter_num,
                    "title": s.chapter_title,
                    "hedging": s.hedging_density,
                    "certainty": s.certainty_density,
                    "periagoge": s.periagoge_signal,
                    "voice_shift": s.voice_shift_from_previous,
                    "register": s.register_tier,
                    "contradictions_found": len(s.contradictions_found),
                    "new_vocabulary": s.new_vocabulary[:5],
                }
                for s in self.snapshots
            ],
        }


def run_progressive_reading(text: str) -> dict:
    """Run a progressive sequential reading of the text.

    Returns a reading journal with per-chapter analysis and synthesis.
    """
    reader = ProgressiveReader()
    return reader.read(text)
