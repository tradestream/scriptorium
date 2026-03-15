"""Format conversion service.

Supports EPUB → KEPUB for Kobo devices via kepubify (optional, install separately).
"""
import asyncio
import shutil
from pathlib import Path
from typing import Optional


SUPPORTED_OUTPUT_FORMATS = ["kepub"]


class ConversionService:
    async def convert_file(
        self,
        input_path: Path,
        output_format: str,
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Convert input_path to output_format. Returns path to output file, or None on failure."""
        output_format = output_format.lower().lstrip('.')
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported format: {output_format}. Supported: {SUPPORTED_OUTPUT_FORMATS}")

        out_dir = output_dir or input_path.parent
        output_path = out_dir / f"{input_path.stem}.kepub.epub"
        return await self._epub_to_kepub(input_path, output_path)

    async def _epub_to_kepub(self, input_path: Path, output_path: Path) -> Optional[Path]:
        """Convert EPUB → KEPUB using kepubify if installed."""
        kepubify = shutil.which("kepubify")
        if not kepubify:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                kepubify, "-o", str(output_path.parent), str(input_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)
            return output_path if output_path.exists() else None
        except Exception:
            return None

    async def get_supported_formats(self) -> list[str]:
        return SUPPORTED_OUTPUT_FORMATS


conversion_service = ConversionService()
