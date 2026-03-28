"""Computational esoteric analysis engine.

Four tools for detecting patterns in texts that may indicate
esoteric writing, based on the methodology described by Arthur Melzer
in 'Philosophy Between the Lines'.

These are computational aids, not decoders — they highlight anomalies
and patterns for human interpretation.
"""

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
# Shared tokenization cache — avoids re-splitting text
# 91 times (once per tool)
# ─────────────────────────────────────────────────────

_text_cache: dict = {}


def _get_shared(text: str, delimiter_pattern: str = None) -> dict:
    """Get pre-computed text data. Computed once, reused by all tools."""
    key = id(text)
    if key not in _text_cache:
        dp = delimiter_pattern or r"\n\s*\n"
        sections = re.split(dp, text)
        sections = [s.strip() for s in sections if s.strip()]
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        _text_cache[key] = {
            'sections': sections,
            'words': words,
            'word_freq': Counter(words),
            'sentences': [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 10],
            'content_words': set(w for w in words if w not in _STOPWORDS),
        }
    return _text_cache[key]


def _clear_cache():
    """Clear the shared tokenization cache."""
    _text_cache.clear()


# ─────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────

@dataclass
class SectionText:
    """A labeled section of text (book, chapter, canto, etc.)."""
    label: str
    text: str
    index: int = 0


@dataclass
class LoudSilenceResult:
    """Result from the Loud Silence Detector."""
    keyword_frequencies: dict[str, dict[str, int]]  # {keyword: {section_label: count}}
    silences: list[dict]  # [{keyword, section, expected_avg, actual}]
    heatmap_data: list[dict]  # For frontend chart rendering

    def to_dict(self) -> dict:
        return {
            "type": "loud_silence",
            "keyword_frequencies": self.keyword_frequencies,
            "silences": self.silences,
            "heatmap_data": self.heatmap_data,
        }


@dataclass
class ContradictionResult:
    """Result from the Contradiction Hunter."""
    entity_sentiments: dict[str, list[dict]]  # {entity: [{section, context, sentiment_score, text}]}
    dissonances: list[dict]  # [{entity, positive_sections, negative_sections, delta}]

    def to_dict(self) -> dict:
        return {
            "type": "contradiction_hunter",
            "entity_sentiments": self.entity_sentiments,
            "dissonances": self.dissonances,
        }


@dataclass
class CenterResult:
    """Result from the Center Locator."""
    total_words: int
    total_lines: int
    center_passage: str
    center_line_start: int
    center_line_end: int
    section_centers: list[dict]  # [{section_label, center_text, center_line}]

    def to_dict(self) -> dict:
        return {
            "type": "center_locator",
            "total_words": self.total_words,
            "total_lines": self.total_lines,
            "center_passage": self.center_passage,
            "center_line_range": [self.center_line_start, self.center_line_end],
            "section_centers": self.section_centers,
        }


@dataclass
class ExotericEsotericResult:
    """Result from the Exoteric/Esoteric ratio analysis."""
    section_ratios: list[dict]  # [{section_label, pious_count, subversive_count, ratio}]
    overall_pious: int
    overall_subversive: int
    flagged_sections: list[dict]  # Sections with unusual ratios

    def to_dict(self) -> dict:
        return {
            "type": "exoteric_esoteric_ratio",
            "section_ratios": self.section_ratios,
            "overall_pious": self.overall_pious,
            "overall_subversive": self.overall_subversive,
            "flagged_sections": self.flagged_sections,
        }


# ─────────────────────────────────────────────────────
# Text segmentation
# ─────────────────────────────────────────────────────

def segment_text(text: str, delimiter_pattern: Optional[str] = None) -> list[SectionText]:
    """Split a text into sections (books, chapters, cantos, etc.).

    Auto-detects common structural markers if no delimiter is provided.
    Uses markdown heading detection as a fallback (from epub2md pipeline).
    """
    if delimiter_pattern:
        pattern = delimiter_pattern
    else:
        # Try common delimiters in order of specificity
        patterns = [
            r'(?i)^(book\s+[IVXLCDM\d]+\b[^\n]*)',    # Book I, Book 1, BOOK ONE, Book I: Title
            r'(?i)^(chapter\s+[IVXLCDM\d]+\b[^\n]*)',  # Chapter 1, Chapter One: Title
            r'(?i)^(canto\s+[IVXLCDM\d]+\b[^\n]*)',    # Canto I
            r'(?i)^(part\s+[IVXLCDM\d]+\b[^\n]*)',     # Part 1, Part One
            r'(?i)^(act\s+[IVXLCDM\d]+\b[^\n]*)',      # Act I (plays)
            r'(?i)^(section\s+[IVXLCDM\d]+\b[^\n]*)',  # Section 1
            r'^(#{1,3}\s+.+)',                           # Markdown headings (from epub2md output)
            r'(?i)^(discourse\s+[IVXLCDM\d]+\b[^\n]*)', # Discourse I (Machiavelli)
            r'(?i)^(letter\s+[IVXLCDM\d]+\b[^\n]*)',    # Letter I (epistles)
            r'(?i)^(dialogue\s+[IVXLCDM\d]+\b[^\n]*)',  # Dialogue I
        ]

        pattern = None
        for p in patterns:
            matches = re.findall(p, text, re.MULTILINE)
            if len(matches) >= 2:  # Need at least 2 sections to be useful
                pattern = p
                break

    if pattern:
        # Split by the detected pattern
        splits = re.split(f'({pattern})', text, flags=re.MULTILINE)
        sections = []
        idx = 0
        # Include preamble if substantial
        preamble = splits[0].strip() if splits else ""
        if preamble and len(preamble) > 200:
            sections.append(SectionText(label="Preamble", text=preamble, index=idx))
            idx += 1

        i = 1
        while i < len(splits) - 1:
            label = splits[i].strip().lstrip('#').strip()
            content = splits[i + 1] if i + 1 < len(splits) else ""
            if content.strip():
                sections.append(SectionText(label=label, text=content.strip(), index=idx))
                idx += 1
            i += 2
        return sections if sections else [SectionText(label="Full Text", text=text, index=0)]

    # Fallback: split by paragraph density into ~10 sections
    lines = text.split('\n')
    chunk_size = max(50, len(lines) // 10)
    sections = []
    for i in range(0, len(lines), chunk_size):
        chunk = '\n'.join(lines[i:i + chunk_size])
        if chunk.strip():
            sections.append(SectionText(
                label=f"Section {len(sections) + 1}",
                text=chunk,
                index=len(sections),
            ))
    return sections or [SectionText(label="Full Text", text=text, index=0)]


# ─────────────────────────────────────────────────────
# Tool 1: Loud Silence Detector
# ─────────────────────────────────────────────────────

def detect_loud_silences(
    text: str,
    keywords: list[str],
    delimiter_pattern: Optional[str] = None,
    silence_threshold: float = 0.2,
) -> LoudSilenceResult:
    """Detect where expected terms conspicuously disappear.

    A 'loud silence' is when a keyword that appears regularly throughout
    a work suddenly vanishes from a section — potentially signaling that
    the events in that section relate to the concept's absence.

    Args:
        text: The full text to analyze
        keywords: Terms to track (e.g., ["justice", "truth", "zeus", "piety"])
        delimiter_pattern: Regex for section boundaries (auto-detected if None)
        silence_threshold: A section counts as a 'silence' if its frequency
                          is below this fraction of the average frequency
    """
    sections = segment_text(text, delimiter_pattern)

    # Count keyword occurrences per section
    keyword_frequencies: dict[str, dict[str, int]] = {}
    for kw in keywords:
        keyword_frequencies[kw] = {}
        for section in sections:
            # Case-insensitive word boundary match
            count = len(re.findall(rf'\b{re.escape(kw)}\b', section.text, re.IGNORECASE))
            keyword_frequencies[kw][section.label] = count

    # Detect silences
    silences = []
    for kw in keywords:
        counts = list(keyword_frequencies[kw].values())
        if not counts or max(counts) == 0:
            continue
        avg = sum(counts) / len(counts)
        if avg == 0:
            continue

        for section in sections:
            actual = keyword_frequencies[kw][section.label]
            if actual < avg * silence_threshold and avg >= 1.0:
                silences.append({
                    "keyword": kw,
                    "section": section.label,
                    "expected_avg": round(avg, 2),
                    "actual": actual,
                    "severity": "loud" if actual == 0 and avg >= 2.0 else "notable",
                })

    # Build heatmap data for frontend
    heatmap_data = []
    for section in sections:
        row = {"section": section.label}
        for kw in keywords:
            row[kw] = keyword_frequencies[kw][section.label]
        heatmap_data.append(row)

    return LoudSilenceResult(
        keyword_frequencies=keyword_frequencies,
        silences=sorted(silences, key=lambda s: s["expected_avg"] - s["actual"], reverse=True),
        heatmap_data=heatmap_data,
    )


# ─────────────────────────────────────────────────────
# Tool 2: Contradiction Hunter (Entity Sentiment)
# ─────────────────────────────────────────────────────

# Simple sentiment lexicons (no dependency on spaCy/TextBlob by default)
POSITIVE_WORDS = {
    "noble", "wise", "just", "brave", "pious", "virtuous", "divine", "glorious",
    "honored", "faithful", "true", "good", "righteous", "blessed", "holy",
    "reverent", "worthy", "excellent", "magnificent", "gentle", "kind",
    "brilliant", "clever", "shrewd", "cunning", "resourceful", "great",
    "beloved", "fair", "radiant", "immortal", "sacred", "generous",
}

NEGATIVE_WORDS = {
    "wicked", "cruel", "deceitful", "treacherous", "impious", "cowardly",
    "foolish", "vile", "wrathful", "jealous", "petty", "false", "lying",
    "deceptive", "destructive", "ruthless", "savage", "pitiless", "hateful",
    "arrogant", "proud", "scheming", "manipulative", "vengeful", "bitter",
    "dark", "terrible", "dreadful", "cursed", "doomed", "shameful",
}


def hunt_contradictions(
    text: str,
    entities: list[str],
    delimiter_pattern: Optional[str] = None,
    context_window: int = 150,
) -> ContradictionResult:
    """Track sentiment toward specific entities across sections.

    Identifies where an entity (character, god, concept) is described
    positively in some contexts and negatively in others — a potential
    sign of ironic or esoteric treatment.

    Args:
        text: The full text
        entities: Names/terms to track (e.g., ["Athena", "Odysseus", "Zeus"])
        delimiter_pattern: Section boundary regex
        context_window: Characters of context around each mention
    """
    sections = segment_text(text, delimiter_pattern)

    entity_sentiments: dict[str, list[dict]] = {e: [] for e in entities}

    for entity in entities:
        for section in sections:
            # Find all mentions
            for match in re.finditer(rf'\b{re.escape(entity)}\b', section.text, re.IGNORECASE):
                start = max(0, match.start() - context_window)
                end = min(len(section.text), match.end() + context_window)
                context = section.text[start:end].strip()

                # Simple sentiment scoring
                words = set(re.findall(r'\w+', context.lower()))
                pos_count = len(words & POSITIVE_WORDS)
                neg_count = len(words & NEGATIVE_WORDS)

                if pos_count + neg_count == 0:
                    score = 0.0
                else:
                    score = (pos_count - neg_count) / (pos_count + neg_count)

                entity_sentiments[entity].append({
                    "section": section.label,
                    "context": context,
                    "sentiment_score": round(score, 3),
                    "positive_words": list(words & POSITIVE_WORDS),
                    "negative_words": list(words & NEGATIVE_WORDS),
                })

    # Detect dissonances — entities described both positively and negatively
    dissonances = []
    for entity, mentions in entity_sentiments.items():
        if len(mentions) < 2:
            continue

        positive = [m for m in mentions if m["sentiment_score"] > 0.3]
        negative = [m for m in mentions if m["sentiment_score"] < -0.3]

        if positive and negative:
            avg_pos = sum(m["sentiment_score"] for m in positive) / len(positive)
            avg_neg = sum(m["sentiment_score"] for m in negative) / len(negative)
            dissonances.append({
                "entity": entity,
                "positive_count": len(positive),
                "negative_count": len(negative),
                "total_mentions": len(mentions),
                "avg_positive_score": round(avg_pos, 3),
                "avg_negative_score": round(avg_neg, 3),
                "delta": round(avg_pos - avg_neg, 3),
                "positive_sections": list({m["section"] for m in positive}),
                "negative_sections": list({m["section"] for m in negative}),
            })

    return ContradictionResult(
        entity_sentiments=entity_sentiments,
        dissonances=sorted(dissonances, key=lambda d: d["delta"], reverse=True),
    )


# ─────────────────────────────────────────────────────
# Tool 3: Center Locator
# ─────────────────────────────────────────────────────

def locate_centers(
    text: str,
    delimiter_pattern: Optional[str] = None,
    center_window_lines: int = 25,
) -> CenterResult:
    """Find the physical center of the text and each section.

    Esoteric writers (from Plato to Machiavelli) often placed their most
    important truth at the exact structural center of a work, where casual
    readers who skim beginnings and endings would never look.

    Args:
        text: The full text
        delimiter_pattern: Section boundary regex
        center_window_lines: Lines to extract around the center point
    """
    lines = text.split('\n')
    total_lines = len(lines)
    total_words = len(text.split())

    # Global center
    mid = total_lines // 2
    half_window = center_window_lines // 2
    start = max(0, mid - half_window)
    end = min(total_lines, mid + half_window)
    center_passage = '\n'.join(lines[start:end])

    # Section centers
    sections = segment_text(text, delimiter_pattern)
    section_centers = []
    for section in sections:
        sec_lines = section.text.split('\n')
        if len(sec_lines) < 3:
            continue
        sec_mid = len(sec_lines) // 2
        sec_start = max(0, sec_mid - 5)
        sec_end = min(len(sec_lines), sec_mid + 5)
        section_centers.append({
            "section_label": section.label,
            "total_lines": len(sec_lines),
            "center_line": sec_mid,
            "center_text": '\n'.join(sec_lines[sec_start:sec_end]),
        })

    return CenterResult(
        total_words=total_words,
        total_lines=total_lines,
        center_passage=center_passage,
        center_line_start=start + 1,  # 1-indexed for display
        center_line_end=end,
        section_centers=section_centers,
    )


# ─────────────────────────────────────────────────────
# Tool 4: Exoteric/Esoteric Ratio Analyzer
# ─────────────────────────────────────────────────────

# Default word lists for surface piety vs. philosophical subversion
# Expanded from epub2md Xenophon/Nietzsche/Strauss analysis projects
DEFAULT_PIOUS_WORDS = {
    # Religious/divine
    "god", "gods", "divine", "sacred", "holy", "pious", "piety", "prayer",
    "sacrifice", "temple", "altar", "fate", "destiny", "heaven", "olympus",
    "blessed", "reverent", "worship", "offering", "providence", "miracle",
    "prophet", "revelation", "faith", "salvation", "soul", "spirit",
    # Authority/tradition
    "obey", "obedience", "duty", "righteous", "orthodox", "tradition",
    "custom", "law", "order", "authority", "king", "throne", "honor",
    "glory", "noble", "citizen", "patriot", "loyal", "allegiance",
    "ancestor", "elder", "master", "servant", "humble",
    # Moral convention
    "virtue", "moral", "good", "evil", "sin", "shame", "modesty",
    "temperance", "courage", "prudence", "just", "unjust",
    "gentleman", "decent", "proper", "fitting",
}

DEFAULT_SUBVERSIVE_WORDS = {
    # Deception/concealment
    "clever", "cunning", "trick", "deceive", "lie", "false", "disguise",
    "hidden", "secret", "conceal", "pretend", "mask", "veil", "cover",
    "stratagem", "device", "contrive", "artful", "shrewd",
    # Philosophy/inquiry
    "know", "knowledge", "wisdom", "question", "doubt", "examine",
    "reason", "think", "mind", "nature", "truth", "real", "actual",
    "inquiry", "investigate", "discover", "understand", "contemplate",
    "philosophy", "philosopher", "science", "theory", "hypothesis",
    # Freedom/power
    "challenge", "rebel", "defy", "escape", "freedom", "liberty",
    "self", "choose", "will", "power", "mortal", "human",
    "individual", "independent", "autonomous", "sovereign",
    # Appearance vs. reality
    "appear", "seem", "surface", "opinion", "reputation", "image",
    "illusion", "phantom", "shadow", "cave", "light", "darkness",
    # Craft/skill
    "craft", "skill", "art", "techne", "method", "practice", "experience",
}


def analyze_exoteric_esoteric_ratio(
    text: str,
    pious_words: Optional[set[str]] = None,
    subversive_words: Optional[set[str]] = None,
    delimiter_pattern: Optional[str] = None,
) -> ExotericEsotericResult:
    """Measure the ratio of 'pious/conventional' vs. 'philosophical/subversive' language.

    A section with unusually high pious density may be a "defensive" section
    hiding a dangerous truth. A section with high subversive density may
    contain the esoteric teaching more openly.

    Args:
        text: The full text
        pious_words: Words associated with surface orthodoxy
        subversive_words: Words associated with philosophical inquiry
        delimiter_pattern: Section boundary regex
    """
    pious = pious_words or DEFAULT_PIOUS_WORDS
    subversive = subversive_words or DEFAULT_SUBVERSIVE_WORDS
    sections = segment_text(text, delimiter_pattern)

    section_ratios = []
    total_pious = 0
    total_subversive = 0

    for section in sections:
        words = set(re.findall(r'\w+', section.text.lower()))
        all_words_list = re.findall(r'\w+', section.text.lower())

        p_count = sum(1 for w in all_words_list if w in pious)
        s_count = sum(1 for w in all_words_list if w in subversive)
        total = p_count + s_count

        total_pious += p_count
        total_subversive += s_count

        section_ratios.append({
            "section_label": section.label,
            "pious_count": p_count,
            "subversive_count": s_count,
            "total_tagged": total,
            "pious_ratio": round(p_count / total, 3) if total > 0 else 0,
            "subversive_ratio": round(s_count / total, 3) if total > 0 else 0,
            "dominant": "pious" if p_count > s_count else "subversive" if s_count > p_count else "neutral",
            "word_count": len(all_words_list),
            # Density per 1000 words
            "pious_density": round(p_count / len(all_words_list) * 1000, 2) if all_words_list else 0,
            "subversive_density": round(s_count / len(all_words_list) * 1000, 2) if all_words_list else 0,
        })

    # Flag sections with unusual ratios
    if section_ratios:
        avg_pious_density = sum(r["pious_density"] for r in section_ratios) / len(section_ratios)
        avg_subversive_density = sum(r["subversive_density"] for r in section_ratios) / len(section_ratios)

        flagged = []
        for r in section_ratios:
            reasons = []
            if avg_pious_density > 0 and r["pious_density"] > avg_pious_density * 1.8:
                reasons.append("Unusually high pious density — possible defensive rhetoric")
            if avg_subversive_density > 0 and r["subversive_density"] > avg_subversive_density * 1.8:
                reasons.append("Unusually high subversive density — possible esoteric teaching")
            if r["pious_density"] > 0 and r["subversive_density"] > 0:
                if r["pious_density"] > avg_pious_density * 1.5 and r["subversive_density"] > avg_subversive_density * 1.5:
                    reasons.append("Both densities elevated — possible tension between layers")
            if reasons:
                flagged.append({
                    "section_label": r["section_label"],
                    "reasons": reasons,
                    "pious_density": r["pious_density"],
                    "subversive_density": r["subversive_density"],
                })
    else:
        flagged = []

    return ExotericEsotericResult(
        section_ratios=section_ratios,
        overall_pious=total_pious,
        overall_subversive=total_subversive,
        flagged_sections=flagged,
    )


# ─────────────────────────────────────────────────────
# Tool 5: Repetition with Variation Detector
# ─────────────────────────────────────────────────────

@dataclass
class RepetitionResult:
    """Result from the Repetition with Variation Detector."""
    repeated_phrases: list[dict]  # [{phrase, occurrences: [{section, context, variation}]}]

    def to_dict(self) -> dict:
        return {
            "type": "repetition_variation",
            "repeated_phrases": self.repeated_phrases,
        }


def detect_repetition_with_variation(
    text: str,
    keywords: list[str],
    delimiter_pattern: Optional[str] = None,
    context_window: int = 120,
) -> RepetitionResult:
    """Detect phrases containing tracked keywords that repeat with subtle changes.

    Strauss observed that when an author repeats a formulation but changes
    a word or two, the variation is often the key to the esoteric meaning.
    This tool finds sentences containing tracked keywords and groups them
    to highlight variations across sections.

    Args:
        text: The full text
        keywords: Terms to track for repetition
        delimiter_pattern: Section boundary regex
        context_window: Characters of context around each occurrence
    """
    sections = segment_text(text, delimiter_pattern)
    keyword_set = {k.lower() for k in keywords}

    # Collect all sentences containing keywords, grouped by keyword
    keyword_contexts: dict[str, list[dict]] = defaultdict(list)

    for section in sections:
        sentences = re.split(r'(?<=[.!?])\s+', section.text)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            for kw in keyword_set:
                if kw in sentence_lower.split():
                    # Extract a normalized "shape" for comparison
                    # Remove the keyword to see what varies around it
                    keyword_contexts[kw].append({
                        "section": section.label,
                        "sentence": sentence.strip()[:context_window * 2],
                        "words": set(re.findall(r'\w+', sentence_lower)) - keyword_set,
                    })

    # Find keywords with multiple occurrences where context varies
    repeated = []
    for kw, contexts in keyword_contexts.items():
        if len(contexts) < 3:
            continue

        # Group by similarity — find pairs where most words overlap but some differ
        occurrences = []
        for ctx in contexts:
            occurrences.append({
                "section": ctx["section"],
                "context": ctx["sentence"],
            })

        # Calculate variation: which words appear in some but not all occurrences
        all_words = Counter()
        for ctx in contexts:
            all_words.update(ctx["words"])

        # Words that appear in some but not all — these are the "variations"
        total = len(contexts)
        varying_words = [w for w, count in all_words.items()
                        if 2 <= count < total and len(w) > 3]

        if varying_words:
            repeated.append({
                "keyword": kw,
                "occurrence_count": len(occurrences),
                "varying_words": varying_words[:10],
                "occurrences": occurrences[:8],  # Limit for UI
            })

    repeated.sort(key=lambda r: r["occurrence_count"], reverse=True)

    return RepetitionResult(repeated_phrases=repeated[:15])


# ─────────────────────────────────────────────────────
# Tool 6: Audience Differentiation Detector
# ─────────────────────────────────────────────────────

# Markers indicating the author addresses different audiences
# Based on Melzer's "few vs. many" distinction (Ch. 4, pp. 116-118)
ELITE_MARKERS = {
    "the wise", "the few", "those who understand", "the careful reader",
    "the attentive", "the philosophic", "the learned", "men of understanding",
    "those who know", "the discerning", "for few readers", "the initiated",
    "the intelligent", "gentle reader", "the serious reader",
}

MASS_MARKERS = {
    "the many", "the multitude", "the vulgar", "the common", "the people",
    "the masses", "the populace", "the mob", "the herd", "the crowd",
    "the ignorant", "most readers", "the public", "ordinary men",
    "common opinion", "the unlearned",
}


@dataclass
class AudienceResult:
    """Result from the Audience Differentiation Detector."""
    elite_references: list[dict]    # [{marker, section, context}]
    mass_references: list[dict]     # [{marker, section, context}]
    differentiation_score: float    # 0-1 how strongly the text differentiates audiences

    def to_dict(self) -> dict:
        return {
            "type": "audience_differentiation",
            "elite_references": self.elite_references,
            "mass_references": self.mass_references,
            "differentiation_score": self.differentiation_score,
            "elite_count": len(self.elite_references),
            "mass_count": len(self.mass_references),
        }


def detect_audience_differentiation(
    text: str,
    delimiter_pattern: Optional[str] = None,
    context_window: int = 150,
) -> AudienceResult:
    """Detect markers of audience differentiation — the 'few vs. many' distinction.

    Esoteric writers frequently signal that they address different audiences:
    'the wise' or 'the few' vs. 'the many' or 'the vulgar.' The presence of
    such markers is a strong indicator of esoteric intent.

    Args:
        text: The full text
        delimiter_pattern: Section boundary regex
        context_window: Characters of context around each marker
    """
    sections = segment_text(text, delimiter_pattern)
    text_lower = text.lower()

    elite_refs = []
    mass_refs = []

    for section in sections:
        section_lower = section.text.lower()
        for marker in ELITE_MARKERS:
            pos = 0
            while True:
                idx = section_lower.find(marker, pos)
                if idx == -1:
                    break
                start = max(0, idx - context_window)
                end = min(len(section.text), idx + len(marker) + context_window)
                elite_refs.append({
                    "marker": marker,
                    "section": section.label,
                    "context": section.text[start:end].strip(),
                })
                pos = idx + len(marker)

        for marker in MASS_MARKERS:
            pos = 0
            while True:
                idx = section_lower.find(marker, pos)
                if idx == -1:
                    break
                start = max(0, idx - context_window)
                end = min(len(section.text), idx + len(marker) + context_window)
                mass_refs.append({
                    "marker": marker,
                    "section": section.label,
                    "context": section.text[start:end].strip(),
                })
                pos = idx + len(marker)

    # Score: higher when both elite and mass markers are present (differentiation)
    total = len(elite_refs) + len(mass_refs)
    if total == 0:
        score = 0.0
    elif len(elite_refs) == 0 or len(mass_refs) == 0:
        score = 0.2  # One-sided — weak differentiation
    else:
        # Balance: strongest when both sides are represented
        balance = min(len(elite_refs), len(mass_refs)) / max(len(elite_refs), len(mass_refs))
        density = min(total / 20, 1.0)  # Normalize by ~20 references
        score = round(balance * 0.6 + density * 0.4, 3)

    return AudienceResult(
        elite_references=elite_refs[:20],
        mass_references=mass_refs[:20],
        differentiation_score=score,
    )


# ─────────────────────────────────────────────────────
# Tool 7: Hedging Language Detector ("Mere Possibility")
# ─────────────────────────────────────────────────────

# Phrases that signal an author is stating something as "merely possible"
# rather than asserting it — a key technique per Strauss's reading of Lessing
HEDGING_PHRASES = [
    "perhaps", "it seems", "it would seem", "it might seem", "it appears",
    "it may be", "it could be", "one might say", "one could say",
    "it is possible", "it is not impossible", "a mere possibility",
    "we may suppose", "we might imagine", "some would say", "some might think",
    "if one were to", "were one to suppose", "granting that", "supposing that",
    "not to say", "so to speak", "as it were", "in a manner of speaking",
    "I do not mean to say", "I would not go so far", "I hesitate to",
    "it is tempting to think", "one is tempted to", "at first glance",
    "on the surface", "to the casual observer", "the reader might suppose",
    "the attentive reader", "if I may say so", "if I am not mistaken",
    "unless I am mistaken", "I leave it to the reader",
]


@dataclass
class HedgingResult:
    """Result from the Hedging Language Detector."""
    hedges: list[dict]  # [{phrase, section, context, sentence}]
    hedge_density: float  # hedges per 1000 words
    sections_by_density: list[dict]  # [{section, density, count}]

    def to_dict(self) -> dict:
        return {
            "type": "hedging_language",
            "hedges": self.hedges,
            "hedge_density": self.hedge_density,
            "sections_by_density": self.sections_by_density,
            "total_hedges": len(self.hedges),
        }


def detect_hedging_language(
    text: str,
    delimiter_pattern: Optional[str] = None,
    context_window: int = 150,
) -> HedgingResult:
    """Detect phrases where the author hedges or qualifies — stating views as 'mere possibilities.'

    Per Strauss's reading of Lessing, exoteric statements are presented as
    possibilities rather than assertions. High concentrations of hedging
    language may mark passages where the author is closest to a dangerous truth
    but cannot state it directly.
    """
    sections = segment_text(text, delimiter_pattern)
    all_hedges = []
    section_stats = []
    total_words = 0

    for section in sections:
        section_lower = section.text.lower()
        section_words = len(re.findall(r'\w+', section.text))
        total_words += section_words
        section_count = 0

        for phrase in HEDGING_PHRASES:
            pos = 0
            while True:
                idx = section_lower.find(phrase, pos)
                if idx == -1:
                    break

                # Extract the full sentence containing the hedge
                sent_start = max(0, section.text.rfind('.', 0, idx) + 1)
                sent_end = section.text.find('.', idx + len(phrase))
                if sent_end == -1:
                    sent_end = min(len(section.text), idx + context_window)
                else:
                    sent_end += 1

                sentence = section.text[sent_start:sent_end].strip()

                all_hedges.append({
                    "phrase": phrase,
                    "section": section.label,
                    "context": sentence[:context_window * 2],
                })
                section_count += 1
                pos = idx + len(phrase)

        density = round(section_count / section_words * 1000, 2) if section_words > 0 else 0
        section_stats.append({
            "section": section.label,
            "density": density,
            "count": section_count,
        })

    overall_density = round(len(all_hedges) / total_words * 1000, 2) if total_words > 0 else 0

    # Sort sections by density (highest first)
    section_stats.sort(key=lambda s: s["density"], reverse=True)

    return HedgingResult(
        hedges=all_hedges[:50],  # Cap for UI
        hedge_density=overall_density,
        sections_by_density=section_stats,
    )


# ─────────────────────────────────────────────────────
# Orchestrator: Run all tools
# ─────────────────────────────────────────────────────

@dataclass
class EsotericAnalysisConfig:
    """Configuration for running esoteric computational analysis."""
    keywords: list[str] = field(default_factory=lambda: [
        "justice", "truth", "god", "gods", "fate", "piety", "wisdom",
        "nature", "law", "virtue", "death", "freedom", "courage",
        "knowledge", "opinion", "philosophy", "soul", "reason",
        "noble", "beautiful", "good", "evil", "pleasure", "pain",
    ])
    entities: list[str] = field(default_factory=lambda: [])
    pious_words: Optional[set[str]] = None
    subversive_words: Optional[set[str]] = None
    delimiter_pattern: Optional[str] = None
    silence_threshold: float = 0.2
    context_window: int = 150
    center_window_lines: int = 25


# ─────────────────────────────────────────────────────
# Tool 8: Self-Reference Detector
# ─────────────────────────────────────────────────────

SELF_REFERENCE_MARKERS = [
    "writing between the lines", "esoteric", "exoteric", "hidden teaching",
    "secret teaching", "concealment", "art of writing", "careful reader",
    "careless reader", "between the lines", "noble lie", "pious fraud",
    "literary technique", "peculiar technique", "writing with circumspection",
    "dissimulation", "irony", "ironic", "double meaning",
    "the author discusses", "intentional blunders", "intentional",
    "the wise", "the vulgar", "the few", "the many",
]


@dataclass
class SelfReferenceResult:
    """Result from the Self-Reference Detector."""
    references: list[dict]  # [{marker, section, context}]
    density: float
    meta_esoteric_score: float  # 0-1, how self-referential the text is

    def to_dict(self) -> dict:
        return {
            "type": "self_reference",
            "references": self.references,
            "density": self.density,
            "meta_esoteric_score": self.meta_esoteric_score,
            "total": len(self.references),
        }


def detect_self_reference(
    text: str,
    delimiter_pattern: Optional[str] = None,
    context_window: int = 150,
) -> SelfReferenceResult:
    """Detect when a text discusses its own method of writing or reading.

    When an author discusses concealment, irony, literary technique, or
    esoteric writing, those passages may be simultaneously PERFORMING what
    they describe. High self-reference density signals a meta-esoteric text —
    one that is itself an example of the practice it analyzes.
    """
    sections = segment_text(text, delimiter_pattern)
    text_lower = text.lower()
    total_words = len(re.findall(r'\w+', text))
    refs = []

    for section in sections:
        section_lower = section.text.lower()
        for marker in SELF_REFERENCE_MARKERS:
            pos = 0
            while True:
                idx = section_lower.find(marker, pos)
                if idx == -1:
                    break
                start = max(0, idx - context_window)
                end = min(len(section.text), idx + len(marker) + context_window)
                refs.append({
                    "marker": marker,
                    "section": section.label,
                    "context": section.text[start:end].strip(),
                })
                pos = idx + len(marker)

    density = round(len(refs) / total_words * 1000, 2) if total_words > 0 else 0
    # Score: high density of self-referential language = likely meta-esoteric
    score = min(density / 5.0, 1.0)  # Normalize: 5 per 1000 words = max

    return SelfReferenceResult(
        references=refs[:30],
        density=density,
        meta_esoteric_score=round(score, 3),
    )


# ─────────────────────────────────────────────────────
# Tool 9: Section Proportion Analyzer
# ─────────────────────────────────────────────────────

@dataclass
class SectionProportionResult:
    """Result from the Section Proportion Analyzer."""
    sections: list[dict]  # [{label, word_count, percentage, keyword_density}]
    short_dense_sections: list[dict]  # Sections that are short but keyword-dense

    def to_dict(self) -> dict:
        return {
            "type": "section_proportion",
            "sections": self.sections,
            "short_dense_sections": self.short_dense_sections,
        }


def analyze_section_proportions(
    text: str,
    keywords: list[str],
    delimiter_pattern: Optional[str] = None,
) -> SectionProportionResult:
    """Analyze relative section lengths and keyword density.

    Per Strauss's own method: the esoteric teaching is typically in the
    SHORTER section. When a brief section has disproportionately high
    keyword density or contains the most important claims, it signals
    that the rare/brief statement is the true one.
    """
    sections = segment_text(text, delimiter_pattern)
    keyword_set = {k.lower() for k in keywords}
    total_words = sum(len(re.findall(r'\w+', s.text)) for s in sections)

    section_data = []
    for section in sections:
        words = re.findall(r'\w+', section.text.lower())
        word_count = len(words)
        pct = round(word_count / total_words * 100, 1) if total_words > 0 else 0
        kw_count = sum(1 for w in words if w in keyword_set)
        kw_density = round(kw_count / word_count * 1000, 2) if word_count > 0 else 0

        section_data.append({
            "label": section.label,
            "word_count": word_count,
            "percentage": pct,
            "keyword_density": kw_density,
            "keyword_count": kw_count,
        })

    # Find "short but dense" sections: below median length but above median density
    if len(section_data) >= 2:
        lengths = sorted(s["word_count"] for s in section_data)
        densities = sorted(s["keyword_density"] for s in section_data)
        median_len = lengths[len(lengths) // 2]
        median_density = densities[len(densities) // 2]

        short_dense = [
            {
                "label": s["label"],
                "word_count": s["word_count"],
                "keyword_density": s["keyword_density"],
                "reason": f"Short ({s['percentage']}% of text) but keyword-dense "
                          f"({s['keyword_density']}/1000 vs median {median_density:.1f}/1000) — "
                          f"may contain the esoteric teaching",
            }
            for s in section_data
            if s["word_count"] < median_len and s["keyword_density"] > median_density
        ]
    else:
        short_dense = []

    return SectionProportionResult(
        sections=section_data,
        short_dense_sections=short_dense,
    )


# ─────────────────────────────────────────────────────
# Tool 10: Epigraph Extractor
# ─────────────────────────────────────────────────────

@dataclass
class EpigraphResult:
    """Result from the Epigraph Extractor."""
    epigraphs: list[dict]  # [{text, attribution, location}]

    def to_dict(self) -> dict:
        return {
            "type": "epigraph",
            "epigraphs": self.epigraphs,
            "total": len(self.epigraphs),
        }


def extract_epigraphs(text: str) -> EpigraphResult:
    """Extract epigraphs, mottos, and opening quotations.

    Epigraphs are chosen with extreme care and often contain the key to
    the entire work. They sit at the boundary between paratext and text,
    often expressing the author's true view through someone else's words.
    """
    epigraphs = []

    # Pattern 1: Quoted text followed by attribution (em-dash + name)
    # "Some quotation here." —Author Name
    epigraph_pattern = re.compile(
        r'["\u201c]([^"\u201d]{20,500})["\u201d]\s*'
        r'(?:—|--|-)\s*([A-Z][^\n]{3,80})',
        re.MULTILINE
    )

    for m in epigraph_pattern.finditer(text[:5000]):  # Only check first ~5000 chars
        epigraphs.append({
            "text": m.group(1).strip(),
            "attribution": m.group(2).strip(),
            "location": "opening",
        })

    # Pattern 2: Italic-style epigraph (lines that are short, before main text)
    lines = text[:3000].split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Short line with attribution marker
        if stripped.startswith('—') or stripped.startswith('--'):
            # Previous lines might be the epigraph
            epigraph_text = []
            for j in range(i - 1, max(i - 6, -1), -1):
                prev = lines[j].strip()
                if prev:
                    epigraph_text.insert(0, prev)
                else:
                    break
            if epigraph_text:
                epigraphs.append({
                    "text": ' '.join(epigraph_text),
                    "attribution": stripped.lstrip('—- '),
                    "location": "opening",
                })

    return EpigraphResult(epigraphs=epigraphs[:5])


# ─────────────────────────────────────────────────────
# Tool 11: Conditional Language Detector
# ─────────────────────────────────────────────────────

CONDITIONAL_PATTERNS = [
    re.compile(r'\bif\b\s+(?:it\s+(?:is|be)\s+true\s+that|the|we|one|this|that|there)', re.I),
    re.compile(r'\bgranted\s+that\b', re.I),
    re.compile(r'\bsupposing\s+that\b', re.I),
    re.compile(r'\bassuming\s+that\b', re.I),
    re.compile(r'\bwere\s+(?:it|one|we)\s+to\b', re.I),
    re.compile(r'\bshould\s+(?:it|this|one)\s+(?:be|prove)\b', re.I),
    re.compile(r'\bprovided\s+(?:that|only)\b', re.I),
    re.compile(r'\bon\s+(?:the\s+)?(?:condition|assumption|hypothesis)\s+that\b', re.I),
    re.compile(r'\bif\s+(?:and\s+only\s+if|indeed)\b', re.I),
]


@dataclass
class ConditionalResult:
    """Result from the Conditional Language Detector."""
    conditionals: list[dict]  # [{pattern, section, sentence}]
    density: float
    sections_by_density: list[dict]

    def to_dict(self) -> dict:
        return {
            "type": "conditional_language",
            "conditionals": self.conditionals,
            "density": self.density,
            "sections_by_density": self.sections_by_density,
            "total": len(self.conditionals),
        }


def detect_conditional_language(
    text: str,
    delimiter_pattern: Optional[str] = None,
    context_window: int = 200,
) -> ConditionalResult:
    """Detect conditional/hypothetical framing of central claims.

    Distinct from hedging ('perhaps'/'it seems'): conditional framing uses
    'if/granted that/supposing' to make a claim technically hypothetical
    while communicating it to the careful reader as the author's true view.

    Per Frazer: Strauss's 'There is a necessary conflict between philosophy
    and politics IF the element of society necessarily is opinion' — the
    italicized 'if' is the esoteric signal.
    """
    sections = segment_text(text, delimiter_pattern)
    all_conds = []
    section_stats = []
    total_words = 0

    for section in sections:
        section_words = len(re.findall(r'\w+', section.text))
        total_words += section_words
        count = 0

        for pat in CONDITIONAL_PATTERNS:
            for m in pat.finditer(section.text):
                # Get the full sentence
                start = max(0, section.text.rfind('.', 0, m.start()) + 1)
                end = section.text.find('.', m.end())
                if end == -1:
                    end = min(len(section.text), m.start() + context_window)
                else:
                    end += 1

                all_conds.append({
                    "pattern": m.group(0),
                    "section": section.label,
                    "sentence": section.text[start:end].strip()[:context_window * 2],
                })
                count += 1

        density = round(count / section_words * 1000, 2) if section_words > 0 else 0
        section_stats.append({"section": section.label, "density": density, "count": count})

    overall = round(len(all_conds) / total_words * 1000, 2) if total_words > 0 else 0
    section_stats.sort(key=lambda s: s["density"], reverse=True)

    return ConditionalResult(
        conditionals=all_conds[:40],
        density=overall,
        sections_by_density=section_stats,
    )


# ─────────────────────────────────────────────────────
# Tool 9: Emphasis & Quotation Mark Extractor
# ─────────────────────────────────────────────────────

@dataclass
class EmphasisResult:
    """Result from the Emphasis Extractor."""
    quoted_words: list[dict]  # [{word, section, context}]
    emphasized_words: list[dict]  # [{word, section, type}]

    def to_dict(self) -> dict:
        return {
            "type": "emphasis_quotation",
            "quoted_words": self.quoted_words,
            "emphasized_words": self.emphasized_words,
            "total_quoted": len(self.quoted_words),
            "total_emphasized": len(self.emphasized_words),
        }


def extract_emphasis_markers(
    text: str,
    delimiter_pattern: Optional[str] = None,
) -> EmphasisResult:
    """Extract words/phrases in quotation marks, italics, or other emphasis.

    Per the 'Secret Words' principle: when an author puts common words in
    quotes or italics, these marks signal double meaning. The marked word
    is being used in a sense different from its everyday meaning.
    """
    sections = segment_text(text, delimiter_pattern)

    quoted = []
    emphasized = []

    # Scare quotes / single-word quotation marks (not full sentences)
    scare_quote = re.compile(r'["\u201c]([^"\u201d]{1,50})["\u201d]')
    # Markdown italic/bold
    md_emphasis = re.compile(r'(?:\*\*|__)(.+?)(?:\*\*|__)')
    md_italic = re.compile(r'(?:\*|_)(.+?)(?:\*|_)')

    for section in sections:
        for m in scare_quote.finditer(section.text):
            content = m.group(1).strip()
            # Skip if it's a full sentence (dialogue) — only interested in individual words/short phrases
            if len(content.split()) <= 5 and not content.endswith(('.', '!', '?')):
                start = max(0, m.start() - 80)
                end = min(len(section.text), m.end() + 80)
                quoted.append({
                    "word": content,
                    "section": section.label,
                    "context": section.text[start:end].strip(),
                })

        for m in md_emphasis.finditer(section.text):
            emphasized.append({"word": m.group(1).strip(), "section": section.label, "type": "bold"})

        for m in md_italic.finditer(section.text):
            content = m.group(1).strip()
            if len(content.split()) <= 5:
                emphasized.append({"word": content, "section": section.label, "type": "italic"})

    return EmphasisResult(
        quoted_words=quoted[:40],
        emphasized_words=emphasized[:30],
    )


# ─────────────────────────────────────────────────────
# Tool 10: First/Last Word Extractor (Notarikon)
# ─────────────────────────────────────────────────────

@dataclass
class FirstLastResult:
    """Result from the First/Last Word Extractor."""
    section_boundaries: list[dict]  # [{section, first_word, last_word, first_sentence, last_sentence}]
    overall_first_sentence: str
    overall_last_sentence: str
    opening_closing_words: dict  # {first_word, last_word} of entire text

    def to_dict(self) -> dict:
        return {
            "type": "first_last_words",
            "section_boundaries": self.section_boundaries,
            "overall_first_sentence": self.overall_first_sentence,
            "overall_last_sentence": self.overall_last_sentence,
            "opening_closing_words": self.opening_closing_words,
        }


def extract_first_last_words(
    text: str,
    delimiter_pattern: Optional[str] = None,
) -> FirstLastResult:
    """Extract first and last words/sentences of each section.

    Per Strauss: the first and last words of a work and its sections are
    almost always significant. The Apology ends with 'theos' and the Laws
    begins with 'theos' — connecting the works esoterically. Some authors
    encode messages in opening/closing positions (a form of notarikon).
    """
    sections = segment_text(text, delimiter_pattern)

    # Get overall first/last sentence
    text_stripped = text.strip()
    sentences = re.split(r'(?<=[.!?])\s+', text_stripped)
    sentences = [s.strip() for s in sentences if s.strip()]

    overall_first = sentences[0] if sentences else ""
    overall_last = sentences[-1] if sentences else ""

    # Get first/last word of entire text
    words = re.findall(r'\w+', text_stripped)
    first_word = words[0] if words else ""
    last_word = words[-1] if words else ""

    # Per-section analysis
    boundaries = []
    for section in sections:
        sec_text = section.text.strip()
        if not sec_text:
            continue

        sec_words = re.findall(r'\w+', sec_text)
        sec_sentences = re.split(r'(?<=[.!?])\s+', sec_text)
        sec_sentences = [s.strip() for s in sec_sentences if s.strip()]

        boundaries.append({
            "section": section.label,
            "first_word": sec_words[0] if sec_words else "",
            "last_word": sec_words[-1] if sec_words else "",
            "first_sentence": sec_sentences[0][:200] if sec_sentences else "",
            "last_sentence": sec_sentences[-1][:200] if sec_sentences else "",
        })

    return FirstLastResult(
        section_boundaries=boundaries,
        overall_first_sentence=overall_first[:300],
        overall_last_sentence=overall_last[:300],
        opening_closing_words={"first_word": first_word, "last_word": last_word},
    )


# ─────────────────────────────────────────────────────
# Tool 9: Parenthetical & Footnote Extractor
# ─────────────────────────────────────────────────────

@dataclass
class ParentheticalResult:
    """Result from the Parenthetical & Footnote Extractor."""
    parentheticals: list[dict]  # [{content, section, type}]
    footnote_markers: list[dict]  # [{marker, section, context}]

    def to_dict(self) -> dict:
        return {
            "type": "parenthetical_footnote",
            "parentheticals": self.parentheticals,
            "footnote_markers": self.footnote_markers,
            "total_parentheticals": len(self.parentheticals),
            "total_footnotes": len(self.footnote_markers),
        }


def extract_parentheticals(
    text: str,
    delimiter_pattern: Optional[str] = None,
) -> ParentheticalResult:
    """Extract parenthetical remarks and footnote references.

    Per Strauss (via Lampert): esoteric writers frequently hide their most
    important insights in footnotes, parenthetical asides, and subordinate
    clauses. Strauss 'relegates to a central footnote a central matter.'
    This tool extracts all such material for focused analysis.
    """
    sections = segment_text(text, delimiter_pattern)

    parentheticals = []
    footnote_markers = []

    # Patterns for parenthetical content
    paren_pattern = re.compile(r'\(([^)]{10,300})\)')  # content in parens, 10-300 chars
    bracket_pattern = re.compile(r'\[([^\]]{10,300})\]')  # content in brackets
    dash_pattern = re.compile(r'(?:—|--)\s*([^—\n]{10,200})\s*(?:—|--)')  # em-dash asides
    footnote_pattern = re.compile(r'(?:[\.\,\;\:]\s*)(\d{1,3})(?:\s|$|\.|,)')  # superscript-like numbers

    for section in sections:
        # Parenthetical content
        for m in paren_pattern.finditer(section.text):
            content = m.group(1).strip()
            if not content[0].isdigit():  # Skip pure citations like "(1952)"
                parentheticals.append({
                    "content": content,
                    "section": section.label,
                    "type": "parenthesis",
                })

        # Bracket content
        for m in bracket_pattern.finditer(section.text):
            content = m.group(1).strip()
            if not content[0].isdigit():
                parentheticals.append({
                    "content": content,
                    "section": section.label,
                    "type": "bracket",
                })

        # Em-dash asides
        for m in dash_pattern.finditer(section.text):
            parentheticals.append({
                "content": m.group(1).strip(),
                "section": section.label,
                "type": "em_dash_aside",
            })

        # Footnote markers (superscript numbers after punctuation)
        for m in footnote_pattern.finditer(section.text):
            num = m.group(1)
            start = max(0, m.start() - 100)
            context = section.text[start:m.end()].strip()
            footnote_markers.append({
                "marker": num,
                "section": section.label,
                "context": context,
            })

    return ParentheticalResult(
        parentheticals=parentheticals[:40],
        footnote_markers=footnote_markers[:30],
    )


# ─────────────────────────────────────────────────────
# Tool 9: Structural Obscurity Detector
# ─────────────────────────────────────────────────────

@dataclass
class StructuralObscurityResult:
    """Result from the Structural Obscurity Detector."""
    section_count: int
    section_size_variance: float  # Higher = more uneven sections (possible obscurity)
    digression_candidates: list[dict]  # Sections that seem thematically out of place
    plan_regularity_score: float  # 0-1, higher = more regular/lucid plan

    def to_dict(self) -> dict:
        return {
            "type": "structural_obscurity",
            "section_count": self.section_count,
            "section_size_variance": self.section_size_variance,
            "digression_candidates": self.digression_candidates,
            "plan_regularity_score": self.plan_regularity_score,
        }


def detect_structural_obscurity(
    text: str,
    keywords: list[str],
    delimiter_pattern: Optional[str] = None,
) -> StructuralObscurityResult:
    """Detect whether a text's structure is deliberately obscure.

    Per Strauss: 'A lucid plan does not leave room for hiding places —
    an exoteric book will NOT have a very lucid plan.'

    Measures: section size regularity, thematic coherence between sections,
    and identifies sections that seem thematically displaced (potential digressions
    where important ideas may be hidden).
    """
    sections = segment_text(text, delimiter_pattern)

    if len(sections) <= 1:
        return StructuralObscurityResult(
            section_count=len(sections),
            section_size_variance=0,
            digression_candidates=[],
            plan_regularity_score=1.0,
        )

    # Measure section size variance
    sizes = [len(s.text) for s in sections]
    avg_size = sum(sizes) / len(sizes)
    variance = sum((s - avg_size) ** 2 for s in sizes) / len(sizes)
    normalized_variance = min(variance / (avg_size ** 2) if avg_size > 0 else 0, 10.0)

    # Check keyword distribution across sections to find thematic outliers
    keyword_set = {k.lower() for k in keywords}
    section_profiles = []
    for section in sections:
        words = re.findall(r'\w+', section.text.lower())
        keyword_count = sum(1 for w in words if w in keyword_set)
        density = keyword_count / len(words) * 1000 if words else 0
        section_profiles.append({
            "label": section.label,
            "size": len(section.text),
            "keyword_density": round(density, 2),
            "word_count": len(words),
        })

    # Find thematic outliers — sections with very different keyword density
    densities = [p["keyword_density"] for p in section_profiles]
    if densities:
        avg_density = sum(densities) / len(densities)
        digressions = []
        for p in section_profiles:
            if avg_density > 0:
                ratio = p["keyword_density"] / avg_density if avg_density > 0 else 0
                if ratio < 0.3 and p["word_count"] > 100:
                    digressions.append({
                        "section": p["label"],
                        "keyword_density": p["keyword_density"],
                        "avg_density": round(avg_density, 2),
                        "reason": "Very low keyword density — may be a thematic digression hiding important content",
                    })
                elif ratio > 2.5:
                    digressions.append({
                        "section": p["label"],
                        "keyword_density": p["keyword_density"],
                        "avg_density": round(avg_density, 2),
                        "reason": "Unusually high keyword density — concentrated discussion may signal importance",
                    })
    else:
        digressions = []

    # Plan regularity: how evenly sized and thematically consistent are sections?
    # High regularity = lucid plan = less room for hiding
    size_regularity = 1.0 / (1.0 + normalized_variance)
    theme_regularity = 1.0 - (len(digressions) / max(len(sections), 1))
    plan_score = round((size_regularity * 0.4 + theme_regularity * 0.6), 3)

    return StructuralObscurityResult(
        section_count=len(sections),
        section_size_variance=round(normalized_variance, 3),
        digression_candidates=digressions[:10],
        plan_regularity_score=plan_score,
    )


# ─────────────────────────────────────────────────────
# Tool 9: Disreputable Mouthpiece Detector
# ─────────────────────────────────────────────────────

# Characters through whom an author may voice forbidden truths (per Strauss)
DISREPUTABLE_TYPES = {
    "devil", "demon", "satan", "mephistopheles", "lucifer",
    "madman", "fool", "jester", "buffoon", "clown",
    "sophist", "atheist", "heretic", "infidel", "libertine",
    "drunkard", "drunk", "epicurean", "hedonist",
    "beggar", "slave", "foreigner", "stranger", "barbarian",
    "old woman", "nurse", "servant",
    "tyrant", "despot",
}

# Speech attribution patterns
SPEECH_PATTERNS = [
    re.compile(r'(?:said|says|remarked|declared|asserted|replied|answered|asked|cried|whispered|observed|noted)\s+(?:the\s+)?(\w+)', re.I),
    re.compile(r'(?:according to|as\s+\w+\s+(?:the\s+)?(\w+)\s+(?:says|said|put it|observed|remarked))', re.I),
    re.compile(r'"[^"]+"\s*(?:said|says|cried)\s+(?:the\s+)?(\w+)', re.I),
]


@dataclass
class MouthpieceResult:
    """Result from the Disreputable Mouthpiece Detector."""
    speakers: list[dict]  # [{speaker, type, context, count}]
    disreputable_speech: list[dict]  # [{speaker, context, section}]

    def to_dict(self) -> dict:
        return {
            "type": "disreputable_mouthpiece",
            "speakers": self.speakers,
            "disreputable_speech": self.disreputable_speech,
        }


def detect_disreputable_mouthpieces(
    text: str,
    delimiter_pattern: Optional[str] = None,
    context_window: int = 200,
) -> MouthpieceResult:
    """Detect when disreputable characters are given speech or used to voice views.

    Per Strauss: 'some great writers might have stated certain important truths quite
    openly by using as mouthpiece some disreputable character: they would thus show
    how much they disapproved of pronouncing the truths in question. There would then
    be good reason for our finding in the greatest literature of the past so many
    interesting devils, madmen, beggars, sophists, drunkards, epicureans and buffoons.'
    """
    sections = segment_text(text, delimiter_pattern)
    text_lower = text.lower()

    # Find mentions of disreputable character types
    disreputable_refs = []
    speaker_counts = Counter()

    for section in sections:
        section_lower = section.text.lower()
        for dtype in DISREPUTABLE_TYPES:
            pos = 0
            while True:
                idx = section_lower.find(dtype, pos)
                if idx == -1:
                    break
                # Check if this is in a speech context
                start = max(0, idx - context_window)
                end = min(len(section.text), idx + len(dtype) + context_window)
                context = section.text[start:end].strip()

                # Check for speech indicators near the mention
                speech_nearby = any(w in context.lower() for w in
                    ['said', 'says', 'replied', 'declared', 'asked', 'answered',
                     'observed', 'remarked', 'argued', 'claimed', 'maintained',
                     '"', '\u201c', '\u201d'])

                if speech_nearby:
                    disreputable_refs.append({
                        "speaker": dtype,
                        "section": section.label,
                        "context": context[:context_window * 2],
                    })
                speaker_counts[dtype] += 1
                pos = idx + len(dtype)

    # Build speaker summary
    speakers = [
        {"speaker": s, "count": c}
        for s, c in speaker_counts.most_common()
        if c > 0
    ]

    return MouthpieceResult(
        speakers=speakers[:15],
        disreputable_speech=disreputable_refs[:20],
    )


def run_full_esoteric_analysis(
    text: str,
    config: Optional[EsotericAnalysisConfig] = None,
) -> dict:
    """Run all 56 computational esoteric analysis tools and return combined results."""
    if config is None:
        config = EsotericAnalysisConfig()

    # Pre-compute shared tokenization (used by all tools)
    _clear_cache()
    _get_shared(text, config.delimiter_pattern)

    results = {}

    # 1. Loud Silence Detector
    try:
        silence_result = detect_loud_silences(
            text=text,
            keywords=config.keywords,
            delimiter_pattern=config.delimiter_pattern,
            silence_threshold=config.silence_threshold,
        )
        results["loud_silences"] = silence_result.to_dict()
    except Exception as e:
        logger.error(f"Loud Silence Detector failed: {e}")
        results["loud_silences"] = {"error": str(e)}

    # 2. Contradiction Hunter (only if entities provided)
    if config.entities:
        try:
            contradiction_result = hunt_contradictions(
                text=text,
                entities=config.entities,
                delimiter_pattern=config.delimiter_pattern,
                context_window=config.context_window,
            )
            results["contradictions"] = contradiction_result.to_dict()
        except Exception as e:
            logger.error(f"Contradiction Hunter failed: {e}")
            results["contradictions"] = {"error": str(e)}

    # 3. Center Locator
    try:
        center_result = locate_centers(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
            center_window_lines=config.center_window_lines,
        )
        results["centers"] = center_result.to_dict()
    except Exception as e:
        logger.error(f"Center Locator failed: {e}")
        results["centers"] = {"error": str(e)}

    # 4. Exoteric/Esoteric Ratio
    try:
        ratio_result = analyze_exoteric_esoteric_ratio(
            text=text,
            pious_words=config.pious_words,
            subversive_words=config.subversive_words,
            delimiter_pattern=config.delimiter_pattern,
        )
        results["exoteric_esoteric_ratio"] = ratio_result.to_dict()
    except Exception as e:
        logger.error(f"Exoteric/Esoteric Ratio failed: {e}")
        results["exoteric_esoteric_ratio"] = {"error": str(e)}

    # 5. Repetition with Variation
    try:
        repetition_result = detect_repetition_with_variation(
            text=text,
            keywords=config.keywords,
            delimiter_pattern=config.delimiter_pattern,
            context_window=config.context_window,
        )
        results["repetition_variation"] = repetition_result.to_dict()
    except Exception as e:
        logger.error(f"Repetition with Variation failed: {e}")
        results["repetition_variation"] = {"error": str(e)}

    # 6. Audience Differentiation
    try:
        audience_result = detect_audience_differentiation(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
            context_window=config.context_window,
        )
        results["audience_differentiation"] = audience_result.to_dict()
    except Exception as e:
        logger.error(f"Audience Differentiation failed: {e}")
        results["audience_differentiation"] = {"error": str(e)}

    # 7. Hedging Language ("Mere Possibility")
    try:
        hedging_result = detect_hedging_language(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
            context_window=config.context_window,
        )
        results["hedging_language"] = hedging_result.to_dict()
    except Exception as e:
        logger.error(f"Hedging Language Detector failed: {e}")
        results["hedging_language"] = {"error": str(e)}

    # 8. Disreputable Mouthpiece
    try:
        mouthpiece_result = detect_disreputable_mouthpieces(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
            context_window=config.context_window,
        )
        results["disreputable_mouthpiece"] = mouthpiece_result.to_dict()
    except Exception as e:
        logger.error(f"Disreputable Mouthpiece Detector failed: {e}")
        results["disreputable_mouthpiece"] = {"error": str(e)}

    # Self-Reference Detection
    try:
        selfref_result = detect_self_reference(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
            context_window=config.context_window,
        )
        results["self_reference"] = selfref_result.to_dict()
    except Exception as e:
        logger.error(f"Self-Reference Detector failed: {e}")
        results["self_reference"] = {"error": str(e)}

    # Section Proportion Analysis
    try:
        proportion_result = analyze_section_proportions(
            text=text,
            keywords=config.keywords,
            delimiter_pattern=config.delimiter_pattern,
        )
        results["section_proportion"] = proportion_result.to_dict()
    except Exception as e:
        logger.error(f"Section Proportion Analyzer failed: {e}")
        results["section_proportion"] = {"error": str(e)}

    # Epigraph Extraction
    try:
        epigraph_result = extract_epigraphs(text)
        results["epigraph"] = epigraph_result.to_dict()
    except Exception as e:
        logger.error(f"Epigraph Extractor failed: {e}")
        results["epigraph"] = {"error": str(e)}

    # Conditional Language
    try:
        cond_result = detect_conditional_language(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
            context_window=config.context_window,
        )
        results["conditional_language"] = cond_result.to_dict()
    except Exception as e:
        logger.error(f"Conditional Language Detector failed: {e}")
        results["conditional_language"] = {"error": str(e)}

    # Emphasis & Quotation Marks
    try:
        emphasis_result = extract_emphasis_markers(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
        )
        results["emphasis_quotation"] = emphasis_result.to_dict()
    except Exception as e:
        logger.error(f"Emphasis Extractor failed: {e}")
        results["emphasis_quotation"] = {"error": str(e)}

    # First/Last Word Extraction
    try:
        firstlast_result = extract_first_last_words(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
        )
        results["first_last_words"] = firstlast_result.to_dict()
    except Exception as e:
        logger.error(f"First/Last Word Extractor failed: {e}")
        results["first_last_words"] = {"error": str(e)}

    # 9. Parenthetical & Footnote Extraction
    try:
        paren_result = extract_parentheticals(
            text=text,
            delimiter_pattern=config.delimiter_pattern,
        )
        results["parenthetical_footnote"] = paren_result.to_dict()
    except Exception as e:
        logger.error(f"Parenthetical Extractor failed: {e}")
        results["parenthetical_footnote"] = {"error": str(e)}

    # 9. Structural Obscurity
    try:
        obscurity_result = detect_structural_obscurity(
            text=text,
            keywords=config.keywords,
            delimiter_pattern=config.delimiter_pattern,
        )
        results["structural_obscurity"] = obscurity_result.to_dict()
    except Exception as e:
        logger.error(f"Structural Obscurity Detector failed: {e}")
        results["structural_obscurity"] = {"error": str(e)}

    # Excessive Praise Detector
    try:
        praise_result = detect_excessive_praise(text=text, delimiter_pattern=config.delimiter_pattern)
        results["excessive_praise"] = praise_result
    except Exception as e:
        logger.error(f"Excessive Praise Detector failed: {e}")
        results["excessive_praise"] = {"error": str(e)}

    # Lexical Density Mapper
    try:
        density_result = detect_lexical_density(text=text, delimiter_pattern=config.delimiter_pattern)
        results["lexical_density"] = density_result
    except Exception as e:
        logger.error(f"Lexical Density Mapper failed: {e}")
        results["lexical_density"] = {"error": str(e)}

    # Sentiment Inversion Detector
    try:
        inversion_result = detect_sentiment_inversion(text=text, delimiter_pattern=config.delimiter_pattern)
        results["sentiment_inversion"] = inversion_result
    except Exception as e:
        logger.error(f"Sentiment Inversion Detector failed: {e}")
        results["sentiment_inversion"] = {"error": str(e)}

    # Numerological Significance
    try:
        numerology_result = check_numerological_significance(text=text, delimiter_pattern=config.delimiter_pattern)
        results["numerology"] = numerology_result
    except Exception as e:
        logger.error(f"Numerological Significance failed: {e}")
        results["numerology"] = {"error": str(e)}

    # Acrostic & Telestic Detection
    try:
        results["acrostics"] = detect_acrostics(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Acrostic Detection failed: {e}")
        results["acrostics"] = {"error": str(e)}

    # Hapax Legomena Analysis
    try:
        results["hapax_legomena"] = detect_hapax_legomena(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Hapax Legomena failed: {e}")
        results["hapax_legomena"] = {"error": str(e)}

    # Voice / Persona Shifts
    try:
        results["voice_shifts"] = detect_voice_shifts(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Voice Shifts failed: {e}")
        results["voice_shifts"] = {"error": str(e)}

    # Register Tiers (Averroes)
    try:
        results["register_tiers"] = detect_register_tiers(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Register Tiers failed: {e}")
        results["register_tiers"] = {"error": str(e)}

    # Logos / Mythos Transitions
    try:
        results["logos_mythos"] = detect_logos_mythos(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Logos/Mythos failed: {e}")
        results["logos_mythos"] = {"error": str(e)}

    # Commentary Divergence
    try:
        results["commentary_divergence"] = detect_commentary_divergence(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Commentary Divergence failed: {e}")
        results["commentary_divergence"] = {"error": str(e)}

    # Polysemy Detection
    try:
        results["polysemy"] = detect_polysemy(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Polysemy Detection failed: {e}")
        results["polysemy"] = {"error": str(e)}

    # Aphoristic Fragmentation
    try:
        results["aphoristic_fragmentation"] = detect_aphoristic_fragmentation(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Aphoristic Fragmentation failed: {e}")
        results["aphoristic_fragmentation"] = {"error": str(e)}

    # Benardete: Trapdoor Detection
    try:
        results["trapdoors"] = detect_trapdoors(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Trapdoor Detection failed: {e}")
        results["trapdoors"] = {"error": str(e)}

    # Benardete: Dyadic Structure
    try:
        results["dyadic_structure"] = detect_dyadic_structure(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Dyadic Structure failed: {e}")
        results["dyadic_structure"] = {"error": str(e)}

    # Benardete: Periagoge (Structural Reversal)
    try:
        results["periagoge"] = detect_periagoge(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Periagoge Detection failed: {e}")
        results["periagoge"] = {"error": str(e)}

    # Benardete: Logos-Ergon (Speech-Deed)
    try:
        results["logos_ergon"] = detect_logos_ergon(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Logos-Ergon failed: {e}")
        results["logos_ergon"] = {"error": str(e)}

    # Benardete: Onomastic (Name-Meaning)
    try:
        results["onomastic"] = detect_onomastic(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Onomastic Analysis failed: {e}")
        results["onomastic"] = {"error": str(e)}

    # Benardete: Recognition Structure
    try:
        results["recognition_structure"] = detect_recognition_structure(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Recognition Structure failed: {e}")
        results["recognition_structure"] = {"error": str(e)}

    # Benardete: Nomos-Physis
    try:
        results["nomos_physis"] = detect_nomos_physis(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Nomos-Physis failed: {e}")
        results["nomos_physis"] = {"error": str(e)}

    # Benardete: Impossible Arithmetic
    try:
        results["impossible_arithmetic"] = detect_impossible_arithmetic(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Impossible Arithmetic failed: {e}")
        results["impossible_arithmetic"] = {"error": str(e)}

    # Dwell Passage Detection
    try:
        results["dwell_passages"] = detect_dwell_passages(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Dwell Passages failed: {e}")
        results["dwell_passages"] = {"error": str(e)}

    # Confusion Signal Detection
    try:
        results["confusion_signals"] = detect_confusion_signals(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Confusion Signals failed: {e}")
        results["confusion_signals"] = {"error": str(e)}

    # Rhetorical Beauty Detection
    try:
        results["rhetorical_beauty"] = detect_rhetorical_beauty(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Rhetorical Beauty failed: {e}")
        results["rhetorical_beauty"] = {"error": str(e)}

    # Word Weight Analysis
    try:
        results["word_weight"] = detect_word_weight(text=text, delimiter_pattern=config.delimiter_pattern)
    except Exception as e:
        logger.error(f"Word Weight failed: {e}")
        results["word_weight"] = {"error": str(e)}

    # Rosen methods (26-34)
    ROSEN_TOOLS = [
        ("rhetoric_of_concealment", detect_rhetoric_of_concealment),
        ("transcendental_ambiguity", detect_transcendental_ambiguity),
        ("rhetoric_of_frankness", detect_rhetoric_of_frankness),
        ("intuition_analysis_dialectic", detect_intuition_analysis_dialectic),
        ("logographic_necessity", detect_logographic_necessity),
        ("theological_disavowal", detect_theological_disavowal),
        ("defensive_writing", detect_defensive_writing),
        ("nature_freedom_oscillation", detect_nature_freedom_oscillation),
        ("postmodern_misreading", detect_postmodern_misreading),
    ]
    # Rosen Symposium methods (35-42)
    SYMPOSIUM_TOOLS = [
        ("dramatic_context", detect_dramatic_context),
        ("speech_sequencing", detect_speech_sequencing),
        ("philosophical_comedy", detect_philosophical_comedy),
        ("daimonic_mediation", detect_daimonic_mediation),
        ("medicinal_rhetoric", detect_medicinal_rhetoric),
        ("poetry_philosophy_dialectic", detect_poetry_philosophy_dialectic),
        ("aspiration_achievement_gap", detect_aspiration_achievement_gap),
        ("synoptic_requirement", detect_synoptic_requirement),
    ]

    for name, func in ROSEN_TOOLS + SYMPOSIUM_TOOLS:
        try:
            results[name] = func(text=text, delimiter_pattern=config.delimiter_pattern)
        except Exception as e:
            logger.error(f"{name} failed: {e}")
            results[name] = {"error": str(e)}

    _clear_cache()
    return results


# ─────────────────────────────────────────────────────
# NEW TOOLS: Excessive Praise, Lexical Density,
#             Sentiment Inversion, Numerology
# ─────────────────────────────────────────────────────

# Gematria / Isopsephy / Numerology tables
GEMATRIA_TABLE = {
    'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9,
    'י': 10, 'כ': 20, 'ך': 20, 'ל': 30, 'מ': 40, 'ם': 40, 'נ': 50, 'ן': 50,
    'ס': 60, 'ע': 70, 'פ': 80, 'ף': 80, 'צ': 90, 'ץ': 90, 'ק': 100, 'ר': 200,
    'ש': 300, 'ת': 400,
}

ISOPSEPHY_TABLE = {
    'α': 1, 'β': 2, 'γ': 3, 'δ': 4, 'ε': 5, 'ϛ': 6, 'ζ': 7, 'η': 8, 'θ': 9,
    'ι': 10, 'κ': 20, 'λ': 30, 'μ': 40, 'ν': 50, 'ξ': 60, 'ο': 70, 'π': 80,
    'ϟ': 90, 'ρ': 100, 'σ': 200, 'ς': 200, 'τ': 300, 'υ': 400, 'φ': 500,
    'χ': 600, 'ψ': 700, 'ω': 800, 'ϡ': 900,
}

LATIN_TABLE = {chr(i): i - 96 for i in range(97, 123)}

SIGNIFICANT_NUMBERS = {
    1: "Unity, the One, the Monad", 3: "Triad, harmony, Trinity",
    4: "Tetractys, cosmic completeness", 5: "Pentad, marriage of 2+3",
    6: "Harmony, creation (6 days), perfect number", 7: "Sacred completeness",
    10: "Decad, perfection, Sefirot", 12: "Cosmic order (tribes, apostles, zodiac)",
    13: "Transgression, rebellion; 13 attributes of mercy",
    18: "Chai (life) in gematria", 22: "Hebrew alphabet letters",
    26: "YHWH in gematria (Strauss on Machiavelli)",
    28: "Second perfect number", 32: "Paths of wisdom (Sefirot + letters)",
    36: "Double-chai (36 righteous ones)", 40: "Trial, testing, purification",
    42: "42-letter Name of God", 49: "7×7, completeness squared",
    50: "Jubilee, freedom", 70: "Fullness of nations, Sanhedrin",
    72: "Names of God (Shemhamphorasch)", 100: "Fullness of a cycle",
    142: "Machiavelli's Discourses (Livy's 141 + 1)",
    216: "Plato's Nuptial Number candidate (6³)", 666: "Number of the Beast",
}


def compute_gematria(word: str, table: dict = None) -> int:
    """Compute numerical value of a word using the given letter-value table."""
    if table is None:
        table = LATIN_TABLE
    return sum(table.get(c, 0) for c in word.lower())


def detect_excessive_praise(
    text: str,
    delimiter_pattern: str = r"\n\s*\n",
) -> dict:
    """Detect passages with excessive praise/emphatic agreement ('protesting too much').

    Per Strauss: praising orthodox opinion with unusual vehemence signals disagreement.
    """
    PRAISE_MARKERS = {
        'absolutely', 'certainly', 'undoubtedly', 'unquestionably', 'indisputably',
        'beyond question', 'beyond doubt', 'no one would deny', 'all agree',
        'every reasonable person', 'obviously', 'clearly', 'manifestly',
        'it is evident', 'without doubt', 'universally acknowledged',
        'no sane person', 'self-evident', 'goes without saying', 'needless to say',
        'of course', 'naturally', 'it stands to reason', 'everyone knows',
    }
    SUPERLATIVES = {
        'greatest', 'noblest', 'highest', 'best', 'most excellent', 'most worthy',
        'most admirable', 'supreme', 'unparalleled', 'incomparable', 'matchless',
        'peerless', 'finest', 'most sacred', 'most holy', 'most important',
    }

    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    flagged = []
    text_lower = text.lower()

    for i, section in enumerate(sections):
        if len(section.strip()) < 50:
            continue
        s_lower = section.lower()
        praise_count = sum(1 for m in PRAISE_MARKERS if m in s_lower)
        super_count = sum(1 for s in SUPERLATIVES if s in s_lower)
        word_count = len(s_lower.split())
        if word_count < 10:
            continue

        density = (praise_count + super_count) / word_count
        if praise_count + super_count >= 2 or density > 0.02:
            flagged.append({
                "section": i + 1,
                "praise_markers": praise_count,
                "superlatives": super_count,
                "density": round(density, 4),
                "excerpt": section.strip()[:200],
            })

    flagged.sort(key=lambda x: x["density"], reverse=True)
    return {
        "total_flagged": len(flagged),
        "sections": flagged[:15],
        "interpretation": "Passages with excessive emphatic language may signal the author 'protesting too much' — praising orthodoxy to mask disagreement (Strauss).",
    }


def detect_lexical_density(
    text: str,
    delimiter_pattern: str = r"\n\s*\n",
) -> dict:
    """Measure vocabulary diversity (type-token ratio) per section.

    High lexical density = author writing most carefully = philosophically loaded section.
    """
    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    densities = []

    for i, section in enumerate(sections):
        words = re.findall(r'\b[a-zA-Z]{3,}\b', section.lower())
        if len(words) < 20:
            continue
        types = len(set(words))
        tokens = len(words)
        ttr = types / tokens  # type-token ratio
        densities.append({
            "section": i + 1,
            "type_token_ratio": round(ttr, 4),
            "unique_words": types,
            "total_words": tokens,
            "excerpt": section.strip()[:100],
        })

    if not densities:
        return {"sections": [], "avg_density": 0, "high_density_sections": []}

    avg = sum(d["type_token_ratio"] for d in densities) / len(densities)
    std = (sum((d["type_token_ratio"] - avg) ** 2 for d in densities) / len(densities)) ** 0.5

    high = [d for d in densities if d["type_token_ratio"] > avg + std]
    high.sort(key=lambda x: x["type_token_ratio"], reverse=True)

    return {
        "avg_density": round(avg, 4),
        "std_density": round(std, 4),
        "total_sections": len(densities),
        "high_density_sections": high[:10],
        "interpretation": "High lexical density indicates the author chose words most carefully — these sections likely carry the most philosophically loaded content.",
    }


def detect_sentiment_inversion(
    text: str,
    delimiter_pattern: str = r"\n\s*\n",
) -> dict:
    """Detect topically similar passages with inverted polarity (potential irony/contradiction).

    Uses keyword overlap for topical similarity and negation density differential
    for polarity inversion. More sophisticated than simple contradiction detection.
    """
    NEGATION = {
        'not', 'no', 'never', 'neither', 'nor', 'nothing', 'nowhere',
        'hardly', 'scarcely', 'barely', 'without', 'cannot', "can't",
        "don't", "doesn't", "didn't", "won't", "wouldn't", "shouldn't",
    }
    OPPOSITION = {
        'but', 'however', 'yet', 'nevertheless', 'nonetheless',
        'although', 'contrary', 'opposite', 'whereas', 'instead',
        'rather', 'despite', 'conversely',
    }

    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    parsed = []
    for i, section in enumerate(sections):
        words = re.findall(r'\b[a-zA-Z]{3,}\b', section.lower())
        if len(words) < 15:
            continue
        content_words = set(words) - NEGATION - OPPOSITION - {
            'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was', 'were',
            'have', 'has', 'had', 'been', 'being', 'will', 'would', 'could', 'should',
        }
        neg_density = sum(1 for w in words if w in NEGATION) / len(words)
        opp_density = sum(1 for w in words if w in OPPOSITION) / len(words)
        parsed.append({
            "index": i,
            "content_words": content_words,
            "neg_density": neg_density,
            "opp_density": opp_density,
            "word_count": len(words),
            "excerpt": section.strip()[:200],
        })

    inversions = []
    for a_idx in range(len(parsed)):
        for b_idx in range(a_idx + 1, min(a_idx + 20, len(parsed))):
            a, b = parsed[a_idx], parsed[b_idx]
            # Topical similarity via Jaccard coefficient
            intersection = len(a["content_words"] & b["content_words"])
            union = len(a["content_words"] | b["content_words"])
            if union == 0:
                continue
            similarity = intersection / union
            if similarity < 0.15:
                continue

            # Polarity inversion
            neg_diff = abs(a["neg_density"] - b["neg_density"])
            combined_opp = a["opp_density"] + b["opp_density"]
            inversion_score = similarity * (neg_diff + combined_opp) * 10

            if inversion_score > 0.1:
                inversions.append({
                    "section_a": a["index"] + 1,
                    "section_b": b["index"] + 1,
                    "topical_similarity": round(similarity, 3),
                    "negation_differential": round(neg_diff, 4),
                    "inversion_score": round(min(inversion_score, 1.0), 3),
                    "excerpt_a": a["excerpt"],
                    "excerpt_b": b["excerpt"],
                })

    inversions.sort(key=lambda x: x["inversion_score"], reverse=True)
    return {
        "total_inversions": len(inversions),
        "inversions": inversions[:15],
        "interpretation": "Topically similar passages with inverted polarity may signal deliberate contradiction or irony (Maimonides 7th cause; Strauss on the less emphatic statement).",
    }


def check_numerological_significance(
    text: str,
    delimiter_pattern: str = r"\n\s*\n",
) -> dict:
    """Check structural counts against traditionally significant numbers."""
    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s for s in sections if len(s.strip()) > 50]
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if len(s.strip()) > 10]

    # Count headings (markdown ## or CHAPTER patterns)
    headings = re.findall(r'^#{1,3}\s+.+$|^(?:CHAPTER|Chapter|BOOK|Book|PART|Part)\s+', text, re.MULTILINE)

    counts = {
        "sections": len(sections),
        "sentences": len(sentences),
        "headings": len(headings),
    }

    matches = []
    for label, count in counts.items():
        if count in SIGNIFICANT_NUMBERS:
            matches.append({
                "element": label,
                "count": count,
                "significance": SIGNIFICANT_NUMBERS[count],
            })
        # Check divisors
        for num, meaning in SIGNIFICANT_NUMBERS.items():
            if num > 1 and count > num and count % num == 0 and count != num:
                matches.append({
                    "element": label,
                    "count": count,
                    "divisible_by": num,
                    "significance": f"Divisible by {num}: {meaning}",
                })

    return {
        "counts": counts,
        "significant_matches": matches[:20],
        "interpretation": "Structural counts matching traditionally significant numbers may indicate deliberate numerological construction (Pythagorean, Kabbalistic, Straussian on Machiavelli).",
    }


# ─────────────────────────────────────────────────────
# METHODS 10-17: Advanced Esoteric Detection
# ─────────────────────────────────────────────────────

_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
    'with', 'by', 'from', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
    'may', 'might', 'shall', 'can', 'this', 'that', 'these', 'those', 'it', 'its',
    'he', 'she', 'they', 'we', 'you', 'i', 'me', 'my', 'his', 'her', 'their',
    'our', 'your', 'not', 'no', 'if', 'then', 'than', 'as', 'so', 'up', 'out',
    'about', 'into', 'over', 'after', 'before', 'between', 'through', 'during',
    'without', 'again', 'further', 'once',
}

_SIGNAL_WORDS = {
    'god', 'die', 'sin', 'law', 'war', 'man', 'lie', 'eye', 'one', 'end', 'key',
    'love', 'hate', 'true', 'lies', 'soul', 'mind', 'free', 'hide', 'veil', 'mask',
    'dead', 'evil', 'good', 'king', 'fool', 'wise', 'fire', 'dark', 'self', 'void',
    'fear', 'hope', 'fate', 'lord', 'name', 'truth', 'death', 'light', 'power',
    'slave', 'false', 'secret', 'hidden', 'nature', 'reason', 'divine',
}

_PHILOSOPHICAL_TERMS = {
    'truth', 'being', 'essence', 'nature', 'soul', 'god', 'divine', 'reason',
    'justice', 'virtue', 'freedom', 'knowledge', 'wisdom', 'death', 'immortal',
    'eternal', 'power', 'law', 'good', 'evil', 'beauty', 'love', 'existence',
    'substance', 'form', 'matter', 'spirit', 'mind', 'cosmos', 'creation',
    'revelation', 'prophecy', 'sacred', 'profane', 'hidden', 'secret', 'mystery',
}


def detect_acrostics(text: str, delimiter_pattern: str = None) -> dict:
    """Detect acrostic/telestic patterns in first/last letters of sentences and sections.

    Precedent: Hebrew Bible alphabetic acrostics, Virgil, Renaissance steganography.
    """
    sents = re.split(r'[.!?]+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 10]

    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s.strip() for s in sections if len(s.strip()) > 30]

    def first_letter(t):
        m = re.search(r'[a-zA-Z]', t)
        return m.group(0).lower() if m else ''

    def last_letter(t):
        letters = re.findall(r'[a-zA-Z]', t)
        return letters[-1].lower() if letters else ''

    sent_firsts = ''.join(first_letter(s) for s in sents)
    sent_lasts = ''.join(last_letter(s) for s in sents)
    sect_firsts = ''.join(first_letter(s) for s in sections)

    def find_patterns(seq, label):
        findings = []
        if len(seq) < 3:
            return findings
        # Alphabetic runs
        for i in range(len(seq) - 2):
            run = 1
            for j in range(i + 1, len(seq)):
                if ord(seq[j]) == ord(seq[j-1]) + 1:
                    run += 1
                else:
                    break
            if run >= 3:
                findings.append({"type": "alphabetic_run", "position": i,
                                 "length": run, "sequence": seq[i:i+run], "source": label})
        # Signal words
        for wlen in range(3, min(8, len(seq) + 1)):
            for i in range(len(seq) - wlen + 1):
                cand = seq[i:i+wlen]
                if cand in _SIGNAL_WORDS:
                    findings.append({"type": "word_found", "position": i,
                                     "word": cand, "source": label})
        # Palindromes 4+
        for plen in range(4, min(10, len(seq) + 1)):
            for i in range(len(seq) - plen + 1):
                sub = seq[i:i+plen]
                if sub == sub[::-1]:
                    findings.append({"type": "palindrome", "position": i,
                                     "sequence": sub, "source": label})
        return findings

    all_findings = []
    all_findings.extend(find_patterns(sent_firsts, "sentence_first_letters"))
    all_findings.extend(find_patterns(sent_lasts, "sentence_last_letters"))
    all_findings.extend(find_patterns(sect_firsts, "section_first_letters"))

    return {
        "total_findings": len(all_findings),
        "findings": all_findings[:30],
        "sequences": {
            "sentence_firsts": sent_firsts[:100],
            "sentence_lasts": sent_lasts[:100],
            "section_firsts": sect_firsts[:100],
        },
        "method": "Acrostic & Telestic Detection",
        "precedent": "Hebrew Bible acrostics, Virgil, Renaissance steganography",
        "interpretation": "Patterns in first/last letters may encode hidden words or signals.",
    }


def detect_hapax_legomena(text: str, delimiter_pattern: str = None) -> dict:
    """Find words used exactly once — potential deliberate markers.

    Precedent: Biblical scholarship (1,500+ hapax in Hebrew Bible).
    """
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    freq = Counter(words)
    content_words = {w: c for w, c in freq.items() if w not in _STOPWORDS}

    hapax = {w for w, c in content_words.items() if c == 1}
    total_content = len([w for w in words if w not in _STOPWORDS])
    hapax_ratio = len(hapax) / total_content if total_content else 0

    # Philosophical hapax
    phil_hapax = sorted(hapax & _PHILOSOPHICAL_TERMS)

    # Positional analysis (quintiles)
    sents = re.split(r'[.!?]+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 10]
    n = len(sents)
    pos_counts = {q: 0 for q in range(5)}
    pos_totals = {q: 0 for q in range(5)}
    for i, sent in enumerate(sents):
        q = min(4, int((i / max(n, 1)) * 5))
        sw = re.findall(r'\b[a-zA-Z]{4,}\b', sent.lower())
        sw = [w for w in sw if w not in _STOPWORDS]
        pos_totals[q] += len(sw)
        pos_counts[q] += sum(1 for w in sw if w in hapax)

    labels = {0: "opening", 1: "early", 2: "center", 3: "late", 4: "closing"}
    pos_density = {labels[q]: round(pos_counts[q] / pos_totals[q], 4) if pos_totals[q] else 0 for q in range(5)}

    return {
        "total_hapax": len(hapax),
        "hapax_ratio": round(hapax_ratio, 4),
        "philosophical_hapax": phil_hapax,
        "positional_density": pos_density,
        "sample": sorted(hapax)[:30],
        "method": "Hapax Legomena Analysis",
        "precedent": "Biblical scholarship; words used once may be deliberate markers",
        "interpretation": "Philosophically loaded hapax at the structural center deserve close attention.",
    }


def detect_voice_shifts(text: str, delimiter_pattern: str = None) -> dict:
    """Detect stylistic shifts between sections (Kierkegaard pseudonym method).

    Precedent: Kierkegaard, Plato's character voices, Nietzsche's multiple registers.
    """
    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s for s in sections if len(s.strip()) > 100]

    HEDGE = {'perhaps', 'maybe', 'possibly', 'seemingly', 'apparently', 'might', 'could'}
    CERTAINTY = {'certainly', 'surely', 'undoubtedly', 'clearly', 'obviously', 'must', 'always', 'never'}
    FIRST_PERSON = {'i', 'me', 'my', 'mine', 'we', 'us', 'our'}
    THIRD_PERSON = {'he', 'she', 'it', 'they', 'him', 'her', 'them', 'his', 'its', 'their'}

    profiles = []
    for i, sec in enumerate(sections):
        words = re.findall(r'\b[a-zA-Z]+\b', sec.lower())
        sents = re.split(r'[.!?]+', sec)
        sents = [s for s in sents if s.strip()]
        if len(words) < 20:
            continue
        sent_lens = [len(re.findall(r'\b\w+\b', s)) for s in sents if s.strip()]
        avg_sent = sum(sent_lens) / len(sent_lens) if sent_lens else 0
        q_density = sec.count('?') / max(len(sents), 1)
        fp_ratio = sum(1 for w in words if w in FIRST_PERSON) / len(words)
        tp_ratio = sum(1 for w in words if w in THIRD_PERSON) / len(words)
        hedge_r = sum(1 for w in words if w in HEDGE) / len(words)
        cert_r = sum(1 for w in words if w in CERTAINTY) / len(words)
        ttr = len(set(words)) / len(words)

        profiles.append({
            "section": i + 1, "avg_sent_len": round(avg_sent, 1),
            "question_density": round(q_density, 3),
            "first_person": round(fp_ratio, 4), "third_person": round(tp_ratio, 4),
            "hedge_ratio": round(hedge_r, 4), "certainty_ratio": round(cert_r, 4),
            "ttr": round(ttr, 4),
        })

    shifts = []
    if len(profiles) >= 3:
        for i in range(1, len(profiles)):
            p, c = profiles[i-1], profiles[i]
            features = ['avg_sent_len', 'question_density', 'first_person', 'hedge_ratio', 'ttr']
            diff = sum(abs(c[f] - p[f]) for f in features)
            if diff > 0.3:
                shifts.append({"from_section": p["section"], "to_section": c["section"],
                               "divergence": round(diff, 3)})

    shifts.sort(key=lambda x: x["divergence"], reverse=True)
    return {
        "total_shifts": len(shifts),
        "shifts": shifts[:15],
        "profiles": profiles[:20],
        "method": "Voice / Persona Consistency",
        "precedent": "Kierkegaard pseudonyms; Plato dialogue characters; Nietzsche multiple voices",
        "interpretation": "Sharp stylistic shifts between sections may indicate the author adopting different personae.",
    }


def detect_register_tiers(text: str, delimiter_pattern: str = None) -> dict:
    """Classify passages into Averroes' three tiers: rhetorical, dialectical, demonstrative.

    Precedent: Averroes (Decisive Treatise) — three levels of audience.
    """
    RHETORICAL = {'imagine', 'picture', 'behold', 'consider', 'story', 'tale', 'once',
                  'beautiful', 'glorious', 'terrible', 'wonderful', 'sacred', 'holy',
                  'blessed', 'wretched', 'magnificent', 'alas', 'o ', 'lo ', 'beloved'}
    DIALECTICAL = {'argument', 'objection', 'reply', 'granted', 'premise', 'conclusion',
                   'follows', 'therefore', 'hence', 'thus', 'consequently', 'reason',
                   'however', 'nevertheless', 'although', 'contrary', 'refute', 'prove'}
    DEMONSTRATIVE = {'necessary', 'sufficient', 'impossible', 'axiom', 'theorem',
                     'definition', 'proposition', 'demonstration', 'quod erat',
                     'evidently', 'self-evident', 'analytic', 'synthetic', 'a priori',
                     'deduction', 'induction', 'syllogism', 'corollary'}

    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s for s in sections if len(s.strip()) > 50]

    classified = []
    transitions = []
    prev_tier = None

    for i, sec in enumerate(sections):
        s_lower = sec.lower()
        r_count = sum(1 for w in RHETORICAL if w in s_lower)
        d_count = sum(1 for w in DIALECTICAL if w in s_lower)
        m_count = sum(1 for w in DEMONSTRATIVE if w in s_lower)
        total = r_count + d_count + m_count
        if total == 0:
            tier = "unclassified"
        elif r_count >= d_count and r_count >= m_count:
            tier = "rhetorical"
        elif d_count >= m_count:
            tier = "dialectical"
        else:
            tier = "demonstrative"

        classified.append({"section": i + 1, "tier": tier,
                           "rhetorical": r_count, "dialectical": d_count, "demonstrative": m_count})

        if prev_tier and tier != prev_tier and tier != "unclassified" and prev_tier != "unclassified":
            transitions.append({"from_section": i, "to_section": i + 1,
                                "from_tier": prev_tier, "to_tier": tier})
        if tier != "unclassified":
            prev_tier = tier

    tier_counts = Counter(c["tier"] for c in classified if c["tier"] != "unclassified")

    return {
        "tier_distribution": dict(tier_counts),
        "transitions": transitions[:20],
        "sections": classified[:30],
        "method": "Three-Tier Register Analysis (Averroes)",
        "precedent": "Averroes Decisive Treatise: rhetorical (masses), dialectical (scholars), demonstrative (philosophers)",
        "interpretation": "Texts mixing tiers may address multiple audiences simultaneously — the esoteric teaching lives in the demonstrative tier.",
    }


def detect_logos_mythos(text: str, delimiter_pattern: str = None) -> dict:
    """Detect shifts between rational argument (logos) and myth/narrative (mythos).

    Precedent: Plato's deliberate shifts from dialectic to myth at critical moments.
    """
    LOGOS = {'therefore', 'it follows', 'we must conclude', 'the argument shows',
             'necessarily', 'logically', 'demonstrably', 'proof', 'evidence',
             'from this we see', 'it is clear that', 'reason demands', 'rationally'}
    MYTHOS = {'once upon', 'there was a', 'the story tells', 'according to the myth',
              'legend has it', 'the tale', 'in ancient times', 'the gods', 'the hero',
              'the oracle', 'the prophecy', 'descended from', 'born of', 'spoke thus',
              'the vision', 'the dream', 'revealed to', 'divine', 'sacred grove'}

    sents = re.split(r'[.!?]+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 20]

    labeled = []
    transitions = []
    prev = None

    for i, sent in enumerate(sents):
        s_lower = sent.lower()
        logos_score = sum(1 for m in LOGOS if m in s_lower)
        mythos_score = sum(1 for m in MYTHOS if m in s_lower)

        if logos_score > mythos_score and logos_score > 0:
            mode = "logos"
        elif mythos_score > logos_score and mythos_score > 0:
            mode = "mythos"
        else:
            mode = "neutral"

        if mode != "neutral":
            labeled.append({"sentence": i + 1, "mode": mode, "excerpt": sent[:100]})
            if prev and prev != mode:
                transitions.append({"at_sentence": i + 1, "from": prev, "to": mode,
                                    "excerpt": sent[:80]})
            prev = mode

    return {
        "logos_count": sum(1 for l in labeled if l["mode"] == "logos"),
        "mythos_count": sum(1 for l in labeled if l["mode"] == "mythos"),
        "transitions": transitions[:20],
        "method": "Logos / Mythos Transition Detection",
        "precedent": "Plato shifts from dialectic to myth at critical moments (Cave, Er, Allegory of the Chariot)",
        "interpretation": "Transitions from logos to mythos at key moments may signal the author packaging dangerous rational conclusions in mythological form.",
    }


def detect_commentary_divergence(text: str, delimiter_pattern: str = None) -> dict:
    """Find passages where the author's commentary diverges from cited views.

    Precedent: Strauss on commentators who 'explain' an author while subtly reframing.
    """
    CITATION_MARKERS = [
        r'(\w+)\s+(?:says|argues|maintains|holds|claims|contends|asserts|believes|suggests|notes)',
        r'according to\s+(\w+)',
        r'as\s+(\w+)\s+(?:puts it|observed|noted|remarked|pointed out)',
        r'in (?:the (?:words|view|opinion) of)\s+(\w+)',
    ]
    DIVERGENCE_MARKERS = {'but', 'however', 'yet', 'nevertheless', 'although', 'though',
                          'in fact', 'actually', 'rather', 'on the contrary', 'in truth',
                          'strictly speaking', 'more precisely', 'one might wonder'}

    sents = re.split(r'[.!?]+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 15]

    findings = []
    for i, sent in enumerate(sents):
        cited_author = None
        for pat in CITATION_MARKERS:
            m = re.search(pat, sent, re.I)
            if m:
                cited_author = m.group(1)
                break
        if not cited_author:
            continue

        # Check next 3 sentences for divergence
        window = ' '.join(sents[i:min(i+4, len(sents))]).lower()
        divergences = [d for d in DIVERGENCE_MARKERS if d in window]
        if divergences:
            findings.append({
                "cited_author": cited_author,
                "sentence": i + 1,
                "divergence_markers": divergences,
                "excerpt": sent[:150],
            })

    return {
        "total_divergences": len(findings),
        "findings": findings[:20],
        "method": "Commentary Divergence Analysis",
        "precedent": "Strauss on commentators who explain while subtly reframing; Al-Farabi on Plato",
        "interpretation": "When an author cites another then immediately diverges, the 'commentary' may be the vehicle for the author's own heterodox view.",
    }


def detect_polysemy(text: str, delimiter_pattern: str = None) -> dict:
    """Find key words used in significantly different contexts (Dante four-levels method).

    Precedent: Dante's four levels of meaning; Maimonides on parables.
    """
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    freq = Counter(words)

    # Focus on moderately frequent content words (3-30 occurrences)
    candidates = {w for w, c in freq.items()
                  if 3 <= c <= 30 and w not in _STOPWORDS and w in _PHILOSOPHICAL_TERMS}

    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s for s in sections if len(s.strip()) > 50]

    polysemous = []
    for word in candidates:
        # Find sections containing this word
        contexts = []
        for i, sec in enumerate(sections):
            if word in sec.lower():
                # Get surrounding words (context)
                sec_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', sec.lower())) - _STOPWORDS - {word}
                contexts.append({"section": i + 1, "context_words": sec_words})

        if len(contexts) < 2:
            continue

        # Check if contexts diverge significantly
        all_pairs_overlap = []
        for a in range(len(contexts)):
            for b in range(a + 1, len(contexts)):
                inter = len(contexts[a]["context_words"] & contexts[b]["context_words"])
                union = len(contexts[a]["context_words"] | contexts[b]["context_words"])
                overlap = inter / union if union else 0
                all_pairs_overlap.append(overlap)

        avg_overlap = sum(all_pairs_overlap) / len(all_pairs_overlap) if all_pairs_overlap else 1
        if avg_overlap < 0.15:  # Very different contexts
            polysemous.append({
                "word": word,
                "occurrences": freq[word],
                "contexts_found": len(contexts),
                "avg_context_overlap": round(avg_overlap, 3),
            })

    polysemous.sort(key=lambda x: x["avg_context_overlap"])

    return {
        "total_polysemous": len(polysemous),
        "words": polysemous[:20],
        "method": "Polysemy Detection (Dante Four-Levels)",
        "precedent": "Dante's four levels (literal, allegorical, moral, anagogical); Maimonides on parables",
        "interpretation": "Key terms used in radically different contexts may carry different meanings at different levels of the text.",
    }


def detect_aphoristic_fragmentation(text: str, delimiter_pattern: str = None) -> dict:
    """Measure textual fragmentation (Nietzsche mask method).

    Precedent: Nietzsche's aphoristic style; Bacon on aphorisms vs method.
    """
    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s.strip() for s in sections if s.strip()]

    # Count short isolated sections (< 3 sentences)
    short_sections = 0
    total_sections = len(sections)
    for sec in sections:
        sents = re.split(r'[.!?]+', sec)
        sents = [s for s in sents if len(s.strip()) > 10]
        if len(sents) <= 2:
            short_sections += 1

    frag_ratio = short_sections / total_sections if total_sections else 0

    # Topic shift detection: compare adjacent sections by word overlap
    topic_shifts = 0
    for i in range(1, len(sections)):
        w_prev = set(re.findall(r'\b[a-zA-Z]{4,}\b', sections[i-1].lower())) - _STOPWORDS
        w_curr = set(re.findall(r'\b[a-zA-Z]{4,}\b', sections[i].lower())) - _STOPWORDS
        union = len(w_prev | w_curr)
        if union == 0:
            continue
        overlap = len(w_prev & w_curr) / union
        if overlap < 0.1:
            topic_shifts += 1

    shift_ratio = topic_shifts / max(total_sections - 1, 1)

    # Non-sequential argument markers
    NON_SEQ = {'incidentally', 'by the way', 'to digress', 'parenthetically',
               'as an aside', 'returning to', 'but first', 'before continuing',
               'to return', 'as i was saying', 'on another note'}
    non_seq_count = sum(1 for m in NON_SEQ if m in text.lower())

    score = min(1.0, frag_ratio * 0.5 + shift_ratio * 0.3 + non_seq_count * 0.05)

    return {
        "total_sections": total_sections,
        "short_sections": short_sections,
        "fragmentation_ratio": round(frag_ratio, 3),
        "topic_shifts": topic_shifts,
        "topic_shift_ratio": round(shift_ratio, 3),
        "non_sequential_markers": non_seq_count,
        "score": round(score, 3),
        "method": "Aphoristic Fragmentation (Nietzsche Mask Method)",
        "precedent": "Nietzsche's aphoristic style; Bacon on aphorisms; the principle that fragmentation forces active reader reconstruction",
        "interpretation": "High fragmentation suggests the author deliberately avoids continuous argument, forcing the reader to reconstruct coherence — a mask that rewards only the careful reader.",
    }


# ─────────────────────────────────────────────────────
# BENARDETE METHODS (from "The Argument of the Action")
# ─────────────────────────────────────────────────────

def detect_trapdoors(text: str, delimiter_pattern: str = None) -> dict:
    """Detect Benardete's 'trapdoors' — local impossibilities that force deeper reading.

    Precedent: Benardete on intentional flaws in the apparent argument.
    """
    sents = re.split(r'[.!?]+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 15]

    ABSOLUTES = {'all', 'every', 'always', 'never', 'none', 'certainly', 'undoubtedly',
                 'obviously', 'clearly', 'must', 'necessarily', 'proven', 'beyond doubt',
                 'no one denies', 'everyone agrees', 'without exception'}
    HEDGES = {'perhaps', 'maybe', 'possibly', 'might', 'could', 'seems', 'appears',
              'apparently', 'arguably', 'not entirely', 'not quite', 'one wonders',
              'however', 'yet', 'but', 'although', 'nevertheless', 'admittedly'}
    CONCLUSION = {'therefore', 'thus', 'hence', 'consequently', 'it follows',
                  'this proves', 'this shows', 'accordingly', 'so we see'}
    NEGATION = {'not', 'no', 'never', 'neither', 'nor', 'nothing', 'deny', 'denies',
                'impossible', 'false', 'untrue'}

    trapdoors = []
    local_contradictions = []
    non_sequiturs = []

    for i, sent in enumerate(sents):
        s_low = sent.lower()
        # Hedge near absolute
        if any(m in s_low for m in ABSOLUTES):
            nearby_hedges = []
            for j in range(max(0, i-3), min(len(sents), i+4)):
                if j == i:
                    continue
                h_found = [h for h in HEDGES if h in sents[j].lower()]
                if h_found:
                    nearby_hedges.append({"sentence": j+1, "hedges": h_found[:3]})
            if nearby_hedges:
                trapdoors.append({"type": "hedge_near_absolute", "sentence": i+1,
                                  "excerpt": sent[:150], "nearby_hedges": nearby_hedges,
                                  "position": round(i / max(len(sents), 1), 3)})

        # Non-sequitur
        if any(m in s_low for m in CONCLUSION) and i >= 2:
            conc_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', s_low)) - _STOPWORDS
            prem_words = set()
            for k in range(max(0, i-3), i):
                prem_words |= set(re.findall(r'\b[a-zA-Z]{4,}\b', sents[k].lower())) - _STOPWORDS
            if len(conc_words & prem_words) < 2:
                non_sequiturs.append({"sentence": i+1, "excerpt": sent[:150],
                                      "position": round(i / max(len(sents), 1), 3)})

    # Local self-contradiction
    for i in range(len(sents) - 2):
        s1_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', sents[i].lower())) - _STOPWORDS
        s1_neg = bool(set(re.findall(r'\b\w+\b', sents[i].lower())) & NEGATION)
        for j in range(i+1, min(i+4, len(sents))):
            s2_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', sents[j].lower())) - _STOPWORDS
            s2_neg = bool(set(re.findall(r'\b\w+\b', sents[j].lower())) & NEGATION)
            if len(s1_words & s2_words) >= 3 and s1_neg != s2_neg:
                local_contradictions.append({
                    "sentence_a": i+1, "sentence_b": j+1,
                    "shared": list(s1_words & s2_words)[:5],
                    "excerpt_a": sents[i][:100], "excerpt_b": sents[j][:100],
                })

    total = len(trapdoors) + len(local_contradictions) + len(non_sequiturs)
    return {
        "total_trapdoors": total,
        "hedge_near_absolute": trapdoors[:15],
        "local_contradictions": local_contradictions[:15],
        "non_sequiturs": non_sequiturs[:10],
        "method": "Trapdoor Detection (Benardete)",
        "precedent": "Benardete: intentional flaws induce the reader to drop beneath the surface",
        "interpretation": "Local impossibilities — hedged absolutes, nearby negation reversals, unsupported conclusions — are deliberately planted to force deeper reading.",
    }


def detect_dyadic_structure(text: str, delimiter_pattern: str = None) -> dict:
    """Detect binary opposition pairs and their convergence (Benardete conjunctive/disjunctive two).

    Precedent: Benardete on myth vs logos, parts parading as wholes, phantom images.
    """
    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s for s in sections if len(s.strip()) > 50]

    OPP_PATTERNS = [
        r'\b(\w{3,})\s+(?:and|or|versus|vs\.?|against)\s+(\w{3,})',
        r'\b(?:between|either)\s+(\w{3,})\s+(?:and|or)\s+(\w{3,})',
    ]
    UNITY_WORDS = {'same', 'one', 'identical', 'united', 'inseparable', 'both',
                   'together', 'turns out', 'proves to be', 'is really', 'whole'}
    EIDETIC = {'whole', 'part', 'parts', 'unity', 'one', 'many', 'same', 'other',
               'being', 'becoming', 'appearance', 'reality', 'surface', 'depth',
               'form', 'matter', 'eidos', 'idea', 'image', 'original', 'copy',
               'shadow', 'reflection', 'dyad', 'monad'}
    PHANTOM = {'phantom', 'image', 'apparition', 'double', 'split', 'divided',
               'mask', 'disguise', 'semblance', 'seeming', 'illusion', 'mirror'}

    pairs = []
    pair_positions = defaultdict(list)
    for i, sec in enumerate(sections):
        for pat in OPP_PATTERNS:
            for m in re.finditer(pat, sec.lower()):
                pair = tuple(sorted([m.group(1), m.group(2)]))
                if pair[0] != pair[1]:
                    pairs.append(pair)
                    pair_positions[pair].append(i)

    pair_counts = Counter(pairs)
    recurring = [(list(p), c) for p, c in pair_counts.items() if c >= 2]
    recurring.sort(key=lambda x: -x[1])

    convergences = []
    for pair, positions in pair_positions.items():
        if len(positions) >= 2:
            for later in positions[1:]:
                if later > positions[0] + 2:
                    if any(w in sections[later].lower() for w in UNITY_WORDS):
                        convergences.append({"pair": list(pair), "first": positions[0]+1,
                                             "convergence": later+1})

    all_words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    eidetic_density = sum(1 for w in all_words if w in EIDETIC) / max(len(all_words), 1)

    phantom_passages = []
    for i, sec in enumerate(sections):
        hits = [w for w in PHANTOM if w in sec.lower()]
        if len(hits) >= 2:
            phantom_passages.append({"section": i+1, "terms": hits, "excerpt": sec[:150]})

    return {
        "total_pairs": len(pairs),
        "recurring_pairs": [{"pair": p, "count": c} for p, c in recurring[:15]],
        "convergences": convergences[:10],
        "eidetic_density": round(eidetic_density, 5),
        "phantom_passages": phantom_passages[:10],
        "method": "Dyadic Structure (Benardete Conjunctive/Disjunctive Two)",
        "precedent": "Benardete: conjunctive two (mythical pairing) vs disjunctive two (necessary relation)",
        "interpretation": "Binary oppositions that later converge signal the philosophical 'turn' from myth to logos.",
    }


def detect_periagoge(text: str, delimiter_pattern: str = None) -> dict:
    """Detect structural reversal between first and second halves (Benardete periagoge).

    Precedent: Platonic periagoge (Cave allegory turning); pathei mathos (Aeschylus).
    """
    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s for s in sections if len(s.strip()) > 30]
    if len(sections) < 4:
        return {"score": 0, "method": "Periagoge Detection", "note": "Text too short"}

    mid = len(sections) // 2
    first_half = ' '.join(sections[:mid])
    second_half = ' '.join(sections[mid:])

    fh_words = re.findall(r'\b[a-zA-Z]{4,}\b', first_half.lower())
    sh_words = re.findall(r'\b[a-zA-Z]{4,}\b', second_half.lower())
    fh_words = [w for w in fh_words if w not in _STOPWORDS]
    sh_words = [w for w in sh_words if w not in _STOPWORDS]

    POSITIVE = {'good', 'true', 'beautiful', 'noble', 'just', 'wise', 'virtue',
                'excellent', 'best', 'perfect', 'divine', 'sacred', 'right', 'worthy'}
    NEGATIVE = {'bad', 'false', 'ugly', 'base', 'unjust', 'foolish', 'vice',
                'terrible', 'worst', 'imperfect', 'corrupt', 'wrong', 'shameful'}

    fh_pos = sum(1 for w in fh_words if w in POSITIVE)
    fh_neg = sum(1 for w in fh_words if w in NEGATIVE)
    sh_pos = sum(1 for w in sh_words if w in POSITIVE)
    sh_neg = sum(1 for w in sh_words if w in NEGATIVE)

    fh_polarity = (fh_pos - fh_neg) / max(fh_pos + fh_neg, 1)
    sh_polarity = (sh_pos - sh_neg) / max(sh_pos + sh_neg, 1)
    polarity_shift = sh_polarity - fh_polarity

    # Vocabulary frequency shifts
    fh_freq = Counter(fh_words)
    sh_freq = Counter(sh_words)
    shifts = []
    for word in set(fh_freq) | set(sh_freq):
        f1 = fh_freq.get(word, 0) / max(len(fh_words), 1)
        f2 = sh_freq.get(word, 0) / max(len(sh_words), 1)
        if max(f1, f2) > 0.0005:
            diff = abs(f2 - f1)
            if diff > 0.001:
                shifts.append({"word": word, "first": round(f1, 5), "second": round(f2, 5),
                               "shift": round(diff, 5), "direction": "increases" if f2 > f1 else "decreases"})
    shifts.sort(key=lambda x: -x["shift"])

    # Turning vocabulary in middle third
    TURNING = {'however', 'yet', 'nevertheless', 'on the contrary', 'in truth', 'in reality',
               'actually', 'in fact', 'turn', 'reverse', 'invert', 'conversion', 'transform',
               'overcome', 'transcend', 'second sailing', 'reconsider', 'on reflection'}
    third = len(sections) // 3
    middle = ' '.join(sections[third:2*third]).lower()
    mid_words = re.findall(r'\b[a-zA-Z]{3,}\b', middle)
    turning_count = sum(1 for w in mid_words if w in TURNING)
    turning_density = turning_count / max(len(mid_words), 1)

    score = min(1.0, abs(polarity_shift) * 0.5 + turning_density * 30 + len(shifts[:10]) * 0.01)

    return {
        "polarity_shift": round(polarity_shift, 3),
        "first_half_polarity": round(fh_polarity, 3),
        "second_half_polarity": round(sh_polarity, 3),
        "vocabulary_shifts": shifts[:20],
        "turning_vocabulary_density": round(turning_density, 5),
        "score": round(score, 3),
        "method": "Periagoge Detection (Benardete Structural Reversal)",
        "precedent": "Benardete: periagoge — the turning reproduced in every Platonic dialogue; pathei mathos",
        "interpretation": "A text that leads to a conclusion in its first half then inverts it in the second reproduces the philosophical 'turning' — the reader must undergo error to understand truth.",
    }


# ─────────────────────────────────────────────────────
# BENARDETE METHODS 21-25
# ─────────────────────────────────────────────────────

def detect_logos_ergon(text: str, delimiter_pattern: str = None) -> dict:
    """Detect speech-deed mismatches (Benardete: argument IN the action)."""
    sections = re.split(delimiter_pattern or r"\n\s*\n", text)
    sections = [s for s in sections if len(s.strip()) > 50]

    SPEECH = {'says', 'said', 'claims', 'argues', 'asserts', 'maintains', 'declares',
              'states', 'contends', 'insists', 'professes', 'teaches', 'proposes',
              'speaks', 'spoke', 'tells', 'told', 'replies', 'answered', 'asks', 'asked',
              'believes', 'thinks', 'holds', 'opinion'}
    ACTION = {'does', 'did', 'goes', 'went', 'acts', 'acted', 'performs', 'makes', 'made',
              'takes', 'took', 'gives', 'gave', 'comes', 'came', 'leaves', 'left', 'turns',
              'turned', 'runs', 'ran', 'sits', 'sat', 'stands', 'stood', 'walks', 'walked',
              'fights', 'fought', 'kills', 'killed', 'strikes', 'seizes', 'flees', 'fled',
              'enters', 'entered', 'departs', 'moves', 'compels'}

    mismatches = []
    burstlike = filamentlike = 0

    for i, sec in enumerate(sections):
        words = re.findall(r'\b[a-zA-Z]+\b', sec.lower())
        if len(words) < 10:
            continue
        s_count = sum(1 for w in words if w in SPEECH)
        a_count = sum(1 for w in words if w in ACTION)
        s_d = s_count / len(words)
        a_d = a_count / len(words)
        if s_d > 0.01 and a_d > 0.01:
            mismatches.append({"section": i+1, "speech": round(s_d, 4),
                               "action": round(a_d, 4), "excerpt": sec[:150]})

    for i in range(1, len(sections)):
        w_prev = set(re.findall(r'\b[a-zA-Z]{4,}\b', sections[i-1].lower())) - _STOPWORDS
        w_curr = set(re.findall(r'\b[a-zA-Z]{4,}\b', sections[i].lower())) - _STOPWORDS
        union = len(w_prev | w_curr)
        if union == 0: continue
        overlap = len(w_prev & w_curr) / union
        if overlap < 0.05: burstlike += 1
        elif overlap < 0.20: filamentlike += 1

    return {
        "mismatch_count": len(mismatches), "mismatches": mismatches[:10],
        "burstlike_shifts": burstlike, "filamentlike_shifts": filamentlike,
        "method": "Logos-Ergon (Speech-Deed) Analysis (Benardete)",
        "precedent": "Benardete: 'I didn't understand there was an argument IN the action'",
        "interpretation": "Speech-action co-occurrence = dramatic irony sites; burstlike shifts = sudden argument breaks.",
    }


def detect_onomastic(text: str, delimiter_pattern: str = None) -> dict:
    """Detect etymological/name-meaning commentary (Benardete on significant names)."""
    NAMING = {'name', 'named', 'names', 'naming', 'called', 'call', 'calls',
              'meaning', 'means', 'signifies', 'designates', 'etymology',
              'derives', 'derived', 'origin', 'cognate', 'root', 'literally',
              'properly', 'so-called', 'translated', 'pun', 'wordplay', 'epithet'}

    sents = re.split(r'[.!?]+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 15]

    proper_nouns = Counter()
    naming_passages = []
    for i, sent in enumerate(sents):
        words = re.findall(r'\b[A-Z][a-z]+\b', sent)
        for w in words[1:]:  # skip first word (sentence start)
            proper_nouns[w] += 1
        s_lower = set(re.findall(r'\b[a-zA-Z]+\b', sent.lower()))
        hits = s_lower & NAMING
        if len(hits) >= 2:
            naming_passages.append({"sentence": i+1, "terms": list(hits), "excerpt": sent[:150]})

    all_words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    naming_density = sum(1 for w in all_words if w in NAMING) / max(len(all_words), 1)

    return {
        "naming_density": round(naming_density, 5),
        "naming_passages": naming_passages[:15],
        "top_proper_nouns": proper_nouns.most_common(20),
        "method": "Onomastic / Etymological Analysis (Benardete)",
        "precedent": "Benardete: Odysseus's two names encode the plot; the outis/metis pun is the key",
        "interpretation": "High naming density = author treats names as philosophically significant (compressed arguments).",
    }


def detect_recognition_structure(text: str, delimiter_pattern: str = None) -> dict:
    """Detect concealment→test→reveal pattern (Benardete on Odyssey structure)."""
    CONCEAL = {'hide', 'hidden', 'conceal', 'concealed', 'concealment', 'disguise', 'disguised',
               'mask', 'masked', 'cover', 'covered', 'secret', 'secretly', 'invisible', 'unseen',
               'unknown', 'anonymous', 'pretend', 'veil', 'veiled', 'obscure', 'suppress', 'withhold'}
    TEST = {'test', 'tested', 'testing', 'trial', 'try', 'tried', 'prove', 'proved', 'proof',
            'examine', 'examined', 'question', 'questioned', 'challenge', 'challenged',
            'verify', 'assess', 'probe', 'scrutinize', 'investigate'}
    REVEAL = {'reveal', 'revealed', 'revelation', 'disclose', 'disclosed', 'discover', 'discovered',
              'discovery', 'recognize', 'recognized', 'recognition', 'unmask', 'unmasked',
              'uncover', 'uncovered', 'expose', 'exposed', 'manifest', 'identity', 'identify'}

    sents = re.split(r'[.!?]+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 10]
    if len(sents) < 9:
        return {"score": 0, "method": "Recognition Structure", "note": "Text too short"}

    third = len(sents) // 3
    thirds = [sents[:third], sents[third:2*third], sents[2*third:]]

    densities = []
    for t in thirds:
        all_w = []
        for s in t:
            all_w.extend(re.findall(r'\b[a-zA-Z]+\b', s.lower()))
        total = max(len(all_w), 1)
        densities.append({
            "concealment": round(sum(1 for w in all_w if w in CONCEAL) / total, 5),
            "testing": round(sum(1 for w in all_w if w in TEST) / total, 5),
            "revelation": round(sum(1 for w in all_w if w in REVEAL) / total, 5),
        })

    ideal = (densities[0]["concealment"] >= densities[2]["concealment"] and
             densities[1]["testing"] >= max(densities[0]["testing"], densities[2]["testing"]) and
             densities[2]["revelation"] >= densities[0]["revelation"])

    return {
        "phase_densities": densities,
        "ideal_pattern": ideal,
        "method": "Recognition Scene / Concealment-Test-Reveal (Benardete)",
        "precedent": "Benardete on Odyssey: identity achieved through narrative, not given",
        "interpretation": "Ideal pattern = concealment early, testing middle, revelation late. The reader enacts discovery.",
    }


def detect_nomos_physis(text: str, delimiter_pattern: str = None) -> dict:
    """Detect convention vs. nature tension (Benardete/Herodotus method)."""
    NOMOS = {'law', 'laws', 'lawful', 'custom', 'customs', 'convention', 'conventional',
             'tradition', 'traditional', 'rule', 'rules', 'opinion', 'opinions', 'belief',
             'beliefs', 'agreed', 'agreement', 'prohibition', 'forbidden', 'permitted',
             'obey', 'obedience', 'shame', 'shameful', 'modesty', 'propriety', 'acceptable'}
    PHYSIS = {'nature', 'natural', 'naturally', 'innate', 'born', 'birth', 'inborn',
              'inherent', 'instinct', 'spontaneous', 'necessary', 'necessity', 'inevitable',
              'compel', 'force', 'power', 'capacity', 'body', 'desire', 'desires',
              'passion', 'appetite', 'species', 'kind', 'genus'}
    COMPARATIVE = {'barbarian', 'foreign', 'foreigner', 'alien', 'stranger', 'compare',
                   'contrast', 'differ', 'different', 'unlike', 'practice', 'practices',
                   'rite', 'ritual', 'worship', 'sacrifice'}

    all_words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    total = max(len(all_words), 1)
    n_count = sum(1 for w in all_words if w in NOMOS)
    p_count = sum(1 for w in all_words if w in PHYSIS)
    c_count = sum(1 for w in all_words if w in COMPARATIVE)

    sents = re.split(r'[.!?]+', text)
    co_occ = []
    for i, sent in enumerate(sents):
        sw = set(re.findall(r'\b[a-zA-Z]+\b', sent.lower()))
        n_hits = sw & NOMOS
        p_hits = sw & PHYSIS
        if n_hits and p_hits:
            co_occ.append({"sentence": i+1, "nomos": list(n_hits)[:3], "physis": list(p_hits)[:3],
                           "excerpt": sent.strip()[:120]})

    return {
        "nomos_density": round(n_count / total, 5), "physis_density": round(p_count / total, 5),
        "comparative_density": round(c_count / total, 5),
        "co_occurrences": co_occ[:15], "co_occurrence_count": len(co_occ),
        "method": "Nomos-Physis (Convention vs. Nature) Detection (Benardete/Herodotus)",
        "precedent": "Benardete: 'To discover the human beneath the infinite disguises of custom'",
        "interpretation": "High co-occurrence of nomos+physis = text grappling with the nature/convention distinction.",
    }


def detect_impossible_arithmetic(text: str, delimiter_pattern: str = None) -> dict:
    """Detect productive impossibilities — one=many, same=different (Benardete poetic dialectic)."""
    IMPOSSIBILITY = {'impossible', 'impossibility', 'cannot', 'absurd', 'absurdity',
                     'paradox', 'paradoxical', 'contradiction', 'contradictory', 'inconceivable',
                     'incompatible', 'incoherent', 'unintelligible', 'ridiculous', 'unthinkable'}
    ARITHMETIC = {'one', 'two', 'three', 'many', 'both', 'neither', 'either', 'same',
                  'different', 'equal', 'unequal', 'identical', 'other', 'single', 'double',
                  'whole', 'part', 'parts', 'unity', 'duality', 'plurality', 'divide',
                  'divided', 'division', 'unite', 'united', 'union', 'separate', 'separated',
                  'combine', 'combined', 'split', 'merge', 'together', 'apart', 'join'}
    AFFIRM = {'yet', 'nevertheless', 'nonetheless', 'still', 'even so', 'but', 'however',
              'though', 'although', 'must', 'proves', 'turns out', 'shows'}

    sents = re.split(r'[.!?]+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 15]

    passages = []
    impossible_yet_true = 0
    for i, sent in enumerate(sents):
        sw = set(re.findall(r'\b[a-zA-Z]+\b', sent.lower()))
        imp = sw & IMPOSSIBILITY
        arith = sw & ARITHMETIC
        if imp and arith:
            passages.append({"sentence": i+1, "impossibility": list(imp),
                             "arithmetic": list(arith), "excerpt": sent[:150]})
        if imp and i + 1 < len(sents):
            next_sw = set(re.findall(r'\b[a-zA-Z]+\b', sents[i+1].lower()))
            if next_sw & AFFIRM:
                impossible_yet_true += 1

    all_words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    total = max(len(all_words), 1)

    return {
        "passages": passages[:15], "passage_count": len(passages),
        "impossible_yet_true": impossible_yet_true,
        "impossibility_density": round(sum(1 for w in all_words if w in IMPOSSIBILITY) / total, 5),
        "arithmetic_density": round(sum(1 for w in all_words if w in ARITHMETIC) / total, 5),
        "method": "Impossible Arithmetic / Poetic Dialectic (Benardete)",
        "precedent": "Benardete: 'The poet divides what is necessarily one and unites what is necessarily two'",
        "interpretation": "Productive impossibilities where one=many reveal the text's 'poetic dialectic' — truth in the guise of the impossible.",
    }


# ─────────────────────────────────────────────────────
# HUMAN-READING TOOLS: Dwell, Confusion, Beauty, Weight
# ─────────────────────────────────────────────────────

def detect_dwell_passages(text: str, delimiter_pattern: str = None) -> dict:
    """Find passages that would make a careful reader slow down and dwell.

    A "dwell passage" has high syntactic complexity + semantic density —
    long sentences, nested clauses, rare vocabulary, abstract terms.
    These are passages the author INTENDED the reader to linger on.
    """
    sents = re.split(r'(?<=[.!?])\s+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 20]

    ABSTRACT = {'being', 'nature', 'truth', 'essence', 'soul', 'reason', 'justice',
                'virtue', 'freedom', 'knowledge', 'wisdom', 'good', 'evil', 'beauty',
                'power', 'law', 'necessity', 'possibility', 'existence', 'substance',
                'cause', 'principle', 'form', 'matter', 'end', 'purpose', 'whole',
                'part', 'opinion', 'science', 'philosophy', 'god', 'divine', 'human'}

    dwell_passages = []
    for i, sent in enumerate(sents):
        words = re.findall(r'\b[a-zA-Z]{3,}\b', sent.lower())
        if len(words) < 8:
            continue

        # Syntactic complexity: sentence length + subordinate clause markers
        subordinates = sum(1 for w in words if w in {'which', 'that', 'whom', 'whose',
                                                       'where', 'when', 'while', 'although',
                                                       'because', 'since', 'unless', 'whereas'})
        clause_density = subordinates / len(words)

        # Semantic density: abstract term concentration
        abstract_count = sum(1 for w in words if w in ABSTRACT)
        abstract_density = abstract_count / len(words)

        # Vocabulary rarity: type-token ratio in this sentence
        ttr = len(set(words)) / len(words)

        # Dwell score: long + complex + abstract + rare vocabulary
        dwell_score = (
            min(len(words) / 40, 1.0) * 0.3 +     # length
            min(clause_density * 10, 1.0) * 0.25 +  # complexity
            min(abstract_density * 10, 1.0) * 0.25 + # abstraction
            min(ttr, 1.0) * 0.2                       # vocabulary richness
        )

        if dwell_score > 0.45:
            dwell_passages.append({
                "sentence": i + 1,
                "score": round(dwell_score, 3),
                "word_count": len(words),
                "clause_density": round(clause_density, 4),
                "abstract_density": round(abstract_density, 4),
                "excerpt": sent[:200],
                "position": round(i / max(len(sents), 1), 3),
            })

    dwell_passages.sort(key=lambda x: -x["score"])
    return {
        "total_dwell_passages": len(dwell_passages),
        "passages": dwell_passages[:20],
        "method": "Dwell Passage Detection",
        "precedent": "Benardete: 'the surface of things is the heart of things' — passages that arrest the reader reward lingering",
        "interpretation": "High-dwell passages combine syntactic complexity with semantic density. The author intended the reader to slow down here.",
    }


def detect_confusion_signals(text: str, delimiter_pattern: str = None) -> dict:
    """Detect deliberately obscure passages — confusion as pedagogical technique.

    Per Strauss: deliberate obscurity is a technique. Per Maimonides:
    'the scattered chapters' method requires the reader to struggle.
    Confusion is not failure — it's the beginning of understanding.
    """
    sents = re.split(r'(?<=[.!?])\s+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 20]

    # Markers of deliberate complexity
    QUALIFICATION_CHAINS = {'not that', 'not so much', 'not merely', 'not simply',
                             'not exactly', 'not quite', 'not entirely', 'not only',
                             'in a sense', 'so to speak', 'as it were', 'to some extent',
                             'in a way', 'in a manner'}
    DOUBLE_NEGATION = {'not un', 'not in', 'not im', 'cannot not', 'not without',
                        'not non', 'hardly un', 'scarcely un', 'no small', 'not a few'}
    SELF_CORRECTION = {'or rather', 'more precisely', 'to put it differently',
                        'that is to say', 'i mean', 'in other words', 'or better',
                        'strictly speaking', 'to be more exact', 'to put it more carefully'}

    confusion_passages = []
    for i, sent in enumerate(sents):
        s_lower = sent.lower()
        quals = sum(1 for q in QUALIFICATION_CHAINS if q in s_lower)
        double_negs = sum(1 for d in DOUBLE_NEGATION if d in s_lower)
        corrections = sum(1 for c in SELF_CORRECTION if c in s_lower)

        # Also check for very long sentences (>50 words) with parentheticals
        words = re.findall(r'\b\w+\b', sent)
        parens = sent.count('(') + sent.count('—')
        semicolons = sent.count(';')

        confusion_score = (
            quals * 0.2 +
            double_negs * 0.3 +
            corrections * 0.25 +
            min(parens * 0.1, 0.3) +
            min(semicolons * 0.1, 0.2) +
            (0.2 if len(words) > 50 else 0)
        )

        if confusion_score > 0.3:
            confusion_passages.append({
                "sentence": i + 1,
                "score": round(confusion_score, 3),
                "qualifications": quals,
                "double_negations": double_negs,
                "self_corrections": corrections,
                "excerpt": sent[:200],
                "position": round(i / max(len(sents), 1), 3),
            })

    confusion_passages.sort(key=lambda x: -x["score"])
    return {
        "total_confusion_signals": len(confusion_passages),
        "passages": confusion_passages[:20],
        "method": "Confusion Signal Detection",
        "precedent": "Maimonides: scattered chapters require struggle; Strauss: deliberate obscurity; Benardete: 'the text resists you where it matters most'",
        "interpretation": "Deliberately confusing passages — chains of qualifications, double negations, self-corrections — signal that the author is handling a dangerous or delicate truth.",
    }


def detect_rhetorical_beauty(text: str, delimiter_pattern: str = None) -> dict:
    """Detect passages of unusual rhetorical force — beauty as a philosophical signal.

    Per Rosen: 'the surface of things is the heart of things.'
    Beautiful prose arrests the reader. In philosophical texts, beauty
    often marks the passage where form and content converge.
    """
    sents = re.split(r'(?<=[.!?])\s+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 30]

    # Parallelism detection: repeated syntactic patterns
    # Anaphora: sentences starting with the same word/phrase
    # Isocolon: clauses of similar length within a sentence
    # Tricolon: three parallel elements

    beauty_passages = []
    for i, sent in enumerate(sents):
        score = 0.0
        features = []

        # Check for tricolon / listing patterns (x, y, and z)
        tricolon = len(re.findall(r',\s*\w+,\s*(?:and|or)\s+\w+', sent))
        if tricolon:
            score += 0.2
            features.append("tricolon")

        # Check for balanced clauses (semicolons separating similar-length phrases)
        if ';' in sent:
            parts = sent.split(';')
            if len(parts) >= 2:
                lengths = [len(p.split()) for p in parts]
                if lengths and max(lengths) < min(lengths) * 2:
                    score += 0.2
                    features.append("isocolon")

        # Check for anaphora with nearby sentences
        if i > 0:
            prev_first = re.match(r'^(\w+\s+\w+)', sents[i-1])
            curr_first = re.match(r'^(\w+\s+\w+)', sent)
            if prev_first and curr_first and prev_first.group(1).lower() == curr_first.group(1).lower():
                score += 0.25
                features.append("anaphora")

        # Chiastic structure within sentence: A B ... B' A'
        words = re.findall(r'\b[a-zA-Z]{4,}\b', sent.lower())
        if len(words) >= 8:
            first_half = words[:len(words)//2]
            second_half = words[len(words)//2:]
            reversed_second = list(reversed(second_half))
            mirror_matches = sum(1 for a, b in zip(first_half[:4], reversed_second[:4]) if a == b)
            if mirror_matches >= 2:
                score += 0.3
                features.append("chiasmus")

        # Rhythmic regularity (low variance in word-per-clause count)
        clauses = re.split(r'[,;:]', sent)
        if len(clauses) >= 3:
            clause_lens = [len(c.split()) for c in clauses if c.strip()]
            if clause_lens:
                avg = sum(clause_lens) / len(clause_lens)
                variance = sum((l - avg) ** 2 for l in clause_lens) / len(clause_lens)
                if variance < 4 and avg > 3:
                    score += 0.15
                    features.append("rhythmic")

        # Aphoristic brevity + depth (short sentence with abstract terms)
        abstract = {'truth', 'nature', 'soul', 'beauty', 'justice', 'wisdom', 'good',
                    'evil', 'freedom', 'love', 'death', 'god', 'being', 'nothing'}
        if len(words) < 15 and sum(1 for w in words if w in abstract) >= 2:
            score += 0.25
            features.append("aphoristic")

        if score > 0.3:
            beauty_passages.append({
                "sentence": i + 1,
                "score": round(score, 3),
                "features": features,
                "excerpt": sent[:200],
                "position": round(i / max(len(sents), 1), 3),
            })

    beauty_passages.sort(key=lambda x: -x["score"])
    return {
        "total_beauty_passages": len(beauty_passages),
        "passages": beauty_passages[:20],
        "method": "Rhetorical Beauty Detection",
        "precedent": "Rosen: 'the surface of things is the heart of things'; Benardete on the inseparability of form and content in Plato",
        "interpretation": "Passages of unusual rhetorical beauty — parallelism, chiasmus, aphoristic density — mark moments where form and content converge. The beauty IS the argument.",
    }


def detect_word_weight(text: str, delimiter_pattern: str = None) -> dict:
    """Measure the philosophical 'weight' of individual words across the text.

    Weight = rarity × structural centrality × emphasis markers.
    Heavy words are the ones the author chose with greatest care.
    """
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    freq = Counter(words)
    total = len(words)

    # Positional weight: words at the center carry more weight
    sents = re.split(r'(?<=[.!?])\s+', text)
    n_sents = len(sents)
    word_positions = defaultdict(list)
    for i, sent in enumerate(sents):
        for w in re.findall(r'\b[a-zA-Z]{4,}\b', sent.lower()):
            word_positions[w].append(i / max(n_sents, 1))

    # Emphasis: words that appear in scare quotes or near emphasis markers
    emphasized = set()
    for m in re.finditer(r'"([^"]{3,30})"', text):
        for w in re.findall(r'\b[a-zA-Z]{4,}\b', m.group(1).lower()):
            emphasized.add(w)
    for m in re.finditer(r'\*([^*]{3,30})\*', text):
        for w in re.findall(r'\b[a-zA-Z]{4,}\b', m.group(1).lower()):
            emphasized.add(w)

    # Calculate weight
    weighted = []
    for word, count in freq.items():
        if word in _STOPWORDS or count < 2:
            continue

        # Rarity: inverse frequency (rare = heavy)
        rarity = 1.0 / (count / total * 1000 + 1)

        # Centrality: how concentrated near the structural center (0.4-0.6)
        positions = word_positions.get(word, [])
        center_positions = [p for p in positions if 0.35 <= p <= 0.65]
        centrality = len(center_positions) / max(len(positions), 1)

        # Emphasis bonus
        emph_bonus = 0.3 if word in emphasized else 0.0

        weight = rarity * 0.4 + centrality * 0.3 + emph_bonus + (0.2 if count <= 5 else 0.0)

        if weight > 0.3:
            weighted.append({
                "word": word,
                "weight": round(weight, 3),
                "occurrences": count,
                "rarity": round(rarity, 3),
                "centrality": round(centrality, 3),
                "emphasized": word in emphasized,
            })

    weighted.sort(key=lambda x: -x["weight"])
    return {
        "total_heavy_words": len(weighted),
        "words": weighted[:30],
        "method": "Word Weight Analysis",
        "precedent": "Benardete: every word choice in Plato is philosophically significant; Strauss: the rare statement is the true one",
        "interpretation": "Heavy words — rare, centrally placed, emphasized — are the ones the author chose with greatest care. They carry the argument's weight.",
    }


# ─────────────────────────────────────────────────────
# ROSEN METHODS + SYMPOSIUM METHODS (26-42)
# ─────────────────────────────────────────────────────

def detect_rhetoric_of_concealment(text: str, delimiter_pattern: str = None) -> dict:
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
    for para in re.split(delimiter_pattern or r'\n\s*\n', text):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
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



def detect_transcendental_ambiguity(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    ambig_density = sum(1 for w in all_words if w in ambiguity_markers) / total
    resist_density = sum(1 for w in all_words if w in resistance_vocab) / total
    multi_density = sum(1 for w in all_words if w in multi_sense) / total

    score = min(1.0, (
        ambig_density * 35 + resist_density * 30 + multi_density * 20 +
        len(ambig_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 15
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



def detect_rhetoric_of_frankness(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
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



def detect_intuition_analysis_dialectic(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    int_density = sum(1 for w in all_words if w in intuition_vocab) / total
    lim_density = sum(1 for w in all_words if w in analysis_limit) / total
    refl_density = sum(1 for w in all_words if w in reflexive) / total

    score = min(1.0, (
        int_density * 25 + lim_density * 30 + refl_density * 35 +
        len(int_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 10
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



def detect_logographic_necessity(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    const_density = sum(1 for w in all_words if w in constraint_vocab) / total
    form_density = sum(1 for w in all_words if w in form_content) / total
    narr_density = sum(1 for w in all_words if w in narrative_vocab) / total

    score = min(1.0, (
        const_density * 25 + form_density * 35 + narr_density * 20 +
        len(logo_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 20
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



def detect_theological_disavowal(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
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



def detect_defensive_writing(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
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



def detect_nature_freedom_oscillation(text: str, delimiter_pattern: str = None) -> dict:
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

    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
        nat_count = len(para_words & nature_vocab)
        free_count = len(para_words & freedom_vocab)

        if nat_count > free_count and nat_count > 0:
            nature_paras.append(i)
        elif free_count > nat_count and free_count > 0:
            freedom_paras.append(i)

    # Count alternations
    for i in range(len(re.split(delimiter_pattern or r'\n\s*\n', text)) - 1):
        para_i = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', re.split(delimiter_pattern or r'\n\s*\n', text)[i]) if w.isalpha())
        para_next = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', re.split(delimiter_pattern or r'\n\s*\n', text)[i+1]) if w.isalpha())
        nat_i = len(para_i & nature_vocab)
        free_i = len(para_i & freedom_vocab)
        nat_next = len(para_next & nature_vocab)
        free_next = len(para_next & freedom_vocab)

        if (nat_i > free_i and free_next > nat_next) or (free_i > nat_i and nat_next > free_next):
            oscillations += 1

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    nat_density = sum(1 for w in all_words if w in nature_vocab) / total
    free_density = sum(1 for w in all_words if w in freedom_vocab) / total
    switch_frequency = oscillations / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)) - 1, 1)

    # Detect explicit tension acknowledgments
    tension_detected = False
    for sent in re.split(r'[.!?]+', text):
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



def detect_postmodern_misreading(text: str, delimiter_pattern: str = None) -> dict:
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

    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    n = max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1)

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



def detect_dramatic_context(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    speaker_density = sum(1 for w in all_words if w in speaker_vocab) / total
    setting_density = sum(1 for w in all_words if w in setting_vocab) / total
    persona_density = sum(1 for w in all_words if w in persona_vocab) / total

    # Attribution patterns (quoted speech markers)
    attribution_patterns = sum(1 for para in re.split(delimiter_pattern or r'\n\s*\n', text) if 'said' in para.lower() or '"' in para)
    attribution_density = attribution_patterns / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1)

    score = min(1.0, (
        speaker_density * 25 + setting_density * 25 + persona_density * 20 +
        attribution_density * 15 + len(dramatic_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 15
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



def detect_speech_sequencing(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    ordinal_density = sum(1 for w in all_words if w in ordinal_vocab) / total
    response_density = sum(1 for w in all_words if w in response_vocab) / total
    progression_density = sum(1 for w in all_words if w in progression_vocab) / total

    score = min(1.0, (
        ordinal_density * 20 + response_density * 30 + progression_density * 25 +
        len(sequential_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 25
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



def detect_philosophical_comedy(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    comic_density = sum(1 for w in all_words if w in comic_vocab) / total
    serious_density = sum(1 for w in all_words if w in serious_vocab) / total
    juxtaposition_density = sum(1 for w in all_words if w in juxtaposition_vocab) / total

    score = min(1.0, (
        comic_density * 20 + serious_density * 25 + juxtaposition_density * 20 +
        len(comic_philosophy_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 35
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



def detect_daimonic_mediation(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    mediation_density = sum(1 for w in all_words if w in mediation_vocab) / total
    boundary_density = sum(1 for w in all_words if w in boundary_vocab) / total
    transformation_density = sum(1 for w in all_words if w in transformation_vocab) / total

    score = min(1.0, (
        mediation_density * 30 + boundary_density * 25 + transformation_density * 25 +
        len(daimonic_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 20
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



def detect_medicinal_rhetoric(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    medical_density = sum(1 for w in all_words if w in medical_vocab) / total
    pedagogical_density = sum(1 for w in all_words if w in pedagogical_vocab) / total
    soul_density = sum(1 for w in all_words if w in soul_vocab) / total

    score = min(1.0, (
        medical_density * 25 + pedagogical_density * 30 + soul_density * 25 +
        len(medicinal_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 20
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



def detect_poetry_philosophy_dialectic(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    poetry_density = sum(1 for w in all_words if w in poetry_vocab) / total
    philosophy_density = sum(1 for w in all_words if w in philosophy_vocab) / total
    quarrel_density = sum(1 for w in all_words if w in quarrel_vocab) / total

    score = min(1.0, (
        poetry_density * 25 + philosophy_density * 25 + quarrel_density * 25 +
        len(dialectic_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 25
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



def detect_aspiration_achievement_gap(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
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



def detect_synoptic_requirement(text: str, delimiter_pattern: str = None) -> dict:
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
    for i, para in enumerate(re.split(delimiter_pattern or r'\n\s*\n', text)):
        para_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', para) if w.isalpha())
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

    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()) if w.isalpha()]
    total = max(len(all_words), 1)
    cross_reference_density = sum(1 for w in all_words if w in cross_reference_vocab) / total
    intertextual_density = sum(1 for w in all_words if w in intertextual_vocab) / total
    incompleteness_density = sum(1 for w in all_words if w in incompleteness_vocab) / total

    score = min(1.0, (
        cross_reference_density * 30 + intertextual_density * 25 + incompleteness_density * 25 +
        len(synoptic_passages) / max(len(re.split(delimiter_pattern or r'\n\s*\n', text)), 1) * 20
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



