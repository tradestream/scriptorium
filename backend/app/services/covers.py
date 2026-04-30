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
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Save cover bytes, generate thumbnail, extract dominant color.

        Returns (hash, format, hex_color).
        """
        if not cover_bytes:
            return None, None, None
        try:
            import io

            from PIL import Image

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

            # Extract dominant color
            color = self._dominant_color(img_rgb)

            return cover_hash, img_format, color
        except Exception:
            return None, None, None

    @staticmethod
    def _dominant_color(img) -> Optional[str]:
        """Extract the dominant color from an image as a hex string."""
        try:
            # Resize to 1x1 for average, or use quantize for dominant
            small = img.copy()
            small.thumbnail((50, 50))
            # Quantize to 5 colors, pick the most common non-white/non-black
            quantized = small.quantize(colors=5, method=0)
            palette = quantized.getpalette()
            if not palette:
                return None
            # Get color counts
            color_counts = sorted(quantized.getcolors(), key=lambda c: -c[0])
            for count, idx in color_counts:
                r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
                # Skip near-white and near-black
                if r + g + b > 700 or r + g + b < 60:
                    continue
                return f"#{r:02x}{g:02x}{b:02x}"
            # Fallback to most common
            if color_counts:
                idx = color_counts[0][1]
                r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
                return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            pass
        return None

    async def delete_cover(self, book_uuid: str, cover_format: str) -> None:
        """Remove cover files for a book."""
        for suffix in ["", "_thumb"]:
            path = self.covers_path / f"{book_uuid}{suffix}.{cover_format}"
            if path.exists():
                path.unlink()


cover_service = CoverService()
