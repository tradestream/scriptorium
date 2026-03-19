"""ComicInfo.xml parser — extracts metadata from CBZ/CBR comic archives.

ComicInfo.xml is the standard metadata format for comic archives, originally
from ComicRack. Fields: Title, Series, Number, Volume, Summary, Year, Month,
Writer, Penciller, Inker, Colorist, Letterer, CoverArtist, Editor, Publisher,
Imprint, Genre, PageCount, LanguageISO, AgeRating, StoryArc, etc.
"""

import logging
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def parse_comicinfo_from_cbz(file_path: str) -> Optional[dict]:
    """Extract ComicInfo.xml from a CBZ file and parse it.

    Returns a dict with normalized metadata fields, or None if not found.
    """
    path = Path(file_path)
    if not path.exists():
        return None

    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            # ComicInfo.xml can be at root or in a subfolder
            for name in zf.namelist():
                if name.lower().endswith("comicinfo.xml"):
                    with zf.open(name) as f:
                        return _parse_xml(f.read())
    except (zipfile.BadZipFile, Exception) as exc:
        logger.debug("Failed to read ComicInfo.xml from %s: %s", file_path, exc)

    return None


def parse_comicinfo_from_cbr(file_path: str) -> Optional[dict]:
    """Extract ComicInfo.xml from a CBR (RAR) file."""
    try:
        import rarfile
        with rarfile.RarFile(str(file_path), "r") as rf:
            for name in rf.namelist():
                if name.lower().endswith("comicinfo.xml"):
                    with rf.open(name) as f:
                        return _parse_xml(f.read())
    except ImportError:
        logger.debug("rarfile not installed — cannot parse CBR metadata")
    except Exception as exc:
        logger.debug("Failed to read ComicInfo.xml from %s: %s", file_path, exc)

    return None


def _parse_xml(xml_bytes: bytes) -> dict:
    """Parse ComicInfo.xml content into a normalized dict."""
    root = ET.fromstring(xml_bytes)
    result = {}

    # Simple text fields
    _text = lambda tag: (root.findtext(tag) or "").strip() or None
    _int = lambda tag: int(root.findtext(tag)) if root.findtext(tag) and root.findtext(tag).strip().isdigit() else None

    result["title"] = _text("Title")
    result["series"] = _text("Series")
    result["issue_number"] = _text("Number")
    result["volume_number"] = _int("Volume")
    result["description"] = _text("Summary")
    result["year"] = _int("Year")
    result["month"] = _int("Month")
    result["day"] = _int("Day")
    result["page_count"] = _int("PageCount")
    result["language"] = _text("LanguageISO")
    result["comic_format"] = _text("Format")  # TPB, HC, etc.
    result["age_rating"] = _text("AgeRating")
    result["publisher"] = _text("Publisher")
    result["imprint"] = _text("Imprint")
    result["genre"] = _text("Genre")
    result["reading_direction"] = _text("Manga")  # "Yes" = RTL, "No"/"YesAndRightToLeft" = LTR

    # Map Manga field to ltr/rtl
    manga = (result.get("reading_direction") or "").lower()
    if manga in ("yes", "yesandrighttoleft"):
        result["reading_direction"] = "rtl"
    elif manga:
        result["reading_direction"] = "ltr"
    else:
        result["reading_direction"] = None

    # Story arcs (comma-separated)
    story_arc = _text("StoryArc")
    story_arc_number = _text("StoryArcNumber")
    if story_arc:
        arcs = [a.strip() for a in story_arc.split(",") if a.strip()]
        numbers = [n.strip() for n in (story_arc_number or "").split(",")]
        result["story_arcs"] = []
        for i, arc in enumerate(arcs):
            num = None
            if i < len(numbers) and numbers[i]:
                try:
                    num = float(numbers[i])
                except ValueError:
                    pass
            result["story_arcs"].append({"name": arc, "sequence": num})

    # Credits — comma-separated lists
    credit_fields = {
        "writer": "Writer",
        "penciler": "Penciller",
        "inker": "Inker",
        "colorist": "Colorist",
        "letterer": "Letterer",
        "cover_artist": "CoverArtist",
        "editor": "Editor",
    }
    credits = []
    for role, tag in credit_fields.items():
        val = _text(tag)
        if val:
            for name in val.split(","):
                name = name.strip()
                if name:
                    credits.append({"name": name, "role": role})
    result["credits"] = credits

    # Tags from Genre (comma-separated)
    if result.get("genre"):
        result["tags"] = [g.strip() for g in result["genre"].split(",") if g.strip()]

    # Cover image — first page with Type="FrontCover"
    pages = root.find("Pages")
    if pages is not None:
        for page in pages.findall("Page"):
            if page.get("Type") == "FrontCover":
                result["cover_page_index"] = int(page.get("Image", 0))
                break

    return result


async def apply_comicinfo(work, edition, comicinfo: dict, db) -> bool:
    """Apply parsed ComicInfo.xml metadata to a Work + Edition.

    Creates Publisher, Imprint, StoryArc, ComicCredit records as needed.
    Returns True if any field was changed.
    """
    from sqlalchemy import select
    from app.models.comic import Publisher, Imprint, StoryArc, StoryArcEntry, ComicCredit
    from app.models import Author

    changed = False

    # Publisher
    if comicinfo.get("publisher") and not work.publisher_id:
        pub_name = comicinfo["publisher"]
        pub = (await db.execute(select(Publisher).where(Publisher.name == pub_name))).scalar_one_or_none()
        if not pub:
            pub = Publisher(name=pub_name)
            db.add(pub)
            await db.flush()
        work.publisher_id = pub.id
        changed = True

        # Imprint
        if comicinfo.get("imprint"):
            imp_name = comicinfo["imprint"]
            imp = (await db.execute(
                select(Imprint).where(Imprint.name == imp_name, Imprint.publisher_id == pub.id)
            )).scalar_one_or_none()
            if not imp:
                imp = Imprint(name=imp_name, publisher_id=pub.id)
                db.add(imp)
                await db.flush()
            work.imprint_id = imp.id

    # Simple fields
    if comicinfo.get("issue_number") and not work.issue_number:
        work.issue_number = comicinfo["issue_number"]
        changed = True
    if comicinfo.get("volume_number") and not work.volume_number:
        work.volume_number = comicinfo["volume_number"]
        changed = True
    if comicinfo.get("reading_direction") and not work.reading_direction:
        work.reading_direction = comicinfo["reading_direction"]
        changed = True
    if comicinfo.get("page_count") and not work.page_count_comic:
        work.page_count_comic = comicinfo["page_count"]
        changed = True
    if comicinfo.get("comic_format") and not work.comic_format:
        work.comic_format = comicinfo["comic_format"]
        changed = True
    if comicinfo.get("age_rating") and not work.age_rating:
        work.age_rating = _normalize_age_rating(comicinfo["age_rating"])
        changed = True
    if comicinfo.get("description") and not work.description:
        work.description = comicinfo["description"]
        changed = True

    # Story arcs
    for arc_info in comicinfo.get("story_arcs", []):
        arc_name = arc_info["name"]
        arc = (await db.execute(select(StoryArc).where(StoryArc.name == arc_name))).scalar_one_or_none()
        if not arc:
            arc = StoryArc(name=arc_name)
            db.add(arc)
            await db.flush()
        # Check if entry already exists
        existing = (await db.execute(
            select(StoryArcEntry).where(StoryArcEntry.story_arc_id == arc.id, StoryArcEntry.work_id == work.id)
        )).scalar_one_or_none()
        if not existing:
            db.add(StoryArcEntry(
                story_arc_id=arc.id,
                work_id=work.id,
                sequence_number=arc_info.get("sequence"),
            ))
            changed = True

    # Credits
    for credit in comicinfo.get("credits", []):
        person_name = credit["name"]
        role = credit["role"]
        person = (await db.execute(select(Author).where(Author.name == person_name))).scalar_one_or_none()
        if not person:
            person = Author(name=person_name)
            db.add(person)
            await db.flush()
        existing = (await db.execute(
            select(ComicCredit).where(
                ComicCredit.work_id == work.id, ComicCredit.person_id == person.id, ComicCredit.role == role
            )
        )).scalar_one_or_none()
        if not existing:
            db.add(ComicCredit(work_id=work.id, person_id=person.id, role=role))
            changed = True

    return changed


def _normalize_age_rating(rating: str) -> str:
    """Map ComicInfo age ratings to our standard set."""
    r = rating.lower().strip()
    if r in ("everyone", "all ages", "kids to adults", "g"):
        return "everyone"
    if r in ("teen", "teen+", "12+", "pg", "t"):
        return "teen"
    if r in ("mature", "mature 17+", "17+", "m", "r"):
        return "mature"
    if r in ("adults only", "adults only 18+", "18+", "x", "explicit"):
        return "adult"
    return rating  # preserve unknown values
