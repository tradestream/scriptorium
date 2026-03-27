"""Integrated esoteric analysis: feeds computational findings into LLM prompts.

The 9-stage prompt structure ensures the LLM builds on computational evidence
rather than generating analysis from scratch. This produces much more targeted
and grounded esoteric readings.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


INTEGRATED_SYSTEM_PROMPT = """You are a scholar trained in the tradition of esoteric textual interpretation, \
drawing on the methods of:
- Leo Strauss ("Persecution and the Art of Writing")
- Arthur Melzer ("Philosophy Between the Lines")
- Seth Benardete ("The Argument of the Action", "Socrates' Second Sailing", "The Bow and the Lyre")
- Maimonides, Al-Farabi, Francis Bacon, Clement of Alexandria
- The Pythagorean/Kabbalistic numerological traditions

You are especially attentive to Benardete's methods:
- The "argument IN the action" — what the text DOES vs. what it SAYS
- Trapdoors — intentional local flaws that force deeper reading
- Periagoge — structural reversal where the second half inverts the first
- Dyadic structure — binary oppositions that converge (conjunctive → disjunctive two)
- Recognition scenes — concealment → test → reveal patterns
- Onomastic analysis — names as compressed philosophical arguments
- Nomos-physis — the convention/nature tension beneath every argument
- Impossible arithmetic — productive paradoxes where one = many

You have been provided with COMPUTATIONAL PRE-ANALYSIS findings from 35 analytical tools. \
These are starting points, not conclusions. Your task is to perform a deep esoteric reading \
guided by these findings but going far beyond them.

IMPORTANT METHODOLOGICAL NOTES:
- You are looking for DELIBERATE concealment by a skilled author, not random noise.
- Not every text is esoteric. If the evidence is weak, say so.
- Esoteric reading is "a form of rhetoric" (Melzer), not a mechanical procedure.
- The computational findings are STARTING POINTS, not conclusions.
- The literal surface reading is the FOUNDATION (per Melzer: take the surface with extreme seriousness).
- Per Benardete: "the surface of things is the heart of things" — the dramatic/narrative surface IS philosophically constitutive.
- Your goal is to help the reader see what a careful, historically informed reader would see."""


def _load_stages_template() -> str:
    """Load the 40-stage analysis template.

    Tries to read from the reference llm_esoteric_prompt.md file first,
    falling back to a compact embedded version.
    """
    # Try loading from file (for development/customization)
    import os
    for search_path in [
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'llm_esoteric_prompt.md'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'llm_esoteric_prompt.md'),
        'llm_esoteric_prompt.md',
    ]:
        try:
            p = os.path.abspath(search_path)
            if os.path.exists(p):
                with open(p, encoding='utf-8') as f:
                    content = f.read()
                # Extract just the stages section (from "YOUR TASK" to end)
                idx = content.find("YOUR TASK:")
                if idx >= 0:
                    return content[idx:]
                # Try alternate marker
                idx = content.find("## STAGE 1")
                if idx >= 0:
                    return "YOUR TASK: Perform a deep esoteric reading guided by the computational findings above.\n\n" + content[idx:]
        except Exception:
            continue

    # Fallback: compact embedded stages
    return """YOUR TASK: Perform a deep esoteric reading of this text, guided by the 56-tool \
computational findings above. Proceed through ALL of the following stages:

## STAGE 1: LITERAL SURFACE READING
Describe the exoteric argument. What does the text appear to say? Who is the audience?

## STAGE 2: CONTRADICTION ANALYSIS
Examine contradictions. Per Strauss: the less emphatic statement is likelier true. \
Per Maimonides: 5th cause (pedagogy) or 7th cause (concealment)?

## STAGE 3: STRUCTURAL ANALYSIS
Center placement, ring/chiastic structure, numerological patterns, lexical density.

## STAGE 4: SILENCE AND OMISSION
Why are expected topics absent? Does silence constitute a negative argument?

## STAGE 5: IRONY AND INDIRECT COMMUNICATION
Hedging, excessive praise, conditional language, qualifier-to-assertion ratio.

## STAGE 6: DIGRESSIONS AND SCATTERED ARGUMENTS
Per Maimonides: "combine scattered chapters." Do digressions yield a hidden argument?

## STAGE 7: SOURCE AND AUTHORITY ANALYSIS
Scare quotes, parenthetical asides, commentary divergence, distorted citations.

## STAGE 8: VOICE AND PERSONA (KIERKEGAARD)
Stylistic shifts between sections. Multiple voices? Indirect communication?

## STAGE 9: REGISTER ANALYSIS (AVERROES)
Rhetorical/dialectical/demonstrative modes. Where does the demonstrative register appear?

## STAGE 10: LOGOS/MYTHOS (PLATO)
Transitions between argument and myth/narrative. Myth at the boundary of reason.

## STAGE 11: MULTI-LEVEL READING (DANTE/KABBALAH)
Literal, allegorical, moral, anagogical. Peshat/Remez/Derash/Sod.

## STAGE 12: MASK AND SELF-REFERENCE (NIETZSCHE)
Self-referential concealment. Does the text announce its own esotericism?

## STAGE 13: ACROSTIC AND STEGANOGRAPHIC PATTERNS
First/last letter patterns, numerological structure counts.

## STAGE 14: TRAPDOOR ANALYSIS (BENARDETE)
Hedged absolutes, non-sequiturs, local impossibilities. What lies beneath?

## STAGE 15: DYADIC STRUCTURE (BENARDETE)
Binary oppositions converging. Conjunctive→disjunctive two. Phantom images.

## STAGE 16: PERIAGOGE (BENARDETE)
Second half inverting/deepening the first. The philosophical "turning." Pathei mathos.

## STAGE 17: LOGOS-ERGON (BENARDETE)
Speech vs deed. The argument IN the action. Burstlike vs filamentlike arguments.

## STAGE 18: ONOMASTIC ANALYSIS (BENARDETE)
Names as philosophical arguments. Etymological commentary. The outis/metis pun.

## STAGE 19: RECOGNITION SCENE (BENARDETE)
Concealment→test→reveal. Identity achieved through narrative, not given.

## STAGE 20: NOMOS-PHYSIS (HERODOTEAN METHOD)
Convention vs nature. Alien customs revealing problematic assumptions.

## STAGE 21: IMPOSSIBLE ARITHMETIC (BENARDETE)
One=many, same=different. The poet's dialectic. Truth in two spurious forms.

## STAGE 22: RHETORIC OF CONCEALMENT (ROSEN)
Hidden design beneath disorder. Defensive maneuvering. The disheveled surface.

## STAGE 23: TRANSCENDENTAL AMBIGUITY (ROSEN)
Deliberately unresolved double meanings. Ambiguity as condition of possibility.

## STAGE 24: RHETORIC OF FRANKNESS (ROSEN)
Performative transparency as concealment. "Dare to know" as rhetoric.

## STAGE 25: INTUITION-ANALYSIS DIALECTIC (ROSEN)
Appeals to non-discursive knowing. Limits of formalization. Winke (hints).

## STAGE 26: LOGOGRAPHIC NECESSITY (BENARDETE)
Form carries the logos. Dramatic constraints as philosophical content.

## STAGE 27: THEOLOGICAL DISAVOWAL (ROSEN)
Theology disguised as philosophy. Philosophical substitutes for religious concepts.

## STAGE 28: DEFENSIVE WRITING (ROSEN/STRAUSS)
Preemptive rebuttals, disclaimers, appeals to orthodoxy. Defensive layering.

## STAGE 29: NATURE-FREEDOM OSCILLATION (ROSEN)
Systematic alternation between necessity and freedom. The oscillation IS the insight.

## STAGE 30: POSTMODERN MISREADING VULNERABILITY (ROSEN)
What would deconstruction latch onto? What would it miss? What resists appropriation?

## STAGE 31: DRAMATIC CONTEXT (ROSEN/SYMPOSIUM)
Speaker identity, setting, occasion. Arguments enabled/foreclosed by dramatic situation.

## STAGE 32: SPEECH SEQUENCING (ROSEN/SYMPOSIUM)
Successive sections building/transforming each other. Does sequence matter?

## STAGE 33: PHILOSOPHICAL COMEDY (ROSEN/SYMPOSIUM)
Serious philosophy in comic form. Laughter as philosophical instrument.

## STAGE 34: DAIMONIC MEDIATION (ROSEN/SYMPOSIUM)
Intermediate beings/concepts bridging opposites. Neither/nor positions.

## STAGE 35: MEDICINAL RHETORIC (ROSEN/SYMPOSIUM)
Speech adapted to the listener's soul. Graduated disclosure. Truth in measured doses.

## STAGE 36: POETRY-PHILOSOPHY DIALECTIC (ROSEN/SYMPOSIUM)
The ancient quarrel. The same person writing comedy and tragedy.

## STAGE 37: ASPIRATION-ACHIEVEMENT GAP (ROSEN/SYMPOSIUM)
Philosophy as permanent unfulfilled desire. Unresolved tensions as feature, not bug.

## STAGE 38: SYNOPTIC REQUIREMENT (ROSEN/SYMPOSIUM)
Full understanding requires the wider corpus. Deliberate incompleteness.

## STAGE 39: THE ESOTERIC ARGUMENT
Reconstruct: 1) Exoteric teaching 2) Esoteric teaching 3) Methods of concealment \
4) Evidence 5) Motive (Melzer's four types) 6) Confidence level

## STAGE 40: SAFEGUARDS AGAINST OVER-READING
Does your reading produce MORE coherence? Is evidence convergent? \
Could patterns be accidental? What would DISPROVE your reading?"""


def build_integrated_prompt(
    text: str,
    computational_results: dict,
    metadata: Optional[dict] = None,
    max_text_chars: int = 8000,
) -> str:
    """Build a 9-stage LLM prompt that feeds computational findings as context.

    Args:
        text: The book text (will be truncated to max_text_chars)
        computational_results: Output from run_full_esoteric_analysis + engine_v2
        metadata: Optional dict with title, author, genre, date
    """
    meta = metadata or {}
    title = meta.get("title", "Unknown")
    author = meta.get("author", "Unknown")

    # Extract key findings from computational results
    findings_context = _format_computational_findings(computational_results)

    excerpt = text[:max_text_chars]

    # Load the full 40-stage prompt from the reference file if available,
    # otherwise use the embedded version
    stages_text = _load_stages_template()

    prompt = f"""## TEXT BEING ANALYZED

**Title:** {title}
**Author:** {author}

{excerpt}

---

## COMPUTATIONAL PRE-ANALYSIS FINDINGS (56 tools)

{findings_context}

---

{stages_text}

Begin your analysis now."""

    return prompt


def _format_computational_findings(results: dict) -> str:
    """Format computational results into readable context for the LLM."""
    parts = []

    # Engine v2 overall score
    v2 = results.get("engine_v2", {})
    if v2:
        score = v2.get("overall_score", "N/A")
        finding_count = v2.get("finding_count", 0)
        parts.append(f"**Overall Esoteric Score: {score}** ({finding_count} findings)")

        # Module scores
        module_scores = v2.get("module_scores", {})
        if module_scores:
            scores_str = ", ".join(f"{k}: {v:.1f}" for k, v in sorted(module_scores.items(), key=lambda x: -x[1]) if v > 0)
            parts.append(f"Module scores: {scores_str}")

        # Top findings
        top = v2.get("findings", [])[:10]
        if top:
            parts.append("\n**Top Findings:**")
            for f in top:
                parts.append(f"- [{f.get('score', 0):.1f}|D:{f.get('deliberateness', 0):.1f}] {f.get('technique', '?')}: {f.get('explanation', '')[:120]}")

        # Heatmap
        heatmap = v2.get("structural_summary", {}).get("heatmap", [])
        hot = sorted(heatmap, key=lambda h: h.get("intensity", 0), reverse=True)[:5]
        if hot:
            parts.append("\n**Hottest Sections (most esoteric signals):**")
            for h in hot:
                parts.append(f"- {h.get('section', '?')}: {h.get('heat_level', '?')} ({h.get('finding_count', 0)} findings)")

    # Loud silences
    silences = results.get("loud_silences", {})
    if isinstance(silences, dict) and silences.get("silences"):
        parts.append("\n**Conspicuous Silences:**")
        for s in silences["silences"][:5]:
            parts.append(f"- '{s.get('keyword', '?')}' absent in section {s.get('section', '?')}")

    # Hedging language
    hedge = results.get("hedging_language", {})
    if isinstance(hedge, dict) and hedge.get("total_hedges", 0) > 3:
        parts.append(f"\n**Hedging Language:** {hedge['total_hedges']} instances (density: {hedge.get('hedge_density', 0)})")
        for h in hedge.get("hedges", [])[:3]:
            parts.append(f"- '{h.get('phrase', '?')}' → {h.get('context', '')[:80]}...")

    # Conditional language
    cond = results.get("conditional_language", {})
    if isinstance(cond, dict) and cond.get("total", 0) > 3:
        parts.append(f"\n**Conditional Language:** {cond['total']} instances")
        for c in cond.get("conditionals", [])[:3]:
            parts.append(f"- '{c.get('pattern', '?')}' → {c.get('sentence', '')[:80]}...")

    # Excessive praise
    praise = results.get("excessive_praise", {})
    if isinstance(praise, dict) and praise.get("total_flagged", 0) > 0:
        parts.append(f"\n**Excessive Praise ('Protesting Too Much'):** {praise['total_flagged']} sections")
        for p in praise.get("sections", [])[:3]:
            parts.append(f"- Section {p.get('section', '?')} (density: {p.get('density', 0):.4f}): {p.get('excerpt', '')[:80]}...")

    # Sentiment inversions
    inv = results.get("sentiment_inversion", {})
    if isinstance(inv, dict) and inv.get("total_inversions", 0) > 0:
        parts.append(f"\n**Sentiment Inversions:** {inv['total_inversions']} detected")
        for v in inv.get("inversions", [])[:3]:
            parts.append(f"- Sections {v.get('section_a', '?')} vs {v.get('section_b', '?')} (score: {v.get('inversion_score', 0):.3f})")

    # Lexical density
    lex = results.get("lexical_density", {})
    if isinstance(lex, dict) and lex.get("high_density_sections"):
        parts.append(f"\n**High Lexical Density (most carefully written):**")
        for d in lex["high_density_sections"][:3]:
            parts.append(f"- Section {d.get('section', '?')} (TTR: {d.get('type_token_ratio', 0):.4f}): {d.get('excerpt', '')[:60]}...")

    # Emphasis/scare quotes
    emph = results.get("emphasis_quotation", {})
    if isinstance(emph, dict) and emph.get("total_quoted", 0) > 0:
        parts.append(f"\n**Scare-Quoted Words:** {emph['total_quoted']}")
        for q in emph.get("quoted_words", [])[:5]:
            parts.append(f'- "{q.get("word", "?")}"')

    # Numerology
    num = results.get("numerology", {})
    if isinstance(num, dict) and num.get("significant_matches"):
        parts.append("\n**Numerological Patterns:**")
        for m in num["significant_matches"][:5]:
            parts.append(f"- {m.get('element', '?')}: {m.get('count', '?')} — {m.get('significance', '?')}")

    # First/last words
    fl = results.get("first_last_words", {})
    if isinstance(fl, dict):
        first = fl.get("overall_first_sentence", "")
        last = fl.get("overall_last_sentence", "")
        if first or last:
            parts.append(f"\n**Opening/Closing:**")
            if first:
                parts.append(f"- First: {first[:100]}...")
            if last:
                parts.append(f"- Last: {last[:100]}...")

    # ── Benardete Methods ──

    # Trapdoors
    trap = results.get("trapdoors", {})
    if isinstance(trap, dict) and trap.get("total_trapdoors", 0) > 0:
        parts.append(f"\n**Benardete Trapdoors:** {trap['total_trapdoors']} detected")
        for t in trap.get("hedge_near_absolute", [])[:3]:
            parts.append(f"- Hedge near absolute at sentence {t.get('sentence', '?')}: {t.get('excerpt', '')[:80]}...")
        for t in trap.get("local_contradictions", [])[:2]:
            parts.append(f"- Local contradiction: sentences {t.get('sentence_a', '?')}-{t.get('sentence_b', '?')}")
        for t in trap.get("non_sequiturs", [])[:2]:
            parts.append(f"- Non-sequitur at sentence {t.get('sentence', '?')}: {t.get('excerpt', '')[:60]}...")

    # Periagoge
    peri = results.get("periagoge", {})
    if isinstance(peri, dict) and peri.get("score", 0) > 0:
        parts.append(f"\n**Periagoge (Structural Reversal):** polarity shift={peri.get('polarity_shift', 0):.3f}")
        parts.append(f"- First half polarity: {peri.get('first_half_polarity', 0):.3f}, Second: {peri.get('second_half_polarity', 0):.3f}")
        parts.append(f"- Turning vocabulary density at center: {peri.get('turning_vocabulary_density', 0):.5f}")
        for s in peri.get("vocabulary_shifts", [])[:3]:
            parts.append(f"- '{s.get('word', '?')}' {s.get('direction', '?')} ({s.get('shift', 0):.5f})")

    # Dyadic Structure
    dyad = results.get("dyadic_structure", {})
    if isinstance(dyad, dict) and dyad.get("total_pairs", 0) > 5:
        parts.append(f"\n**Dyadic Structure:** {dyad['total_pairs']} binary pairs")
        for p in dyad.get("recurring_pairs", [])[:3]:
            parts.append(f"- {p.get('pair', '?')} × {p.get('count', 0)}")
        if dyad.get("convergences"):
            parts.append(f"- {len(dyad['convergences'])} convergences detected (conjunctive → disjunctive)")
        if dyad.get("phantom_passages"):
            parts.append(f"- {len(dyad['phantom_passages'])} phantom image passages")

    # Logos-Ergon
    le = results.get("logos_ergon", {})
    if isinstance(le, dict) and le.get("mismatch_count", 0) > 0:
        parts.append(f"\n**Logos-Ergon (Speech-Deed):** {le['mismatch_count']} mismatches, {le.get('burstlike_shifts', 0)} burstlike shifts")
        for m in le.get("mismatches", [])[:2]:
            parts.append(f"- Section {m.get('section', '?')}: speech={m.get('speech', 0):.4f} action={m.get('action', 0):.4f}")

    # Recognition Structure
    rec = results.get("recognition_structure", {})
    if isinstance(rec, dict) and rec.get("phase_densities"):
        ideal = rec.get("ideal_pattern", False)
        parts.append(f"\n**Recognition Pattern (Conceal→Test→Reveal):** {'IDEAL pattern detected' if ideal else 'non-ideal pattern'}")
        for i, label in enumerate(["First third", "Middle third", "Final third"]):
            d = rec["phase_densities"][i]
            parts.append(f"- {label}: conceal={d.get('concealment', 0):.5f} test={d.get('testing', 0):.5f} reveal={d.get('revelation', 0):.5f}")

    # Onomastic
    ono = results.get("onomastic", {})
    if isinstance(ono, dict) and ono.get("naming_passages"):
        parts.append(f"\n**Onomastic (Name-Meaning):** {len(ono['naming_passages'])} etymological passages, density={ono.get('naming_density', 0):.5f}")
        for p in ono.get("naming_passages", [])[:3]:
            parts.append(f"- {p.get('excerpt', '')[:80]}...")

    # Nomos-Physis
    np_ = results.get("nomos_physis", {})
    if isinstance(np_, dict) and np_.get("co_occurrence_count", 0) > 0:
        parts.append(f"\n**Nomos-Physis (Convention vs Nature):** {np_['co_occurrence_count']} co-occurrences")
        parts.append(f"- Nomos density: {np_.get('nomos_density', 0):.5f}, Physis: {np_.get('physis_density', 0):.5f}")

    # Impossible Arithmetic
    ia = results.get("impossible_arithmetic", {})
    if isinstance(ia, dict) and ia.get("passage_count", 0) > 0:
        parts.append(f"\n**Impossible Arithmetic (Poetic Dialectic):** {ia['passage_count']} passages, {ia.get('impossible_yet_true', 0)} 'impossible yet true'")
        for p in ia.get("passages", [])[:2]:
            parts.append(f"- Sentence {p.get('sentence', '?')}: {p.get('excerpt', '')[:80]}...")

    # Voice shifts
    vs = results.get("voice_shifts", {})
    if isinstance(vs, dict) and vs.get("total_shifts", 0) > 0:
        parts.append(f"\n**Voice/Persona Shifts:** {vs['total_shifts']} detected")

    # Register tiers
    rt = results.get("register_tiers", {})
    if isinstance(rt, dict) and rt.get("tier_distribution"):
        parts.append(f"\n**Register Tiers (Averroes):** {rt['tier_distribution']}")

    # Acrostics
    acr = results.get("acrostics", {})
    if isinstance(acr, dict) and acr.get("total_findings", 0) > 0:
        parts.append(f"\n**Acrostic Patterns:** {acr['total_findings']} findings")

    # Hapax legomena
    hap = results.get("hapax_legomena", {})
    if isinstance(hap, dict) and hap.get("philosophical_hapax"):
        parts.append(f"\n**Philosophical Hapax (words used exactly once):** {', '.join(hap['philosophical_hapax'][:10])}")

    return "\n".join(parts) if parts else "No significant computational findings."


async def run_integrated_analysis(
    text: str,
    computational_results: dict,
    metadata: Optional[dict] = None,
    provider=None,
    max_tokens: int = 8192,
) -> dict:
    """Run the full integrated analysis: computational findings → LLM 9-stage reading.

    Args:
        text: Full book text
        computational_results: Pre-computed results from run_full_esoteric_analysis + engine_v2
        metadata: Optional {title, author, genre}
        provider: LLM provider instance
        max_tokens: Max LLM output tokens

    Returns:
        dict with prompt, response, model, tokens
    """
    if provider is None:
        from app.services.llm import get_llm_provider
        provider = get_llm_provider()

    prompt = build_integrated_prompt(text, computational_results, metadata)

    resp = await provider.generate(
        INTEGRATED_SYSTEM_PROMPT,
        prompt,
        max_tokens=max_tokens,
    )

    return {
        "analysis": resp.content,
        "model": resp.model,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "total_tokens": resp.total_tokens,
        "prompt_used": prompt[:500] + "...",  # truncated for storage
        "stages": _extract_stages(resp.content),
    }


def _extract_stages(content: str) -> dict:
    """Extract individual stages from the LLM response for structured storage."""
    import re as _re
    stages = {}
    stage_pattern = r'###?\s*STAGE\s*(\d+)[:\s]*([^\n]*)\n(.*?)(?=###?\s*STAGE\s*\d+|$)'
    for match in _re.finditer(stage_pattern, content, _re.DOTALL):
        num = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3).strip()
        stages[f"stage_{num}"] = {"title": title, "content": body[:3000]}
    return stages


# ── Highlight-Based Prompts ──────────────────────────────────────────────────
# Inspired by Readwise Ghostreader — use reader's own highlights/annotations
# as the basis for targeted LLM analysis.


HIGHLIGHT_PROMPTS = {
    "esoteric_highlights": {
        "name": "Esoteric Highlight Analysis",
        "system": INTEGRATED_SYSTEM_PROMPT,
        "template": """The reader has highlighted the following passages from "{title}" by {author}.
Analyze these specific highlights through the lens of esoteric writing:

## HIGHLIGHTED PASSAGES

{highlights}

---

For each highlight:
1. Why might the reader have flagged this passage?
2. Does it contain esoteric signals (hedging, contradiction, irony, excessive praise)?
3. What is the relationship between the highlighted passage and its surrounding context?
4. Does the highlight sit at a structurally significant position (center, opening, closing)?

Then synthesize:
5. What pattern emerges across ALL the highlights taken together?
6. Do the highlights, when read as a sequence, reveal an argument not visible on the surface?
7. What passages SHOULD the reader have highlighted but didn't?""",
    },

    "socratic_questions": {
        "name": "Socratic Questions from Highlights",
        "system": "You are a Socratic interlocutor. Your role is to generate probing questions \
that challenge the reader's understanding and push toward deeper insight. Never provide answers — \
only questions that the careful reader must think through.",
        "template": """Based on these highlighted passages from "{title}" by {author}:

{highlights}

Generate 10 Socratic questions that:
1. Challenge the surface meaning of each highlight
2. Expose tensions between different highlighted passages
3. Ask what the author DIDN'T say in the vicinity of each highlight
4. Push the reader to consider why the author chose THESE specific words
5. Connect the highlights to the broader argument of the work

Format each question with the relevant highlight excerpt.""",
    },

    "contradiction_map": {
        "name": "Contradiction Map from Highlights",
        "system": "You are an expert in detecting contradictions in philosophical texts, \
following the methods of Maimonides (7th cause) and Leo Strauss.",
        "template": """The reader has highlighted these passages from "{title}" by {author}:

{highlights}

For each pair of highlights that could be in tension:
1. State the apparent contradiction
2. Is it reconcilable or genuine?
3. If genuine: which statement is more emphatic (exoteric) and which more hidden (esoteric)?
4. What does the contradiction teach us about the author's real position?
5. Does it fall under Maimonides' 5th cause (pedagogy) or 7th cause (concealment)?""",
    },

    "missing_highlights": {
        "name": "What You Missed",
        "system": "You are a careful reader trained in esoteric interpretation. The user has \
shared their highlights, but a careful reader would have noticed additional passages.",
        "template": """The reader highlighted these passages from "{title}" by {author}:

{highlights}

Now examine the FULL TEXT below and identify 5-10 passages the reader SHOULD have \
highlighted but didn't — passages that contain esoteric signals the reader may have missed:

{text}

For each missed passage:
1. Quote the exact passage
2. Explain what esoteric signal it contains
3. Explain how it relates to the passages the reader DID highlight""",
    },

    "deep_passage": {
        "name": "Deep Passage Analysis",
        "system": "You are a scholar performing a close reading in the tradition of \
Benardete's 'argument of the action' — treating every word, every dramatic detail, \
every name as philosophically significant.",
        "template": """Perform a deep close reading of this specific passage from "{title}" by {author}:

## PASSAGE

{focused_paragraph}

## SURROUNDING CONTEXT

{context}

Analyze:
1. **Every word choice** — why THIS word and not a synonym?
2. **Sentence structure** — what does the syntax do that a paraphrase would lose?
3. **Names and references** — what do they mean etymologically? What do they evoke?
4. **What is NOT said** — what would a reader expect here that the author omits?
5. **Position in the work** — where does this sit structurally? Why here?
6. **Tone and register** — is the author speaking in logos or mythos? To whom?
7. **The argument in the action** — what does this passage DO, beyond what it says?""",
    },
}


def build_highlight_prompt(
    prompt_key: str,
    title: str = "",
    author: str = "",
    highlights: list[str] = None,
    text: str = "",
    focused_paragraph: str = "",
    context: str = "",
) -> tuple[str, str]:
    """Build a highlight-based prompt.

    Returns (system_prompt, user_prompt) tuple.
    """
    if prompt_key not in HIGHLIGHT_PROMPTS:
        raise ValueError(f"Unknown prompt key: {prompt_key}. Available: {list(HIGHLIGHT_PROMPTS.keys())}")

    prompt_def = HIGHLIGHT_PROMPTS[prompt_key]
    system = prompt_def["system"]

    # Format highlights as numbered list
    formatted_highlights = ""
    if highlights:
        formatted_highlights = "\n".join(f"{i+1}. > {h}" for i, h in enumerate(highlights))

    user = prompt_def["template"].format(
        title=title or "Unknown",
        author=author or "Unknown",
        highlights=formatted_highlights,
        text=text[:8000] if text else "",
        focused_paragraph=focused_paragraph,
        context=context[:2000] if context else "",
    )

    return system, user
