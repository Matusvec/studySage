"""
PDF Parser Module
Handles PDF loading, TOC extraction, and text extraction by page range.
Uses PyMuPDF (fitz) for fast and reliable parsing.
"""

import fitz  # PyMuPDF
import re
import os
import io
import json
from typing import Optional


class PDFParser:
    """Parses PDF files, extracts TOC and chapter text."""

    # Expanded list of monospace / code font name indicators
    MONO_FONT_HINTS = [
        "mono", "courier", "consola", "menlo", "monaco", "inconsolata",
        "typewriter", "fixedsys", "firacode", "jetbrains", "pragmata",
        "lucidaconsole", "lucidasanstypewriter", "anonymous",
        "notomono", "robotomono", "ubuntumono", "ibmplexmono",
        "dejavusansmono", "droidsansmono", "sourcecode", "sourcecodepro",
        "cmu typewriter", "cmtt", "nimbusmono", "freemono", "tlwg mono",
        "go mono", "spacemono", "overpass mono", "oxygen mono",
        "pt mono", "share tech mono", "b612 mono",
    ]

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.total_pages = len(self.doc)
        self.filename = os.path.basename(pdf_path)

    @staticmethod
    def _is_mono_font(font_name: str) -> bool:
        """Check if a font name indicates a monospace/code font."""
        lower = font_name.lower().replace(" ", "").replace("-", "")
        for hint in PDFParser.MONO_FONT_HINTS:
            if hint.replace(" ", "").replace("-", "") in lower:
                return True
        return False

    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()

    def get_toc(self) -> list[dict]:
        """
        Extract table of contents from PDF metadata.
        Returns list of dicts: [{level, title, page}, ...]
        """
        raw_toc = self.doc.get_toc()
        toc = []
        for entry in raw_toc:
            level, title, page = entry
            toc.append({
                "level": level,
                "title": title.strip(),
                "page": page  # 1-based page number
            })
        return toc

    def extract_chapters(self, max_level: int = 2) -> list[dict]:
        """
        Extract chapter entries from the TOC.
        Filters to entries at or below max_level (1 = top-level chapters, 2 = sections, etc.)
        Calculates start and end pages for each chapter.

        Returns list of dicts:
        [{title, start_page, end_page, level, verified}, ...]
        Pages are 0-based for internal use.
        """
        toc = self.get_toc()
        if not toc:
            return []

        # Filter to desired levels
        filtered = [e for e in toc if e["level"] <= max_level]

        chapters = []
        for i, entry in enumerate(filtered):
            start_page = entry["page"] - 1  # Convert to 0-based

            # End page = start of next entry at same or higher level, or end of doc
            end_page = self.total_pages - 1
            for j in range(i + 1, len(filtered)):
                if filtered[j]["level"] <= entry["level"]:
                    end_page = filtered[j]["page"] - 2  # Page before next chapter
                    break

            # Ensure end >= start
            end_page = max(end_page, start_page)

            chapters.append({
                "title": entry["title"],
                "start_page": start_page,
                "end_page": end_page,
                "level": entry["level"],
                "verified": False
            })

        return chapters

    def extract_text(self, start_page: int, end_page: int) -> str:
        """
        Extract text from a range of pages (0-based, inclusive).
        """
        start_page = max(0, start_page)
        end_page = min(end_page, self.total_pages - 1)

        text = ""
        for page_num in range(start_page, end_page + 1):
            page = self.doc[page_num]
            text += page.get_text("text") + "\n\n"
        return text.strip()

    def extract_text_blocks(self, start_page: int, end_page: int) -> list[dict]:
        """
        Extract text blocks with position info (useful for identifying
        headings, code blocks, etc.).

        Uses two heuristics for monospace detection:
        1. Font name matching against known monospace fonts
        2. "Minority font" heuristic — if a font is used by <15% of text,
           it's likely code/commands (works even with obfuscated font names)
        """
        blocks = []
        start_page = max(0, start_page)
        end_page = min(end_page, self.total_pages - 1)

        # First pass: collect all spans to determine font usage statistics
        from collections import Counter
        font_char_counts = Counter()  # font_name -> total characters
        all_lines_raw = []

        for page_num in range(start_page, end_page + 1):
            page = self.doc[page_num]
            for block in page.get_text("dict")["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        line_data = {"spans": line["spans"], "page": page_num}
                        all_lines_raw.append(line_data)
                        for span in line["spans"]:
                            font_name = span["font"]
                            char_count = len(span["text"].strip())
                            if char_count > 0:
                                font_char_counts[font_name] += char_count

        # Determine the dominant "body" font (most characters)
        total_chars = sum(font_char_counts.values())
        body_font = font_char_counts.most_common(1)[0][0] if font_char_counts else ""
        body_font_chars = font_char_counts.get(body_font, 0)

        # Build set of "minority fonts" — fonts with <15% of total text
        # that are NOT the body font. These are likely code/emphasis fonts.
        minority_fonts = set()
        if total_chars > 100:  # Only apply heuristic if enough text
            for font_name, count in font_char_counts.items():
                ratio = count / total_chars
                if ratio < 0.15 and font_name != body_font:
                    # Extra check: don't flag bold variants of body font as code
                    body_base = body_font.lower().replace("bold", "").replace("italic", "").strip()
                    font_base = font_name.lower().replace("bold", "").replace("italic", "").strip()
                    if font_base != body_base:
                        minority_fonts.add(font_name)

        # Second pass: build blocks with improved mono detection
        for line_data in all_lines_raw:
            text = ""
            font_size = 0
            is_bold = False
            is_mono = False
            span_fonts = set()

            for span in line_data["spans"]:
                text += span["text"]
                font_size = max(font_size, span["size"])
                font_name = span["font"]
                span_fonts.add(font_name)

                if "bold" in font_name.lower() or "Bold" in font_name:
                    is_bold = True

                # Method 1: Known monospace font name matching
                if self._is_mono_font(font_name):
                    is_mono = True

                # Method 2: Minority font heuristic
                if font_name in minority_fonts and len(span["text"].strip()) > 0:
                    is_mono = True

            if text.strip():
                blocks.append({
                    "text": text.strip(),
                    "page": line_data["page"],
                    "font_size": round(font_size, 1),
                    "is_bold": is_bold,
                    "is_mono": is_mono,
                    "fonts": list(span_fonts),
                })
        return blocks

    def fallback_chapter_detection(self) -> list[dict]:
        """
        If no TOC metadata exists, try to detect chapters by scanning
        for common patterns like 'Chapter N', 'Part N', numbered headings, etc.
        """
        chapters = []
        chapter_pattern = re.compile(
            r'^(?:chapter|part|section|unit)\s+\d+',
            re.IGNORECASE
        )
        numbered_pattern = re.compile(
            r'^\d+[\.\)]\s+\w+',
            re.IGNORECASE
        )

        for page_num in range(self.total_pages):
            page = self.doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    text = ""
                    max_size = 0
                    for span in line["spans"]:
                        text += span["text"]
                        max_size = max(max_size, span["size"])

                    text = text.strip()
                    if not text:
                        continue

                    # Check if it looks like a chapter heading
                    # (larger font OR matches chapter pattern)
                    is_chapter = False
                    if chapter_pattern.match(text):
                        is_chapter = True
                    elif max_size > 16 and len(text) < 100 and numbered_pattern.match(text):
                        is_chapter = True

                    if is_chapter:
                        chapters.append({
                            "title": text,
                            "start_page": page_num,
                            "end_page": page_num,  # Will be recalculated
                            "level": 1,
                            "verified": False
                        })

        # Recalculate end pages
        for i in range(len(chapters)):
            if i + 1 < len(chapters):
                chapters[i]["end_page"] = chapters[i + 1]["start_page"] - 1
            else:
                chapters[i]["end_page"] = self.total_pages - 1

        return chapters

    def get_page_text(self, page_num: int) -> str:
        """Get text from a single page (0-based)."""
        if 0 <= page_num < self.total_pages:
            return self.doc[page_num].get_text("text")
        return ""

    def get_metadata(self) -> dict:
        """Get PDF metadata (title, author, etc.)."""
        meta = self.doc.metadata
        return {
            "title": meta.get("title", self.filename),
            "author": meta.get("author", "Unknown"),
            "pages": self.total_pages,
            "filename": self.filename
        }

    def extract_images(
        self, start_page: int, end_page: int, min_size: int = 100, max_images: int = 15
    ) -> list[dict]:
        """
        Extract embedded images from a page range.

        Args:
            start_page: Start page (0-based)
            end_page: End page (0-based, inclusive)
            min_size: Minimum width/height in pixels to filter small icons
            max_images: Maximum number of images to return

        Returns:
            List of dicts: {bytes, page, width, height, label, mime_type}
        """
        start_page = max(0, start_page)
        end_page = min(end_page, self.total_pages - 1)

        images = []
        seen_xrefs = set()

        for page_num in range(start_page, end_page + 1):
            page = self.doc[page_num]
            image_list = page.get_images(full=True)

            for img_info in image_list:
                if len(images) >= max_images:
                    break

                xref = img_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                try:
                    base_image = self.doc.extract_image(xref)
                    if not base_image:
                        continue

                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)

                    if width < min_size or height < min_size:
                        continue

                    img_bytes = base_image["image"]
                    ext = base_image.get("ext", "png")

                    # Convert to PNG if needed for consistent handling
                    if ext != "png":
                        from PIL import Image as PILImage
                        pil_img = PILImage.open(io.BytesIO(img_bytes))
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        img_bytes = buf.getvalue()

                    images.append({
                        "bytes": img_bytes,
                        "page": page_num,
                        "width": width,
                        "height": height,
                        "label": f"Figure (page {page_num + 1})",
                        "mime_type": "image/png",
                        "type": "image",
                    })
                except Exception:
                    continue

            if len(images) >= max_images:
                break

        return images

    def extract_table_images(
        self, start_page: int, end_page: int, min_cells: int = 4, max_tables: int = 10
    ) -> list[dict]:
        """
        Detect tables and render them as images.

        Args:
            start_page: Start page (0-based)
            end_page: End page (0-based, inclusive)
            min_cells: Minimum number of cells to consider a valid table
            max_tables: Maximum number of tables to return

        Returns:
            List of dicts: {bytes, page, label, text, mime_type, type}
        """
        start_page = max(0, start_page)
        end_page = min(end_page, self.total_pages - 1)

        tables = []

        for page_num in range(start_page, end_page + 1):
            page = self.doc[page_num]

            try:
                found_tables = page.find_tables()
            except Exception:
                continue

            for t_idx, table in enumerate(found_tables.tables):
                if len(tables) >= max_tables:
                    break

                # Filter small/noise tables
                cells = table.extract()
                total_cells = sum(len(row) for row in cells)
                if total_cells < min_cells:
                    continue

                try:
                    clip = fitz.Rect(table.bbox)
                    # Add small padding
                    clip.x0 = max(0, clip.x0 - 5)
                    clip.y0 = max(0, clip.y0 - 5)
                    clip.x1 = min(page.rect.width, clip.x1 + 5)
                    clip.y1 = min(page.rect.height, clip.y1 + 5)

                    pix = page.get_pixmap(clip=clip, dpi=200)
                    img_bytes = pix.tobytes("png")

                    # Also extract text content for reference
                    text_content = ""
                    for row in cells:
                        text_content += " | ".join(str(c) if c else "" for c in row) + "\n"

                    tables.append({
                        "bytes": img_bytes,
                        "page": page_num,
                        "label": f"Table (page {page_num + 1})",
                        "text": text_content.strip(),
                        "mime_type": "image/png",
                        "type": "table",
                    })
                except Exception:
                    continue

            if len(tables) >= max_tables:
                break

        return tables

    def chunk_text(self, text: str, max_chars: int = 12000) -> list[str]:
        """
        Split text into chunks that respect paragraph boundaries.
        Useful for sending to AI APIs with token limits.
        """
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text[:max_chars]]

    def extract_sections(self, start_page: int, end_page: int) -> list[dict]:
        """
        Detect sub-sections within a page range by analyzing font sizes.
        Headings are identified as lines with larger-than-body font size
        and short length (< 120 chars).

        Returns list of dicts:
        [{"title": "Section Title", "text": "section body text...", "page": 5}, ...]
        """
        start_page = max(0, start_page)
        end_page = min(end_page, self.total_pages - 1)

        # Phase 1: Collect all lines with font info
        lines = []
        for page_num in range(start_page, end_page + 1):
            page = self.doc[page_num]
            for block in page.get_text("dict")["blocks"]:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    text = ""
                    max_size = 0
                    is_bold = False
                    for span in line["spans"]:
                        text += span["text"]
                        max_size = max(max_size, span["size"])
                        if "bold" in span["font"].lower() or "Bold" in span["font"]:
                            is_bold = True
                    text = text.strip()
                    if text:
                        lines.append({
                            "text": text,
                            "font_size": round(max_size, 1),
                            "is_bold": is_bold,
                            "page": page_num,
                        })

        if not lines:
            # Fallback: return single section with all text
            return [{"title": "Full Chapter", "text": self.extract_text(start_page, end_page), "page": start_page}]

        # Phase 2: Determine body font size (the most common size)
        from collections import Counter
        size_counts = Counter()
        for line in lines:
            # Only count lines with substantial text (not single chars/numbers)
            if len(line["text"]) > 10:
                size_counts[line["font_size"]] += 1

        if not size_counts:
            return [{"title": "Full Chapter", "text": self.extract_text(start_page, end_page), "page": start_page}]

        body_size = size_counts.most_common(1)[0][0]

        # Phase 3: Identify heading lines
        # A heading is: larger than body text, short (< 120 chars), and not monospace-looking
        heading_indices = []
        for i, line in enumerate(lines):
            is_heading = False
            # Significantly larger font = heading
            if line["font_size"] > body_size + 1.0 and len(line["text"]) < 120:
                is_heading = True
            # Bold + slightly larger = heading
            elif line["is_bold"] and line["font_size"] > body_size + 0.3 and len(line["text"]) < 120:
                is_heading = True
            # Much larger font (like chapter titles)
            elif line["font_size"] > body_size * 1.3 and len(line["text"]) < 120:
                is_heading = True

            if is_heading:
                heading_indices.append(i)

        # If no headings found (or just 1), return as single section
        if len(heading_indices) < 2:
            full_text = self.extract_text(start_page, end_page)
            title = lines[heading_indices[0]]["text"] if heading_indices else "Full Chapter"
            return [{"title": title, "text": full_text, "page": start_page}]

        # Phase 4: Build sections from heading positions
        sections = []
        for idx_pos, h_idx in enumerate(heading_indices):
            title = lines[h_idx]["text"]
            page = lines[h_idx]["page"]

            # Collect text from this heading to the next heading
            if idx_pos + 1 < len(heading_indices):
                end_idx = heading_indices[idx_pos + 1]
            else:
                end_idx = len(lines)

            body_lines = []
            for j in range(h_idx + 1, end_idx):
                body_lines.append(lines[j]["text"])

            body_text = "\n".join(body_lines).strip()

            # Skip empty sections or very short ones (likely decorative headings)
            if len(body_text) > 50:
                sections.append({
                    "title": title,
                    "text": body_text,
                    "page": page,
                })

        # If we filtered out everything, return full text
        if not sections:
            return [{"title": "Full Chapter", "text": self.extract_text(start_page, end_page), "page": start_page}]

        # Capture any text BEFORE the first heading as an intro section
        if heading_indices[0] > 0:
            intro_lines = [lines[j]["text"] for j in range(0, heading_indices[0])]
            intro_text = "\n".join(intro_lines).strip()
            if len(intro_text) > 50:
                sections.insert(0, {
                    "title": "Introduction",
                    "text": intro_text,
                    "page": start_page,
                })

        return sections
