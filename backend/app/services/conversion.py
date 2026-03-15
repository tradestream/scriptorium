"""Format conversion service using Calibre CLI."""
from pathlib import Path
from typing import Optional
from app.config import get_settings
from app.utils.calibre import convert_ebook

settings = get_settings()

SUPPORTED_OUTPUT_FORMATS = ["epub", "mobi", "azw3", "pdf", "txt", "html", "rtf", "odt"]


class ConversionService:
    async def convert_file(
        self,
        input_path: Path,
        output_format: str,
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Convert input_path to output_format. Returns path to output file."""
        output_format = output_format.lower().lstrip('.')
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported format: {output_format}")

        stem = input_path.stem
        out_dir = output_dir or input_path.parent
        output_path = out_dir / f"{stem}.{output_format}"

        success = await convert_ebook(input_path, output_path, output_format)
        return output_path if success else None

    async def get_supported_formats(self) -> list[str]:
        return SUPPORTED_OUTPUT_FORMATS


conversion_service = ConversionService()
