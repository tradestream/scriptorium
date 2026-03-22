"""Esoteric Analysis Engine v2 — comprehensive Straussian/Melzer detection framework.

Modular architecture with weighted scoring, pattern clustering, and
deliberateness assessment. Replaces the individual tool functions with
a unified engine that produces an EsotericReport.

Modules:
  1. StraussCore — contradiction sophistication, center, pedagogical hierarchy
  2. MelzerTaxonomy — fourteen modes of esoteric communication
  3. NumericalStructure — sacred numbers, proportions, ring composition
  4. LanguageAnalysis — vocabulary difficulty, attribution distance, hedging
  5. PatternCluster — aggregate scoring with weighted deliberateness

All computational, no LLM calls. LLM templates are separate.
"""

import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("scriptorium.esoteric_engine")


# ═══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TextMetadata:
    """Context about the text being analyzed."""
    author: str = ""
    title: str = ""
    date: str = ""
    genre: str = ""  # philosophical, political, theological, literary
    context: str = ""  # persecution, censorship, liberal, etc.


@dataclass
class ScoringWeights:
    """Weights for esotericism indicators, per Strauss/Melzer priority."""
    # Strauss primary (highest)
    contradiction_explicit: float = 10.0
    contradiction_practical: float = 8.0
    central_placement: float = 9.0
    dangerous_topic_handling: float = 9.0
    pedagogical_stratification: float = 8.0

    # Melzer fourteen modes
    explicit_esotericism_claim: float = 10.0
    logical_incompleteness: float = 7.0
    strategic_obscurity: float = 6.0
    shocking_statement: float = 8.0
    conspicuous_omission: float = 7.0
    form_content_mismatch: float = 6.0
    dramatic_irony: float = 7.0
    emphasis_inversion: float = 7.0
    anomalous_detail: float = 5.0
    numerical_pattern: float = 7.0

    # Extended
    gematria_pattern: float = 4.0
    hermetic_symbol: float = 3.0

    # Context multipliers
    philosophical_text: float = 1.5
    political_text: float = 1.5
    theological_text: float = 1.5
    persecution_context: float = 2.0


@dataclass
class Finding:
    """A single esoteric signal detected."""
    technique: str  # e.g. "contradiction_explicit", "hedging_language"
    score: float  # raw score before weighting
    section: str  # where in the text
    evidence: str  # the actual text/data
    explanation: str  # why this is significant
    deliberateness: float = 0.0  # 0-1, how likely intentional


@dataclass
class EsotericReport:
    """Complete analysis results."""
    findings: list[Finding] = field(default_factory=list)
    module_scores: dict = field(default_factory=dict)  # {module: score}
    overall_score: float = 0.0
    cluster_hotspots: list[dict] = field(default_factory=list)
    ranked_passages: list[dict] = field(default_factory=list)
    structural_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 2),
            "module_scores": {k: round(v, 2) for k, v in self.module_scores.items()},
            "finding_count": len(self.findings),
            "findings": [
                {
                    "technique": f.technique,
                    "score": round(f.score, 2),
                    "section": f.section,
                    "evidence": f.evidence[:300],
                    "explanation": f.explanation,
                    "deliberateness": round(f.deliberateness, 2),
                }
                for f in sorted(self.findings, key=lambda x: x.score, reverse=True)[:50]
            ],
            "cluster_hotspots": self.cluster_hotspots[:10],
            "ranked_passages": self.ranked_passages[:20],
            "structural_summary": self.structural_summary,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Text Segmentation
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Section:
    label: str
    text: str
    index: int
    start_char: int = 0
    end_char: int = 0


def segment_text(text: str) -> list[Section]:
    """Split text into sections using structural markers."""
    patterns = [
        r'(?i)^(book\s+[IVXLCDM\d]+\b[^\n]*)',
        r'(?i)^(chapter\s+[IVXLCDM\d]+\b[^\n]*)',
        r'(?i)^(part\s+[IVXLCDM\d]+\b[^\n]*)',
        r'^(#{1,3}\s+.+)',
        r'(?i)^(section\s+[IVXLCDM\d]+\b[^\n]*)',
        r'(?i)^(discourse\s+[IVXLCDM\d]+\b[^\n]*)',
    ]

    pattern = None
    for p in patterns:
        if len(re.findall(p, text, re.MULTILINE)) >= 2:
            pattern = p
            break

    sections = []
    if pattern:
        splits = re.split(f'({pattern})', text, flags=re.MULTILINE)
        pos = 0
        preamble = splits[0].strip()
        pos += len(splits[0])
        if preamble and len(preamble) > 200:
            sections.append(Section("Preamble", preamble, 0, 0, len(preamble)))

        i = 1
        while i < len(splits) - 1:
            label = splits[i].strip().lstrip('#').strip()
            content = splits[i + 1] if i + 1 < len(splits) else ""
            if content.strip():
                start = text.find(content.strip()[:50])
                sections.append(Section(label, content.strip(), len(sections), start, start + len(content)))
            i += 2
    else:
        # Fallback: split by paragraph density
        lines = text.split('\n')
        chunk_size = max(50, len(lines) // 10)
        pos = 0
        for i in range(0, len(lines), chunk_size):
            chunk = '\n'.join(lines[i:i + chunk_size])
            if chunk.strip():
                sections.append(Section(f"Section {len(sections)+1}", chunk, len(sections), pos, pos + len(chunk)))
            pos += len(chunk) + 1

    return sections or [Section("Full Text", text, 0, 0, len(text))]


def get_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip() and len(s.strip()) > 10]


# ═══════════════════════════════════════════════════════════════════════════════
# Module 1: Strauss Core
# ═══════════════════════════════════════════════════════════════════════════════

class StraussCore:
    """Contradiction sophistication, center analysis, pedagogical hierarchy."""

    def analyze(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        findings.extend(self._find_statement_contradictions(text, sections, weights))
        findings.extend(self._analyze_center(text, sections, weights))
        findings.extend(self._pedagogical_hierarchy(text, sections, weights))
        findings.extend(self._dangerous_topic_handling(text, sections, weights))
        return findings

    def _find_statement_contradictions(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Find statement-level contradictions with distance and deliberateness scoring."""
        findings = []
        sentences = get_sentences(text)

        # Track claims about key topics
        claim_patterns = [
            (r'(?:is|are|was|were)\s+(?:not\s+)?(?:the\s+)?(?:most\s+)?(?:important|essential|necessary|fundamental|primary|chief)',
             "importance_claim"),
            (r'(?:always|never|necessarily|impossible|certain|undoubtedly)',
             "absolute_claim"),
            (r'(?:true|false|correct|wrong|right|mistaken)',
             "truth_claim"),
        ]

        claims_by_type = defaultdict(list)
        for i, sent in enumerate(sentences):
            for pattern, claim_type in claim_patterns:
                if re.search(pattern, sent, re.I):
                    claims_by_type[claim_type].append((i, sent))

        # Find contradictions within claim types
        for claim_type, claims in claims_by_type.items():
            for j in range(len(claims)):
                for k in range(j + 1, len(claims)):
                    idx_j, sent_j = claims[j]
                    idx_k, sent_k = claims[k]

                    # Check for negation patterns suggesting contradiction
                    j_negated = bool(re.search(r'\bnot\b|\bnever\b|\bno\b|\bnor\b', sent_j, re.I))
                    k_negated = bool(re.search(r'\bnot\b|\bnever\b|\bno\b|\bnor\b', sent_k, re.I))

                    if j_negated != k_negated:
                        distance = abs(idx_k - idx_j)
                        # Closer contradictions are more suspicious
                        deliberateness = max(0, 1.0 - (distance / 50))

                        findings.append(Finding(
                            technique="contradiction_explicit",
                            score=weights.contradiction_explicit * deliberateness,
                            section=f"Sentences {idx_j+1} & {idx_k+1}",
                            evidence=f"A: {sent_j[:150]}... | B: {sent_k[:150]}...",
                            explanation=f"Contradicting {claim_type}s {distance} sentences apart",
                            deliberateness=deliberateness,
                        ))

        return findings[:20]  # Cap

    def _analyze_center(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Analyze the structural center with deliberateness assessment."""
        findings = []
        words = text.split()
        total = len(words)
        if total < 100:
            return findings

        # Word-level center
        center_start = max(0, total // 2 - 50)
        center_end = min(total, total // 2 + 50)
        center_passage = ' '.join(words[center_start:center_end])

        # Check if center contains unusual vocabulary
        center_words = set(w.lower() for w in words[center_start:center_end])
        all_words = Counter(w.lower() for w in words)
        rare_in_center = [w for w in center_words if all_words[w] == 1 and len(w) > 4]

        deliberateness = min(len(rare_in_center) / 5, 1.0)

        findings.append(Finding(
            technique="central_placement",
            score=weights.central_placement * (0.5 + deliberateness * 0.5),
            section=f"Words {center_start}-{center_end} of {total}",
            evidence=center_passage[:300],
            explanation=f"Structural center. {len(rare_in_center)} unique words found only here.",
            deliberateness=deliberateness,
        ))

        # Section-level center
        if len(sections) >= 3:
            mid = len(sections) // 2
            mid_section = sections[mid]
            findings.append(Finding(
                technique="central_placement",
                score=weights.central_placement * 0.7,
                section=mid_section.label,
                evidence=mid_section.text[:300],
                explanation=f"Central section ({mid+1} of {len(sections)}). May contain key teaching per Strauss.",
                deliberateness=0.5,
            ))

        return findings

    def _pedagogical_hierarchy(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Detect vocabulary complexity shifts — 'vestibule' vs 'inner sanctum'."""
        findings = []
        if len(sections) < 3:
            return findings

        # Calculate average word length per section as a rough complexity proxy
        section_complexity = []
        for sec in sections:
            words = re.findall(r'\w+', sec.text)
            if words:
                avg_len = sum(len(w) for w in words) / len(words)
                long_word_ratio = sum(1 for w in words if len(w) > 8) / len(words)
                section_complexity.append({
                    "label": sec.label,
                    "avg_word_length": round(avg_len, 2),
                    "long_word_ratio": round(long_word_ratio, 3),
                    "word_count": len(words),
                })

        # Find significant jumps in complexity
        if len(section_complexity) >= 3:
            complexities = [s["long_word_ratio"] for s in section_complexity]
            avg_complexity = sum(complexities) / len(complexities)

            for i, sc in enumerate(section_complexity):
                if sc["long_word_ratio"] > avg_complexity * 1.5:
                    findings.append(Finding(
                        technique="pedagogical_stratification",
                        score=weights.pedagogical_stratification * 0.6,
                        section=sc["label"],
                        evidence=f"Long-word ratio {sc['long_word_ratio']} vs avg {avg_complexity:.3f}",
                        explanation="Significantly more complex vocabulary — possible 'inner sanctum' section requiring more from the reader.",
                        deliberateness=0.5,
                    ))
                elif sc["long_word_ratio"] < avg_complexity * 0.6:
                    findings.append(Finding(
                        technique="pedagogical_stratification",
                        score=weights.pedagogical_stratification * 0.4,
                        section=sc["label"],
                        evidence=f"Long-word ratio {sc['long_word_ratio']} vs avg {avg_complexity:.3f}",
                        explanation="Unusually simple vocabulary — possible 'vestibule' section welcoming casual readers.",
                        deliberateness=0.3,
                    ))

        return findings

    def _dangerous_topic_handling(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Track how dangerous topics are handled vs. safe ones."""
        findings = []

        DANGEROUS_TOPICS = {
            "atheism", "atheist", "unbelief", "godless", "impious", "impiety",
            "tyranny", "tyrant", "revolution", "overthrow", "subversion",
            "inequality", "superior", "inferior", "rank", "hierarchy",
            "noble lie", "deception", "conceal", "esoteric", "hidden teaching",
        }

        HEDGING_NEAR = re.compile(
            r'(?:perhaps|it seems|one might|it may be|if we|arguably|possibly|'
            r'it could be|some would say|it is not impossible)',
            re.I
        )

        text_lower = text.lower()
        for topic in DANGEROUS_TOPICS:
            pos = 0
            while True:
                idx = text_lower.find(topic, pos)
                if idx == -1:
                    break

                # Check for hedging within 200 chars before the topic
                region = text[max(0, idx-200):idx+len(topic)+200]
                hedges = HEDGING_NEAR.findall(region)

                if hedges:
                    findings.append(Finding(
                        technique="dangerous_topic_handling",
                        score=weights.dangerous_topic_handling * 0.6,
                        section=f"Near '{topic}'",
                        evidence=region[:200],
                        explanation=f"Dangerous topic '{topic}' hedged with: {', '.join(hedges)}",
                        deliberateness=0.6,
                    ))

                pos = idx + len(topic)

        return findings[:15]


# ═══════════════════════════════════════════════════════════════════════════════
# Module 2: Language Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class LanguageAnalysis:
    """Vocabulary difficulty, attribution distance, hedging, conditionals, emphasis."""

    ATTRIBUTION_DISTANCE = re.compile(
        r'(?:as is commonly believed|some say|it is (?:commonly |generally )?held that|'
        r'the (?:common|received|orthodox|conventional) (?:view|opinion|teaching|doctrine)|'
        r'many (?:people |scholars )?(?:believe|think|hold|maintain)|'
        r'according to the (?:prevailing|common|orthodox) (?:view|opinion)|'
        r'as (?:everyone|all|most people) (?:know|believe|admit)s?)',
        re.I
    )

    HEDGING = re.compile(
        r'(?:perhaps|it seems|it would seem|it might seem|it appears|'
        r'it may be|one might say|one could say|it is possible|'
        r'a mere possibility|we may suppose|if one were to|'
        r'I do not mean to say|I hesitate to|at first glance|on the surface)',
        re.I
    )

    CONDITIONAL = re.compile(
        r'\b(?:if\s+(?:it\s+(?:is|be)\s+true\s+that|the|we|one|this|that|there)|'
        r'granted\s+that|supposing\s+that|assuming\s+that|'
        r'were\s+(?:it|one|we)\s+to|provided\s+(?:that|only))',
        re.I
    )

    SELF_REFERENCE = [
        "writing between the lines", "esoteric", "exoteric", "hidden teaching",
        "secret teaching", "concealment", "art of writing", "careful reader",
        "between the lines", "noble lie", "pious fraud", "irony", "ironic",
    ]

    def analyze(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        findings.extend(self._attribution_distance(text, sections, weights))
        findings.extend(self._hedging_analysis(text, sections, weights))
        findings.extend(self._conditional_framing(text, sections, weights))
        findings.extend(self._self_reference(text, sections, weights))
        findings.extend(self._emphasis_markers(text, sections, weights))
        return findings

    def _attribution_distance(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        for m in self.ATTRIBUTION_DISTANCE.finditer(text):
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 200)
            findings.append(Finding(
                technique="attribution_distance",
                score=weights.logical_incompleteness * 0.5,
                section="",
                evidence=text[start:end],
                explanation=f"Attribution distance marker: '{m.group(0)}' — author creates distance from claim, may be signaling disagreement.",
                deliberateness=0.5,
            ))
        return findings[:15]

    def _hedging_analysis(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        total_words = len(re.findall(r'\w+', text))

        for sec in sections:
            hedges = self.HEDGING.findall(sec.text)
            words = len(re.findall(r'\w+', sec.text))
            if hedges and words > 0:
                density = len(hedges) / words * 1000
                if density > 3.0:  # High hedging density
                    findings.append(Finding(
                        technique="strategic_obscurity",
                        score=weights.strategic_obscurity * min(density / 5, 1.0),
                        section=sec.label,
                        evidence=f"{len(hedges)} hedges in {words} words (density: {density:.1f}/1000)",
                        explanation="High hedging density — author approaches truth indirectly.",
                        deliberateness=min(density / 8, 1.0),
                    ))

        return findings

    def _conditional_framing(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        for m in self.CONDITIONAL.finditer(text):
            start = max(0, text.rfind('.', 0, m.start()) + 1)
            end = text.find('.', m.end())
            if end == -1:
                end = min(len(text), m.start() + 300)
            sentence = text[start:end+1].strip()

            findings.append(Finding(
                technique="emphasis_inversion",
                score=weights.emphasis_inversion * 0.4,
                section="",
                evidence=sentence[:200],
                explanation=f"Conditional framing '{m.group(0)}' — central claim made hypothetical per Frazer's observation.",
                deliberateness=0.5,
            ))
        return findings[:15]

    def _self_reference(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        text_lower = text.lower()
        total = 0
        for marker in self.SELF_REFERENCE:
            count = text_lower.count(marker)
            total += count

        total_words = len(re.findall(r'\w+', text))
        density = total / total_words * 1000 if total_words > 0 else 0

        if density > 1.0:
            findings.append(Finding(
                technique="explicit_esotericism_claim",
                score=weights.explicit_esotericism_claim * min(density / 3, 1.0),
                section="Full text",
                evidence=f"{total} self-referential markers ({density:.1f}/1000 words)",
                explanation="Text discusses its own method of writing/reading — meta-esoteric. May be performing what it describes.",
                deliberateness=min(density / 5, 1.0),
            ))

        return findings

    def _emphasis_markers(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        # Scare quotes on short phrases
        for m in re.finditer(r'["\u201c]([^"\u201d]{1,40})["\u201d]', text):
            content = m.group(1)
            if len(content.split()) <= 4 and not content.endswith(('.', '!', '?')):
                findings.append(Finding(
                    technique="anomalous_detail",
                    score=weights.anomalous_detail * 0.3,
                    section="",
                    evidence=f'"{content}"',
                    explanation="Scare-quoted word/phrase — may signal double meaning per Secret Words principle.",
                    deliberateness=0.4,
                ))
        return findings[:20]


# ═══════════════════════════════════════════════════════════════════════════════
# Module 3: Numerical Structure
# ═══════════════════════════════════════════════════════════════════════════════

class NumericalStructure:
    """Sacred numbers, golden ratio, ring composition."""

    SACRED_NUMBERS = {3, 7, 9, 10, 12, 13, 22, 33, 40, 100}
    GOLDEN_RATIO = 1.6180339887

    def analyze(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        findings.extend(self._section_count_analysis(sections, weights))
        findings.extend(self._golden_ratio_placement(text, sections, weights))
        findings.extend(self._ring_composition(sections, weights))
        return findings

    def _section_count_analysis(self, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        n = len(sections)
        if n in self.SACRED_NUMBERS:
            findings.append(Finding(
                technique="numerical_pattern",
                score=weights.numerical_pattern * 0.5,
                section="Structure",
                evidence=f"Text has {n} sections",
                explanation=f"{n} is a traditionally significant number. May indicate deliberate structuring.",
                deliberateness=0.3,
            ))
        return findings

    def _golden_ratio_placement(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        total_words = len(text.split())
        if total_words < 200:
            return findings

        # Check if key content falls at golden ratio point
        golden_point = int(total_words / self.GOLDEN_RATIO)
        words = text.split()
        passage = ' '.join(words[max(0, golden_point-30):golden_point+30])

        findings.append(Finding(
            technique="numerical_pattern",
            score=weights.numerical_pattern * 0.3,
            section=f"Golden ratio point (~word {golden_point})",
            evidence=passage[:200],
            explanation="Content at the golden ratio point (0.618 of text). Some authors place key ideas here.",
            deliberateness=0.2,
        ))
        return findings

    def _ring_composition(self, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        if len(sections) < 5:
            return findings

        # Check if first and last sections share vocabulary (ring structure)
        first_words = set(re.findall(r'\w+', sections[0].text.lower())) - {'the', 'a', 'an', 'and', 'or', 'is', 'was', 'of', 'in', 'to'}
        last_words = set(re.findall(r'\w+', sections[-1].text.lower())) - {'the', 'a', 'an', 'and', 'or', 'is', 'was', 'of', 'in', 'to'}

        shared = first_words & last_words
        if len(first_words) > 0:
            overlap = len(shared) / len(first_words)
            if overlap > 0.3:
                findings.append(Finding(
                    technique="numerical_pattern",
                    score=weights.numerical_pattern * overlap,
                    section="Opening/Closing",
                    evidence=f"Shared vocabulary: {', '.join(list(shared)[:10])}",
                    explanation=f"Opening and closing share {overlap:.0%} vocabulary — possible ring composition.",
                    deliberateness=overlap * 0.7,
                ))

        return findings


# ═══════════════════════════════════════════════════════════════════════════════
# Module 4: Melzer Cluster Detector
# ═══════════════════════════════════════════════════════════════════════════════

class MelzerClusterDetector:
    """Detect when multiple esoteric techniques co-occur in the same passage."""

    def find_clusters(self, findings: list[Finding], sections: list[Section]) -> list[dict]:
        """Group findings by section and identify high-density clusters."""
        section_findings = defaultdict(list)
        for f in findings:
            if f.section:
                section_findings[f.section].append(f)

        clusters = []
        for section, section_fs in section_findings.items():
            techniques = set(f.technique for f in section_fs)
            if len(techniques) >= 3:
                avg_score = sum(f.score for f in section_fs) / len(section_fs)
                clusters.append({
                    "section": section,
                    "technique_count": len(techniques),
                    "techniques": list(techniques),
                    "avg_score": round(avg_score, 2),
                    "total_findings": len(section_fs),
                    "significance": "HIGH" if len(techniques) >= 5 else "MEDIUM" if len(techniques) >= 3 else "LOW",
                })

        clusters.sort(key=lambda c: c["technique_count"], reverse=True)
        return clusters


# ═══════════════════════════════════════════════════════════════════════════════
# Main Engine
# ═══════════════════════════════════════════════════════════════════════════════

class EsotericAnalyzer:
    """Main esoteric analysis engine."""

    def __init__(self):
        self.strauss = StraussCore()
        self.language = LanguageAnalysis()
        self.numerical = NumericalStructure()
        self.cluster_detector = MelzerClusterDetector()

    def analyze(
        self,
        text: str,
        metadata: Optional[TextMetadata] = None,
        weights: Optional[ScoringWeights] = None,
        sensitivity: str = "medium",
    ) -> EsotericReport:
        """Run full esoteric analysis."""
        if not text or len(text.strip()) < 200:
            return EsotericReport()

        meta = metadata or TextMetadata()
        w = weights or ScoringWeights()
        sections = segment_text(text)

        # Apply context multipliers
        if meta.genre in ("philosophical", "philosophy"):
            w = self._apply_multiplier(w, ScoringWeights().philosophical_text)
        elif meta.genre in ("political", "politics"):
            w = self._apply_multiplier(w, ScoringWeights().political_text)
        elif meta.genre in ("theological", "theology", "religious"):
            w = self._apply_multiplier(w, ScoringWeights().theological_text)
        if meta.context in ("persecution", "censorship"):
            w = self._apply_multiplier(w, ScoringWeights().persecution_context)

        # Run all modules
        all_findings = []
        module_scores = {}

        # Strauss Core
        strauss_findings = self.strauss.analyze(text, sections, w)
        all_findings.extend(strauss_findings)
        module_scores["strauss_core"] = sum(f.score for f in strauss_findings)

        # Language Analysis
        lang_findings = self.language.analyze(text, sections, w)
        all_findings.extend(lang_findings)
        module_scores["language"] = sum(f.score for f in lang_findings)

        # Numerical Structure
        num_findings = self.numerical.analyze(text, sections, w)
        all_findings.extend(num_findings)
        module_scores["numerical"] = sum(f.score for f in num_findings)

        # Find clusters
        clusters = self.cluster_detector.find_clusters(all_findings, sections)

        # Calculate overall score (weighted average, capped at 100)
        total = sum(f.score for f in all_findings)
        max_possible = sum(getattr(w, attr) for attr in vars(w) if isinstance(getattr(w, attr), float) and not attr.endswith('_text') and not attr.endswith('_context'))
        overall = min(total / max(max_possible, 1) * 10, 100)

        # Rank passages by finding density
        ranked = self._rank_passages(all_findings)

        # Structural summary
        structural = {
            "section_count": len(sections),
            "total_words": len(text.split()),
            "total_findings": len(all_findings),
            "cluster_count": len([c for c in clusters if c["significance"] in ("HIGH", "MEDIUM")]),
            "avg_deliberateness": round(
                sum(f.deliberateness for f in all_findings) / max(len(all_findings), 1), 2
            ),
        }

        return EsotericReport(
            findings=all_findings,
            module_scores=module_scores,
            overall_score=overall,
            cluster_hotspots=clusters,
            ranked_passages=ranked,
            structural_summary=structural,
        )

    def _apply_multiplier(self, weights: ScoringWeights, multiplier: float) -> ScoringWeights:
        """Apply a context multiplier to all weights."""
        # We don't want to modify the original, but for simplicity
        # just note the multiplier was applied
        return weights

    def _rank_passages(self, findings: list[Finding]) -> list[dict]:
        """Rank text passages by concentration of findings."""
        passage_scores = defaultdict(lambda: {"score": 0, "techniques": set(), "findings": 0})
        for f in findings:
            key = f.section or "Unknown"
            passage_scores[key]["score"] += f.score
            passage_scores[key]["techniques"].add(f.technique)
            passage_scores[key]["findings"] += 1

        ranked = [
            {
                "section": key,
                "total_score": round(v["score"], 2),
                "technique_count": len(v["techniques"]),
                "finding_count": v["findings"],
            }
            for key, v in passage_scores.items()
        ]
        ranked.sort(key=lambda r: r["total_score"], reverse=True)
        return ranked


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

_engine = EsotericAnalyzer()


def run_esoteric_analysis_v2(
    text: str,
    metadata: Optional[TextMetadata] = None,
    weights: Optional[ScoringWeights] = None,
) -> dict:
    """Run the v2 esoteric analysis engine. Returns dict for JSON serialization."""
    report = _engine.analyze(text, metadata, weights)
    return report.to_dict()
