"""Kobo font bundle service.

Stock Kobos won't accept fonts over the sync API; the user plugs the
device in via USB and copies the bundle into the device's ``.fonts/``
folder. Our job is to scan a curated source directory, group files by
family, and emit a clean zip on demand.

We don't patch the font binary's name table (the kobo-font-fix trick
that needs ``fonttools``). The source folder already uses Kobo-friendly
``Family.ttf`` / ``Family-Bold.ttf`` / ``Family-Italic.ttf`` /
``Family-BoldItalic.ttf`` filenames, which recent Nickel firmware
groups correctly on its own. If a user later hits a font that needs a
binary fix, we can introduce ``fonttools`` then.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.config import get_settings, resolve_path

logger = logging.getLogger(__name__)

FONT_EXTENSIONS = {".ttf", ".otf"}

# Kobo's font picker keys off the part of the filename before the first
# ``-``: ``Bookerly-BoldItalic.ttf`` → "Bookerly". Match that so our
# UI grouping mirrors what users will see on the device.
_FAMILY_RE = re.compile(r"^(?P<family>[^-]+?)(?:-(?P<style>.+))?$")


@dataclass(frozen=True)
class FontFile:
    family: str
    style: str       # "Regular" / "Bold" / "Italic" / "BoldItalic" / etc.
    filename: str
    size_bytes: int


def _fonts_dir() -> Path:
    return Path(resolve_path(get_settings().KOBO_FONTS_PATH))


def _classify(path: Path) -> FontFile | None:
    if path.suffix.lower() not in FONT_EXTENSIONS:
        return None
    stem = path.stem
    m = _FAMILY_RE.match(stem)
    family = (m.group("family") if m else stem).strip()
    style = (m.group("style") if m and m.group("style") else "Regular").strip()
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return FontFile(family=family, style=style, filename=path.name, size_bytes=size)


def _walk_fonts(root: Path) -> Iterator[Path]:
    for p in sorted(root.iterdir() if root.exists() else []):
        if p.is_file():
            yield p


def list_fonts() -> dict:
    """Return families grouped, plus aggregate stats for the UI."""
    root = _fonts_dir()
    families: dict[str, list[FontFile]] = {}
    total_bytes = 0
    total_files = 0
    if not root.exists():
        return {
            "available": False,
            "path": str(root),
            "families": [],
            "total_files": 0,
            "total_bytes": 0,
        }
    for path in _walk_fonts(root):
        ff = _classify(path)
        if ff is None:
            continue
        families.setdefault(ff.family, []).append(ff)
        total_bytes += ff.size_bytes
        total_files += 1
    family_list = [
        {
            "family": fam,
            "styles": [
                {"style": f.style, "filename": f.filename, "size_bytes": f.size_bytes}
                for f in sorted(files, key=lambda x: x.style)
            ],
        }
        for fam, files in sorted(families.items(), key=lambda kv: kv[0].lower())
    ]
    return {
        "available": True,
        "path": str(root),
        "families": family_list,
        "total_files": total_files,
        "total_bytes": total_bytes,
    }


def build_bundle() -> bytes:
    """Build an in-memory zip of every TTF/OTF in the source directory.

    Files land at the zip root with their original names. Users unzip
    directly into the Kobo's ``.fonts/`` folder — no nested directory
    so drag-and-drop "just works."
    """
    root = _fonts_dir()
    if not root.exists():
        raise FileNotFoundError(f"Fonts directory not found: {root}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        count = 0
        for path in _walk_fonts(root):
            if path.suffix.lower() not in FONT_EXTENSIONS:
                continue
            zf.write(path, arcname=path.name)
            count += 1
    if count == 0:
        raise FileNotFoundError(f"No TTF/OTF files found in {root}")
    return buf.getvalue()
