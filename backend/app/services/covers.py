"""Cover extraction and processing service."""

import hashlib
from pathlib import Path
from typing import Optional

from app.config import get_settings

settings = get_settings()

_SUPPORTED_FORMATS = {"jpeg", "jpg", "png", "webp", "gif"}
_THUMBNAIL_SIZE = (300, 450)  # width x height


class CoverService:
    """Saves and thumbnails book cover images."""

    def __init__(self):
        self.covers_path = Path(settings.COVERS_PATH)

    async def save_cover(
        self, cover_bytes: bytes, book_uuid: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Save cover bytes, generate thumbnail, return (hash, format)."""
        if not cover_bytes:
            return None, None
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(cover_bytes))
            img_format = (img.format or "JPEG").lower()
            if img_format == "jpg":
                img_format = "jpeg"
            if img_format not in _SUPPORTED_FORMATS:
                img_format = "jpeg"

            cover_hash = hashlib.sha256(cover_bytes).hexdigest()
            self.covers_path.mkdir(parents=True, exist_ok=True)

            # Save full cover
            full_path = self.covers_path / f"{book_uuid}.{img_format}"
            with open(full_path, "wb") as f:
                f.write(cover_bytes)

            # Save thumbnail
            thumb_path = self.covers_path / f"{book_uuid}_thumb.{img_format}"
            img_rgb = img.convert("RGB")
            img_rgb.thumbnail(_THUMBNAIL_SIZE, Image.LANCZOS)
            img_rgb.save(str(thumb_path), format=img_format.upper().replace("JPEG", "JPEG"))

            return cover_hash, img_format
        except Exception:
            return None, None

    async def delete_cover(self, book_uuid: str, cover_format: str) -> None:
        """Remove cover files for a book."""
        for suffix in ["", "_thumb"]:
            path = self.covers_path / f"{book_uuid}{suffix}.{cover_format}"
            if path.exists():
                path.unlink()


cover_service = CoverService()
