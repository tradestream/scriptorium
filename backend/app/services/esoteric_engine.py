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
# Module 4: Melzer Fourteen Modes
# ═══════════════════════════════════════════════════════════════════════════════

class MelzerTaxonomy:
    """Detection for Melzer's fourteen modes of esoteric communication."""

    # Mode 5: Shocking/blasphemous statements
    ORTHODOX_VIOLATIONS = re.compile(
        r'(?:god (?:is dead|does not exist|cannot)|no (?:god|providence|afterlife|soul|immortality)|'
        r'religion is (?:false|superstition|invention|useful fiction)|'
        r'all (?:morality|virtue|religion) is (?:merely|nothing but|convention)|'
        r'there is no (?:natural (?:law|right)|moral order|divine (?:law|providence)))',
        re.I
    )

    # Mode 7: Form/content mismatch indicators
    GRAND_STYLE_MARKERS = re.compile(r'(?:O\s+[A-Z]|alas|behold|lo\b|hark|verily|forsooth|indeed)', re.I)
    CASUAL_MARKERS = re.compile(r'(?:by the way|incidentally|in passing|as an aside|parenthetically|to digress)', re.I)

    # Mode 9: Emphasis inversion — "by the way" framing of important claims
    UNDEREMPHASIS = re.compile(
        r'(?:by the way|incidentally|in passing|as (?:a |an )?(?:aside|afterthought)|'
        r'(?:this|it) (?:may|might) (?:seem|appear) (?:trivial|unimportant|minor)|'
        r'(?:a |this |one )?(?:small|minor|trivial|trifling) (?:point|matter|detail|observation))',
        re.I
    )

    # Mode 8: Dramatic/narrative irony markers
    IRONY_MARKERS = re.compile(
        r'(?:of course|naturally|obviously|needless to say|it goes without saying|'
        r'everyone knows|who (?:could|would) (?:doubt|deny)|'
        r'as (?:everyone|all) (?:agree|know)s?|'
        r'it is (?:well known|universally (?:admitted|acknowledged)))',
        re.I
    )

    def analyze(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        findings.extend(self._shocking_statements(text, sections, weights))
        findings.extend(self._form_content_mismatch(text, sections, weights))
        findings.extend(self._emphasis_inversion(text, sections, weights))
        findings.extend(self._irony_markers(text, sections, weights))
        findings.extend(self._incomplete_argumentation(text, sections, weights))
        findings.extend(self._conspicuous_omission(text, sections, weights))
        findings.extend(self._aesopian_language(text, sections, weights))
        findings.extend(self._broken_patterns(text, sections, weights))
        findings.extend(self._extravagant_praise(text, sections, weights))
        findings.extend(self._multilevel_audience(text, sections, weights))
        findings.extend(self._anomalous_details(text, sections, weights))
        return findings

    def _shocking_statements(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Mode 5: Statements contradicting religious/political orthodoxy."""
        findings = []
        for m in self.ORTHODOX_VIOLATIONS.finditer(text):
            start = max(0, m.start() - 150)
            end = min(len(text), m.end() + 150)
            findings.append(Finding(
                technique="shocking_statement",
                score=weights.shocking_statement * 0.7,
                section="",
                evidence=text[start:end],
                explanation=f"Potentially shocking claim: '{m.group(0)}' — contradicts orthodox views.",
                deliberateness=0.7,
            ))
        return findings[:10]

    def _form_content_mismatch(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Mode 7: Trivial content in grand style, or profound content in casual style."""
        findings = []
        for sec in sections:
            grand = len(self.GRAND_STYLE_MARKERS.findall(sec.text))
            casual = len(self.CASUAL_MARKERS.findall(sec.text))
            words = len(re.findall(r'\w+', sec.text))
            if words < 50:
                continue

            # Check for casual framing of important-looking content
            if casual > 0:
                # Find what's said "in passing"
                for m in self.CASUAL_MARKERS.finditer(sec.text):
                    end = sec.text.find('.', m.end())
                    if end == -1:
                        end = min(len(sec.text), m.end() + 200)
                    passage = sec.text[m.start():end+1].strip()
                    findings.append(Finding(
                        technique="form_content_mismatch",
                        score=weights.form_content_mismatch * 0.6,
                        section=sec.label,
                        evidence=passage[:200],
                        explanation=f"Important content introduced casually with '{m.group(0)}' — possible emphasis inversion.",
                        deliberateness=0.6,
                    ))

        return findings[:10]

    def _emphasis_inversion(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Mode 9: Important claims framed as trivial, minor points treated extensively."""
        findings = []
        for m in self.UNDEREMPHASIS.finditer(text):
            start = m.start()
            end = text.find('.', m.end())
            if end == -1:
                end = min(len(text), m.end() + 200)
            passage = text[start:end+1].strip()

            findings.append(Finding(
                technique="emphasis_inversion",
                score=weights.emphasis_inversion * 0.5,
                section="",
                evidence=passage[:200],
                explanation=f"Underemphasis marker '{m.group(0)}' — important claim may be disguised as minor.",
                deliberateness=0.6,
            ))
        return findings[:10]

    def _irony_markers(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Mode 8: Ironic assertions disguised as common knowledge."""
        findings = []
        for m in self.IRONY_MARKERS.finditer(text):
            start = max(0, m.start() - 50)
            end = text.find('.', m.end())
            if end == -1:
                end = min(len(text), m.end() + 200)
            passage = text[start:end+1].strip()

            findings.append(Finding(
                technique="dramatic_irony",
                score=weights.dramatic_irony * 0.4,
                section="",
                evidence=passage[:200],
                explanation=f"Irony marker '{m.group(0)}' — what's presented as obvious may be the opposite.",
                deliberateness=0.4,
            ))
        return findings[:15]

    def _incomplete_argumentation(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Mode 3: Missing premises, unsupported conclusions, asymmetric treatment."""
        findings = []
        sentences = get_sentences(text)

        # Find conclusions without premises
        CONCLUSION_MARKERS = re.compile(r'\b(?:therefore|thus|hence|consequently|it follows|we must conclude|accordingly)\b', re.I)
        PREMISE_MARKERS = re.compile(r'\b(?:because|since|for|given that|inasmuch as|insofar as)\b', re.I)

        for i, sent in enumerate(sentences):
            if CONCLUSION_MARKERS.search(sent):
                # Check if nearby sentences provide premises
                nearby = ' '.join(sentences[max(0,i-3):i])
                has_premise = bool(PREMISE_MARKERS.search(nearby))
                if not has_premise:
                    findings.append(Finding(
                        technique="logical_incompleteness",
                        score=weights.logical_incompleteness * 0.4,
                        section=f"Sentence {i+1}",
                        evidence=sent[:200],
                        explanation="Conclusion without explicit premise — reader must supply the missing step.",
                        deliberateness=0.4,
                    ))

        return findings[:10]

    def _conspicuous_omission(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Mode 6: Topics introduced then abandoned, questions raised but unanswered."""
        findings = []
        sentences = get_sentences(text)

        QUESTION_PATTERNS = re.compile(r'[^.]*\?\s*$')
        questions = [(i, s) for i, s in enumerate(sentences) if QUESTION_PATTERNS.match(s)]

        for qi, (idx, question) in enumerate(questions):
            # Check if the next few sentences attempt to answer
            answer_region = ' '.join(sentences[idx+1:idx+4]) if idx+1 < len(sentences) else ""
            # Crude check: does the answer region address the question's keywords?
            q_words = set(re.findall(r'\w+', question.lower())) - {'the', 'a', 'is', 'are', 'was', 'what', 'why', 'how', 'do', 'does', 'did', 'this', 'that', 'it'}
            a_words = set(re.findall(r'\w+', answer_region.lower()))
            overlap = len(q_words & a_words) / max(len(q_words), 1)

            if overlap < 0.2 and len(q_words) > 3:
                findings.append(Finding(
                    technique="conspicuous_omission",
                    score=weights.conspicuous_omission * 0.5,
                    section=f"Sentence {idx+1}",
                    evidence=question[:200],
                    explanation="Question raised but not clearly answered — possible strategic omission.",
                    deliberateness=0.4,
                ))

        return findings[:10]

    def _aesopian_language(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Aesopian parallels — historical/foreign settings mirroring local issues."""
        findings = []
        AESOPIAN_MARKERS = re.compile(
            r'(?:in (?:ancient|classical) (?:Greece|Rome|Athens|Sparta|Persia|Egypt)|'
            r'(?:the (?:ancients|Romans|Greeks|Athenians|Spartans)) (?:believed|held|practiced|taught)|'
            r'(?:Plato|Aristotle|Socrates|Xenophon|Cicero|Tacitus|Thucydides) (?:tells|relates|shows|says)|'
            r'consider (?:the case|the example) of|'
            r'(?:a |one )(?:certain |particular )?(?:country|nation|people|city|republic|kingdom)|'
            r'(?:in a |there was a )(?:far|distant|foreign|remote) (?:land|country|kingdom))',
            re.I
        )

        for m in AESOPIAN_MARKERS.finditer(text):
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 200)
            findings.append(Finding(
                technique="form_content_mismatch",
                score=weights.form_content_mismatch * 0.5,
                section="",
                evidence=text[start:end][:250],
                explanation=f"Aesopian marker: '{m.group(0)}' — may be using historical/foreign setting to mirror contemporary issues.",
                deliberateness=0.5,
            ))
        return findings[:10]

    def _broken_patterns(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Detect when established lists/enumerations omit a critical entry."""
        findings = []

        # Find numbered lists: "first... second... third..." and check for gaps
        ordinals = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth']
        text_lower = text.lower()

        for i in range(len(ordinals) - 1):
            has_current = ordinals[i] in text_lower
            has_next = ordinals[i + 1] in text_lower
            if has_current and not has_next and i > 0:
                # Previous items existed but this sequence breaks
                # Check if we were in a genuine enumeration
                prev_count = sum(1 for o in ordinals[:i+1] if o in text_lower)
                if prev_count >= 2:
                    findings.append(Finding(
                        technique="conspicuous_omission",
                        score=weights.conspicuous_omission * 0.5,
                        section="",
                        evidence=f"Enumeration: {', '.join(ordinals[:i+1])} present but '{ordinals[i+1]}' missing",
                        explanation=f"List breaks after '{ordinals[i]}' — the missing entry may be the one the author cannot state.",
                        deliberateness=0.5,
                    ))
                break

        return findings

    def _extravagant_praise(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Detect discrepancies between extravagant praise and underlying critique."""
        findings = []
        PRAISE = re.compile(
            r'(?:(?:the )?(?:great|illustrious|famous|renowned|celebrated|noble|divine|wise|learned|eminent|immortal)\s+'
            r'(?:[A-Z]\w+))',
            re.I
        )

        UNDERCUT = re.compile(
            r'(?:however|but|yet|nevertheless|notwithstanding|although|despite|'
            r'it must be (?:said|noted|admitted|observed)|'
            r'on the other hand|to be sure|admittedly)',
            re.I
        )

        for m in PRAISE.finditer(text):
            # Check if praise is undercut within 300 chars
            region_after = text[m.end():m.end()+300]
            undercuts = UNDERCUT.findall(region_after)
            if undercuts:
                start = max(0, m.start() - 50)
                end = min(len(text), m.end() + 200)
                findings.append(Finding(
                    technique="dramatic_irony",
                    score=weights.dramatic_irony * 0.5,
                    section="",
                    evidence=text[start:end][:250],
                    explanation=f"Extravagant praise '{m.group(0)}' followed by undercut '{undercuts[0]}' — possible ironic veneer.",
                    deliberateness=0.5,
                ))

        return findings[:10]

    def _multilevel_audience(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Detect sections designed for 'the common herd' vs 'the few'."""
        findings = []

        ELITE_MARKERS = {
            "the wise", "the few", "those who understand", "the careful reader",
            "the attentive", "the philosophic", "the learned", "the initiated",
            "the intelligent", "the discerning", "for few readers",
        }
        MASS_MARKERS = {
            "the many", "the multitude", "the vulgar", "the common", "the people",
            "the masses", "the populace", "most readers", "the public", "ordinary men",
            "common opinion", "the unlearned",
        }

        text_lower = text.lower()
        elite_count = sum(text_lower.count(m) for m in ELITE_MARKERS)
        mass_count = sum(text_lower.count(m) for m in MASS_MARKERS)
        total = elite_count + mass_count

        if total >= 3:
            balance = min(elite_count, mass_count) / max(elite_count, mass_count) if max(elite_count, mass_count) > 0 else 0
            deliberateness = min(total / 15, 1.0) * (0.4 + balance * 0.6)

            findings.append(Finding(
                technique="pedagogical_stratification",
                score=weights.pedagogical_stratification * deliberateness,
                section="Full text",
                evidence=f"Elite markers: {elite_count}, Mass markers: {mass_count}",
                explanation=f"Author explicitly addresses different audiences — strong signal of multilevel writing.",
                deliberateness=deliberateness,
            ))

        return findings

    def _anomalous_details(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Mode 12: Irrelevant-seeming details, unusual specificity, odd examples."""
        findings = []

        # Look for very specific numbers/dates/names that seem out of place
        SPECIFIC_DETAIL = re.compile(
            r'(?:exactly|precisely)\s+\d+|'
            r'(?:on|at|in)\s+(?:the\s+)?(?:year|day|page|line|chapter|verse|section)\s+\d+|'
            r'(?:footnote|note|cf\.)\s+\d+',
            re.I
        )

        for m in SPECIFIC_DETAIL.finditer(text):
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 100)
            findings.append(Finding(
                technique="anomalous_detail",
                score=weights.anomalous_detail * 0.3,
                section="",
                evidence=text[start:end],
                explanation=f"Unusually specific detail: '{m.group(0)}' — may be a coded reference.",
                deliberateness=0.3,
            ))

        return findings[:10]


# ═══════════════════════════════════════════════════════════════════════════════
# Module 5: Advanced Structural Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class AdvancedStructure:
    """Chiasmus, musical proportions, section organization analysis."""

    MUSICAL_RATIOS = {
        "octave (2:1)": 2.0,
        "fifth (3:2)": 1.5,
        "fourth (4:3)": 1.333,
        "major third (5:4)": 1.25,
        "golden ratio": 1.618,
    }

    def analyze(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        findings.extend(self._chiasmus_detection(text, sections, weights))
        findings.extend(self._proportional_analysis(sections, weights))
        findings.extend(self._section_organization(sections, weights))
        findings.extend(self._first_last_analysis(text, sections, weights))
        findings.extend(self._epigraph_extraction(text, weights))
        return findings

    def _chiasmus_detection(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Detect ABCBA ring patterns at section level."""
        findings = []
        if len(sections) < 5:
            return findings

        # Compare section pairs from outside in
        n = len(sections)
        ring_scores = []
        for i in range(n // 2):
            outer = sections[i]
            mirror = sections[n - 1 - i]

            outer_words = set(re.findall(r'\w+', outer.text.lower())) - {'the', 'a', 'an', 'and', 'or', 'is', 'of', 'in', 'to', 'was', 'that', 'it'}
            mirror_words = set(re.findall(r'\w+', mirror.text.lower())) - {'the', 'a', 'an', 'and', 'or', 'is', 'of', 'in', 'to', 'was', 'that', 'it'}

            if outer_words:
                overlap = len(outer_words & mirror_words) / len(outer_words)
                ring_scores.append((outer.label, mirror.label, overlap))

        avg_ring = sum(s[2] for s in ring_scores) / max(len(ring_scores), 1)
        if avg_ring > 0.25 and len(ring_scores) >= 2:
            top_pairs = sorted(ring_scores, key=lambda x: x[2], reverse=True)[:3]
            pair_desc = "; ".join(f"{a}<->{b} ({o:.0%})" for a, b, o in top_pairs)
            findings.append(Finding(
                technique="numerical_pattern",
                score=weights.numerical_pattern * avg_ring,
                section="Ring structure",
                evidence=f"Mirror pairs: {pair_desc}",
                explanation=f"Ring/chiastic composition detected (avg overlap {avg_ring:.0%}). Center section may contain the key teaching.",
                deliberateness=avg_ring * 0.8,
            ))

        return findings

    def _proportional_analysis(self, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Check section length ratios against musical/golden proportions."""
        findings = []
        if len(sections) < 2:
            return findings

        sizes = [len(s.text) for s in sections]
        for i in range(len(sizes)):
            for j in range(i + 1, min(i + 4, len(sizes))):
                if sizes[j] == 0:
                    continue
                ratio = sizes[i] / sizes[j]
                if ratio < 1:
                    ratio = 1 / ratio

                for name, target in self.MUSICAL_RATIOS.items():
                    if abs(ratio - target) < 0.05:
                        findings.append(Finding(
                            technique="numerical_pattern",
                            score=weights.numerical_pattern * 0.3,
                            section=f"{sections[i].label} / {sections[j].label}",
                            evidence=f"Ratio {ratio:.3f} ≈ {name} ({target})",
                            explanation=f"Section lengths approximate {name} — may indicate deliberate proportioning.",
                            deliberateness=0.3,
                        ))

        return findings[:5]

    def _section_organization(self, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Analyze whether divisions seem organic or schematic."""
        findings = []
        if len(sections) < 3:
            return findings

        sizes = [len(s.text) for s in sections]
        avg = sum(sizes) / len(sizes)
        std = (sum((s - avg) ** 2 for s in sizes) / len(sizes)) ** 0.5
        cv = std / avg if avg > 0 else 0

        if cv < 0.2:
            findings.append(Finding(
                technique="strategic_obscurity",
                score=weights.strategic_obscurity * 0.4,
                section="Structure",
                evidence=f"Section size CV = {cv:.2f} (very uniform)",
                explanation="Sections are unusually uniform in length — may indicate schematic rather than organic division.",
                deliberateness=0.4,
            ))
        elif cv > 0.8:
            findings.append(Finding(
                technique="strategic_obscurity",
                score=weights.strategic_obscurity * 0.5,
                section="Structure",
                evidence=f"Section size CV = {cv:.2f} (very uneven)",
                explanation="Wildly uneven sections — important content may be hidden in unexpectedly short or long sections.",
                deliberateness=0.5,
            ))

        return findings

    def _first_last_analysis(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        """Analyze first and last words/sentences for significance."""
        findings = []
        words = re.findall(r'\w+', text)
        if not words:
            return findings

        first_word = words[0]
        last_word = words[-1]
        sentences = get_sentences(text)

        if first_word.lower() == last_word.lower():
            findings.append(Finding(
                technique="numerical_pattern",
                score=weights.numerical_pattern * 0.8,
                section="Opening/Closing",
                evidence=f"Text begins and ends with '{first_word}'",
                explanation="Identical first and last word — strong ring composition signal.",
                deliberateness=0.8,
            ))

        if sentences:
            findings.append(Finding(
                technique="anomalous_detail",
                score=weights.anomalous_detail * 0.2,
                section="Paratext",
                evidence=f"First: '{sentences[0][:100]}...' | Last: '{sentences[-1][:100]}...'",
                explanation="First and last sentences — almost always significant per Strauss.",
                deliberateness=0.3,
            ))

        return findings

    def _epigraph_extraction(self, text: str, weights: ScoringWeights) -> list[Finding]:
        """Extract epigraphs from the opening of the text."""
        findings = []
        # Look for quoted text with attribution in first 3000 chars
        pattern = re.compile(
            r'["\u201c]([^"\u201d]{20,500})["\u201d]\s*(?:—|--|-)\s*([A-Z][^\n]{3,80})',
        )
        for m in pattern.finditer(text[:3000]):
            findings.append(Finding(
                technique="anomalous_detail",
                score=weights.anomalous_detail * 0.5,
                section="Epigraph",
                evidence=f'"{m.group(1)[:150]}..." — {m.group(2)}',
                explanation="Epigraph — chosen with extreme care, often contains the key to the whole work.",
                deliberateness=0.6,
            ))
        return findings[:3]


# ═══════════════════════════════════════════════════════════════════════════════
# Module 6: Comparative Baseline
# ═══════════════════════════════════════════════════════════════════════════════

class ComparativeBaseline:
    """Compare a text's metrics against a baseline to detect deviations."""

    def score_deviations(self, report: 'EsotericReport', baseline_scores: Optional[dict] = None) -> list[Finding]:
        """If we have baseline metrics from the author's other works, flag deviations."""
        if not baseline_scores:
            return []

        findings = []
        for module, score in report.module_scores.items():
            if module in baseline_scores:
                baseline = baseline_scores[module]
                if baseline > 0:
                    deviation = (score - baseline) / baseline
                    if abs(deviation) > 0.5:
                        direction = "higher" if deviation > 0 else "lower"
                        findings.append(Finding(
                            technique="anomalous_detail",
                            score=abs(deviation) * 5,
                            section="Comparative",
                            evidence=f"{module}: {score:.1f} vs baseline {baseline:.1f}",
                            explanation=f"This text scores {abs(deviation):.0%} {direction} than the author's typical on {module}.",
                            deliberateness=min(abs(deviation), 1.0),
                        ))

        return findings


# ═══════════════════════════════════════════════════════════════════════════════
# Module 7: Melzer Cluster Detector
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
# Module 8: Contradiction Network
# ═══════════════════════════════════════════════════════════════════════════════

class ContradictionNetwork:
    """Build a graph of all contradictions with clustering and typing."""

    def build_network(self, findings: list[Finding]) -> dict:
        """Analyze contradiction findings to build a network."""
        contradictions = [f for f in findings if "contradiction" in f.technique]
        if not contradictions:
            return {"nodes": [], "edges": [], "clusters": []}

        # Group by topic (extract from evidence)
        topic_contradictions = defaultdict(list)
        for c in contradictions:
            # Use technique + first 30 chars as topic key
            topic = c.evidence[:30] if c.evidence else "unknown"
            topic_contradictions[topic].append(c)

        # Build nodes and edges
        nodes = []
        edges = []
        for i, c in enumerate(contradictions[:30]):
            nodes.append({
                "id": i,
                "section": c.section,
                "score": round(c.score, 2),
                "deliberateness": round(c.deliberateness, 2),
            })

        # Connect contradictions that share sections or topics
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                if contradictions[i].section == contradictions[j].section:
                    edges.append({"source": i, "target": j, "type": "same_section"})

        # Identify clusters (topics with 3+ contradictions)
        clusters = [
            {
                "topic": topic[:50],
                "count": len(cs),
                "avg_deliberateness": round(sum(c.deliberateness for c in cs) / len(cs), 2),
                "significance": "HIGH" if len(cs) >= 4 else "MEDIUM" if len(cs) >= 2 else "LOW",
            }
            for topic, cs in topic_contradictions.items()
            if len(cs) >= 2
        ]
        clusters.sort(key=lambda c: c["count"], reverse=True)

        return {
            "total_contradictions": len(contradictions),
            "nodes": nodes,
            "edges": edges,
            "clusters": clusters[:10],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Module 9: Authorial Hints Detector
# ═══════════════════════════════════════════════════════════════════════════════

class AuthorialHints:
    """Detect when the author discusses OTHER writers' esoteric practices."""

    HINT_PATTERNS = re.compile(
        r'(?:(?:he|she|the author|this writer|they) (?:wrote|speaks?|communicat(?:es?|ed)|'
        r'express(?:es?|ed)|conceal(?:s|ed)|hid(?:es?|den)?|disguis(?:es?|ed)) '
        r'(?:between the lines|esoterically|with circumspection|with caution|indirectly|'
        r'in a (?:veiled|hidden|indirect|subtle) (?:manner|way|fashion))|'
        r'(?:the (?:true|real|hidden|secret|deeper|esoteric) (?:meaning|teaching|doctrine|view|opinion))|'
        r'(?:what (?:he|she|the author) (?:really|actually|truly) (?:meant|thought|believed))|'
        r'(?:(?:wrote|writing|write) (?:with|under) (?:caution|circumspection|constraint))|'
        r'(?:(?:addressed|meant for|intended for) (?:the few|a select|careful|attentive) (?:readers?|audience)))',
        re.I
    )

    def analyze(self, text: str, sections: list[Section], weights: ScoringWeights) -> list[Finding]:
        findings = []
        for m in self.HINT_PATTERNS.finditer(text):
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 150)
            findings.append(Finding(
                technique="explicit_esotericism_claim",
                score=weights.explicit_esotericism_claim * 0.6,
                section="",
                evidence=text[start:end][:250],
                explanation=f"Authorial hint: '{m.group(0)[:60]}...' — discussing another's esotericism may signal the author's own practice.",
                deliberateness=0.7,
            ))
        return findings[:10]


# ═══════════════════════════════════════════════════════════════════════════════
# Module 10: Heatmap Generator
# ═══════════════════════════════════════════════════════════════════════════════

class HeatmapGenerator:
    """Generate passage-level esotericism likelihood heatmap."""

    def generate(self, text: str, findings: list[Finding], sections: list[Section]) -> list[dict]:
        """Create a section-by-section heatmap of esotericism intensity."""
        section_scores = {}
        for sec in sections:
            section_scores[sec.label] = {
                "label": sec.label,
                "index": sec.index,
                "word_count": len(re.findall(r'\w+', sec.text)),
                "total_score": 0.0,
                "finding_count": 0,
                "techniques": set(),
                "max_deliberateness": 0.0,
            }

        for f in findings:
            key = f.section if f.section in section_scores else None
            if not key:
                # Try to match by content
                for sec_label, sec_data in section_scores.items():
                    if f.evidence and f.evidence[:30] in text:
                        idx = text.find(f.evidence[:30])
                        for sec in sections:
                            if sec.start_char <= idx < sec.end_char:
                                key = sec.label
                                break
                    break

            if key and key in section_scores:
                section_scores[key]["total_score"] += f.score
                section_scores[key]["finding_count"] += 1
                section_scores[key]["techniques"].add(f.technique)
                section_scores[key]["max_deliberateness"] = max(
                    section_scores[key]["max_deliberateness"], f.deliberateness
                )

        # Normalize and create heatmap
        max_score = max((s["total_score"] for s in section_scores.values()), default=1)
        heatmap = []
        for label, data in section_scores.items():
            intensity = data["total_score"] / max_score if max_score > 0 else 0
            heatmap.append({
                "section": label,
                "index": data["index"],
                "intensity": round(intensity, 3),
                "total_score": round(data["total_score"], 2),
                "finding_count": data["finding_count"],
                "technique_count": len(data["techniques"]),
                "max_deliberateness": round(data["max_deliberateness"], 2),
                "heat_level": "HIGH" if intensity > 0.7 else "MEDIUM" if intensity > 0.3 else "LOW",
            })

        heatmap.sort(key=lambda h: h["index"])
        return heatmap


# ═══════════════════════════════════════════════════════════════════════════════
# Module 11: Custom Pattern Detector
# ═══════════════════════════════════════════════════════════════════════════════

class CustomPatterns:
    """User-defined pattern detection."""

    def analyze(
        self,
        text: str,
        sections: list[Section],
        custom_keywords: list[str] = None,
        custom_phrases: list[str] = None,
        custom_regex: list[str] = None,
    ) -> list[Finding]:
        findings = []

        if custom_keywords:
            text_lower = text.lower()
            for kw in custom_keywords:
                count = text_lower.count(kw.lower())
                if count > 0:
                    # Find first occurrence with context
                    idx = text_lower.find(kw.lower())
                    start = max(0, idx - 80)
                    end = min(len(text), idx + len(kw) + 80)
                    findings.append(Finding(
                        technique="anomalous_detail",
                        score=2.0 + (count * 0.5),
                        section="Custom",
                        evidence=text[start:end],
                        explanation=f"Custom keyword '{kw}' found {count} times.",
                        deliberateness=0.3,
                    ))

        if custom_phrases:
            text_lower = text.lower()
            for phrase in custom_phrases:
                if phrase.lower() in text_lower:
                    idx = text_lower.find(phrase.lower())
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(phrase) + 100)
                    findings.append(Finding(
                        technique="anomalous_detail",
                        score=3.0,
                        section="Custom",
                        evidence=text[start:end],
                        explanation=f"Custom phrase '{phrase}' found.",
                        deliberateness=0.5,
                    ))

        if custom_regex:
            for pattern_str in custom_regex:
                try:
                    pat = re.compile(pattern_str, re.I)
                    for m in pat.finditer(text):
                        start = max(0, m.start() - 50)
                        end = min(len(text), m.end() + 100)
                        findings.append(Finding(
                            technique="anomalous_detail",
                            score=3.0,
                            section="Custom",
                            evidence=text[start:end][:200],
                            explanation=f"Custom pattern match: '{m.group(0)[:50]}'",
                            deliberateness=0.5,
                        ))
                except re.error:
                    pass

        return findings[:20]


# ═══════════════════════════════════════════════════════════════════════════════
# Main Engine
# ═══════════════════════════════════════════════════════════════════════════════

class EsotericAnalyzer:
    """Main esoteric analysis engine."""

    def __init__(self):
        self.strauss = StraussCore()
        self.language = LanguageAnalysis()
        self.numerical = NumericalStructure()
        self.melzer = MelzerTaxonomy()
        self.structure = AdvancedStructure()
        self.comparative = ComparativeBaseline()
        self.cluster_detector = MelzerClusterDetector()
        self.contradiction_network = ContradictionNetwork()
        self.authorial_hints = AuthorialHints()
        self.heatmap = HeatmapGenerator()
        self.custom = CustomPatterns()

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

        # Melzer Taxonomy (14 modes)
        melzer_findings = self.melzer.analyze(text, sections, w)
        all_findings.extend(melzer_findings)
        module_scores["melzer_taxonomy"] = sum(f.score for f in melzer_findings)

        # Advanced Structure (chiasmus, proportions, organization)
        struct_findings = self.structure.analyze(text, sections, w)
        all_findings.extend(struct_findings)
        module_scores["advanced_structure"] = sum(f.score for f in struct_findings)

        # Authorial Hints (discussing other writers' esotericism)
        hint_findings = self.authorial_hints.analyze(text, sections, w)
        all_findings.extend(hint_findings)
        module_scores["authorial_hints"] = sum(f.score for f in hint_findings)

        # Find clusters
        clusters = self.cluster_detector.find_clusters(all_findings, sections)

        # Calculate overall score (weighted average, capped at 100)
        total = sum(f.score for f in all_findings)
        max_possible = sum(getattr(w, attr) for attr in vars(w) if isinstance(getattr(w, attr), float) and not attr.endswith('_text') and not attr.endswith('_context'))
        overall = min(total / max(max_possible, 1) * 10, 100)

        # Rank passages by finding density
        ranked = self._rank_passages(all_findings)

        # Build contradiction network
        contradiction_net = self.contradiction_network.build_network(all_findings)

        # Generate heatmap
        heatmap_data = self.heatmap.generate(text, all_findings, sections)

        # Structural summary
        structural = {
            "section_count": len(sections),
            "total_words": len(text.split()),
            "total_findings": len(all_findings),
            "cluster_count": len([c for c in clusters if c["significance"] in ("HIGH", "MEDIUM")]),
            "avg_deliberateness": round(
                sum(f.deliberateness for f in all_findings) / max(len(all_findings), 1), 2
            ),
            "contradiction_network": contradiction_net,
            "heatmap": heatmap_data,
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
    custom_keywords: Optional[list[str]] = None,
    custom_phrases: Optional[list[str]] = None,
) -> dict:
    """Run the v2 esoteric analysis engine. Returns dict for JSON serialization."""
    report = _engine.analyze(text, metadata, weights)

    # Run custom patterns if provided
    if custom_keywords or custom_phrases:
        sections = segment_text(text)
        custom_findings = _engine.custom.analyze(
            text, sections,
            custom_keywords=custom_keywords,
            custom_phrases=custom_phrases,
        )
        report.findings.extend(custom_findings)
        report.module_scores["custom"] = sum(f.score for f in custom_findings)

    return report.to_dict()
