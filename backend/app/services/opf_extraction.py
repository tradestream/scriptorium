"""OPF metadata extraction — reads embedded Dublin Core metadata from EPUB files.

Extracts ISBN, publisher, language, description, authors, and published date
from the OPF package document inside EPUB archives.
"""

import logging
import re
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from app.utils.isbn import clean as isbn_clean, validate_isbn13_checksum, validate_isbn10_checksum, isbn10_to_isbn13

logger = logging.getLogger("scriptorium.opf")

DC_NS = "http://purl.org/dc/elements/1.1/"
OPF_NS = "http://www.idpf.org/2007/opf"
NS = {"dc": DC_NS, "opf": OPF_NS}

_HTML_TAG = re.compile(r"<[^>]+>")

LANG_MAP = {
    "en": "English", "en-us": "English", "en-gb": "English", "en-au": "English", "en-ca": "English",
    "eng": "English",
    "de": "German", "de-de": "German", "ger": "German", "deu": "German",
    "es": "Spanish", "es-es": "Spanish", "spa": "Spanish",
    "fr": "French", "fr-fr": "French", "fre": "French", "fra": "French",
    "pt": "Portuguese", "pt-br": "Portuguese", "por": "Portuguese",
    "it": "Italian", "it-it": "Italian", "ita": "Italian",
    "nl": "Dutch", "nl-nl": "Dutch", "dut": "Dutch", "nld": "Dutch",
    "ja": "Japanese", "ja-jp": "Japanese", "jpn": "Japanese",
    "zh": "Chinese", "zh-cn": "Chinese", "zh-tw": "Chinese", "chi": "Chinese", "zho": "Chinese",
    "la": "Latin", "lat": "Latin",
    "el": "Greek", "gre": "Greek", "ell": "Greek",
    "ru": "Russian", "rus": "Russian",
    "ar": "Arabic", "ara": "Arabic",
    "he": "Hebrew", "heb": "Hebrew",
    "ko": "Korean", "kor": "Korean",
    "sv": "Swedish", "swe": "Swedish",
    "da": "Danish", "dan": "Danish",
    "no": "Norwegian", "nor": "Norwegian",
    "fi": "Finnish", "fin": "Finnish",
    "pl": "Polish", "pol": "Polish",
    "cs": "Czech", "cze": "Czech", "ces": "Czech",
    "hr": "Croatian", "hrv": "Croatian",
    "bg": "Bulgarian", "bul": "Bulgarian",
    "et": "Estonian", "est": "Estonian",
    "hu": "Hungarian", "hun": "Hungarian",
    "ro": "Romanian", "rum": "Romanian", "ron": "Romanian",
    "tr": "Turkish", "tur": "Turkish",
    "uk": "Ukrainian", "ukr": "Ukrainian",
}


def _find_opf(zf: zipfile.ZipFile) -> Optional[str]:
    """Locate the OPF file path inside an EPUB archive."""
    try:
        container = zf.read("META-INF/container.xml").decode("utf-8")
        m = re.search(r'rootfile[^>]+full-path="([^"]+)"', container)
        if m:
            return m.group(1)
    except Exception:
        pass
    for name in zf.namelist():
        if name.endswith(".opf"):
            return name
    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return _HTML_TAG.sub("", text).strip()


def _normalize_language(raw: str) -> str:
    """Normalize language codes/names to full English names."""
    key = raw.lower().strip()
    return LANG_MAP.get(key, raw.strip().title())


def _extract_isbn(identifiers: list[ET.Element]) -> tuple[Optional[str], Optional[str]]:
    """Extract ISBN-13 and ISBN-10 from dc:identifier elements."""
    for ident in identifiers:
        text = (ident.text or "").replace("-", "").replace(" ", "").strip()
        scheme = ident.get(f"{{{OPF_NS}}}scheme", "").upper()

        # ISBN-13
        if re.match(r"^97[89]\d{10}$", text) and validate_isbn13_checksum(text):
            isbn13 = text
            core = isbn13[3:12]
            total = sum((10 - i) * int(d) for i, d in enumerate(core))
            r = (11 - (total % 11)) % 11
            isbn10 = core + ("X" if r == 10 else str(r))
            return isbn13, isbn10

        # ISBN-10
        if (re.match(r"^\d{9}[\dXx]$", text) or scheme == "ISBN") and len(text) == 10:
            if validate_isbn10_checksum(text):
                isbn13 = isbn10_to_isbn13(text)
                return isbn13, text

    return None, None


def _fix_author_name(name: str) -> str:
    """Convert 'Last, First' to 'First Last'."""
    name = name.strip()
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 2 and parts[1] and not " " in parts[0]:
        return f"{parts[1]} {parts[0]}"
    return name


def extract_opf_metadata(filepath: str | Path) -> dict:
    """Extract Dublin Core metadata from an EPUB's OPF file.

    Returns dict with: isbn_13, isbn_10, publisher, language,
    description, authors (list[str]), published_date.
    """
    result = {
        "isbn_13": None, "isbn_10": None,
        "publisher": None, "language": None,
        "description": None, "authors": [],
        "published_date": None,
    }

    filepath = Path(filepath)
    if not filepath.exists() or filepath.suffix.lower() != ".epub":
        return result

    try:
        with zipfile.ZipFile(filepath) as zf:
            opf_path = _find_opf(zf)
            if not opf_path:
                return result

            tree = ET.parse(zf.open(opf_path))
            root = tree.getroot()

            # Find metadata element (with or without namespace)
            meta = root.find(f"{{{OPF_NS}}}metadata")
            if meta is None:
                meta = root.find("metadata")
            if meta is None:
                return result

            # ISBN from identifiers
            identifiers = meta.findall(f"{{{DC_NS}}}identifier")
            if not identifiers:
                identifiers = meta.findall("identifier")
            isbn13, isbn10 = _extract_isbn(identifiers)
            result["isbn_13"] = isbn13
            result["isbn_10"] = isbn10

            # Publisher
            pub = meta.findtext(f"{{{DC_NS}}}publisher")
            if not pub:
                pub = meta.findtext("publisher")
            if pub and pub.strip():
                result["publisher"] = pub.strip()

            # Language
            lang = meta.findtext(f"{{{DC_NS}}}language")
            if not lang:
                lang = meta.findtext("language")
            if lang and lang.strip():
                result["language"] = _normalize_language(lang)

            # Description
            desc = meta.findtext(f"{{{DC_NS}}}description")
            if not desc:
                desc = meta.findtext("description")
            if desc:
                clean = _strip_html(desc)
                if len(clean) > 20:
                    result["description"] = clean

            # Authors
            creators = meta.findall(f"{{{DC_NS}}}creator")
            if not creators:
                creators = meta.findall("creator")
            BAD_AUTHORS = {"unknown", "various", "anonymous", "", "harriet elinor smith", "mark twain"}
            for el in creators:
                if el.text and el.text.strip():
                    name = _fix_author_name(el.text.strip())
                    if name.lower() not in BAD_AUTHORS:
                        result["authors"].append(name)

            # Published date
            date = meta.findtext(f"{{{DC_NS}}}date")
            if not date:
                date = meta.findtext("date")
            if date and re.match(r"\d{4}", date):
                result["published_date"] = date[:10]

    except Exception as exc:
        logger.debug("OPF extraction failed for %s: %s", filepath, exc)

    return result


async def extract_embedded_metadata_for_edition(edition_id: int) -> dict:
    """Extract embedded metadata from an edition's files and update empty DB fields.

    Supports:
    - EPUB: OPF Dublin Core metadata
    - CBZ: ComicInfo.xml
    - CBR: ComicInfo.xml

    Returns dict of fields that were found and applied.
    """
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.database import get_session_factory
    from app.models.edition import Edition
    from app.models.work import Work
    from app.models.book import Author

    factory = get_session_factory()

    # Phase 1: resolve file path and format
    async with factory() as db:
        result = await db.execute(
            select(Edition)
            .where(Edition.id == edition_id)
            .options(
                joinedload(Edition.files),
                joinedload(Edition.work).options(joinedload(Work.authors)),
            )
        )
        edition = result.unique().scalar_one_or_none()
        if not edition or not edition.files:
            return {}

        # Prefer EPUB for OPF, then CBZ/CBR for ComicInfo
        FORMAT_PRIORITY = {"epub": 0, "cbz": 1, "cbr": 2}
        eligible = [f for f in edition.files if f.format.lower() in FORMAT_PRIORITY]
        if not eligible:
            # Mark as scanned even if no extractable format
            edition.opf_scanned = True
            await db.commit()
            return {}

        eligible.sort(key=lambda f: FORMAT_PRIORITY.get(f.format.lower(), 99))
        chosen = eligible[0]
        fpath = Path(chosen.file_path)
        fmt = chosen.format.lower()

        had_isbn = bool(edition.isbn)
        had_publisher = bool(edition.publisher)
        had_language = bool(edition.language)
        had_description = bool(edition.work and edition.work.description)
        had_authors = bool(edition.work and edition.work.authors)
        had_date = bool(edition.published_date)

        if not fpath.exists():
            edition.opf_scanned = True
            await db.commit()
            return {}

    # Phase 2: extract metadata based on format
    meta = {}
    try:
        if fmt == "epub":
            meta = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, extract_opf_metadata, fpath),
                timeout=10.0,
            )
        elif fmt in ("cbz", "cbr"):
            from app.services.comicinfo import parse_comicinfo_from_cbz, parse_comicinfo_from_cbr
            parser = parse_comicinfo_from_cbz if fmt == "cbz" else parse_comicinfo_from_cbr
            comicinfo = await asyncio.get_event_loop().run_in_executor(None, parser, str(fpath))
            if comicinfo:
                # Normalize comicinfo fields to our standard dict
                meta = {
                    "isbn_13": None, "isbn_10": None,
                    "publisher": comicinfo.get("publisher"),
                    "language": comicinfo.get("language_iso"),
                    "description": comicinfo.get("description"),
                    "authors": [],
                    "published_date": None,
                }
                # Extract authors from credits
                for credit in comicinfo.get("credits", []):
                    if credit.get("role", "").lower() in ("writer", "author"):
                        meta["authors"].append(credit["person"])
                # Published date from year/month
                if comicinfo.get("year"):
                    month = comicinfo.get("month", "01")
                    meta["published_date"] = f"{comicinfo['year']}-{str(month).zfill(2)}-01"
                # Language normalization
                if meta["language"]:
                    meta["language"] = _normalize_language(meta["language"])
    except asyncio.TimeoutError:
        meta = {}
    except Exception as exc:
        logger.debug("Embedded metadata extraction failed for edition %d: %s", edition_id, exc)
        meta = {}

    if not meta:
        async with factory() as db:
            ed = await db.get(Edition, edition_id)
            if ed:
                ed.opf_scanned = True
                await db.commit()
        return {}

    # Phase 3: write results to DB (only fill empty fields)
    found = {}
    async with factory() as db:
        result = await db.execute(
            select(Edition)
            .where(Edition.id == edition_id)
            .options(joinedload(Edition.work).options(joinedload(Work.authors)))
        )
        edition = result.unique().scalar_one_or_none()
        if not edition:
            return {}

        work = edition.work

        if meta.get("isbn_13") and not had_isbn:
            edition.isbn = meta["isbn_13"]
            edition.isbn_10 = meta.get("isbn_10")
            found["isbn"] = True

        if meta.get("publisher") and not had_publisher:
            edition.publisher = meta["publisher"]
            found["publisher"] = True

        if meta.get("language") and not had_language:
            edition.language = meta["language"]
            found["language"] = True

        if meta.get("description") and not had_description and work:
            work.description = meta["description"]
            found["description"] = True

        if meta.get("published_date") and not had_date:
            edition.published_date = meta["published_date"]
            found["date"] = True

        if meta.get("authors") and not had_authors and work:
            for aname in meta["authors"]:
                existing = await db.execute(
                    select(Author).where(Author.name == aname)
                )
                author = existing.scalar_one_or_none()
                if not author:
                    author = Author(name=aname)
                    db.add(author)
                    await db.flush()
                if author not in work.authors:
                    work.authors.append(author)
            found["authors"] = True

        edition.opf_scanned = True
        await db.commit()

    return found
