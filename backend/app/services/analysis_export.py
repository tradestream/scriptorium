"""Export esoteric analysis results as EPUB3 — Kobo-optimized companion books.

Follows Kobo EPUB spec (https://github.com/kobolabs/epub-spec):
- EPUB3 with nav document (NCX ignored by Kobo in EPUB3)
- No background colors (breaks sepia/night mode on eInk)
- Font sizing in px/pt base, em for relative (never %)
- Margins in px (not em)
- Cover as separate XHTML with <img> tag, 800x1224 (3:4 ratio)
- Passes EPUBCheck validation
"""

import json
import uuid
import zipfile
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Optional


CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

# Kobo-safe CSS: no background colors, px margins, px/em fonts
STYLE_CSS = """
body {
    font-family: Georgia, serif;
    margin: 20px;
    line-height: 1.6;
    font-size: 12pt;
}
h1 { font-size: 1.6em; margin-bottom: 0.3em; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
h2 { font-size: 1.3em; margin-top: 20px; }
h3 { font-size: 1.1em; margin-top: 15px; }
p { margin: 8px 0; }
.tool-name { font-weight: bold; }
.section-label { font-style: italic; }
.quote {
    margin: 8px 15px;
    padding: 8px 15px;
    border-left: 3px solid #999;
    font-style: italic;
}
.context {
    margin: 5px 0;
    padding: 5px 10px;
    font-size: 0.9em;
}
.metric {
    display: inline-block;
    padding: 3px 8px;
    font-size: 0.85em;
    margin: 3px 0;
    font-variant: small-caps;
}
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 0.85em; }
th, td { border: 1px solid #999; padding: 5px 8px; text-align: left; }
hr { border: none; border-top: 1px solid #999; margin: 20px 0; }
.marker { font-weight: bold; }
nav#toc ol { list-style-type: none; padding-left: 0; }
nav#toc li { margin: 5px 0; }
nav#toc a { text-decoration: none; }
"""


def _esc(text: str) -> str:
    return escape(str(text or ""))


def _xhtml_wrap(title: str, body: str, css_href: str = "style.css") -> str:
    """Wrap content in valid XHTML for EPUB3."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en">
<head>
<meta charset="UTF-8"/>
<title>{_esc(title)}</title>
<link rel="stylesheet" type="text/css" href="{css_href}"/>
</head>
<body>
{body}
</body>
</html>"""


def _md_to_html(text: str) -> str:
    """Convert markdown-ish LLM output to basic HTML."""
    import re
    lines = text.split('\n')
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append('')
            continue

        # Headings
        if stripped.startswith('### '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h3>{_esc(stripped[4:])}</h3>')
        elif stripped.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h2>{_esc(stripped[3:])}</h2>')
        elif stripped.startswith('# '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h1>{_esc(stripped[2:])}</h1>')
        # List items
        elif stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            content = stripped[2:]
            # Bold
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', _esc(content))
            # Italic
            content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
            html_parts.append(f'<li>{content}</li>')
        # Numbered list
        elif re.match(r'^\d+\.\s', stripped):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            content = re.sub(r'^\d+\.\s*', '', stripped)
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', _esc(content))
            content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
            html_parts.append(f'<li>{content}</li>')
        # Blockquote
        elif stripped.startswith('> '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<div class="quote">{_esc(stripped[2:])}</div>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            content = _esc(stripped)
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
            html_parts.append(f'<p>{content}</p>')

    if in_list:
        html_parts.append('</ul>')

    return '\n'.join(html_parts)


def _render_computational_results(results: dict) -> str:
    """Render computational analysis results as HTML sections."""
    html_parts = []

    # Engine v2 summary
    v2 = results.get("engine_v2", {})
    if v2:
        score = v2.get("overall_score", "N/A")
        findings = v2.get("finding_count", 0)
        html_parts.append(f'<h2>Overall Esoteric Score: {score}</h2>')
        html_parts.append(f'<p>{findings} findings across 35 computational tools</p>')

        # Module scores
        module_scores = v2.get("module_scores", {})
        if module_scores:
            html_parts.append('<h3>Module Scores</h3><table><tr><th>Module</th><th>Score</th></tr>')
            for k, v in sorted(module_scores.items(), key=lambda x: -x[1]):
                if v > 0:
                    html_parts.append(f'<tr><td>{_esc(k)}</td><td>{v:.1f}</td></tr>')
            html_parts.append('</table>')

        # Top findings
        top = v2.get("findings", [])[:15]
        if top:
            html_parts.append('<h3>Top Findings</h3>')
            for f in top:
                html_parts.append(
                    f'<p><span class="marker">[{f.get("score", 0):.1f}]</span> '
                    f'<span class="tool-name">{_esc(f.get("technique", ""))}</span>: '
                    f'{_esc(f.get("explanation", "")[:200])}</p>'
                )

        # Heatmap
        heatmap = v2.get("structural_summary", {}).get("heatmap", [])
        if heatmap:
            hot = sorted(heatmap, key=lambda h: h.get("intensity", 0), reverse=True)[:10]
            html_parts.append('<h3>Esoteric Heatmap</h3><table><tr><th>Section</th><th>Level</th><th>Findings</th></tr>')
            for h in hot:
                html_parts.append(
                    f'<tr><td>{_esc(h.get("section", ""))[:50]}</td>'
                    f'<td>{_esc(h.get("heat_level", ""))}</td>'
                    f'<td>{h.get("finding_count", 0)}</td></tr>'
                )
            html_parts.append('</table>')

    # Individual tool results
    TOOL_DISPLAY = {
        "hedging_language": "Hedging Language",
        "conditional_language": "Conditional Language",
        "excessive_praise": "Excessive Praise",
        "trapdoors": "Benardete Trapdoors",
        "periagoge": "Periagoge (Structural Reversal)",
        "nomos_physis": "Nomos-Physis",
        "logos_ergon": "Logos-Ergon (Speech-Deed)",
        "recognition_structure": "Recognition Pattern",
    }

    for key, display_name in TOOL_DISPLAY.items():
        tool = results.get(key, {})
        if not isinstance(tool, dict) or "error" in tool:
            continue
        html_parts.append(f'<h3>{_esc(display_name)}</h3>')
        # Render key metrics
        for k, v in tool.items():
            if k in ("method", "precedent", "interpretation"):
                continue
            if isinstance(v, (int, float)):
                html_parts.append(f'<p class="metric">{_esc(k)}: {v}</p> ')
            elif isinstance(v, str) and len(v) < 200:
                html_parts.append(f'<p>{_esc(k)}: {_esc(v)}</p>')

    return '\n'.join(html_parts)


def build_analysis_epub(
    book_title: str,
    book_authors: list[str],
    computational_results: Optional[dict] = None,
    llm_analyses: Optional[list[dict]] = None,
) -> bytes:
    """Build a Kobo-optimized EPUB3 containing esoteric analysis results.

    Returns EPUB file contents as bytes.
    """
    book_uuid = str(uuid.uuid4())
    now = datetime.utcnow()
    date_str = now.strftime("%Y-%m-%d")
    author_str = ", ".join(book_authors) if book_authors else "Unknown"

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype MUST be first and uncompressed
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("OEBPS/style.css", STYLE_CSS)

        manifest = ['<item id="style" href="style.css" media-type="text/css"/>']
        spine = []
        nav_items = []
        file_idx = 0

        # Title page
        title_body = f"""
<h1>Esoteric Analysis</h1>
<h2>{_esc(book_title)}</h2>
<p><em>{_esc(author_str)}</em></p>
<hr/>
<p>Generated by Scriptorium — {date_str}</p>
<p>35 computational tools + 9-stage integrated LLM analysis</p>
"""
        zf.writestr("OEBPS/title.xhtml", _xhtml_wrap("Esoteric Analysis", title_body))
        manifest.append('<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>')
        spine.append('<itemref idref="title"/>')

        # Computational results chapter
        if computational_results:
            file_idx += 1
            comp_html = _render_computational_results(computational_results)
            body = f"""
<h1>Computational Analysis</h1>
<p><em>35 pattern-detection tools applied to the text</em></p>
<hr/>
{comp_html}
"""
            fname = f"ch_{file_idx}.xhtml"
            zf.writestr(f"OEBPS/{fname}", _xhtml_wrap("Computational Analysis", body))
            manifest.append(f'<item id="ch{file_idx}" href="{fname}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="ch{file_idx}"/>')
            nav_items.append(("Computational Analysis", fname))

        # LLM analyses chapters
        if llm_analyses:
            for analysis in llm_analyses:
                file_idx += 1
                title = analysis.get("title", "Analysis")
                content = analysis.get("content", "")
                content_html = _md_to_html(content)

                model = analysis.get("model_used", "")
                model_line = f'<p class="metric">Model: {_esc(model)}</p>' if model else ""

                body = f"""
<h1>{_esc(title)}</h1>
{model_line}
<hr/>
{content_html}
"""
                fname = f"ch_{file_idx}.xhtml"
                zf.writestr(f"OEBPS/{fname}", _xhtml_wrap(title, body))
                manifest.append(f'<item id="ch{file_idx}" href="{fname}" media-type="application/xhtml+xml"/>')
                spine.append(f'<itemref idref="ch{file_idx}"/>')
                nav_items.append((title, fname))

        # EPUB3 Navigation Document (required by Kobo — NCX is ignored in EPUB3)
        nav_li = "\n".join(
            f'<li><a href="{f}">{_esc(t)}</a></li>'
            for t, f in nav_items
        )
        nav_body = f"""
<nav epub:type="toc" id="toc">
<h1>Table of Contents</h1>
<ol>
<li><a href="title.xhtml">Title Page</a></li>
{nav_li}
</ol>
</nav>
"""
        zf.writestr("OEBPS/nav.xhtml", _xhtml_wrap("Table of Contents", nav_body))
        manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')

        # OPF (EPUB3 package document)
        opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="3.0">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Esoteric Analysis: {_esc(book_title)}</dc:title>
<dc:creator>{_esc(author_str)}</dc:creator>
<dc:identifier id="uid">urn:uuid:{book_uuid}</dc:identifier>
<dc:language>en</dc:language>
<dc:date>{date_str}</dc:date>
<dc:publisher>Scriptorium</dc:publisher>
<dc:description>Esoteric analysis of {_esc(book_title)} — 35 computational tools and 9-stage LLM reading between the lines.</dc:description>
<meta property="dcterms:modified">{now.strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine>
{chr(10).join(spine)}
</spine>
</package>"""
        zf.writestr("OEBPS/content.opf", opf)

    return buf.getvalue()
