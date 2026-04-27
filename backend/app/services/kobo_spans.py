"""KoboSpan extraction and resolution for KEPUB round-tripping.

kepubify wraps the textual content of every KEPUB chapter in
``<span class="koboSpan" id="kobo.N.M">…</span>`` elements. Kobo Nickel
uses those ids to identify the user's reading position — both when
reporting ``CurrentBookmark.Location.Value`` back to a sync server and
when restoring position after reload.

Without storing the per-chapter span sequences ourselves, two things
break:

1. **Emit**: when sending a bookmark to the device we have nothing real
   to put in ``Value`` and fall back to a synthetic ``"spine#N"`` token.
   Some devices accept it but won't restore position to a paragraph;
   they just open the chapter at the top.
2. **Receive**: when a device posts a real KoboSpan id back, we cannot
   resolve it to a position within our progress model and the bookmark
   silently disappears.

This module owns:
- ``extract_span_maps(kepub_path)`` — parse a generated .kepub.epub and
  return per-chapter ordered span id sequences.
- ``store_span_maps(edition_file_id, maps, db)`` — persist them.
- ``span_for_progress(edition_file_id, progress, db)`` — pick the span
  to emit for a global ``content_source_progress`` value (0-1).
- ``resolve_span(edition_file_id, chapter_href, span_id, db)`` — turn an
  incoming (chapter, span) pair back into (spine_index, in-chapter
  fraction).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kobo_span import KoboSpanMap


_OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "cn": "urn:oasis:names:tc:opendocument:xmlns:container",
}


def extract_span_maps(kepub_path: Path) -> list[dict]:
    """Walk a generated KEPUB and return one entry per spine document.

    Returns a list of ``{"spine_index": int, "chapter_href": str,
    "span_ids": list[str]}`` in spine order. Documents without any
    koboSpan ids are still included with an empty ``span_ids`` list so
    callers can rely on every spine slot being represented.
    """
    if not kepub_path.exists():
        return []

    out: list[dict] = []
    try:
        with zipfile.ZipFile(kepub_path) as zf:
            try:
                container_xml = zf.read("META-INF/container.xml")
            except KeyError:
                return []
            container_root = ET.fromstring(container_xml)
            rootfile = container_root.find(".//cn:rootfile", _OPF_NS)
            if rootfile is None:
                return []
            opf_path = rootfile.get("full-path", "")
            try:
                opf_root = ET.fromstring(zf.read(opf_path))
            except (KeyError, ET.ParseError):
                return []

            opf_dir = str(Path(opf_path).parent)

            # manifest: id → href (and media-type for filtering)
            manifest = opf_root.find("opf:manifest", _OPF_NS)
            if manifest is None:
                return []
            manifest_map: dict[str, tuple[str, str]] = {}
            for item in manifest:
                item_id = item.get("id", "")
                href = item.get("href", "")
                mt = item.get("media-type", "")
                if item_id and href:
                    manifest_map[item_id] = (href, mt)

            spine = opf_root.find("opf:spine", _OPF_NS)
            if spine is None:
                return []

            for spine_index, itemref in enumerate(spine):
                idref = itemref.get("idref", "")
                href, mt = manifest_map.get(idref, ("", ""))
                if not href or "html" not in mt.lower():
                    continue

                chapter_path = href if not opf_dir or opf_dir == "." else f"{opf_dir}/{href}"
                # Drop any fragment from the href since spine items address
                # whole documents.
                chapter_path = chapter_path.split("#", 1)[0]
                try:
                    body = zf.read(chapter_path)
                except KeyError:
                    continue

                span_ids = _extract_span_ids(body)
                out.append(
                    {
                        "spine_index": spine_index,
                        "chapter_href": chapter_path,
                        "span_ids": span_ids,
                    }
                )
    except zipfile.BadZipFile:
        return []
    return out


def _extract_span_ids(xhtml_bytes: bytes) -> list[str]:
    """Pull every koboSpan id out of one chapter document, in document order.

    Uses a tolerant ElementTree parse and an XHTML-namespace-aware lookup;
    falls back to a regex pass when the document has malformed markup or
    declarations the parser refuses (kepubify's output is well-formed
    XHTML in practice but EPUBs in the wild are not).
    """
    ids: list[str] = []
    try:
        # ElementTree won't follow XHTML namespaces by default; iterate all
        # elements and check for the koboSpan class regardless of namespace.
        root = ET.fromstring(xhtml_bytes)
        for el in root.iter():
            if el.get("class", "") == "koboSpan":
                span_id = el.get("id", "")
                if span_id:
                    ids.append(span_id)
        if ids:
            return ids
    except ET.ParseError:
        pass

    # Fallback: regex scan. Only used when ET parsing fails; not as
    # accurate (no element ordering guarantee across multi-line spans)
    # but better than dropping the chapter entirely.
    import re

    pattern = re.compile(
        rb'class\s*=\s*"koboSpan"[^>]*\bid\s*=\s*"([^"]+)"', re.IGNORECASE
    )
    pattern_rev = re.compile(
        rb'\bid\s*=\s*"([^"]+)"[^>]*class\s*=\s*"koboSpan"', re.IGNORECASE
    )
    for m in pattern.finditer(xhtml_bytes):
        ids.append(m.group(1).decode("utf-8", "replace"))
    for m in pattern_rev.finditer(xhtml_bytes):
        ids.append(m.group(1).decode("utf-8", "replace"))
    # Dedupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            unique.append(i)
    return unique


async def store_span_maps(
    edition_file_id: int,
    maps: list[dict],
    db: AsyncSession,
) -> int:
    """Replace any existing maps for ``edition_file_id`` with ``maps``.

    Returns the number of rows written. Called after a successful KEPUB
    conversion so the stored ids match the .kepub on disk.
    """
    # Drop any prior rows; the KEPUB may have been regenerated.
    existing = await db.execute(
        select(KoboSpanMap).where(KoboSpanMap.edition_file_id == edition_file_id)
    )
    for row in existing.scalars().all():
        await db.delete(row)

    written = 0
    for entry in maps:
        db.add(
            KoboSpanMap(
                edition_file_id=edition_file_id,
                spine_index=entry["spine_index"],
                chapter_href=entry["chapter_href"],
                span_ids=json.dumps(entry["span_ids"]),
            )
        )
        written += 1
    await db.flush()
    return written


async def _load_maps(
    edition_file_id: int, db: AsyncSession
) -> list[KoboSpanMap]:
    res = await db.execute(
        select(KoboSpanMap)
        .where(KoboSpanMap.edition_file_id == edition_file_id)
        .order_by(KoboSpanMap.spine_index)
    )
    return list(res.scalars().all())


async def span_for_progress(
    edition_file_id: int,
    progress: float,
    db: AsyncSession,
) -> Optional[tuple[str, str, int]]:
    """Pick a (chapter_href, span_id, spine_index) to emit for a global progress.

    ``progress`` is 0.0-1.0 across the whole book. We sum span counts to
    map a global fraction to a specific span. Returns ``None`` if no map
    exists for this file (caller should fall back to synthetic values).
    """
    maps = await _load_maps(edition_file_id, db)
    if not maps:
        return None

    decoded: list[tuple[KoboSpanMap, list[str]]] = []
    total = 0
    for m in maps:
        try:
            ids = json.loads(m.span_ids)
        except (TypeError, ValueError):
            ids = []
        decoded.append((m, ids))
        total += len(ids)

    if total == 0:
        # Map exists but no spans were extracted (e.g. fixed-layout chapters).
        return None

    progress = max(0.0, min(1.0, progress))
    target = int(progress * total)
    if target >= total:
        target = total - 1

    cursor = 0
    for m, ids in decoded:
        if not ids:
            continue
        if target < cursor + len(ids):
            within = target - cursor
            return m.chapter_href, ids[within], m.spine_index
        cursor += len(ids)

    # Fallback to last span of last non-empty chapter.
    for m, ids in reversed(decoded):
        if ids:
            return m.chapter_href, ids[-1], m.spine_index
    return None


async def cfi_to_span_lookup(
    cfi: Optional[str],
    edition_file_id: int,
    db: AsyncSession,
) -> Optional[tuple[str, str, int]]:
    """Translate a web-reader CFI into the Kobo (chapter_href, span_id).

    Used by the Kobo emit path when ``EditionPosition.current_format`` is
    ``cfi`` (i.e. the most recent cursor came from the web reader). We
    parse out the spine_index, look up the matching chapter in the span
    map, and pick the koboSpan id at the in-chapter fraction the CFI's
    char offset suggests. Returns ``None`` when the CFI is malformed,
    the spine_index is out of range, or no spans were extracted for that
    chapter — in those cases the caller should fall back to chapter-only
    emit.
    """
    from app.utils.cfi import parse_cfi

    parsed = parse_cfi(cfi)
    if parsed is None:
        return None

    maps = await _load_maps(edition_file_id, db)
    target = next((m for m in maps if m.spine_index == parsed.spine_index), None)
    if target is None:
        return None
    try:
        spans = json.loads(target.span_ids)
    except (TypeError, ValueError):
        return None
    if not spans:
        return None

    span_idx = min(len(spans) - 1, int(parsed.in_chapter_fraction * len(spans)))
    return target.chapter_href, spans[span_idx], target.spine_index


async def span_to_cfi(
    chapter_href: str,
    span_id: str,
    edition_file_id: int,
    db: AsyncSession,
) -> Optional[str]:
    """Translate a Kobo (chapter_href, span_id) into a partial CFI.

    Used by the web-reader GET path when ``EditionPosition.current_format``
    is ``kobo_span`` (the most recent cursor came from the device). We
    look up the chapter in the span map to recover its spine_index and
    in-chapter position, then build a partial CFI that opens at that
    spine document. Without DOM-walking the chapter we can't reach the
    exact paragraph; epubjs's ``rendition.display(cfi)`` opens at chapter
    top — strictly better than dropping the cursor entirely.
    """
    from app.utils.cfi import build_partial_cfi

    if not chapter_href:
        return None
    maps = await _load_maps(edition_file_id, db)
    target_href = chapter_href.split("#", 1)[0].lstrip("./")
    for m in maps:
        normalized = m.chapter_href.split("#", 1)[0].lstrip("./")
        if normalized != target_href:
            continue
        try:
            spans = json.loads(m.span_ids)
        except (TypeError, ValueError):
            spans = []
        in_chapter_fraction = 0.0
        if spans and span_id:
            try:
                idx = spans.index(span_id)
            except ValueError:
                idx = 0
            if len(spans) > 0:
                in_chapter_fraction = idx / len(spans)
        return build_partial_cfi(m.spine_index, in_chapter_fraction)
    return None


async def resolve_span(
    edition_file_id: int,
    chapter_href: str,
    span_id: str,
    db: AsyncSession,
) -> Optional[tuple[int, float, float]]:
    """Resolve an incoming KoboSpan reference back into our position model.

    Returns ``(spine_index, in_chapter_fraction, global_fraction)`` or
    ``None`` when the chapter or span id is unknown.
    """
    maps = await _load_maps(edition_file_id, db)
    if not maps:
        return None

    decoded: list[tuple[KoboSpanMap, list[str]]] = []
    total = 0
    for m in maps:
        try:
            ids = json.loads(m.span_ids)
        except (TypeError, ValueError):
            ids = []
        decoded.append((m, ids))
        total += len(ids)

    # Match by chapter href (drop fragment, normalize separators).
    target_href = chapter_href.split("#", 1)[0].lstrip("./")

    cursor = 0
    for m, ids in decoded:
        normalized = m.chapter_href.split("#", 1)[0].lstrip("./")
        if normalized == target_href:
            try:
                idx = ids.index(span_id)
            except ValueError:
                # Chapter matched but the span id is not in our list.
                # Treat that as "start of chapter" rather than dropping.
                in_chapter = 0.0
                global_pos = (cursor / total) if total else 0.0
                return m.spine_index, in_chapter, global_pos
            in_chapter = (idx / len(ids)) if ids else 0.0
            global_pos = ((cursor + idx) / total) if total else 0.0
            return m.spine_index, in_chapter, global_pos
        cursor += len(ids)
    return None
