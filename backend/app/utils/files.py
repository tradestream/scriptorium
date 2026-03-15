"""File utilities for hashing, format detection, and safe path handling."""

import hashlib
from pathlib import Path
from typing import Optional


def calculate_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Calculate hash of a file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, md5, etc.)

    Returns:
        Hex digest of file hash
    """
    hash_obj = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def get_file_format(file_path: Path) -> Optional[str]:
    """Detect file format from extension.

    Args:
        file_path: Path to file

    Returns:
        Format string (epub, pdf, cbz, etc.) or None
    """
    suffix = file_path.suffix.lower().lstrip(".")
    supported = {
        "epub": "epub",
        "pdf": "pdf",
        "cbz": "cbz",
        "cbr": "cbr",
        "mobi": "mobi",
        "azw": "azw",
        "azw3": "azw3",
        "txt": "txt",
        "html": "html",
        "htm": "html",
    }
    return supported.get(suffix)


def is_book_file(file_path: Path) -> bool:
    """Check if file is a supported book format.

    Args:
        file_path: Path to file

    Returns:
        True if supported format, False otherwise
    """
    return get_file_format(file_path) is not None


def safe_path(base_path: Path, relative_path: str) -> Path:
    """Safely resolve a path within a base directory.

    Prevents directory traversal attacks.

    Args:
        base_path: Base directory
        relative_path: Relative path to resolve

    Returns:
        Resolved path, or None if outside base_path

    Raises:
        ValueError: If path tries to escape base directory
    """
    base_path = base_path.resolve()
    full_path = (base_path / relative_path).resolve()

    # Ensure resolved path is within base_path
    if not str(full_path).startswith(str(base_path)):
        raise ValueError(f"Path {relative_path} escapes base directory {base_path}")

    return full_path


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes.

    Args:
        file_path: Path to file

    Returns:
        File size in bytes
    """
    return file_path.stat().st_size
