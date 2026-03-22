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
# Tool 8: First/Last Word Extractor (Notarikon)
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
    """Run all eleven computational esoteric analysis tools and return combined results."""
    if config is None:
        config = EsotericAnalysisConfig()

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

    # 8. First/Last Word Extraction
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

    return results
