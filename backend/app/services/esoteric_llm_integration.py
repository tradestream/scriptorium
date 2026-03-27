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
drawing on the methods of Leo Strauss ("Persecution and the Art of Writing"), Arthur Melzer \
("Philosophy Between the Lines"), and the broader tradition including Maimonides, Al-Farabi, \
Francis Bacon, Clement of Alexandria, and the Pythagorean/Kabbalistic numerological traditions.

You have been provided with COMPUTATIONAL PRE-ANALYSIS findings. These are starting points, \
not conclusions. Your task is to perform a deep esoteric reading guided by these findings \
but going far beyond them.

IMPORTANT METHODOLOGICAL NOTES:
- You are looking for DELIBERATE concealment by a skilled author, not random noise.
- Not every text is esoteric. If the evidence is weak, say so.
- Esoteric reading is "a form of rhetoric" (Melzer), not a mechanical procedure.
- The computational findings are STARTING POINTS, not conclusions.
- The literal surface reading is the FOUNDATION (per Melzer: take the surface with extreme seriousness).
- Your goal is to help the reader see what a careful, historically informed reader would see."""


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

    prompt = f"""## TEXT BEING ANALYZED

**Title:** {title}
**Author:** {author}

{excerpt}

---

## COMPUTATIONAL PRE-ANALYSIS FINDINGS

{findings_context}

---

## YOUR TASK: 9-STAGE ESOTERIC ANALYSIS

### STAGE 1: LITERAL SURFACE READING
Describe the text's apparent (exoteric) argument — what it seems to say on the surface. \
What is its declared subject, stated thesis, overt conclusions? Who is the apparent intended audience?

### STAGE 2: CONTRADICTION ANALYSIS
Examine the computationally flagged contradictions and sentiment inversions above. For each:
- Is this a genuine contradiction, or can it be harmonized?
- If genuine: which statement is more emphatic/public, and which is more hidden/qualified?
- Per Strauss: the less emphatic, more hidden statement is likelier to represent the author's true view.
- Does this fall under Maimonides' 5th cause (pedagogical simplification) or 7th cause (necessary concealment)?

### STAGE 3: STRUCTURAL ANALYSIS
Examine the text's architecture using the computational findings:
- What is placed at the STRUCTURAL CENTER?
- Does it exhibit RING or CHIASTIC structure?
- Are there numerologically significant structural features?
- Which sections have the highest lexical density (most carefully written)?

### STAGE 4: SILENCE AND OMISSION
Based on the loud silence detector findings:
- Why might the author have omitted flagged topics?
- Does the silence constitute a "negative argument"?

### STAGE 5: IRONY AND INDIRECT COMMUNICATION
Using the hedging language, conditional language, and excessive praise findings:
- Where does the author hedge on central claims?
- Where does emphatic praise suggest "protesting too much"?
- Are there passages where qualifier-to-assertion ratio is unusually high?

### STAGE 6: DIGRESSIONS AND SCATTERED ARGUMENTS
Using the structural obscurity findings:
- Do flagged digressions carry content that, when reassembled (per Maimonides), yields a hidden argument?
- Are digressions at structurally significant locations?

### STAGE 7: SOURCE AND AUTHORITY ANALYSIS
Using the emphasis/quotation and parenthetical findings:
- What words does the author put in scare quotes or italics?
- What do parenthetical asides reveal when isolated from their context?
- Are cited authorities being used sincerely or subversively?

### STAGE 8: THE ESOTERIC ARGUMENT
Reconstruct the text's esoteric teaching:
1. **The exoteric teaching** (what the text appears to say)
2. **The esoteric teaching** (what it actually communicates to the careful reader)
3. **The methods of concealment** (which techniques, citing historical precedent)
4. **The evidence** (specific textual passages)
5. **The motive** (defensive, protective, pedagogical, or political esotericism per Melzer)
6. **Confidence level** (how strong is the case?)

### STAGE 9: SAFEGUARDS AGAINST OVER-READING
Critically evaluate your own esoteric reading:
- Does it produce a MORE coherent interpretation than the surface reading?
- Is the evidence convergent (multiple methods pointing to the same conclusion)?
- Could the patterns be explained by accident, editorial history, or genre conventions?
- What would DISPROVE your esoteric reading?

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
    stages = {}
    stage_pattern = r'###?\s*STAGE\s*(\d+)[:\s]*([^\n]*)\n(.*?)(?=###?\s*STAGE\s*\d+|$)'
    for match in __import__('re').finditer(stage_pattern, content, __import__('re').DOTALL):
        num = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3).strip()
        stages[f"stage_{num}"] = {"title": title, "content": body[:2000]}
    return stages
