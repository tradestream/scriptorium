"""Calibre CLI subprocess wrapper."""
import asyncio
from pathlib import Path
from typing import Optional
from app.config import get_settings

settings = get_settings()


async def run_calibre_command(command: str, args: list[str], timeout: int = 300) -> tuple[int, str, str]:
    calibre_path = Path(settings.CALIBRE_PATH)
    cmd_path = str(calibre_path / command)
    try:
        proc = await asyncio.create_subprocess_exec(
            cmd_path, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(errors='replace'), stderr.decode(errors='replace')
    except asyncio.TimeoutError:
        return 124, "", f"Command timeout after {timeout}s"
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd_path}"
    except Exception as e:
        return 1, "", str(e)


async def get_ebook_metadata(file_path: Path) -> Optional[dict]:
    """Extract metadata using ebook-meta."""
    rc, stdout, stderr = await run_calibre_command("ebook-meta", [str(file_path)])
    if rc != 0:
        return None
    meta = {}
    for line in stdout.splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            k = key.strip().lower().replace(' ', '_')
            v = val.strip()
            if v and v != 'Unknown':
                meta[k] = v
    # Normalize common fields
    result = {}
    if 'title' in meta:
        result['title'] = meta['title']
    if 'author(s)' in meta:
        result['authors'] = [a.strip() for a in meta['author(s)'].split('&')]
    if 'tags' in meta:
        result['tags'] = [t.strip() for t in meta['tags'].split(',')]
    if 'isbn' in meta:
        result['isbn'] = meta['isbn']
    if 'published' in meta:
        result['published_date'] = meta['published'][:10]
    if 'languages' in meta:
        result['language'] = meta['languages'].split(',')[0].strip()
    if 'comments' in meta:
        result['description'] = meta['comments']
    return result or None


async def convert_ebook(input_path: Path, output_path: Path, output_format: str) -> bool:
    """Convert ebook using ebook-convert."""
    rc, stdout, stderr = await run_calibre_command(
        "ebook-convert",
        [str(input_path), str(output_path)],
        timeout=600,
    )
    return rc == 0 and output_path.exists()
