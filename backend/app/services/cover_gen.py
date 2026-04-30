"""AI-powered book cover generation using Gemini image generation via OpenRouter.

Generates covers for books missing cover art, optimized for Kobo eInk displays.
Cover spec: 800x1224px (3:4 ratio) PNG, per kobolabs/epub-spec.
"""

import hashlib
import logging
from io import BytesIO
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Kobo optimal cover dimensions (3:4 ratio)
COVER_WIDTH = 800
COVER_HEIGHT = 1224


def _build_cover_prompt(title: str, author: str, description: str = "", genre: str = "") -> str:
    """Build a prompt for AI cover generation."""
    parts = [
        "Generate a book cover image for:",
        f"Title: {title}",
        f"Author: {author}",
    ]
    if genre:
        parts.append(f"Genre: {genre}")
    if description:
        # Truncate description to keep prompt focused
        parts.append(f"Description: {description[:300]}")

    parts.extend([
        "",
        "Requirements:",
        "- Professional book cover design, suitable for an e-reader",
        "- Portrait orientation (3:4 aspect ratio)",
        "- Clear, readable title text prominently displayed",
        "- Author name visible but smaller than title",
        "- Evocative imagery that reflects the book's theme",
        "- Clean, elegant design — not cluttered",
        "- No borders or frames",
        "- Style: sophisticated, literary, timeless",
    ])

    return "\n".join(parts)


async def generate_cover_ai(
    title: str,
    author: str,
    description: str = "",
    genre: str = "",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[bytes]:
    """Generate a book cover using AI image generation.

    Uses Gemini 2.5 Flash via OpenRouter for image generation.
    Returns PNG bytes or None if generation fails.
    """
    settings = get_settings()
    api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
    base_url = base_url or getattr(settings, 'OPENAI_BASE_URL', 'https://openrouter.ai/api/v1')
    # Use a model that supports image generation
    model = model or "google/gemini-2.5-flash-preview:thinking"

    if not api_key:
        logger.warning("No API key configured for cover generation")
        return None

    prompt = _build_cover_prompt(title, author, description, genre)

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    "max_tokens": 4096,
                    # Request image output if the model supports it
                    "response_format": {"type": "image"},
                },
            )

            if resp.status_code != 200:
                logger.warning("Cover generation API error: %d %s", resp.status_code, resp.text[:200])
                return None

            data = resp.json()

            # Extract image from response
            # Different models return images differently
            choices = data.get("choices", [])
            if not choices:
                return None

            message = choices[0].get("message", {})
            content = message.get("content", "")

            # Check for base64 image in content
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image":
                        import base64
                        img_data = part.get("data", "") or part.get("image", "")
                        if img_data:
                            return base64.b64decode(img_data)
            elif isinstance(content, str) and content.startswith("data:image"):
                import base64
                # data:image/png;base64,...
                _, b64 = content.split(",", 1)
                return base64.b64decode(b64)

            logger.info("Cover generation returned text, not image — model may not support image output")
            return None

    except Exception as e:
        logger.warning("Cover generation failed: %s", e)
        return None


def generate_placeholder_cover(
    title: str,
    author: str = "",
    width: int = COVER_WIDTH,
    height: int = COVER_HEIGHT,
) -> bytes:
    """Generate a simple typographic placeholder cover using Pillow.

    Creates a clean, readable cover with title and author text
    on a muted background. No AI needed.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not available for placeholder cover generation")
        return b""

    # Color palette — muted, literary
    BACKGROUNDS = [
        (45, 55, 72),    # dark blue-gray
        (55, 48, 42),    # dark brown
        (38, 50, 56),    # dark teal
        (48, 42, 55),    # dark purple
        (42, 55, 45),    # dark green
        (60, 45, 45),    # dark red
    ]
    # Pick color based on title hash for consistency
    bg_idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(BACKGROUNDS)
    bg_color = BACKGROUNDS[bg_idx]
    text_color = (240, 235, 225)  # warm off-white

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to use a nice font, fall back to default
    title_size = 48
    author_size = 28
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Georgia.ttf", title_size)
        author_font = ImageFont.truetype("/System/Library/Fonts/Georgia.ttf", author_size)
    except (OSError, IOError):
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", title_size)
            author_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", author_size)
        except (OSError, IOError):
            title_font = ImageFont.load_default()
            author_font = ImageFont.load_default()

    # Word-wrap title
    def wrap_text(text, font, max_width):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        return lines

    max_text_width = width - 80  # 40px margin each side
    title_lines = wrap_text(title, title_font, max_text_width)

    # Calculate vertical position (center the text block)
    line_height_title = title_size + 10
    line_height_author = author_size + 8
    total_height = len(title_lines) * line_height_title + 40 + line_height_author
    y_start = (height - total_height) // 2

    # Draw decorative line above title
    line_y = y_start - 30
    draw.line([(width // 4, line_y), (3 * width // 4, line_y)], fill=text_color, width=1)

    # Draw title
    y = y_start
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y), line, fill=text_color, font=title_font)
        y += line_height_title

    # Draw decorative line between title and author
    y += 15
    draw.line([(width // 3, y), (2 * width // 3, y)], fill=text_color, width=1)
    y += 25

    # Draw author
    if author:
        bbox = draw.textbbox((0, 0), author, font=author_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y), author, fill=text_color, font=author_font)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def generate_cover_for_edition(
    edition_id: int,
    use_ai: bool = True,
) -> Optional[bytes]:
    """Generate a cover for a specific edition.

    Tries AI generation first (if enabled), falls back to placeholder.
    Returns PNG bytes.
    """
    import sqlite3

    from app.services.background_jobs import _get_sync_db_path

    db_path = _get_sync_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT w.title, w.description, w.subtitle,
                   GROUP_CONCAT(a.name, ', ') as authors
            FROM editions e
            JOIN works w ON w.id = e.work_id
            LEFT JOIN work_authors wa ON wa.work_id = w.id
            LEFT JOIN authors a ON a.id = wa.author_id
            WHERE e.id = ?
            GROUP BY e.id
        """, (edition_id,)).fetchone()

        if not row:
            return None

        title = row["title"] or "Untitled"
        author = row["authors"] or "Unknown"
        description = row["description"] or ""
        subtitle = row["subtitle"] or ""
        full_title = f"{title}: {subtitle}" if subtitle else title

    finally:
        conn.close()

    # Try AI generation
    if use_ai:
        cover = await generate_cover_ai(full_title, author, description)
        if cover:
            logger.info("AI cover generated for edition %d: %s", edition_id, title)
            return cover

    # Fallback to placeholder
    cover = generate_placeholder_cover(full_title, author)
    if cover:
        logger.info("Placeholder cover generated for edition %d: %s", edition_id, title)
    return cover
