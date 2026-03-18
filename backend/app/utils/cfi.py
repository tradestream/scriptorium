"""EPUB CFI (Canonical Fragment Identifier) utilities.

Converts between Kobo content_id/spine_index position format and
KoReader's XPointer-based progress format, enabling cross-device
progress synchronization.

EPUB CFI spec: https://www.w3.org/publishing/epub3/epub-cfi.html
"""

import re
from typing import Optional


def kobo_to_cfi(spine_index: int, content_source_progress: float) -> str:
    """Convert Kobo spine_index + progress into an approximate EPUB CFI.

    Kobo stores:
      - spine_index: 0-based index into the EPUB spine
      - content_source_progress: 0.0-1.0 progress within that spine item

    Returns: An EPUB CFI string like "epubcfi(/6/4!/4/2,/1:0,/1:100)"
    """
    # EPUB CFI spine step: /6 = package, then even-numbered child steps
    # spine_index 0 → /6/2, spine_index 1 → /6/4, etc.
    spine_step = (spine_index + 1) * 2
    # Approximate character offset from progress
    # We use a nominal 5000-char-per-chapter estimate
    approx_chars = int(content_source_progress * 5000)

    return f"epubcfi(/6/{spine_step}!/4/2/1:{approx_chars})"


def cfi_to_kobo(cfi: str) -> tuple[int, float]:
    """Extract approximate spine_index and progress from an EPUB CFI.

    Returns: (spine_index, content_source_progress)
    """
    # Parse spine step from CFI
    m = re.search(r"epubcfi\(/6/(\d+)", cfi)
    if not m:
        return 0, 0.0

    spine_step = int(m.group(1))
    spine_index = max(0, (spine_step // 2) - 1)

    # Parse character offset if present
    char_match = re.search(r":(\d+)\)", cfi)
    if char_match:
        chars = int(char_match.group(1))
        progress = min(1.0, chars / 5000)
    else:
        progress = 0.0

    return spine_index, progress


def koreader_to_cfi(xpointer: str, spine_index: int = 0) -> str:
    """Convert KoReader XPointer position to an approximate EPUB CFI.

    KoReader stores progress as XPointer strings like:
      "/body/DocFragment[3]/body/div/p[7]/text().0"

    The DocFragment index maps roughly to the spine index.
    """
    # Extract DocFragment index
    doc_match = re.search(r"DocFragment\[(\d+)\]", xpointer)
    if doc_match:
        spine_index = int(doc_match.group(1)) - 1  # 1-based to 0-based

    # Extract paragraph index for rough progress
    p_match = re.findall(r"/p\[(\d+)\]", xpointer)
    para_idx = int(p_match[-1]) if p_match else 1
    # Rough progress: assume ~50 paragraphs per chapter
    progress = min(1.0, para_idx / 50)

    spine_step = (spine_index + 1) * 2
    approx_chars = int(progress * 5000)
    return f"epubcfi(/6/{spine_step}!/4/2/1:{approx_chars})"


def cfi_to_koreader(cfi: str) -> str:
    """Convert an EPUB CFI to an approximate KoReader XPointer.

    Returns: An XPointer string like "/body/DocFragment[3]/body/div/p[1]/text().0"
    """
    spine_index, progress = cfi_to_kobo(cfi)
    doc_fragment = spine_index + 1  # 1-based
    para_idx = max(1, int(progress * 50))

    return f"/body/DocFragment[{doc_fragment}]/body/div/p[{para_idx}]/text().0"


def kobo_to_koreader(spine_index: int, content_source_progress: float) -> str:
    """Direct Kobo → KoReader position conversion."""
    cfi = kobo_to_cfi(spine_index, content_source_progress)
    return cfi_to_koreader(cfi)


def koreader_to_kobo(xpointer: str) -> tuple[int, float]:
    """Direct KoReader → Kobo position conversion."""
    cfi = koreader_to_cfi(xpointer)
    return cfi_to_kobo(cfi)


def normalize_progress(
    kobo_progress: Optional[float] = None,
    koreader_xpointer: Optional[str] = None,
    spine_index: Optional[int] = None,
) -> dict:
    """Normalize progress from any device format into a unified format.

    Returns dict with keys: cfi, kobo_progress, koreader_xpointer, percentage
    """
    result = {"cfi": None, "kobo_progress": None, "koreader_xpointer": None, "percentage": 0.0}

    if kobo_progress is not None and spine_index is not None:
        result["cfi"] = kobo_to_cfi(spine_index, kobo_progress)
        result["kobo_progress"] = kobo_progress
        result["koreader_xpointer"] = kobo_to_koreader(spine_index, kobo_progress)
        # Rough global percentage (needs total spine items for accuracy)
        result["percentage"] = round(kobo_progress * 100, 1)

    elif koreader_xpointer:
        si, progress = koreader_to_kobo(koreader_xpointer)
        result["cfi"] = koreader_to_cfi(koreader_xpointer, si)
        result["kobo_progress"] = progress
        result["koreader_xpointer"] = koreader_xpointer
        result["percentage"] = round(progress * 100, 1)

    return result
