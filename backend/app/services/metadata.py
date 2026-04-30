"""Metadata extraction service for EPUB, PDF, and CBZ files."""

import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET


class MetadataService:
    """Extracts book metadata from EPUB, PDF, and CBZ files."""

    async def extract_from_epub(self, file_path: Path) -> dict:
        """Extract metadata from EPUB file using the OPF package document."""
        result = {
            "title": file_path.stem,
            "authors": [],
            "description": None,
            "isbn": None,
            "language": None,
            "published_date": None,
            "cover_image": None,  # bytes or None
            "is_fixed_layout": False,
        }
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # Find the OPF file via META-INF/container.xml
                try:
                    container_xml = zf.read("META-INF/container.xml")
                    root = ET.fromstring(container_xml)
                    ns = {"cn": "urn:oasis:names:tc:opendocument:xmlns:container"}
                    rootfile = root.find(".//cn:rootfile", ns)
                    if rootfile is None:
                        return result
                    opf_path = rootfile.get("full-path", "")
                except (KeyError, ET.ParseError):
                    return result

                try:
                    opf_data = zf.read(opf_path)
                    opf_root = ET.fromstring(opf_data)
                except (KeyError, ET.ParseError):
                    return result

                # Namespace maps for OPF/DC
                ns_opf = {
                    "opf": "http://www.idpf.org/2007/opf",
                    "dc": "http://purl.org/dc/elements/1.1/",
                }

                metadata = opf_root.find("opf:metadata", ns_opf)
                if metadata is None:
                    # Try without namespace
                    metadata = opf_root.find("metadata")
                    if metadata is None:
                        return result

                def find_dc(tag: str) -> Optional[str]:
                    el = metadata.find(f"dc:{tag}", ns_opf)
                    if el is None:
                        el = metadata.find(f"{{{_dc_ns}}}{tag}")
                    return el.text.strip() if el is not None and el.text else None

                _dc_ns = "http://purl.org/dc/elements/1.1/"

                title = find_dc("title")
                if title:
                    result["title"] = title

                # Authors (multiple dc:creator elements)
                authors = []
                for creator in metadata.findall("dc:creator", ns_opf):
                    if creator.text:
                        authors.append(creator.text.strip())
                if not authors:
                    for creator in metadata.findall(f"{{{_dc_ns}}}creator"):
                        if creator.text:
                            authors.append(creator.text.strip())
                result["authors"] = authors

                description = find_dc("description")
                if description:
                    # Strip HTML tags from description
                    result["description"] = re.sub(r"<[^>]+>", "", description).strip()

                language = find_dc("language")
                if language:
                    result["language"] = language[:10]

                # ISBN from dc:identifier (normalize to ISBN-13)
                raw_isbn = None
                for ident in metadata.findall("dc:identifier", ns_opf):
                    scheme = ident.get(
                        "{http://www.idpf.org/2007/opf}scheme", ""
                    ) or ident.get("scheme", "")
                    if scheme.lower() == "isbn" and ident.text:
                        raw_isbn = ident.text.strip()
                        break
                if not raw_isbn:
                    for ident in metadata.findall(f"{{{_dc_ns}}}identifier"):
                        scheme = ident.get("{http://www.idpf.org/2007/opf}scheme", "")
                        if scheme.lower() == "isbn" and ident.text:
                            raw_isbn = ident.text.strip()
                            break
                if raw_isbn:
                    try:
                        from app.utils.isbn import normalize as _normalize_isbn
                        isbn13, isbn10 = _normalize_isbn(raw_isbn)
                        result["isbn"] = isbn13 or raw_isbn
                        if isbn10:
                            result["isbn_10"] = isbn10
                    except Exception:
                        result["isbn"] = raw_isbn

                # Publication date
                date_str = find_dc("date")
                if date_str:
                    result["published_date"] = _parse_date(date_str)

                # EPUB3 rendition:layout — fixed-layout titles (children's
                # picture books, manga, comics-as-EPUB, photo books) need
                # pre-paginated handling and should not be KEPUB-converted.
                # Either an opf:meta property="rendition:layout" element or
                # the legacy spine attribute can declare it.
                for meta in metadata.findall("opf:meta", ns_opf):
                    if meta.get("property") == "rendition:layout":
                        if (meta.text or "").strip() == "pre-paginated":
                            result["is_fixed_layout"] = True
                            break
                if not result["is_fixed_layout"]:
                    spine = opf_root.find("opf:spine", ns_opf) or opf_root.find("spine")
                    if spine is not None:
                        for itemref in spine:
                            if itemref.get(
                                "{http://www.idpf.org/2013/rendition}layout"
                            ) == "pre-paginated":
                                result["is_fixed_layout"] = True
                                break

                # Kobo's legacy fixed-layout signal: a sibling of
                # ``container.xml`` named ``com.kobobooks.display-options.xml``
                # that carries ``<option name="fixed-layout">true</option>``.
                # Older Kobo-targeted EPUBs declare FXL only here, with no
                # rendition:layout in the OPF — the spec calls it out
                # explicitly so the device picker doesn't try to reflow them.
                if not result["is_fixed_layout"]:
                    try:
                        opts_xml = zf.read("META-INF/com.kobobooks.display-options.xml")
                        opts_root = ET.fromstring(opts_xml)
                        for option in opts_root.iter("option"):
                            if option.get("name") == "fixed-layout" and (option.text or "").strip().lower() == "true":
                                result["is_fixed_layout"] = True
                                break
                    except (KeyError, ET.ParseError):
                        pass  # display-options.xml is optional + non-fatal

                # Cover image — find cover in manifest
                manifest = opf_root.find("opf:manifest", ns_opf) or opf_root.find("manifest")
                if manifest is not None:
                    opf_dir = str(Path(opf_path).parent)
                    cover_item = None
                    # Look for item with id="cover" or properties="cover-image"
                    for item in manifest:
                        item_id = item.get("id", "")
                        props = item.get("properties", "")
                        media_type = item.get("media-type", "")
                        if (
                            "cover" in item_id.lower() or "cover-image" in props
                        ) and media_type.startswith("image/"):
                            cover_item = item
                            break
                    # Also check metadata for cover id reference
                    if cover_item is None:
                        for meta in metadata.findall("opf:meta", ns_opf):
                            if meta.get("name") == "cover":
                                cover_id = meta.get("content", "")
                                for item in manifest:
                                    if item.get("id") == cover_id:
                                        cover_item = item
                                        break
                    if cover_item is not None:
                        href = cover_item.get("href", "")
                        cover_path_in_zip = (
                            href if not opf_dir or opf_dir == "." else f"{opf_dir}/{href}"
                        )
                        try:
                            result["cover_image"] = zf.read(cover_path_in_zip)
                        except KeyError:
                            pass
        except (zipfile.BadZipFile, OSError):
            pass
        return result

    async def extract_from_pdf(self, file_path: Path) -> dict:
        """Extract metadata from PDF file."""
        result = {
            "title": file_path.stem,
            "authors": [],
            "description": None,
            "isbn": None,
            "language": None,
            "published_date": None,
            "cover_image": None,
        }
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            info = reader.metadata
            if info:
                title = info.get("/Title") or info.get("title")
                if title:
                    result["title"] = str(title).strip()

                author = info.get("/Author") or info.get("author")
                if author:
                    # PDF author field may have multiple authors separated by ; or ,
                    result["authors"] = [
                        a.strip() for a in re.split(r"[;,]", str(author)) if a.strip()
                    ]

                subject = info.get("/Subject") or info.get("subject")
                if subject:
                    result["description"] = str(subject).strip()

                date_str = info.get("/CreationDate") or info.get("creation_date")
                if date_str:
                    result["published_date"] = _parse_pdf_date(str(date_str))
        except Exception:
            pass
        return result

    async def extract_from_cbz(self, file_path: Path) -> dict:
        """Extract metadata from CBZ (comic) file via ComicInfo.xml."""
        result = {
            "title": file_path.stem,
            "authors": [],
            "description": None,
            "isbn": None,
            "language": None,
            "published_date": None,
            "cover_image": None,
        }
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()

                # ComicInfo.xml (case-insensitive search)
                comic_info_name = next(
                    (n for n in names if n.lower() == "comicinfo.xml"), None
                )
                if comic_info_name:
                    try:
                        xml_data = zf.read(comic_info_name)
                        root = ET.fromstring(xml_data)

                        def ci(tag: str) -> Optional[str]:
                            el = root.find(tag)
                            return el.text.strip() if el is not None and el.text else None

                        title = ci("Title")
                        if title:
                            result["title"] = title

                        writers = ci("Writer")
                        if writers:
                            result["authors"] = [w.strip() for w in writers.split(",") if w.strip()]

                        result["description"] = ci("Summary")
                        result["language"] = ci("LanguageISO")

                        year = ci("Year")
                        month = ci("Month") or "1"
                        day = ci("Day") or "1"
                        if year:
                            try:
                                result["published_date"] = datetime(
                                    int(year), int(month), int(day)
                                )
                            except ValueError:
                                pass
                    except ET.ParseError:
                        pass

                # First image as cover
                image_names = sorted(
                    n for n in names if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                )
                if image_names:
                    result["cover_image"] = zf.read(image_names[0])
        except (zipfile.BadZipFile, OSError):
            pass
        return result

    def detect_format(self, file_path: Path) -> Optional[str]:
        """Detect book format, preferring file content over filename extension.

        We sniff magic bytes / container shape first so a renamed file (or a
        malicious upload) cannot cause the wrong extractor to run on attacker-
        controlled bytes. Falls back to extension only when the file is
        unreadable or the content sniffer cannot identify it.
        """
        content_fmt = detect_format_from_content(file_path)
        if content_fmt is not None:
            return content_fmt

        ext = file_path.suffix.lower()
        format_map = {
            ".epub": "epub",
            ".pdf": "pdf",
            ".cbz": "cbz",
            ".cbr": "cbr",
            ".mobi": "mobi",
            ".azw": "azw",
            ".azw3": "azw3",
            ".fb2": "fb2",
            ".djvu": "djvu",
        }
        return format_map.get(ext)


def detect_format_from_content(file_path: Path) -> Optional[str]:
    """Identify a book file's format by sniffing its bytes.

    Returns one of: "epub", "pdf", "cbz", "cbr", "mobi", "azw3", "fb2",
    "djvu", or None if the format cannot be determined from content.

    Order of checks is by signature reliability (PDF/DJVU/MOBI/RAR magic
    numbers first; then ZIP containers disambiguated by inner contents
    since both EPUB and CBZ are ZIPs; FB2 last because it's an XML
    document and we want to keep the read budget small).
    """
    try:
        with file_path.open("rb") as f:
            head = f.read(2048)
    except OSError:
        return None

    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"AT&TFORM"):
        return "djvu"
    # MOBI / AZW / AZW3: PalmDOC header has "BOOKMOBI" at offset 60.
    if len(head) >= 68 and head[60:68] == b"BOOKMOBI":
        # MOBI vs AZW3 is a version distinction inside the MOBI header;
        # for our routing they share an extractor. Prefer the explicit
        # extension if it disambiguates, otherwise call it MOBI.
        ext = file_path.suffix.lower()
        if ext in (".azw", ".azw3"):
            return ext.lstrip(".")
        return "mobi"
    # RAR (CBR): "Rar!\x1a\x07\x00" (v1.5) or "Rar!\x1a\x07\x01\x00" (v5)
    if head.startswith(b"Rar!\x1a\x07\x00") or head.startswith(b"Rar!\x1a\x07\x01\x00"):
        return "cbr"
    # ZIP container: could be EPUB or CBZ.
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        try:
            with zipfile.ZipFile(file_path) as zf:
                # EPUB spec: a "mimetype" entry containing exactly
                # "application/epub+zip" is the canonical signal.
                try:
                    mt = zf.read("mimetype").strip()
                    if mt == b"application/epub+zip":
                        return "epub"
                except KeyError:
                    pass
                names = zf.namelist()
                if "META-INF/container.xml" in names:
                    return "epub"
                # CBZ: comic-style archives are ZIPs of image files.
                image_exts = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
                if any(n.lower().endswith(image_exts) for n in names):
                    return "cbz"
        except zipfile.BadZipFile:
            return None
        return None
    # FB2: XML document with a FictionBook root element.
    if head.startswith(b"<?xml") or head.startswith(b"\xef\xbb\xbf<?xml"):
        if b"<FictionBook" in head or b"<fictionbook" in head.lower():
            return "fb2"
    return None


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse an ISO-ish date string into a datetime."""
    for fmt, length in [
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%d", 10),
        ("%Y-%m", 7),
        ("%Y", 4),
    ]:
        try:
            return datetime.strptime(date_str[:length], fmt)
        except ValueError:
            continue
    return None


def _parse_pdf_date(date_str: str) -> Optional[datetime]:
    """Parse PDF date format: D:YYYYMMDDHHmmSS"""
    s = date_str.lstrip("D:").replace("'", "")
    for fmt, length in [("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8), ("%Y", 4)]:
        try:
            return datetime.strptime(s[:length], fmt)
        except ValueError:
            continue
    return None


metadata_service = MetadataService()
