"""
Chapter Manager Module
Handles chapter state: saving, loading, verification status,
caching extracted text per chapter, and the book library.
"""

import json
import os
import shutil
import hashlib
from datetime import datetime
from typing import Optional


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
BOOKS_DIR = os.path.join(CACHE_DIR, "books")
LIBRARY_FILE = os.path.join(CACHE_DIR, "library.json")


def _ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(BOOKS_DIR, exist_ok=True)


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


def save_command_registry(filename: str, registry_data: dict) -> str:
    """
    Save the command registry to a JSON file for a specific book.

    Args:
        filename: Original PDF filename
        registry_data: Output of CommandRegistry.to_dict()

    Returns:
        Path to the saved file
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)
    path = os.path.join(CACHE_DIR, f"{book_id}_commands.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=2, ensure_ascii=False)

    return path


def load_command_registry(filename: str) -> Optional[dict]:
    """
    Load a previously saved command registry.

    Returns:
        Registry dict (pass to CommandRegistry.from_dict), or None
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)
    path = os.path.join(CACHE_DIR, f"{book_id}_commands.json")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    return None


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


# ═══════════════════════════════════════════════════════════════════════════════
# Book Library — persistent book history with covers
# ═══════════════════════════════════════════════════════════════════════════════

def _load_library() -> dict:
    """Load the library index file."""
    _ensure_cache_dir()
    if os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"books": {}}


def _save_library(library: dict):
    """Save the library index file."""
    _ensure_cache_dir()
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(library, f, indent=2, ensure_ascii=False)


def save_book_to_library(
    filename: str,
    pdf_source_path: str,
    title: str = "",
    author: str = "",
    total_pages: int = 0,
    num_chapters: int = 0,
    cover_png_bytes: bytes | None = None,
) -> str:
    """
    Save a book to the persistent library.

    - Copies the PDF to .cache/books/ for permanent storage
    - Saves cover thumbnail as PNG
    - Updates library index

    Args:
        filename: Original PDF filename
        pdf_source_path: Current path to the PDF (temp or original)
        title: Book title from metadata
        author: Author from metadata
        total_pages: Number of pages
        num_chapters: Number of detected chapters
        cover_png_bytes: First-page PNG thumbnail (optional)

    Returns:
        The permanent path to the stored PDF
    """
    _ensure_cache_dir()
    book_id = _get_book_id(filename)

    # Copy PDF to permanent storage
    pdf_dest = os.path.join(BOOKS_DIR, f"{book_id}.pdf")
    if not os.path.exists(pdf_dest):
        shutil.copy2(pdf_source_path, pdf_dest)

    # Save cover thumbnail
    cover_path = os.path.join(BOOKS_DIR, f"{book_id}_cover.png")
    if cover_png_bytes and not os.path.exists(cover_path):
        with open(cover_path, "wb") as f:
            f.write(cover_png_bytes)

    # Update library index
    library = _load_library()
    library["books"][book_id] = {
        "filename": filename,
        "title": title or filename,
        "author": author,
        "total_pages": total_pages,
        "num_chapters": num_chapters,
        "pdf_path": pdf_dest,
        "cover_path": cover_path if cover_png_bytes else "",
        "last_opened": datetime.now().isoformat(),
        "added": library.get("books", {}).get(book_id, {}).get(
            "added", datetime.now().isoformat()
        ),
    }
    _save_library(library)
    return pdf_dest


def update_library_last_opened(filename: str):
    """Update the last_opened timestamp for a book."""
    book_id = _get_book_id(filename)
    library = _load_library()
    if book_id in library.get("books", {}):
        library["books"][book_id]["last_opened"] = datetime.now().isoformat()
        _save_library(library)


def get_library_books() -> list[dict]:
    """
    Get all books in the library, sorted by last opened (most recent first).

    Returns:
        List of book dicts with: filename, title, author, total_pages,
        num_chapters, pdf_path, cover_path, last_opened, added, book_id
    """
    library = _load_library()
    books = []
    for book_id, info in library.get("books", {}).items():
        # Only include books whose PDF still exists
        if os.path.exists(info.get("pdf_path", "")):
            entry = {**info, "book_id": book_id}
            books.append(entry)

    # Sort by last_opened descending
    books.sort(key=lambda b: b.get("last_opened", ""), reverse=True)
    return books


def get_book_cover(filename: str) -> bytes | None:
    """Load the cover thumbnail PNG for a book."""
    book_id = _get_book_id(filename)
    cover_path = os.path.join(BOOKS_DIR, f"{book_id}_cover.png")
    if os.path.exists(cover_path):
        with open(cover_path, "rb") as f:
            return f.read()
    return None


def remove_book_from_library(filename: str):
    """Remove a book and all its cached data from the library."""
    book_id = _get_book_id(filename)

    # Remove from library index
    library = _load_library()
    library.get("books", {}).pop(book_id, None)
    _save_library(library)

    # Remove PDF and cover
    for ext in [".pdf", "_cover.png"]:
        path = os.path.join(BOOKS_DIR, f"{book_id}{ext}")
        if os.path.exists(path):
            os.remove(path)

    # Remove all cache files for this book
    clear_cache(filename)
