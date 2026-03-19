"""DiViNa (Digital Visual Narratives) WebPub Manifest generation.

Produces Readium WebPub Manifest (JSON) for CBZ/CBR comic files,
enabling reading in any Readium-compatible client (Thorium, R2 Reader,
Panels, etc.).

Spec: https://readium.org/webpub-manifest/profiles/divina
"""

import logging
import zipfile
from pathlib import Path
from typing import Optional

from app.config import resolve_path

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp"}


def generate_divina_manifest(
    edition_id: int,
    file_id: int,
    file_path: str,
    title: str,
    authors: list[str],
    base_url: str,
    reading_direction: str = "ltr",
    page_count: Optional[int] = None,
) -> Optional[dict]:
    """Generate a DiViNa WebPub Manifest for a comic file.

    Returns a dict matching the Readium WebPub Manifest schema, or None on failure.
    """
    resolved = resolve_path(file_path)
    path = Path(resolved)
    if not path.exists():
        return None

    # List image pages in the archive
    pages = _list_pages(path)
    if not pages:
        return None

    page_base = f"{base_url}/api/v1/books/{edition_id}/files/{file_id}/pages"

    manifest = {
        "@context": "https://readium.org/webpub-manifest/context.jsonld",
        "metadata": {
            "@type": "http://schema.org/ComicIssue",
            "conformsTo": "https://readium.org/webpub-manifest/profiles/divina",
            "title": title,
            "author": authors,
            "readingProgression": reading_direction,
            "numberOfPages": len(pages),
        },
        "readingOrder": [
            {
                "href": f"{page_base}/{i}",
                "type": _image_mime(page_name),
                "properties": {"page": "center"},
            }
            for i, page_name in enumerate(pages)
        ],
    }

    # Add cover as first resource
    if pages:
        manifest["resources"] = [
            {
                "href": f"{page_base}/0",
                "type": _image_mime(pages[0]),
                "rel": "cover",
            }
        ]

    # Table of contents (none for simple comics, could be chapters)
    manifest["toc"] = []

    return manifest


def _list_pages(archive_path: Path) -> list[str]:
    """List image filenames in a CBZ archive, sorted naturally."""
    try:
        with zipfile.ZipFile(str(archive_path), "r") as zf:
            images = [
                name for name in zf.namelist()
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS
                and not name.startswith("__MACOSX")
                and not Path(name).name.startswith(".")
            ]
            return sorted(images)
    except Exception as exc:
        logger.debug("Failed to list pages in %s: %s", archive_path, exc)
        return []


def _image_mime(filename: str) -> str:
    """Map image extension to MIME type."""
    ext = Path(filename).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".avif": "image/avif",
        ".bmp": "image/bmp",
    }.get(ext, "image/jpeg")
