"""
Chapter Manager Module
Handles chapter state: saving, loading, verification status,
and caching extracted text per chapter.
"""

import json
import os
import hashlib
from typing import Optional


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")


def _ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def _get_book_id(filename: str) -> str:
    """Generate a safe ID for a book based on filename."""
    return hashlib.md5(filename.encode()).hexdigest()[:12]


def save_chapters(filename: str, chapters: list[dict]) -> str:
    """
    Save chapter data (with verification status) to a JSON file.

    Args:
        filename: Original PDF filename
        chapters: List of chapter dicts from PDFParser

    Returns:
        Path to the saved JSON file
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)
    cache_path = os.path.join(CACHE_DIR, f"{book_id}_chapters.json")

    data = {
        "filename": filename,
        "chapters": chapters,
    }

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return cache_path


def load_chapters(filename: str) -> Optional[list[dict]]:
    """
    Load previously saved chapter data.

    Returns:
        List of chapter dicts, or None if not found
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)
    cache_path = os.path.join(CACHE_DIR, f"{book_id}_chapters.json")

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("chapters", [])

    return None


def update_chapter_verification(filename: str, chapter_index: int, verified: bool) -> bool:
    """
    Update the verification status of a specific chapter.

    Returns:
        True if successful, False if chapter not found
    """
    chapters = load_chapters(filename)
    if chapters is None or chapter_index >= len(chapters):
        return False

    chapters[chapter_index]["verified"] = verified
    save_chapters(filename, chapters)
    return True


def update_chapter_pages(filename: str, chapter_index: int, start_page: int, end_page: int) -> bool:
    """
    Update the page range of a specific chapter (user correction).

    Returns:
        True if successful
    """
    chapters = load_chapters(filename)
    if chapters is None or chapter_index >= len(chapters):
        return False

    chapters[chapter_index]["start_page"] = start_page
    chapters[chapter_index]["end_page"] = end_page
    save_chapters(filename, chapters)
    return True


def cache_chapter_text(filename: str, chapter_index: int, text: str) -> str:
    """
    Cache extracted chapter text for faster re-access.

    Returns:
        Path to the cached text file
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)
    text_path = os.path.join(CACHE_DIR, f"{book_id}_ch{chapter_index}.txt")

    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)

    return text_path


def load_cached_text(filename: str, chapter_index: int) -> Optional[str]:
    """
    Load cached chapter text if available.

    Returns:
        Cached text or None
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)
    text_path = os.path.join(CACHE_DIR, f"{book_id}_ch{chapter_index}.txt")

    if os.path.exists(text_path):
        with open(text_path, "r", encoding="utf-8") as f:
            return f.read()

    return None


def cache_summary(filename: str, chapter_index: int, depth: str, summary: str) -> str:
    """
    Cache a generated summary to avoid re-generating.

    Returns:
        Path to cached summary file
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)
    summary_path = os.path.join(CACHE_DIR, f"{book_id}_ch{chapter_index}_{depth}.md")

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    return summary_path


def load_cached_summary(filename: str, chapter_index: int, depth: str) -> Optional[str]:
    """
    Load a cached summary if available.

    Returns:
        Cached summary string or None
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)
    summary_path = os.path.join(CACHE_DIR, f"{book_id}_ch{chapter_index}_{depth}.md")

    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return f.read()

    return None


def clear_cache(filename: Optional[str] = None):
    """
    Clear cached data. If filename is given, only clear that book's cache.
    Otherwise, clear all cache.
    """
    _ensure_cache_dir()

    if filename:
        book_id = _get_book_id(filename)
        for f in os.listdir(CACHE_DIR):
            if f.startswith(book_id):
                os.remove(os.path.join(CACHE_DIR, f))
    else:
        for f in os.listdir(CACHE_DIR):
            filepath = os.path.join(CACHE_DIR, f)
            if os.path.isfile(filepath):
                os.remove(filepath)


def get_all_books() -> list[dict]:
    """
    List all books that have cached chapter data.

    Returns:
        List of dicts with filename and chapter count
    """
    _ensure_cache_dir()
    books = []

    for f in os.listdir(CACHE_DIR):
        if f.endswith("_chapters.json"):
            filepath = os.path.join(CACHE_DIR, f)
            with open(filepath, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                books.append({
                    "filename": data.get("filename", "Unknown"),
                    "chapters": len(data.get("chapters", [])),
                })

    return books
