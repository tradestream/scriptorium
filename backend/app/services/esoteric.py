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
    """
    if delimiter_pattern:
        pattern = delimiter_pattern
    else:
        # Try common delimiters in order of specificity
        patterns = [
            r'(?i)^(book\s+\w+)',           # Book I, Book 1, BOOK ONE
            r'(?i)^(chapter\s+\w+)',         # Chapter 1, Chapter One
            r'(?i)^(canto\s+\w+)',           # Canto I
            r'(?i)^(part\s+\w+)',            # Part 1, Part One
            r'(?i)^(act\s+\w+)',             # Act I (plays)
            r'(?i)^(section\s+\w+)',         # Section 1
        ]

        pattern = None
        for p in patterns:
            if re.search(p, text, re.MULTILINE):
                pattern = p
                break

    if pattern:
        # Split by the detected pattern
        splits = re.split(f'({pattern})', text, flags=re.MULTILINE)
        sections = []
        idx = 0
        i = 1  # Skip preamble (splits[0])
        while i < len(splits) - 1:
            label = splits[i].strip()
            content = splits[i + 1] if i + 1 < len(splits) else ""
            sections.append(SectionText(label=label, text=content.strip(), index=idx))
            idx += 1
            i += 2
        return sections if sections else [SectionText(label="Full Text", text=text, index=0)]

    # Fallback: split into roughly equal chunks
    lines = text.split('\n')
    chunk_size = max(50, len(lines) // 10)
    sections = []
    for i in range(0, len(lines), chunk_size):
        chunk = '\n'.join(lines[i:i + chunk_size])
        sections.append(SectionText(
            label=f"Section {len(sections) + 1}",
            text=chunk,
            index=len(sections),
        ))
    return sections


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
DEFAULT_PIOUS_WORDS = {
    "god", "gods", "divine", "sacred", "holy", "pious", "prayer", "sacrifice",
    "temple", "altar", "fate", "destiny", "heaven", "olympus", "blessed",
    "reverent", "worship", "offering", "obey", "obedience", "duty",
    "righteous", "orthodox", "tradition", "custom", "law", "order",
    "authority", "king", "throne", "honor", "glory", "noble",
}

DEFAULT_SUBVERSIVE_WORDS = {
    "clever", "cunning", "trick", "deceive", "lie", "false", "disguise",
    "hidden", "secret", "know", "knowledge", "wisdom", "question",
    "doubt", "challenge", "rebel", "defy", "escape", "freedom",
    "reason", "think", "mind", "nature", "truth", "real", "actual",
    "appear", "seem", "surface", "mask", "pretend", "craft", "skill",
    "self", "choose", "will", "power", "mortal", "human",
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
# Orchestrator: Run all tools
# ─────────────────────────────────────────────────────

@dataclass
class EsotericAnalysisConfig:
    """Configuration for running esoteric computational analysis."""
    keywords: list[str] = field(default_factory=lambda: [
        "justice", "truth", "god", "gods", "fate", "piety", "wisdom",
        "nature", "law", "virtue", "death", "freedom",
    ])
    entities: list[str] = field(default_factory=lambda: [])
    pious_words: Optional[set[str]] = None
    subversive_words: Optional[set[str]] = None
    delimiter_pattern: Optional[str] = None
    silence_threshold: float = 0.2
    context_window: int = 150
    center_window_lines: int = 25


def run_full_esoteric_analysis(
    text: str,
    config: Optional[EsotericAnalysisConfig] = None,
) -> dict:
    """Run all four computational esoteric analysis tools and return combined results."""
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

    return results
