"""Format conversion service — pure Python, no external tools required.

Supported conversions
─────────────────────
  EPUB  → KEPUB   Kobo-optimised EPUB with Kobo span markup (lxml)
                  Uses kepubify binary as a drop-in if available.
  CBZ   → EPUB    Comic images packaged as fixed-layout EPUB3
  CBR   → EPUB    Same (most modern CBR files are ZIP-compatible)
  CBR   → CBZ     Repackage as ZIP-based CBZ
  MOBI  → EPUB    Kindle MOBI/AZW/AZW3 → EPUB via mobi library
  AZW   → EPUB    (same)
  AZW3  → EPUB    (same)
  PDF   → EPUB    Text-based PDF → flowing EPUB via pdfplumber

All I/O runs in a thread-pool executor so it never blocks the event loop.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

SUPPORTED_CONVERSIONS: dict[str, list[str]] = {
    "epub": ["kepub"],
    "cbz":  ["epub"],
    "cbr":  ["epub", "cbz"],
    "mobi": ["epub"],
    "azw":  ["epub"],
    "azw3": ["epub"],
    "pdf":  ["epub"],
}


class ConversionService:
    async def convert_file(
        self,
        input_path: Path,
        output_format: str,
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Convert *input_path* to *output_format*.

        Returns the output Path on success, None if conversion produced no output.
        Raises ValueError for unsupported combinations.
        """
        src_fmt = input_path.suffix.lstrip(".").lower()
        dst_fmt = output_format.lower().lstrip(".")
        if dst_fmt not in SUPPORTED_CONVERSIONS.get(src_fmt, []):
            raise ValueError(
                f"Cannot convert {src_fmt!r} → {dst_fmt!r}. "
                f"Supported: {SUPPORTED_CONVERSIONS}"
            )

        out_dir = output_dir or input_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        if src_fmt == "epub" and dst_fmt == "kepub":
            out = out_dir / f"{input_path.stem}.kepub.epub"
            return await _run(_epub_to_kepub, input_path, out)

        if src_fmt in ("cbz", "cbr") and dst_fmt == "epub":
            out = out_dir / f"{input_path.stem}.epub"
            return await _run(_cbz_to_epub, input_path, out)

        if src_fmt == "cbr" and dst_fmt == "cbz":
            out = out_dir / f"{input_path.stem}.cbz"
            return await _run(_cbr_to_cbz, input_path, out)

        if src_fmt in ("mobi", "azw", "azw3") and dst_fmt == "epub":
            out = out_dir / f"{input_path.stem}.epub"
            return await _run(_mobi_to_epub, input_path, out)

        if src_fmt == "pdf" and dst_fmt == "epub":
            out = out_dir / f"{input_path.stem}.epub"
            return await _run(_pdf_to_epub, input_path, out)

        return None

    async def get_supported_conversions(self) -> dict[str, list[str]]:
        return SUPPORTED_CONVERSIONS


conversion_service = ConversionService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# EPUB → KEPUB
# ---------------------------------------------------------------------------

_XHTML_NS = "http://www.w3.org/1999/xhtml"
_KOBO_NS  = "http://kobobooks.com/ns"
_EPUB_NS  = "http://www.idpf.org/2007/opf"
_DC_NS    = "http://purl.org/dc/elements/1.1/"

_BLOCK_TAGS = {
    f"{{{_XHTML_NS}}}{t}"
    for t in ("p", "h1", "h2", "h3", "h4", "h5", "h6",
              "li", "td", "th", "blockquote", "dd", "dt")
}
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')


def _epub_to_kepub(epub_path: Path, out_path: Path) -> Optional[Path]:
    """EPUB → KEPUB.  Tries kepubify first, falls back to native Python."""
    kepubify = shutil.which("kepubify")
    if kepubify:
        import subprocess
        r = subprocess.run(
            [kepubify, "-o", str(out_path.parent), str(epub_path)],
            capture_output=True, timeout=120,
        )
        if r.returncode == 0 and out_path.exists():
            return out_path

    try:
        return _epub_to_kepub_native(epub_path, out_path)
    except Exception:
        return None


def _epub_to_kepub_native(epub_path: Path, out_path: Path) -> Optional[Path]:
    with zipfile.ZipFile(epub_path, "r") as src, \
         zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as dst:

        opf_path = _find_opf_path(src)
        opf_dir  = str(Path(opf_path).parent).rstrip("/") if opf_path else ""
        content_docs = _opf_content_docs(src, opf_path, opf_dir) if opf_path else set()

        para_counter = [0]
        for name in src.namelist():
            data = src.read(name)
            if name in content_docs:
                data = _koboify_xhtml(data, para_counter)
            elif name == opf_path:
                data = _koboify_opf(data)
            dst.writestr(name, data)

    return out_path


def _find_opf_path(zf: zipfile.ZipFile) -> Optional[str]:
    from xml.etree import ElementTree as ET
    try:
        root = ET.fromstring(zf.read("META-INF/container.xml"))
        ns = {"cn": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rf = root.find(".//cn:rootfile", ns)
        return rf.get("full-path") if rf is not None else None
    except Exception:
        return None


def _opf_content_docs(zf: zipfile.ZipFile, opf_path: str, opf_dir: str) -> set[str]:
    from xml.etree import ElementTree as ET
    docs: set[str] = set()
    try:
        root = ET.fromstring(zf.read(opf_path))
        for item in root.findall(f".//{{{_EPUB_NS}}}item"):
            mt = item.get("media-type", "")
            if mt in ("application/xhtml+xml", "text/html"):
                href = item.get("href", "")
                full = f"{opf_dir}/{href}".lstrip("/") if opf_dir else href
                docs.add(full)
    except Exception:
        pass
    return docs


def _koboify_xhtml(data: bytes, para_counter: list[int]) -> bytes:
    try:
        from lxml import etree
        root = etree.fromstring(data)

        for elem in root.iter():
            if elem.tag not in _BLOCK_TAGS:
                continue
            if any(c.tag in _BLOCK_TAGS for c in elem):
                continue  # skip parent blocks; children will be processed

            full_text = "".join(elem.itertext()).strip()
            if not full_text:
                continue

            para_counter[0] += 1
            para_n = para_counter[0]
            sentences = _SENTENCE_RE.split(full_text)

            elem.text = None
            for child in list(elem):
                elem.remove(child)

            for span_n, sentence in enumerate(sentences, 1):
                span = etree.SubElement(
                    elem,
                    f"{{{_XHTML_NS}}}span",
                    attrib={"id": f"kobo.{para_n}.{span_n}"},
                )
                span.text = sentence
                if span_n < len(sentences):
                    span.tail = " "

        return etree.tostring(root, xml_declaration=True, encoding="utf-8")
    except Exception:
        return data


def _koboify_opf(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8", errors="replace")
        if "kobobooks.com" not in text:
            text = text.replace("<package ", f'<package xmlns:kobo="{_KOBO_NS}" ', 1)
        return text.encode("utf-8")
    except Exception:
        return data


# ---------------------------------------------------------------------------
# CBZ / CBR → EPUB
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
_MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png",  ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp",
}


def _cbz_to_epub(cbz_path: Path, out_path: Path) -> Optional[Path]:
    pages = _extract_cbz_images(cbz_path)
    if not pages:
        return None
    _write_image_epub(pages, cbz_path.stem, out_path)
    return out_path


def _extract_cbz_images(cbz_path: Path) -> list[tuple[str, bytes]]:
    images: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(cbz_path, "r") as zf:
            for name in sorted(zf.namelist()):
                if Path(name).suffix.lower() in _IMAGE_EXTS:
                    images.append((Path(name).name, zf.read(name)))
    except zipfile.BadZipFile:
        pass
    return images


def _write_image_epub(pages: list[tuple[str, bytes]], title: str, out_path: Path) -> None:
    book_id = str(uuid.uuid4())
    manifest_items: list[str] = []
    spine_items:    list[str] = []
    nav_items:      list[str] = []

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles>"
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>",
        )

        for i, (fname, img_data) in enumerate(pages):
            ext    = Path(fname).suffix.lower()
            img_id = f"img{i:04d}"
            pg_id  = f"page{i:04d}"
            img_p  = f"images/{img_id}{ext}"
            pg_p   = f"pages/{pg_id}.xhtml"
            mt     = _MEDIA_TYPES.get(ext, "image/jpeg")

            zf.writestr(f"OEBPS/{img_p}", img_data)
            zf.writestr(
                f"OEBPS/{pg_p}",
                f'<?xml version="1.0" encoding="utf-8"?>'
                f'<html xmlns="{_XHTML_NS}" xmlns:epub="http://www.idpf.org/2007/ops">'
                f'<head><meta charset="utf-8"/>'
                f'<meta name="viewport" content="width=1200,height=1700"/>'
                f'<style>html,body{{margin:0;padding:0;background:#000}}'
                f'img{{max-width:100%;max-height:100%;display:block;margin:auto}}</style>'
                f'</head>'
                f'<body><img src="../{img_p}" alt="Page {i+1}"/></body></html>',
            )
            manifest_items.append(
                f'<item id="{img_id}" href="{img_p}" media-type="{mt}"/>'
                f'<item id="{pg_id}" href="{pg_p}" media-type="application/xhtml+xml"'
                f' properties="rendition:page-spread-center"/>'
            )
            spine_items.append(f'<itemref idref="{pg_id}"/>')
            nav_items.append(f'<li><a href="{pg_p}">Page {i+1}</a></li>')

        zf.writestr(
            "OEBPS/nav.xhtml",
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<html xmlns="{_XHTML_NS}" xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<head><meta charset="utf-8"/><title>{_esc(title)}</title></head>'
            f'<body><nav epub:type="toc"><h1>{_esc(title)}</h1>'
            f'<ol>{"".join(nav_items)}</ol></nav></body></html>',
        )
        zf.writestr(
            "OEBPS/content.opf",
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<package xmlns="{_EPUB_NS}" version="3.0" unique-identifier="uid">'
            f'<metadata xmlns:dc="{_DC_NS}">'
            f'<dc:identifier id="uid">{book_id}</dc:identifier>'
            f'<dc:title>{_esc(title)}</dc:title>'
            f'<dc:language>en</dc:language>'
            f'<meta property="rendition:layout">pre-paginated</meta>'
            f'<meta property="rendition:orientation">auto</meta>'
            f'<meta property="rendition:spread">auto</meta>'
            f'</metadata>'
            f'<manifest>'
            f'<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
            f'{"".join(manifest_items)}'
            f'</manifest>'
            f'<spine>{"".join(spine_items)}</spine>'
            f'</package>',
        )


# ---------------------------------------------------------------------------
# CBR → CBZ
# ---------------------------------------------------------------------------

def _cbr_to_cbz(cbr_path: Path, out_path: Path) -> Optional[Path]:
    """Repackage a CBR as CBZ (ZIP).

    Most modern CBR files are actually ZIP archives regardless of extension.
    True RAR-format CBR is not supported without the ``rarfile`` / ``unrar``
    library; those files are skipped gracefully.
    """
    try:
        with zipfile.ZipFile(cbr_path, "r") as src, \
             zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as dst:
            for name in src.namelist():
                dst.writestr(name, src.read(name))
        return out_path
    except zipfile.BadZipFile:
        # True RAR file — skip for now
        return None


# ---------------------------------------------------------------------------
# MOBI / AZW / AZW3 → EPUB
# ---------------------------------------------------------------------------

def _mobi_to_epub(mobi_path: Path, out_path: Path) -> Optional[Path]:
    """Convert Kindle MOBI/AZW/AZW3 to EPUB.

    Uses the ``mobi`` Python library to extract the book content, then
    packages the resulting HTML + images as a standard EPUB3.
    """
    try:
        import mobi as _mobi
    except ImportError:
        return None

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            _tmpdir, extracted = _mobi.extract(str(mobi_path), str(tmpdir))
            extracted_path = Path(extracted)
            if not extracted_path.exists():
                return None

            title = mobi_path.stem
            html_text = extracted_path.read_text(errors="replace")
            img_dir = extracted_path.parent

            # Collect images referenced by the HTML
            img_files: list[tuple[str, bytes]] = []
            for img_path in sorted(img_dir.iterdir()):
                if img_path.suffix.lower() in _IMAGE_EXTS and img_path != extracted_path:
                    img_files.append((img_path.name, img_path.read_bytes()))

            _write_html_epub(title, html_text, img_files, out_path)
            return out_path
    except Exception:
        return None


def _write_html_epub(
    title: str,
    html_text: str,
    images: list[tuple[str, bytes]],
    out_path: Path,
) -> None:
    """Package HTML content as a minimal EPUB3."""
    book_id = str(uuid.uuid4())
    manifest_items: list[str] = []
    extra_entries:  list[tuple[str, bytes]] = []

    for fname, data in images:
        ext = Path(fname).suffix.lower()
        mt  = _MEDIA_TYPES.get(ext, "image/jpeg")
        img_id = f"img_{Path(fname).stem}"
        manifest_items.append(
            f'<item id="{img_id}" href="images/{fname}" media-type="{mt}"/>'
        )
        extra_entries.append((f"OEBPS/images/{fname}", data))

    manifest_items.append(
        '<item id="content" href="content.xhtml" media-type="application/xhtml+xml"/>'
    )

    content_xhtml = (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<html xmlns="{_XHTML_NS}"><head><meta charset="utf-8"/>'
        f'<title>{_esc(title)}</title></head>'
        f'<body>{html_text}</body></html>'
    )

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles>"
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>",
        )
        zf.writestr("OEBPS/content.xhtml", content_xhtml)
        for path, data in extra_entries:
            zf.writestr(path, data)
        zf.writestr(
            "OEBPS/nav.xhtml",
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<html xmlns="{_XHTML_NS}" xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<head><meta charset="utf-8"/><title>{_esc(title)}</title></head>'
            f'<body><nav epub:type="toc"><ol>'
            f'<li><a href="content.xhtml">{_esc(title)}</a></li>'
            f'</ol></nav></body></html>',
        )
        zf.writestr(
            "OEBPS/content.opf",
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<package xmlns="{_EPUB_NS}" version="3.0" unique-identifier="uid">'
            f'<metadata xmlns:dc="{_DC_NS}">'
            f'<dc:identifier id="uid">{book_id}</dc:identifier>'
            f'<dc:title>{_esc(title)}</dc:title>'
            f'<dc:language>en</dc:language>'
            f'</metadata>'
            f'<manifest>'
            f'<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
            f'{"".join(manifest_items)}'
            f'</manifest>'
            f'<spine><itemref idref="content"/></spine>'
            f'</package>',
        )


# ---------------------------------------------------------------------------
# PDF → EPUB
# ---------------------------------------------------------------------------

# Heuristics for detecting section headings in plain-extracted PDF text
_HEADING_RE = re.compile(
    r'^(?:'
    r'(?:chapter|section|part)\s+\w+.*'   # "Chapter 1 ..."
    r'|[A-Z][A-Z\s]{4,60}$'               # ALL CAPS SHORT LINE
    r'|(?:\d+\.)+\s+[A-Z].*'             # "1.2 Title"
    r')$',
    re.IGNORECASE,
)


def _pdf_to_epub(pdf_path: Path, out_path: Path) -> Optional[Path]:
    """Extract text from a PDF and package it as a flowing EPUB3.

    Works best for text-heavy PDFs (academic papers, ebooks scanned as PDF).
    Complex layouts (multi-column, tables, equations) will degrade gracefully
    to a single-column linear text flow.
    """
    try:
        import pdfplumber
    except ImportError:
        return None

    try:
        sections: list[tuple[str, str]] = []  # (heading, html_body)
        current_heading = "Content"
        current_lines: list[str] = []

        with pdfplumber.open(pdf_path) as pdf:
            title = pdf.metadata.get("Title", "").strip() or pdf_path.stem

            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                for raw_line in text.splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    if _HEADING_RE.match(line) and len(line) < 120:
                        if current_lines:
                            sections.append(
                                (current_heading, _lines_to_html(current_lines))
                            )
                            current_lines = []
                        current_heading = line
                    else:
                        current_lines.append(line)

        if current_lines:
            sections.append((current_heading, _lines_to_html(current_lines)))
        if not sections:
            return None

        _write_sectioned_epub(title, sections, out_path)
        return out_path
    except Exception:
        return None


def _lines_to_html(lines: list[str]) -> str:
    """Convert plain text lines to HTML paragraphs.

    Consecutive non-blank lines are merged into paragraphs; a blank-ish line
    (very short line) triggers a paragraph break.
    """
    paragraphs: list[str] = []
    buf: list[str] = []

    for line in lines:
        if len(line) < 4:
            if buf:
                paragraphs.append(" ".join(buf))
                buf = []
        else:
            # If line ends with a period/question/exclamation → sentence boundary
            buf.append(line)
            if re.search(r'[.!?]\s*$', line) and len(buf) > 1:
                paragraphs.append(" ".join(buf))
                buf = []

    if buf:
        paragraphs.append(" ".join(buf))

    return "".join(f"<p>{_esc(p)}</p>" for p in paragraphs if p.strip())


def _write_sectioned_epub(
    title: str,
    sections: list[tuple[str, str]],
    out_path: Path,
) -> None:
    """Write a multi-chapter EPUB3 from (heading, html_body) sections."""
    book_id = str(uuid.uuid4())
    manifest_items: list[str] = []
    spine_items:    list[str] = []
    nav_items:      list[str] = []
    content_files:  list[tuple[str, str]] = []

    for i, (heading, body) in enumerate(sections):
        ch_id   = f"ch{i:04d}"
        ch_file = f"chapters/{ch_id}.xhtml"
        xhtml = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<html xmlns="{_XHTML_NS}"><head><meta charset="utf-8"/>'
            f'<title>{_esc(heading)}</title></head>'
            f'<body><h1>{_esc(heading)}</h1>{body}</body></html>'
        )
        content_files.append((f"OEBPS/{ch_file}", xhtml))
        manifest_items.append(
            f'<item id="{ch_id}" href="{ch_file}" media-type="application/xhtml+xml"/>'
        )
        spine_items.append(f'<itemref idref="{ch_id}"/>')
        nav_items.append(f'<li><a href="{ch_file}">{_esc(heading)}</a></li>')

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles>"
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>",
        )
        for path, data in content_files:
            zf.writestr(path, data)
        zf.writestr(
            "OEBPS/nav.xhtml",
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<html xmlns="{_XHTML_NS}" xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<head><meta charset="utf-8"/><title>{_esc(title)}</title></head>'
            f'<body><nav epub:type="toc"><h1>{_esc(title)}</h1>'
            f'<ol>{"".join(nav_items)}</ol></nav></body></html>',
        )
        zf.writestr(
            "OEBPS/content.opf",
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<package xmlns="{_EPUB_NS}" version="3.0" unique-identifier="uid">'
            f'<metadata xmlns:dc="{_DC_NS}">'
            f'<dc:identifier id="uid">{book_id}</dc:identifier>'
            f'<dc:title>{_esc(title)}</dc:title>'
            f'<dc:language>en</dc:language>'
            f'</metadata>'
            f'<manifest>'
            f'<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
            f'{"".join(manifest_items)}'
            f'</manifest>'
            f'<spine>{"".join(spine_items)}</spine>'
            f'</package>',
        )
