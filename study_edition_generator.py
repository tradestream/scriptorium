"""
Study Edition Generator
=======================

Generates study editions of philosophical and "Great Books" texts in EPUB and PDF format,
modeled on the Revised New Jerusalem Bible Study Edition structure.

Features:
- Book/chapter/section introductions
- Inline cross-references [bracketed, linked]
- Footnote annotations (letter-keyed, linked back-and-forth)
- Section headers and subheaders
- Thematic essays (appended or interleaved)
- Integration with EsotericAnalyzer for automated commentary layer
- EPUB 3 output with proper navigation
- PDF output via WeasyPrint

Usage:
    from study_edition_generator import StudyEdition

    edition = StudyEdition(
        title="Plato's Republic",
        author="Plato",
        editor="Your Name",
        subtitle="A Study Edition with Esoteric Commentary",
    )

    # Add a book/part introduction
    edition.add_introduction("The Republic", "Plato's *Republic* is the founding...")

    # Add chapters with text, footnotes, and cross-references
    ch = edition.add_chapter("Book I", "On Justice")
    ch.add_section_header("Socrates and Cephalus (327a-331d)")
    ch.add_paragraph(
        "I went down yesterday to the Piraeus with Glaucon...",
        footnotes={"a": "The descent to the Piraeus mirrors the descent into the Cave (514a)."},
        cross_refs=["Rep 514a", "Phd 59d"],
    )

    # Add a thematic essay
    edition.add_essay("The Dramatic Setting", "The Republic's opening scene...")

    # Auto-generate esoteric commentary from the analyzer
    edition.generate_esoteric_commentary(text, analyzer_results)

    # Export
    edition.export_epub("republic_study.epub")
    edition.export_pdf("republic_study.pdf")
"""

import os
import re
import uuid
import html
import textwrap
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class Footnote:
    """A single footnote annotation."""
    key: str            # e.g. "a", "b", "c"
    text: str           # The footnote content (may contain HTML)
    anchor_id: str = "" # Auto-generated

@dataclass
class CrossRef:
    """A cross-reference to another passage."""
    label: str          # e.g. "Rep 514a", "Gn 1:1"
    target_id: str = "" # Internal link target (if available)

@dataclass
class Paragraph:
    """A paragraph of text with optional annotations."""
    text: str
    footnotes: list = field(default_factory=list)      # List of Footnote
    cross_refs: list = field(default_factory=list)      # List of CrossRef
    css_class: str = "indent"
    paragraph_num: Optional[int] = None
    section_num: Optional[str] = None  # e.g. "331d" for Stephanus numbers

@dataclass
class SectionHeader:
    """An inline section/subheader within a chapter."""
    title: str
    level: int = 1  # 1 = main header, 2 = subheader

@dataclass
class SidebarEssay:
    """A short sidebar essay embedded inline within a chapter (JANT-style).

    In the JANT, these appear as indented blockquote sections between verses,
    with bold titles, providing focused commentary on a specific topic.
    """
    title: str
    content: str          # May contain paragraphs separated by \\n\\n
    sidebar_id: str = ""

    def __post_init__(self):
        if not self.sidebar_id:
            self.sidebar_id = re.sub(r'[^a-zA-Z0-9]', '_', self.title.lower())[:30]

@dataclass
class TextualNote:
    """A textual/translation note (JANT-style asterisk annotations).

    These form a second tier of annotation distinct from the letter-keyed
    footnotes. In the JANT, they are marked with * and link to brief
    variant readings or translation alternatives.
    """
    text: str             # e.g. "Or 'birth'"
    anchor_id: str = ""

@dataclass
class Chapter:
    """A chapter containing paragraphs, headers, footnotes."""
    title: str
    subtitle: str = ""
    introduction: str = ""
    elements: list = field(default_factory=list)  # Paragraphs, SectionHeaders, etc.
    footnote_counter: int = 0
    chapter_id: str = ""

    def __post_init__(self):
        if not self.chapter_id:
            self.chapter_id = re.sub(r'[^a-zA-Z0-9]', '_', self.title.lower())[:30]

    def add_paragraph(self, text: str, footnotes: dict = None,
                      cross_refs: list = None, section_num: str = None,
                      css_class: str = "indent") -> Paragraph:
        """Add a paragraph with optional footnotes and cross-references."""
        fn_list = []
        if footnotes:
            for key, fn_text in footnotes.items():
                self.footnote_counter += 1
                fn = Footnote(
                    key=key,
                    text=fn_text,
                    anchor_id=f"{self.chapter_id}_fn{self.footnote_counter}",
                )
                fn_list.append(fn)

        cr_list = []
        if cross_refs:
            for ref in cross_refs:
                cr_list.append(CrossRef(label=ref))

        para = Paragraph(
            text=text,
            footnotes=fn_list,
            cross_refs=cr_list,
            css_class=css_class,
            section_num=section_num,
        )
        self.elements.append(para)
        return para

    def add_section_header(self, title: str, level: int = 1) -> SectionHeader:
        """Add a section header within the chapter."""
        sh = SectionHeader(title=title, level=level)
        self.elements.append(sh)
        return sh

    def add_sidebar_essay(self, title: str, content: str) -> SidebarEssay:
        """Add a JANT-style sidebar essay embedded inline within the chapter.

        Sidebar essays appear as indented blockquote sections between
        paragraphs, with bold titles. They provide focused commentary on
        a specific topic relevant to the surrounding text.
        """
        sb = SidebarEssay(title=title, content=content)
        self.elements.append(sb)
        return sb

    def add_paragraph_with_notes(self, text: str, footnotes: dict = None,
                                 textual_notes: list = None,
                                 cross_refs: list = None,
                                 section_num: str = None,
                                 css_class: str = "indent") -> Paragraph:
        """Add a paragraph with both letter-keyed footnotes AND asterisk textual notes.

        textual_notes: list of strings, e.g. ["Or 'birth'", "Other MSS read 'Christ'"]
        Each becomes a * (or **, ***) superscript linked to the note.
        """
        # Build textual notes as Footnote objects with * keys
        combined_footnotes = {}
        if footnotes:
            combined_footnotes.update(footnotes)

        if textual_notes:
            for i, note_text in enumerate(textual_notes):
                key = "*" * (i + 1)  # *, **, ***
                combined_footnotes[key] = note_text

        return self.add_paragraph(
            text=text,
            footnotes=combined_footnotes,
            cross_refs=cross_refs,
            section_num=section_num,
            css_class=css_class,
        )

    def add_raw_html(self, html_content: str):
        """Add raw HTML content (for special formatting)."""
        self.elements.append(('raw_html', html_content))

@dataclass
class Essay:
    """A thematic essay included in the study apparatus."""
    title: str
    content: str  # HTML or markdown-like content
    author: str = ""      # JANT-style: essays have named authors
    essay_id: str = ""

    def __post_init__(self):
        if not self.essay_id:
            self.essay_id = re.sub(r'[^a-zA-Z0-9]', '_', self.title.lower())[:30]


# ---------------------------------------------------------------------------
# STUDY EDITION
# ---------------------------------------------------------------------------

class StudyEdition:
    """
    Main class for generating study editions in EPUB and PDF format.
    """

    def __init__(self, title: str, author: str, editor: str = "",
                 subtitle: str = "", language: str = "en"):
        self.title = title
        self.author = author
        self.editor = editor
        self.subtitle = subtitle
        self.language = language
        self.uid = str(uuid.uuid4())
        self.date = datetime.now().strftime("%Y-%m-%d")

        self.general_introduction = ""
        self.chapters: list[Chapter] = []
        self.essays: list[Essay] = []
        self.abbreviations: dict[str, str] = {}
        self.bibliography: list[str] = []

    # ------------------------------------------------------------------
    # CONTENT BUILDING
    # ------------------------------------------------------------------

    def set_general_introduction(self, text: str):
        """Set the general introduction for the entire edition."""
        self.general_introduction = text

    def add_chapter(self, title: str, subtitle: str = "",
                    introduction: str = "") -> Chapter:
        """Add a chapter and return it for further population."""
        ch = Chapter(title=title, subtitle=subtitle, introduction=introduction)
        self.chapters.append(ch)
        return ch

    def add_essay(self, title: str, content: str, author: str = "") -> Essay:
        """Add a thematic essay (JANT-style: optionally with named author)."""
        essay = Essay(title=title, content=content, author=author)
        self.essays.append(essay)
        return essay

    def add_abbreviation(self, abbr: str, full: str):
        """Add an abbreviation to the abbreviations list."""
        self.abbreviations[abbr] = full

    def add_bibliography_entry(self, entry: str):
        """Add a bibliography entry."""
        self.bibliography.append(entry)

    # ------------------------------------------------------------------
    # AUTOMATIC COMMENTARY FROM ESOTERIC ANALYZER
    # ------------------------------------------------------------------

    def generate_esoteric_commentary(self, analyzer_results: dict) -> Chapter:
        """
        Generate a commentary chapter from EsotericAnalyzer results.
        Returns the generated Chapter for further customization.
        """
        ch = Chapter(
            title="Esoteric Analysis Commentary",
            subtitle="Computational findings from the 25-method esoteric analyzer",
            introduction=(
                "The following commentary has been generated by computational analysis "
                "using methods derived from the tradition of esoteric interpretation: "
                "Strauss, Melzer, Maimonides, Al-Farabi, Benardete, and others. "
                "These findings are starting points for interpretation, not conclusions."
            ),
        )

        score = analyzer_results.get('composite_esoteric_score', 0)
        interp = analyzer_results.get('score_interpretation', '')
        ch.add_section_header("Composite Score", level=1)
        ch.add_paragraph(
            f"Composite Esoteric Score: {score} — {interp}",
            css_class="indent",
        )

        analyses = analyzer_results.get('analyses', {})

        # Group methods by category
        method_groups = {
            'Straussian Core': ['contradiction', 'central_placement', 'silence', 'repetition'],
            'Structural': ['symmetry', 'numerology', 'digression', 'lexical_density'],
            'Stylistic': ['irony', 'voice_consistency', 'register', 'logos_mythos',
                          'polysemy', 'aphoristic_fragmentation'],
            'Steganographic': ['acrostic', 'hapax_legomena'],
            'Benardete Methods': ['trapdoor', 'dyadic_structure', 'periagoge',
                                  'logos_ergon', 'onomastic', 'recognition_structure',
                                  'nomos_physis', 'impossible_arithmetic'],
            'Intertextual': ['commentary_divergence'],
        }

        for group_name, method_keys in method_groups.items():
            group_methods = [(k, analyses[k]) for k in method_keys if k in analyses]
            if not group_methods:
                continue

            ch.add_section_header(group_name, level=1)

            for key, data in group_methods:
                method_name = data.get('method', key)
                method_score = data.get('score', 0)
                precedent = data.get('precedent', '')
                interpretation = data.get('interpretation', '')

                ch.add_section_header(f"{method_name} (Score: {method_score})", level=2)

                if precedent:
                    ch.add_paragraph(
                        f"Precedent: {precedent}",
                        css_class="indent",
                    )

                if interpretation and method_score > 0.1:
                    ch.add_paragraph(interpretation, css_class="indent")

                # Add specific findings based on method type
                self._add_method_findings(ch, key, data)

        self.chapters.append(ch)
        return ch

    def _add_method_findings(self, ch: Chapter, key: str, data: dict):
        """Add specific findings from a method to a chapter."""
        if key == 'contradiction' and data.get('contradictions'):
            for c in data['contradictions'][:5]:
                ch.add_paragraph(
                    f"Contradiction detected: \"{c.get('sentence_a', '')[:100]}...\" vs. "
                    f"\"{c.get('sentence_b', '')[:100]}...\" (similarity: {c.get('similarity', 0)})",
                    css_class="indent",
                )
        elif key == 'trapdoor':
            for td in data.get('hedge_near_absolute', [])[:3]:
                ch.add_paragraph(
                    f"Trapdoor — Hedged absolute: \"{td.get('text', '')[:150]}...\"",
                    css_class="indent",
                )
        elif key == 'dyadic_structure':
            for rp in data.get('recurring_pairs', [])[:5]:
                ch.add_paragraph(
                    f"Binary pair: {rp.get('pair', ['?','?'])[0]}/{rp.get('pair', ['?','?'])[1]} ({rp.get('count', 0)}x)",
                    css_class="indent",
                )
        elif key == 'logos_ergon':
            for mm in data.get('mismatches', [])[:3]:
                ch.add_paragraph(
                    f"Speech-deed mismatch (para {mm.get('paragraph_index', '?')}): "
                    f"speech={mm.get('speech_density', 0)}, action={mm.get('action_density', 0)}",
                    css_class="indent",
                )
        elif key == 'onomastic':
            top_names = data.get('top_proper_nouns', [])[:10]
            if top_names:
                names_str = ", ".join(f"{n[0]} ({n[1]}x)" for n in top_names)
                ch.add_paragraph(f"Key names: {names_str}", css_class="indent")
        elif key == 'recognition_structure':
            if data.get('ideal_pattern_detected'):
                ch.add_paragraph(
                    "Ideal concealment→test→reveal pattern DETECTED across text thirds.",
                    css_class="indent",
                )
        elif key == 'nomos_physis':
            ch.add_paragraph(
                f"Convention (nomos) density: {data.get('nomos_density', 0)}, "
                f"Nature (physis) density: {data.get('physis_density', 0)}, "
                f"Co-occurrences: {data.get('co_occurrence_count', 0)}",
                css_class="indent",
            )

    # ------------------------------------------------------------------
    # IMPORT FROM PLAIN TEXT
    # ------------------------------------------------------------------

    def import_text(self, text: str, chapter_pattern: str = r'(?:Chapter|Book|Part)\s+\w+',
                    paragraph_separator: str = '\n\n'):
        """
        Import a plain text, auto-detecting chapters and paragraphs.
        Returns self for chaining.
        """
        # Split into chapters
        chapter_splits = re.split(f'({chapter_pattern})', text, flags=re.IGNORECASE)

        if len(chapter_splits) <= 1:
            # No chapters detected — treat whole text as one chapter
            ch = self.add_chapter("Full Text")
            for para in text.split(paragraph_separator):
                para = para.strip()
                if para:
                    ch.add_paragraph(para, css_class="indent")
        else:
            # Process chapter splits
            i = 0
            if chapter_splits[0].strip():
                # Text before first chapter marker = introduction
                self.set_general_introduction(chapter_splits[0].strip())
                i = 1
            while i < len(chapter_splits) - 1:
                title = chapter_splits[i].strip()
                body = chapter_splits[i + 1].strip() if i + 1 < len(chapter_splits) else ""
                ch = self.add_chapter(title)
                for para in body.split(paragraph_separator):
                    para = para.strip()
                    if para:
                        ch.add_paragraph(para, css_class="indent")
                i += 2

        return self

    # ------------------------------------------------------------------
    # RENDERING: COMMON HTML
    # ------------------------------------------------------------------

    def _get_css(self, kobo_color: bool = False) -> str:
        """Generate study edition CSS (modeled on RNJB style).

        If kobo_color=True, uses saturated colors optimized for Kaleido 3
        (4096-color E Ink) and pixel-based margins per Kobo spec.
        """
        # Color palette: standard (screen/print) vs Kobo Colour (saturated for Kaleido 3)
        if kobo_color:
            # Kaleido 3 mutes everything ~30-40%, so we start with oversaturated values
            fn_color = '#CC0000'       # bright red → readable dark red on Kaleido 3
            xref_color = '#444444'     # darker gray → visible on e-ink
            section_num_color = '#666666'
            subtitle_color = '#333333'
            editor_color = '#444444'
            border_color = '#999999'
            link_color = '#0055CC'     # strong blue → readable on Kaleido 3
            intro_accent = '#005599'   # teal-blue for intro titles
            essay_heading = '#663300'  # warm brown → visible accent on Kaleido 3
            margin_unit = 'px'
            body_margin = '24px'
            body_bg = ''  # NO background-color per Kobo spec (breaks sepia/night modes)
            body_color = '#000000'     # pure black for max e-ink contrast
        else:
            fn_color = '#8b0000'
            xref_color = '#555'
            section_num_color = '#888'
            subtitle_color = '#555'
            editor_color = '#666'
            border_color = '#ccc'
            link_color = '#8b0000'
            intro_accent = '#555'
            essay_heading = '#333'
            margin_unit = 'em'
            body_margin = '2em'
            body_bg = '\n            background: #fefefe;'
            body_color = '#1a1a1a'

        return textwrap.dedent(f"""\
        /* Study Edition CSS — modeled on RNJB Study Edition */
        /* {"Kobo Colour (Kaleido 3) optimized" if kobo_color else "Standard screen/print"} */
        @charset "UTF-8";

        body {{
            font-family: Georgia, "Times New Roman", serif;
            font-size: 1em;
            line-height: 1.6;
            margin: {body_margin};
            color: {body_color};{body_bg}
        }}

        h1.edition-title {{
            text-align: center;
            font-size: 2.4em;
            margin: 15% 0 0.3em 0;
            font-weight: normal;
            letter-spacing: 0.05em;
        }}
        h2.edition-subtitle {{
            text-align: center;
            font-size: 1.2em;
            font-weight: normal;
            font-style: italic;
            margin: 0 0 0.5em 0;
            color: {subtitle_color};
        }}
        p.edition-author {{
            text-align: center;
            font-size: 1.1em;
            margin: 1em 0;
        }}
        p.edition-editor {{
            text-align: center;
            font-size: 0.95em;
            font-style: italic;
            color: {editor_color};
        }}

        /* Chapter headers */
        h1.chapter-title {{
            text-align: center;
            font-size: 2.0em;
            margin: {"32px" if kobo_color else "2em"} 0 {"4px" if kobo_color else "0.2em"} 0;
            page-break-before: always;
            font-weight: normal;
            letter-spacing: 0.03em;
        }}
        h2.chapter-subtitle {{
            text-align: center;
            font-size: 1.1em;
            font-style: italic;
            font-weight: normal;
            margin: 0 0 {"20px" if kobo_color else "1.5em"} 0;
            color: {subtitle_color};
        }}

        /* Introduction blocks */
        .introduction {{
            font-size: 0.95em;
            line-height: 1.5;
            margin-bottom: {"24px" if kobo_color else "2em"};
            border-bottom: 1px solid {border_color};
            padding-bottom: {"18px" if kobo_color else "1.5em"};
        }}
        .introduction p.intro-title {{
            text-align: center;
            font-size: 1.2em;
            font-style: italic;
            margin-bottom: {"10px" if kobo_color else "0.8em"};
            color: {intro_accent};
        }}

        /* Section headers */
        .section-header {{
            font-size: 1.05em;
            font-weight: bold;
            margin-top: {"22px" if kobo_color else "1.8em"};
            margin-bottom: {"4px" if kobo_color else "0.3em"};
        }}
        .section-header-2 {{
            font-size: 0.95em;
            font-weight: bold;
            margin-top: {"14px" if kobo_color else "1.2em"};
            margin-bottom: {"3px" if kobo_color else "0.2em"};
        }}

        /* Paragraphs */
        p.indent {{
            text-indent: {"18px" if kobo_color else "1.5em"};
            margin: {"4px" if kobo_color else "0.3em"} 0;
        }}
        p.no-indent {{
            text-indent: 0;
            margin: {"4px" if kobo_color else "0.3em"} 0;
        }}
        p.block-quote {{
            margin: {"12px 24px" if kobo_color else "1em 2em"};
            font-style: italic;
            font-size: 0.95em;
        }}

        /* Section/line numbers */
        .section-num {{
            font-family: sans-serif;
            font-weight: bold;
            font-size: 0.8em;
            vertical-align: 0.05em;
            color: {section_num_color};
            margin-right: {"4px" if kobo_color else "0.3em"};
        }}

        /* Footnote references (superscript in text) */
        .fn-ref {{
            font-size: 0.7em;
            vertical-align: super;
            line-height: 0;
            color: {fn_color};
            text-decoration: none;
            font-weight: bold;
        }}

        /* Cross-references (inline, bracketed) */
        .xref {{
            font-size: 0.75em;
            color: {xref_color};
            line-height: 0;
        }}
        .xref a {{
            color: {link_color};
            text-decoration: none;
        }}

        /* Footnote section */
        .footnotes {{
            margin-top: {"24px" if kobo_color else "2em"};
            padding-top: {"12px" if kobo_color else "1em"};
            border-top: 1px solid #999;
            font-size: 0.9em;
        }}
        .footnotes h3 {{
            font-size: 1em;
            font-weight: bold;
            margin-bottom: {"6px" if kobo_color else "0.5em"};
        }}
        p.footnote {{
            margin: {"4px" if kobo_color else "0.3em"} 0 {"4px" if kobo_color else "0.3em"} {"18px" if kobo_color else "1.5em"};
            text-indent: {"-18px" if kobo_color else "-1.5em"};
        }}
        p.footnote a.fn-back {{
            font-weight: bold;
            color: {fn_color};
            text-decoration: none;
        }}

        /* Sidebar essays (JANT-style inline blockquotes within chapters) */
        .sidebar-essay {{
            margin: {"16px 24px" if kobo_color else "1.2em 2em"};
            padding: {"10px 16px" if kobo_color else "0.8em 1.2em"};
            {"border-left: 3px solid " + fn_color + ";" if kobo_color else
             "border-left: 3px solid #8b0000;"}
            font-size: 0.93em;
            line-height: 1.45;
        }}
        .sidebar-title {{
            font-size: 1.05em;
            margin-bottom: {"6px" if kobo_color else "0.4em"};
            {"color: " + fn_color + ";" if kobo_color else "color: #8b0000;"}
        }}
        .sidebar-para {{
            text-indent: {"12px" if kobo_color else "1em"};
            margin: {"3px" if kobo_color else "0.2em"} 0;
        }}
        .sidebar-para:first-of-type {{
            text-indent: 0;
        }}

        /* Essay sections (back-matter or standalone) */
        .essay {{
            margin-top: {"24px" if kobo_color else "2em"};
            page-break-before: always;
        }}
        .essay h2 {{
            text-align: center;
            font-size: 1.4em;
            font-weight: normal;
            font-style: italic;
            margin-bottom: {"4px" if kobo_color else "0.3em"};
            color: {essay_heading};
        }}
        .essay-author {{
            text-align: center;
            font-size: 0.95em;
            font-style: italic;
            margin-bottom: {"12px" if kobo_color else "1em"};
            color: {subtitle_color};
        }}

        /* Esoteric analysis color coding (Kobo Colour optimized) */
        .esoteric-high {{
            {"border-left: 3px solid #CC0000; padding-left: 8px;" if kobo_color else
             "border-left: 3px solid #8b0000; padding-left: 0.5em;"}
        }}
        .esoteric-medium {{
            {"border-left: 3px solid #CC8800; padding-left: 8px;" if kobo_color else
             "border-left: 3px solid #b8860b; padding-left: 0.5em;"}
        }}
        .esoteric-low {{
            {"border-left: 3px solid #006600; padding-left: 8px;" if kobo_color else
             "border-left: 3px solid #2e8b57; padding-left: 0.5em;"}
        }}
        .score-badge {{
            font-family: sans-serif;
            font-size: 0.8em;
            font-weight: bold;
            {"color: #CC0000;" if kobo_color else "color: #8b0000;"}
        }}

        /* Table of contents */
        .toc h1 {{ text-align: center; font-size: 1.8em; margin: {"24px" if kobo_color else "2em"} 0 {"12px" if kobo_color else "1em"} 0; }}
        .toc-entry {{ margin: {"4px" if kobo_color else "0.3em"} 0 {"4px" if kobo_color else "0.3em"} {"12px" if kobo_color else "1em"}; }}
        .toc-entry.level-0 {{ font-size: 1.1em; font-weight: bold; margin-left: 0; margin-top: {"10px" if kobo_color else "0.8em"}; }}
        .toc-entry.level-1 {{ font-size: 1em; margin-left: {"18px" if kobo_color else "1.5em"}; }}
        .toc-entry.level-2 {{ font-size: 0.9em; margin-left: {"36px" if kobo_color else "3em"}; font-style: italic; }}
        .toc-entry a {{ text-decoration: none; color: {body_color}; }}

        /* Abbreviations */
        .abbreviations {{ page-break-before: always; }}
        .abbreviations h2 {{ text-align: center; font-size: 1.4em; margin-bottom: {"12px" if kobo_color else "1em"}; }}
        .abbr-entry {{ margin: {"3px" if kobo_color else "0.2em"} 0 {"3px" if kobo_color else "0.2em"} {"24px" if kobo_color else "2em"}; text-indent: {"-24px" if kobo_color else "-2em"}; }}

        /* Bibliography */
        .bibliography {{ page-break-before: always; }}
        .bibliography h2 {{ text-align: center; font-size: 1.4em; margin-bottom: {"12px" if kobo_color else "1em"}; }}
        .bib-entry {{ margin: {"5px" if kobo_color else "0.4em"} 0 {"5px" if kobo_color else "0.4em"} {"24px" if kobo_color else "2em"}; text-indent: {"-24px" if kobo_color else "-2em"}; font-size: 0.95em; }}

        /* Print/PDF adjustments */
        @media print {{
            body {{ margin: 0; font-size: 10pt; }}
            h1.chapter-title {{ page-break-before: always; }}
            .fn-ref {{ color: #000; }}
        }}
        """)

    def _render_paragraph_html(self, para: Paragraph, chapter: Chapter) -> str:
        """Render a single paragraph to HTML with footnotes and cross-refs."""
        parts = []

        # Section number
        if para.section_num:
            parts.append(f'<span class="section-num">{html.escape(para.section_num)}</span> ')

        # Main text
        text = html.escape(para.text)
        # Convert basic markdown-like formatting
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        parts.append(text)

        # Footnote references (superscript letters) — epub:type="noteref" for Kobo popup
        for fn in para.footnotes:
            fn_ref_id = f"{fn.anchor_id}_ref"
            fn_note_id = fn.anchor_id
            parts.append(
                f'<a class="fn-ref" epub:type="noteref" role="doc-noteref" '
                f'id="{fn_ref_id}" href="#{fn_note_id}">{html.escape(fn.key)}</a>'
            )

        # Cross-references [bracketed]
        if para.cross_refs:
            refs = "; ".join(html.escape(cr.label) for cr in para.cross_refs)
            parts.append(f' <span class="xref">[{refs}]</span>')

        return f'<p class="{para.css_class}">{"".join(parts)}</p>'

    def _render_footnotes_html(self, chapter: Chapter) -> str:
        """Render all footnotes for a chapter."""
        all_footnotes = []
        for elem in chapter.elements:
            if isinstance(elem, Paragraph):
                all_footnotes.extend(elem.footnotes)

        if not all_footnotes:
            return ""

        lines = ['<div class="footnotes">', f'<h3>{html.escape(chapter.title)} — Notes</h3>']
        for fn in all_footnotes:
            fn_ref_id = f"{fn.anchor_id}_ref"
            fn_text = html.escape(fn.text)
            # Convert basic formatting in footnotes
            fn_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', fn_text)
            fn_text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', fn_text)
            lines.append(
                f'<p class="footnote" epub:type="footnote" role="doc-footnote" id="{fn.anchor_id}">'
                f'<a class="fn-back" href="#{fn_ref_id}">{html.escape(fn.key)}.</a> '
                f'{fn_text}</p>'
            )
        lines.append('</div>')
        return '\n'.join(lines)

    def _render_sidebar_html(self, sidebar: SidebarEssay) -> str:
        """Render a JANT-style sidebar essay as an indented blockquote section."""
        lines = [f'<div class="sidebar-essay" id="{sidebar.sidebar_id}">']
        lines.append(f'<p class="sidebar-title"><b>{html.escape(sidebar.title)}</b></p>')

        content = html.escape(sidebar.content)
        content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', content)
        content = re.sub(r'\*(.+?)\*', r'<i>\1</i>', content)
        for p in content.split('\n\n'):
            p = p.strip()
            if p:
                lines.append(f'<p class="sidebar-para">{p}</p>')

        lines.append('</div>')
        return '\n'.join(lines)

    def _render_chapter_html(self, chapter: Chapter) -> str:
        """Render a full chapter to HTML."""
        lines = [f'<div class="chapter" id="{chapter.chapter_id}">']

        # Title
        lines.append(f'<h1 class="chapter-title">{html.escape(chapter.title)}</h1>')
        if chapter.subtitle:
            lines.append(f'<h2 class="chapter-subtitle">{html.escape(chapter.subtitle)}</h2>')

        # Introduction
        if chapter.introduction:
            intro_html = html.escape(chapter.introduction)
            intro_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', intro_html)
            intro_html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', intro_html)
            intro_paras = intro_html.split('\n\n')
            lines.append('<div class="introduction">')
            lines.append('<p class="intro-title"><i>Introduction</i></p>')
            for p in intro_paras:
                p = p.strip()
                if p:
                    lines.append(f'<p class="indent">{p}</p>')
            lines.append('</div>')

        # Elements
        for elem in chapter.elements:
            if isinstance(elem, Paragraph):
                lines.append(self._render_paragraph_html(elem, chapter))
            elif isinstance(elem, SectionHeader):
                cls = "section-header" if elem.level == 1 else "section-header-2"
                lines.append(f'<p class="{cls}"><b>{html.escape(elem.title)}</b></p>')
            elif isinstance(elem, SidebarEssay):
                lines.append(self._render_sidebar_html(elem))
            elif isinstance(elem, tuple) and elem[0] == 'raw_html':
                lines.append(elem[1])

        # Footnotes
        lines.append(self._render_footnotes_html(chapter))
        lines.append('</div>')

        return '\n'.join(lines)

    def _render_toc_html(self) -> str:
        """Render table of contents."""
        lines = ['<div class="toc">', '<h1>Contents</h1>']

        if self.general_introduction:
            lines.append('<p class="toc-entry level-0"><a href="#general-intro">General Introduction</a></p>')

        for ch in self.chapters:
            lines.append(
                f'<p class="toc-entry level-0">'
                f'<a href="#{ch.chapter_id}">{html.escape(ch.title)}</a></p>'
            )
            if ch.subtitle:
                lines.append(
                    f'<p class="toc-entry level-1">'
                    f'<i>{html.escape(ch.subtitle)}</i></p>'
                )

        if self.essays:
            lines.append('<p class="toc-entry level-0" style="margin-top:1.5em;"><b>Essays</b></p>')
            for essay in self.essays:
                lines.append(
                    f'<p class="toc-entry level-1">'
                    f'<a href="#{essay.essay_id}">{html.escape(essay.title)}</a></p>'
                )

        if self.abbreviations:
            lines.append('<p class="toc-entry level-0"><a href="#abbreviations">Abbreviations</a></p>')
        if self.bibliography:
            lines.append('<p class="toc-entry level-0"><a href="#bibliography">Bibliography</a></p>')

        lines.append('</div>')
        return '\n'.join(lines)

    def _render_full_html(self, kobo_color: bool = False) -> str:
        """Render the complete study edition as a single HTML document."""
        parts = []

        # Title page
        parts.append('<div class="title-page">')
        parts.append(f'<h1 class="edition-title">{html.escape(self.title)}</h1>')
        if self.subtitle:
            parts.append(f'<h2 class="edition-subtitle">{html.escape(self.subtitle)}</h2>')
        parts.append(f'<p class="edition-author">{html.escape(self.author)}</p>')
        if self.editor:
            parts.append(f'<p class="edition-editor">Edited by {html.escape(self.editor)}</p>')
        parts.append('</div>')

        # TOC
        parts.append(self._render_toc_html())

        # General introduction
        if self.general_introduction:
            intro = html.escape(self.general_introduction)
            intro = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', intro)
            intro = re.sub(r'\*(.+?)\*', r'<i>\1</i>', intro)
            intro_paras = intro.split('\n\n')
            parts.append('<div class="introduction" id="general-intro" style="page-break-before:always;">')
            parts.append('<p class="intro-title"><i>General Introduction</i></p>')
            for p in intro_paras:
                p = p.strip()
                if p:
                    parts.append(f'<p class="indent">{p}</p>')
            parts.append('</div>')

        # Chapters
        for ch in self.chapters:
            parts.append(self._render_chapter_html(ch))

        # Essays
        for essay in self.essays:
            essay_html = html.escape(essay.content)
            essay_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', essay_html)
            essay_html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', essay_html)
            essay_paras = essay_html.split('\n\n')
            parts.append(f'<div class="essay" id="{essay.essay_id}">')
            parts.append(f'<h2>{html.escape(essay.title)}</h2>')
            if essay.author:
                parts.append(f'<p class="essay-author">{html.escape(essay.author)}</p>')
            for p in essay_paras:
                p = p.strip()
                if p:
                    parts.append(f'<p class="indent">{p}</p>')
            parts.append('</div>')

        # Abbreviations
        if self.abbreviations:
            parts.append('<div class="abbreviations" id="abbreviations">')
            parts.append('<h2>Abbreviations</h2>')
            for abbr, full in sorted(self.abbreviations.items()):
                parts.append(
                    f'<p class="abbr-entry"><b>{html.escape(abbr)}</b> — {html.escape(full)}</p>'
                )
            parts.append('</div>')

        # Bibliography
        if self.bibliography:
            parts.append('<div class="bibliography" id="bibliography">')
            parts.append('<h2>Bibliography</h2>')
            for entry in self.bibliography:
                entry_html = html.escape(entry)
                entry_html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', entry_html)
                parts.append(f'<p class="bib-entry">{entry_html}</p>')
            parts.append('</div>')

        body = '\n\n'.join(parts)

        return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{self.language}">
<head>
<meta charset="utf-8"/>
<title>{html.escape(self.title)}</title>
<style>
{self._get_css(kobo_color=kobo_color)}
</style>
</head>
<body>
{body}
</body>
</html>"""

    # ------------------------------------------------------------------
    # EPUB EXPORT
    # ------------------------------------------------------------------

    def export_epub(self, filepath: str, kobo_color: bool = False):
        """Export as EPUB 3 with proper navigation and linked footnotes.

        If kobo_color=True, uses Kaleido 3-optimized CSS (saturated colors,
        px margins, no background-color) and adds epub:type footnote/noteref
        attributes for Kobo popup footnote support.

        To sideload on Kobo eInk, rename the file to .kepub.epub — or use
        export_kepub() which does this automatically.
        """
        from ebooklib import epub

        book = epub.EpubBook()
        book.set_identifier(self.uid)
        book.set_title(self.title)
        book.set_language(self.language)
        book.add_author(self.author)
        if self.editor:
            book.add_metadata('DC', 'contributor', self.editor)

        # CSS
        css_item = epub.EpubItem(
            uid='style',
            file_name='style/study.css',
            media_type='text/css',
            content=self._get_css(kobo_color=kobo_color).encode('utf-8'),
        )
        book.add_item(css_item)

        spine = ['nav']
        toc = []

        # Title page
        title_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>{html.escape(self.title)}</title>
<link href="style/study.css" rel="stylesheet" type="text/css"/></head>
<body>
<div class="title-page">
<h1 class="edition-title">{html.escape(self.title)}</h1>
{"<h2 class='edition-subtitle'>" + html.escape(self.subtitle) + "</h2>" if self.subtitle else ""}
<p class="edition-author">{html.escape(self.author)}</p>
{"<p class='edition-editor'>Edited by " + html.escape(self.editor) + "</p>" if self.editor else ""}
</div>
</body></html>"""
        title_page = epub.EpubHtml(title='Title Page', file_name='title.xhtml', lang=self.language)
        title_page.content = title_html.encode('utf-8')
        title_page.add_item(css_item)
        book.add_item(title_page)
        spine.append(title_page)

        # General introduction
        if self.general_introduction:
            intro_body = html.escape(self.general_introduction)
            intro_body = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', intro_body)
            intro_body = re.sub(r'\*(.+?)\*', r'<i>\1</i>', intro_body)
            intro_paras = '\n'.join(
                f'<p class="indent">{p.strip()}</p>'
                for p in intro_body.split('\n\n') if p.strip()
            )
            intro_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>General Introduction</title>
<link href="style/study.css" rel="stylesheet" type="text/css"/></head>
<body>
<div class="introduction" id="general-intro">
<p class="intro-title"><i>General Introduction</i></p>
{intro_paras}
</div>
</body></html>"""
            intro_page = epub.EpubHtml(title='General Introduction', file_name='intro.xhtml', lang=self.language)
            intro_page.content = intro_html.encode('utf-8')
            intro_page.add_item(css_item)
            book.add_item(intro_page)
            spine.append(intro_page)
            toc.append(epub.Link('intro.xhtml', 'General Introduction', 'intro'))

        # Chapters
        for i, ch in enumerate(self.chapters):
            ch_body = self._render_chapter_html(ch)
            ch_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>{html.escape(ch.title)}</title>
<link href="style/study.css" rel="stylesheet" type="text/css"/></head>
<body>
{ch_body}
</body></html>"""
            ch_page = epub.EpubHtml(
                title=ch.title,
                file_name=f'ch{i+1:03d}.xhtml',
                lang=self.language,
            )
            ch_page.content = ch_html.encode('utf-8')
            ch_page.add_item(css_item)
            book.add_item(ch_page)
            spine.append(ch_page)
            toc.append(epub.Link(f'ch{i+1:03d}.xhtml', ch.title, f'ch{i+1:03d}'))

        # Essays
        for i, essay in enumerate(self.essays):
            essay_body_html = html.escape(essay.content)
            essay_body_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', essay_body_html)
            essay_body_html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', essay_body_html)
            essay_paras = '\n'.join(
                f'<p class="indent">{p.strip()}</p>'
                for p in essay_body_html.split('\n\n') if p.strip()
            )
            essay_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>{html.escape(essay.title)}</title>
<link href="style/study.css" rel="stylesheet" type="text/css"/></head>
<body>
<div class="essay" id="{essay.essay_id}">
<h2>{html.escape(essay.title)}</h2>
{"<p class='essay-author'>" + html.escape(essay.author) + "</p>" if essay.author else ""}
{essay_paras}
</div>
</body></html>"""
            essay_page = epub.EpubHtml(
                title=essay.title,
                file_name=f'essay{i+1:03d}.xhtml',
                lang=self.language,
            )
            essay_page.content = essay_html.encode('utf-8')
            essay_page.add_item(css_item)
            book.add_item(essay_page)
            spine.append(essay_page)
            toc.append(epub.Link(f'essay{i+1:03d}.xhtml', essay.title, f'essay{i+1:03d}'))

        # Navigation
        book.toc = toc
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        epub.write_epub(filepath, book, {})
        return filepath

    # ------------------------------------------------------------------
    # PDF EXPORT
    # ------------------------------------------------------------------

    def export_pdf(self, filepath: str):
        """Export as PDF via WeasyPrint."""
        from weasyprint import HTML as WeasyHTML
        full_html = self._render_full_html()
        WeasyHTML(string=full_html).write_pdf(filepath)
        return filepath

    # ------------------------------------------------------------------
    # HTML EXPORT (for previewing)
    # ------------------------------------------------------------------

    def export_html(self, filepath: str, kobo_color: bool = False):
        """Export as a single HTML file.

        If kobo_color=True, uses Kaleido 3-optimized CSS for previewing
        how the edition will look on a Kobo Colour device.
        """
        full_html = self._render_full_html(kobo_color=kobo_color)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_html)
        return filepath

    # ------------------------------------------------------------------
    # KOBO KEPUB EXPORT
    # ------------------------------------------------------------------

    def export_kepub(self, filepath: str):
        """Export as .kepub.epub with Kobo Colour-optimized CSS.

        This is a convenience wrapper around export_epub that:
        1. Enables Kaleido 3-optimized colors (oversaturated to survive
           the ~30-40% muting of the color E Ink panel)
        2. Uses pixel-based margins (not em) per Kobo spec to prevent
           margin blowup at large user font sizes
        3. Omits background-color (breaks sepia/night reading modes)
        4. Adds epub:type footnote/noteref for Kobo popup footnote support
        5. Ensures .kepub.epub extension to trigger Kobo WebKit on sideload

        Target devices: Kobo Libra Colour, Kobo Clara Colour (Kaleido 3)
        """
        # Ensure .kepub.epub extension
        if not filepath.endswith('.kepub.epub'):
            filepath = filepath.replace('.epub', '.kepub.epub')
            if not filepath.endswith('.kepub.epub'):
                filepath += '.kepub.epub'
        return self.export_epub(filepath, kobo_color=True)


# ---------------------------------------------------------------------------
# DEMO / SELF-TEST
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    edition = StudyEdition(
        title="On Virtue, Soul, and Political Order",
        author="Anonymous",
        editor="Study Edition Editor",
        subtitle="A Study Edition with Esoteric Commentary",
    )

    edition.set_general_introduction(
        "This short philosophical text, composed in an deliberately archaic style, "
        "treats the traditional themes of virtue, the soul, and political order. "
        "Its apparent orthodoxy conceals a more radical teaching about the relationship "
        "between philosophy and the city, visible only to the careful reader.\n\n"
        "The text exhibits many of the hallmarks of the esoteric writing tradition: "
        "strategic contradictions, significant silences, and a carefully constructed "
        "periagoge (structural reversal) between its first and second halves."
    )

    ch1 = edition.add_chapter("Chapter I", "On Justice")
    ch1.add_section_header("The Foundation of Order")
    ch1.add_paragraph(
        "Justice is the foundation of all political order. This is universally "
        "acknowledged by all reasonable people.",
        footnotes={
            "a": "The opening formula echoes Republic 331c, where Cephalus offers "
                 "the conventional definition of justice as 'giving to each what is owed.' "
                 "Socrates will spend the rest of the dialogue demolishing this view.",
        },
        cross_refs=["Rep 331c", "Nic. Eth. V.1"],
    )
    ch1.add_paragraph_with_notes(
        "Yet Socrates, that wisest of men, was condemned by a just court under just laws. "
        "Perhaps justice is not so simple as it first appears.",
        footnotes={
            "b": "The contradiction between Socrates' wisdom and Athens' justice is the "
                 "founding paradox of political philosophy. Cf. Apology 38a: 'The unexamined "
                 "life is not worth living.'",
        },
        textual_notes=["Or 'righteous court under righteous laws' — Gk. dikaios admits both senses."],
    )

    # JANT-style sidebar essay embedded between paragraphs
    ch1.add_sidebar_essay(
        "JUSTICE IN GREEK AND HEBREW THOUGHT",
        "The Greek word dikaiosyne ('justice' or 'righteousness') maps imperfectly onto "
        "the Hebrew tsedaqah. Where Greek philosophy tends to define justice as a "
        "mathematical proportion — giving to each according to merit — the Hebrew "
        "concept carries overtones of covenant faithfulness and compassion for the poor.\n\n"
        "This semantic gap means that every translation of a philosophical text about "
        "justice is already an interpretation. The apparent universalism of the opening "
        "claim conceals the question: whose justice? The Greek polis or the biblical covenant?"
    )

    ch2 = edition.add_chapter("Chapter II", "On the Soul")
    ch2.add_paragraph(
        "The soul is immortal. This is the teaching of all the great philosophers, "
        "and no reasonable person would deny it.",
        footnotes={
            "a": "Note the assertive confidence — 'no reasonable person would deny it' — "
                 "immediately before the author proceeds to enumerate reasons for doubt. "
                 "This is a classic 'trapdoor' (Benardete): the absolute claim is the "
                 "signal to look for the qualification.",
        },
        cross_refs=["Phd 69e-72e", "Rep 608d"],
    )

    edition.add_essay(
        "The Art of Esoteric Writing",
        "The tradition of esoteric writing — saying one thing while meaning another — "
        "is as old as philosophy itself. Plato's Seventh Letter (341c-d) declares that "
        "the most important philosophical truths cannot be written down at all.\n\n"
        "Leo Strauss recovered this tradition for modern readers in *Persecution and "
        "the Art of Writing* (1952), arguing that philosophers who lived under conditions "
        "of political or religious censorship developed sophisticated techniques for "
        "communicating dangerous truths to careful readers while presenting an innocuous "
        "surface to casual ones.",
        author="Study Edition Editor",
    )

    edition.add_abbreviation("Rep", "Plato, Republic")
    edition.add_abbreviation("Phd", "Plato, Phaedo")
    edition.add_abbreviation("Nic. Eth.", "Aristotle, Nicomachean Ethics")

    edition.add_bibliography_entry(
        "Strauss, Leo. *Persecution and the Art of Writing*. Chicago: University of Chicago Press, 1952."
    )
    edition.add_bibliography_entry(
        "Melzer, Arthur. *Philosophy Between the Lines*. Chicago: University of Chicago Press, 2014."
    )
    edition.add_bibliography_entry(
        "Benardete, Seth. *The Argument of the Action*. Chicago: University of Chicago Press, 2000."
    )

    # Export
    base = "/sessions/sweet-youthful-wright/mnt/scriptorium"
    edition.export_epub(f"{base}/study_edition_demo.epub")
    print(f"EPUB exported: {base}/study_edition_demo.epub")

    edition.export_kepub(f"{base}/study_edition_demo.kepub.epub")
    print(f"KEPUB exported: {base}/study_edition_demo.kepub.epub")

    edition.export_html(f"{base}/study_edition_demo.html")
    print(f"HTML exported: {base}/study_edition_demo.html")

    edition.export_html(f"{base}/study_edition_demo_kobo.html", kobo_color=True)
    print(f"Kobo HTML preview: {base}/study_edition_demo_kobo.html")

    try:
        edition.export_pdf(f"{base}/study_edition_demo.pdf")
        print(f"PDF exported: {base}/study_edition_demo.pdf")
    except Exception as e:
        print(f"PDF export error (may need fonts): {e}")

    print("\nDone.")
