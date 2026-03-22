"""Export esoteric analysis results as EPUB — readable companion books for e-readers."""

import json
import uuid
import zipfile
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Optional


CONTAINER_XML = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

STYLE_CSS = """
body { font-family: Georgia, serif; margin: 1em; line-height: 1.6; color: #222; }
h1 { font-size: 1.6em; margin-bottom: 0.3em; border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }
h2 { font-size: 1.3em; margin-top: 1.5em; color: #333; }
h3 { font-size: 1.1em; margin-top: 1.2em; color: #555; }
.tool-name { font-weight: bold; color: #1a5276; }
.section-label { font-style: italic; color: #666; }
.quote { margin: 0.5em 1em; padding: 0.5em 1em; border-left: 3px solid #d4a574; background: #faf6f1; font-style: italic; }
.context { margin: 0.3em 0; padding: 0.4em 0.8em; background: #f5f5f5; border-radius: 4px; font-size: 0.9em; }
.metric { display: inline-block; padding: 0.2em 0.6em; background: #e8e8e8; border-radius: 3px; font-size: 0.85em; margin: 0.2em 0; }
.high { background: #dcfce7; color: #166534; }
.medium { background: #fef9c3; color: #854d0e; }
.low { background: #fee2e2; color: #991b1b; }
table { border-collapse: collapse; width: 100%; margin: 0.5em 0; font-size: 0.85em; }
th, td { border: 1px solid #ddd; padding: 0.4em 0.6em; text-align: left; }
th { background: #f0f0f0; }
hr { border: none; border-top: 1px solid #ddd; margin: 1.5em 0; }
.marker { font-weight: bold; color: #b45309; }
.toc a { text-decoration: none; color: #1a5276; }
.toc li { margin: 0.3em 0; }
"""


def _esc(text: str) -> str:
    return escape(str(text or ""))


def _render_computational_results(results: dict) -> str:
    """Render computational analysis results as HTML sections."""
    html_parts = []

    # Loud Silences
    silences = results.get("loud_silences", {})
    if silences and not silences.get("error"):
        html_parts.append("<h2>Loud Silences</h2>")
        for s in silences.get("silences", [])[:10]:
            html_parts.append(
                f'<p><span class="marker">{_esc(s["keyword"])}</span> '
                f'silent in <span class="section-label">{_esc(s["section"])}</span> '
                f'(expected avg: {s.get("expected_avg", 0):.1f}, actual: {s.get("actual", 0)})</p>'
            )

    # Center
    center = results.get("centers", {})
    if center and not center.get("error") and center.get("center_passage"):
        html_parts.append("<h2>Structural Center</h2>")
        html_parts.append(f'<div class="quote">{_esc(center["center_passage"][:500])}</div>')

    # Exoteric/Esoteric Ratio
    ratio = results.get("exoteric_esoteric_ratio", {})
    if ratio and not ratio.get("error"):
        html_parts.append("<h2>Exoteric/Esoteric Ratio</h2>")
        html_parts.append(f'<p>Overall: {ratio.get("overall_pious", 0)} pious / {ratio.get("overall_subversive", 0)} subversive</p>')
        for f in ratio.get("flagged_sections", [])[:5]:
            html_parts.append(f'<p><span class="section-label">{_esc(f["section_label"])}</span>: {", ".join(f.get("reasons", []))}</p>')

    # Audience Differentiation
    aud = results.get("audience_differentiation", {})
    if aud and not aud.get("error"):
        html_parts.append("<h2>Audience Differentiation</h2>")
        html_parts.append(f'<p class="metric">Score: {aud.get("differentiation_score", 0)}</p>')
        for ref in aud.get("elite_references", [])[:5]:
            html_parts.append(f'<p>Elite: "<span class="marker">{_esc(ref["marker"])}</span>" — {_esc(ref.get("context", "")[:150])}</p>')
        for ref in aud.get("mass_references", [])[:5]:
            html_parts.append(f'<p>Mass: "<span class="marker">{_esc(ref["marker"])}</span>" — {_esc(ref.get("context", "")[:150])}</p>')

    # Hedging Language
    hedge = results.get("hedging_language", {})
    if hedge and not hedge.get("error") and hedge.get("total_hedges", 0) > 0:
        html_parts.append("<h2>Hedging Language</h2>")
        html_parts.append(f'<p class="metric">Density: {hedge.get("hedge_density", 0)}/1000 words ({hedge.get("total_hedges", 0)} total)</p>')
        for h in hedge.get("hedges", [])[:8]:
            html_parts.append(f'<p>"<span class="marker">{_esc(h["phrase"])}</span>" — <span class="context">{_esc(h.get("context", "")[:150])}</span></p>')

    # Self-Reference
    selfref = results.get("self_reference", {})
    if selfref and not selfref.get("error") and selfref.get("total", 0) > 0:
        html_parts.append("<h2>Self-Reference (Meta-Esoteric)</h2>")
        html_parts.append(f'<p class="metric">Meta-esoteric score: {selfref.get("meta_esoteric_score", 0)}</p>')

    # First/Last Words
    fl = results.get("first_last_words", {})
    if fl and not fl.get("error"):
        html_parts.append("<h2>First &amp; Last Words</h2>")
        oc = fl.get("opening_closing_words", {})
        html_parts.append(f'<p>First word: <strong>{_esc(oc.get("first_word", ""))}</strong> | '
                          f'Last word: <strong>{_esc(oc.get("last_word", ""))}</strong></p>')
        if fl.get("overall_first_sentence"):
            html_parts.append(f'<p><em>Opening:</em> {_esc(fl["overall_first_sentence"][:200])}</p>')
        if fl.get("overall_last_sentence"):
            html_parts.append(f'<p><em>Closing:</em> {_esc(fl["overall_last_sentence"][:200])}</p>')

    # Epigraphs
    epi = results.get("epigraph", {})
    if epi and not epi.get("error") and epi.get("total", 0) > 0:
        html_parts.append("<h2>Epigraphs</h2>")
        for e in epi.get("epigraphs", []):
            html_parts.append(f'<div class="quote">{_esc(e.get("text", ""))}<br/>— {_esc(e.get("attribution", ""))}</div>')

    # Repetition with Variation
    rep = results.get("repetition_variation", {})
    if rep and not rep.get("error"):
        phrases = rep.get("repeated_phrases", [])
        if phrases:
            html_parts.append("<h2>Repetition with Variation</h2>")
            for r in phrases[:5]:
                html_parts.append(f'<p><span class="marker">{_esc(r["keyword"])}</span>: '
                                  f'{r["occurrence_count"]} occurrences, varying: {", ".join(r.get("varying_words", [])[:5])}</p>')

    # Disreputable Mouthpieces
    mouth = results.get("disreputable_mouthpiece", {})
    if mouth and not mouth.get("error"):
        speakers = mouth.get("speakers", [])
        if speakers:
            html_parts.append("<h2>Disreputable Mouthpieces</h2>")
            for s in speakers[:8]:
                html_parts.append(f'<p><span class="marker">{_esc(s["speaker"])}</span>: {s["count"]} mentions</p>')

    # Section Proportions
    prop = results.get("section_proportion", {})
    if prop and not prop.get("error"):
        short_dense = prop.get("short_dense_sections", [])
        if short_dense:
            html_parts.append("<h2>Short but Dense Sections</h2>")
            html_parts.append("<p><em>Per Strauss: the rare/brief statement is the true one.</em></p>")
            for s in short_dense:
                html_parts.append(f'<p><span class="section-label">{_esc(s["label"])}</span>: {_esc(s.get("reason", ""))}</p>')

    return "\n".join(html_parts)


def build_analysis_epub(
    book_title: str,
    book_authors: list[str],
    computational_results: Optional[dict] = None,
    llm_analyses: Optional[list[dict]] = None,
) -> bytes:
    """Build an EPUB containing esoteric analysis results.

    Returns EPUB file contents as bytes.
    """
    book_uuid = str(uuid.uuid4())
    now = datetime.utcnow()
    date_str = now.strftime("%Y-%m-%d")
    author_str = ", ".join(book_authors) if book_authors else "Unknown"

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("style.css", STYLE_CSS)

        manifest = ['<item id="style" href="style.css" media-type="text/css"/>']
        spine = []
        toc_entries = []
        file_idx = 0

        # Title page
        title_html = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Esoteric Analysis</title><link rel="stylesheet" href="style.css"/></head>
<body>
<h1>Esoteric Analysis</h1>
<h2>{_esc(book_title)}</h2>
<p>{_esc(author_str)}</p>
<p><em>Generated by Scriptorium — {date_str}</em></p>
<p><em>15 LLM templates, 16 computational tools</em></p>
<hr/>
</body></html>"""
        zf.writestr("title.xhtml", title_html)
        manifest.append('<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>')
        spine.append('<itemref idref="title"/>')

        # Computational results chapter
        if computational_results:
            file_idx += 1
            comp_html = _render_computational_results(computational_results)
            page = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Computational Analysis</title><link rel="stylesheet" href="style.css"/></head>
<body>
<h1>Computational Analysis</h1>
<p><em>16 pattern-detection tools applied to the text</em></p>
<hr/>
{comp_html}
</body></html>"""
            fname = f"ch_{file_idx}.xhtml"
            zf.writestr(fname, page)
            manifest.append(f'<item id="ch{file_idx}" href="{fname}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="ch{file_idx}"/>')
            toc_entries.append(("Computational Analysis", fname))

        # LLM analyses chapters
        if llm_analyses:
            for analysis in llm_analyses:
                file_idx += 1
                title = analysis.get("title", "Analysis")
                content = analysis.get("content", "")
                # Convert markdown-ish content to basic HTML
                content_html = _esc(content).replace("\n\n", "</p><p>").replace("\n", "<br/>")
                content_html = f"<p>{content_html}</p>"

                page = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{_esc(title)}</title><link rel="stylesheet" href="style.css"/></head>
<body>
<h1>{_esc(title)}</h1>
{content_html}
</body></html>"""
                fname = f"ch_{file_idx}.xhtml"
                zf.writestr(fname, page)
                manifest.append(f'<item id="ch{file_idx}" href="{fname}" media-type="application/xhtml+xml"/>')
                spine.append(f'<itemref idref="ch{file_idx}"/>')
                toc_entries.append((title, fname))

        # NCX
        nav_points = "\n".join(
            f'<navPoint id="np_{i}" playOrder="{i+1}"><navLabel><text>{_esc(t)}</text></navLabel><content src="{f}"/></navPoint>'
            for i, (t, f) in enumerate(toc_entries)
        )
        ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="{book_uuid}"/></head>
<docTitle><text>Esoteric Analysis: {_esc(book_title)}</text></docTitle>
<navMap>{nav_points}</navMap></ncx>"""
        zf.writestr("toc.ncx", ncx)
        manifest.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')

        # OPF
        opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="2.0">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Esoteric Analysis: {_esc(book_title)}</dc:title>
<dc:creator>{_esc(author_str)}</dc:creator>
<dc:identifier id="uid">{book_uuid}</dc:identifier>
<dc:language>en</dc:language>
<dc:date>{now.isoformat()}</dc:date>
<dc:publisher>Scriptorium</dc:publisher>
<dc:description>Esoteric analysis of {_esc(book_title)} — computational pattern detection and LLM-powered reading between the lines.</dc:description>
</metadata>
<manifest>{chr(10).join(manifest)}</manifest>
<spine toc="ncx">{chr(10).join(spine)}</spine>
</package>"""
        zf.writestr("content.opf", opf)

    return buf.getvalue()
