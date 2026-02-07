"""
StudySage — PDF Study Helper
Upload books → detect chapters → get AI-powered summaries with adjustable depth
Ask questions about specific chapters, extract commands, key terms, and more.

Usage:
    streamlit run app.py
"""

import streamlit as st
import os
import re
import tempfile
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.pdf_parser import PDFParser
from src.summarizer import GeminiSummarizer, SummaryDepth
from src.command_extractor import CommandExtractor, CommandRegistry
from src.pdf_exporter import SummaryPDFExporter
from src.man_page import fetch_man_page
from src.category_parser import (
    parse_categorized_summary,
    filter_sections,
    rebuild_summary_text,
    get_active_categories,
    get_category_display,
    get_category_icon,
    CATEGORIES,
)
from src.chapter_manager import (
    save_chapters,
    load_chapters,
    update_chapter_verification,
    update_chapter_pages,
    cache_chapter_text,
    load_cached_text,
    cache_summary,
    load_cached_summary,
    clear_cache,
    save_command_registry,
    load_command_registry,
    save_book_to_library,
    update_library_last_opened,
    get_library_books,
    get_book_cover,
    remove_book_from_library,
)

# ── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="StudySage",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom Styles ────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .stApp {
        max-width: 1400px;
        margin: 0 auto;
    }
    .chapter-card {
        padding: 0.5rem 1rem;
        margin: 0.25rem 0;
        border-radius: 8px;
        border-left: 4px solid #4CAF50;
    }
    .chapter-unverified {
        border-left-color: #FF9800;
    }
    .depth-label {
        font-size: 0.8rem;
        color: #888;
    }
    /* Inline media thumbnails */
    .media-container {
        margin: 1rem 0;
        padding: 0.75rem;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        background: #fafafa;
    }
    .media-label {
        font-size: 0.85rem;
        color: #555;
        margin-bottom: 0.25rem;
        font-weight: 600;
    }
    .media-description {
        font-size: 0.9rem;
        color: #444;
        margin-top: 0.5rem;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)

# ── Helper: Generate cover thumbnail from first page ─────────────────────────

def _generate_cover_thumbnail(parser) -> bytes | None:
    """Render the first page of a PDF as a small PNG thumbnail."""
    try:
        import fitz
        page = parser.doc[0]
        pix = page.get_pixmap(dpi=72)
        return pix.tobytes("png")
    except Exception:
        return None


def _open_book(pdf_path: str, filename: str):
    """
    Open a book from a PDF path — used by both upload and library re-open.
    Sets up parser, chapters, command registry, and library entry.
    """
    from src.pdf_parser import PDFParser as _PDFParser

    if st.session_state.parser:
        st.session_state.parser.close()

    st.session_state.parser = _PDFParser(pdf_path)
    st.session_state.pdf_filename = filename

    # Load or extract chapters
    cached_chapters = load_chapters(filename)
    if cached_chapters:
        st.session_state.chapters = cached_chapters
    else:
        chapters = st.session_state.parser.extract_chapters(max_level=2)
        if not chapters:
            chapters = st.session_state.parser.fallback_chapter_detection()
        st.session_state.chapters = chapters
        save_chapters(filename, chapters)

    # Load saved command registry
    saved_registry = load_command_registry(filename)
    if saved_registry:
        st.session_state.command_registry = CommandRegistry.from_dict(saved_registry)
    else:
        st.session_state.command_registry = CommandRegistry()

    # Save to library (with cover)
    meta = st.session_state.parser.get_metadata()
    cover = _generate_cover_thumbnail(st.session_state.parser)
    save_book_to_library(
        filename=filename,
        pdf_source_path=pdf_path,
        title=meta.get("title", filename),
        author=meta.get("author", "Unknown"),
        total_pages=meta.get("pages", 0),
        num_chapters=len(st.session_state.chapters),
        cover_png_bytes=cover,
    )

    # Reset chapter selection
    st.session_state.current_chapter_idx = None
    st.session_state.chapter_text = ""
    st.session_state.current_summary = ""
    st.session_state.current_summary_depth = ""
    st.session_state.chapter_media = []


# ── Session State Initialization ─────────────────────────────────────────────

if "parser" not in st.session_state:
    st.session_state.parser = None
if "chapters" not in st.session_state:
    st.session_state.chapters = []
if "current_chapter_idx" not in st.session_state:
    st.session_state.current_chapter_idx = None
if "chapter_text" not in st.session_state:
    st.session_state.chapter_text = ""
if "pdf_filename" not in st.session_state:
    st.session_state.pdf_filename = ""
if "summarizer" not in st.session_state:
    st.session_state.summarizer = None
if "current_summary" not in st.session_state:
    st.session_state.current_summary = ""
if "current_summary_depth" not in st.session_state:
    st.session_state.current_summary_depth = ""
if "chapter_media" not in st.session_state:
    st.session_state.chapter_media = []
if "man_summaries" not in st.session_state:
    st.session_state.man_summaries = {}  # {command: {summary, status}}
if "command_registry" not in st.session_state:
    st.session_state.command_registry = CommandRegistry()
if "category_filter" not in st.session_state:
    st.session_state.category_filter = []  # empty = show all
if "summary_from_cache" not in st.session_state:
    st.session_state.summary_from_cache = False

# ── Sidebar — Settings & Upload ──────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/book-shelf.png", width=64)
    st.title("📚 StudySage")
    st.caption("Upload books • Detect chapters • AI-powered study")

    st.divider()

    # API Key — auto-loaded from .env
    st.subheader("🔑 Gemini API Key")
    env_key = os.getenv("GEMINI_API_KEY", "")
    api_key = st.text_input(
        "Gemini API key",
        value=env_key,
        type="password",
        help="Auto-loaded from .env — or paste a different key here",
        key="api_key_input",
    )

    if api_key:
        model_choice = st.selectbox(
            "Gemini Model",
            ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-3-flash", "gemini-3-pro"],
            index=0,
            help="2.5 Flash = fast & cheap. 2.5 Pro = best for complex chapters. 3.x = newest."
        )
        st.session_state.summarizer = GeminiSummarizer(api_key, model_choice)
        st.success("✅ API key loaded from .env")
    else:
        st.info("Add GEMINI_API_KEY to your .env file or paste it above")

    st.divider()

    # PDF Upload
    st.subheader("📄 Upload PDF")
    uploaded_file = st.file_uploader(
        "Choose a PDF book",
        type="pdf",
        help="Upload any PDF book — the TOC will be auto-detected",
    )

    if uploaded_file:
        # Save to temp file and open
        if st.session_state.pdf_filename != uploaded_file.name:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name

            _open_book(tmp_path, uploaded_file.name)
            st.success(f"📖 Loaded {len(st.session_state.chapters)} chapters")

        # Show book info
        if st.session_state.parser:
            meta = st.session_state.parser.get_metadata()
            st.markdown(f"**{meta['title']}**")
            st.caption(f"Author: {meta['author']} • {meta['pages']} pages")

    st.divider()

    # Cache management
    if st.session_state.pdf_filename:
        if st.button("🗑️ Clear Cache", help="Remove all cached data for this book"):
            clear_cache(st.session_state.pdf_filename)
            st.session_state.chapters = []
            st.session_state.current_chapter_idx = None
            st.session_state.chapter_text = ""
            st.rerun()

# ── Helper: Display summary with inline media ──────────────────────────────────

def _display_summary_with_inline_media(
    summary_text: str, media_items: list[dict], chapter: dict
):
    """
    Split the summary by ## headings and insert media items at the
    correct positions based on their page numbers relative to the chapter.
    Media is shown as smaller thumbnails with a click-to-enlarge popover.
    """
    # Split summary into sections by ## headings
    sections = re.split(r'(?=^## )', summary_text, flags=re.MULTILINE)
    sections = [s for s in sections if s.strip()]
    n_sections = len(sections)

    if n_sections == 0:
        st.markdown(summary_text)
        return

    # Distribute media across sections based on relative page position
    ch_start = chapter["start_page"]
    ch_end = chapter["end_page"]
    ch_span = max(ch_end - ch_start, 1)

    # Map each media item to a section index
    media_by_section: dict[int, list[dict]] = {}
    for media in media_items:
        page_offset = media["page"] - ch_start
        # Proportional position → section index
        section_idx = min(int((page_offset / ch_span) * n_sections), n_sections - 1)
        section_idx = max(0, section_idx)
        media_by_section.setdefault(section_idx, []).append(media)

    # Render each section followed by its media
    for s_idx, section_md in enumerate(sections):
        st.markdown(section_md)

        if s_idx in media_by_section:
            for m_idx, media in enumerate(media_by_section[s_idx]):
                icon = "📊" if media["type"] == "table" else "🖼️"
                label = media.get("label", "Figure")

                # Compact card: small image + description
                st.markdown(
                    f'<div class="media-container">'
                    f'<div class="media-label">{icon} {label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                # Small thumbnail — columns for sizing
                col_img, col_desc = st.columns([1, 2])
                with col_img:
                    st.image(media["bytes"], width=280)
                    # Click to enlarge via popover
                    with st.popover("🔍 Enlarge"):
                        st.image(media["bytes"], use_container_width=True)
                        st.caption(label)
                with col_desc:
                    st.markdown(media.get("description", ""), unsafe_allow_html=False)


# ── Main Content Area ────────────────────────────────────────────────────────

if not st.session_state.parser:
    # ── Home Screen: Book Library ─────────────────────────────────────────
    st.markdown("# 📚 StudySage")
    st.markdown("**Your AI-powered study companion for PDF textbooks.**")

    library_books = get_library_books()

    if library_books:
        st.divider()
        st.subheader("📖 Your Library")
        st.caption("Click a book to pick up where you left off")

        # Display books in a grid (3 per row)
        cols_per_row = 3
        for row_start in range(0, len(library_books), cols_per_row):
            row_books = library_books[row_start:row_start + cols_per_row]
            cols = st.columns(cols_per_row)

            for col_idx, book in enumerate(row_books):
                with cols[col_idx]:
                    # Cover image or placeholder
                    cover = get_book_cover(book["filename"])
                    if cover:
                        st.image(cover, use_container_width=True)
                    else:
                        st.markdown(
                            '<div style="background:#e8e8e8;border-radius:8px;'
                            'height:200px;display:flex;align-items:center;'
                            'justify-content:center;font-size:3rem;">📕</div>',
                            unsafe_allow_html=True,
                        )

                    # Book info
                    display_title = book.get("title", book["filename"])
                    if len(display_title) > 40:
                        display_title = display_title[:37] + "..."
                    st.markdown(f"**{display_title}**")

                    author = book.get("author", "Unknown")
                    pages = book.get("total_pages", "?")
                    n_ch = book.get("num_chapters", 0)
                    st.caption(f"{author} • {pages} pages • {n_ch} chapters")

                    # Last opened timestamp
                    last_opened = book.get("last_opened", "")
                    if last_opened:
                        try:
                            dt = datetime.fromisoformat(last_opened)
                            st.caption(f"Last opened: {dt.strftime('%b %d, %Y %I:%M %p')}")
                        except Exception:
                            pass

                    # Open button
                    if st.button(
                        "📖 Open",
                        key=f"lib_open_{book['book_id']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        pdf_path = book["pdf_path"]
                        _open_book(pdf_path, book["filename"])
                        update_library_last_opened(book["filename"])
                        st.rerun()

                    # Delete button (small)
                    if st.button(
                        "🗑️",
                        key=f"lib_del_{book['book_id']}",
                        help="Remove from library",
                    ):
                        remove_book_from_library(book["filename"])
                        st.rerun()

        st.divider()

    # Getting started section
    st.subheader("➕ Add a New Book")
    st.markdown(
        "Upload a PDF in the **sidebar** to get started. "
        "It will be saved to your library for next time."
    )

    if not library_books:
        st.markdown("""
        ### How it works:
        1. **Upload** your PDF book using the sidebar
        2. **Review & verify** the auto-detected chapter structure
        3. **Select a chapter** to explore
        4. **Get summaries** at your preferred depth (brief → comprehensive)
        5. **Ask questions** about specific chapters
        6. **Extract** key commands, terms, and concepts

        ---
        *Get a free Gemini API key at [Google AI Studio](https://aistudio.google.com/apikey)*
        """)

    st.stop()

# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_chapters, tab_summary, tab_qa, tab_extract = st.tabs([
    "📑 Chapters", "📝 Summary", "❓ Q&A", "🔍 Extract"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: Chapter Management
# ═══════════════════════════════════════════════════════════════════════════════

with tab_chapters:
    st.header("📑 Chapter Structure")

    chapters = st.session_state.chapters

    if not chapters:
        st.warning(
            "No chapters detected automatically. This PDF might not have a table of contents embedded. "
            "You can add chapters manually below."
        )

        # Manual chapter addition
        with st.expander("➕ Add Chapter Manually"):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                manual_title = st.text_input("Chapter Title")
            with col2:
                manual_start = st.number_input("Start Page", min_value=1, value=1)
            with col3:
                manual_end = st.number_input(
                    "End Page",
                    min_value=1,
                    value=st.session_state.parser.total_pages if st.session_state.parser else 1
                )

            if st.button("Add Chapter") and manual_title:
                new_chapter = {
                    "title": manual_title,
                    "start_page": manual_start - 1,  # Convert to 0-based
                    "end_page": manual_end - 1,
                    "level": 1,
                    "verified": True,
                }
                st.session_state.chapters.append(new_chapter)
                save_chapters(st.session_state.pdf_filename, st.session_state.chapters)
                st.success(f"Added: {manual_title}")
                st.rerun()
    else:
        # Chapter verification controls
        st.markdown(
            f"**{len(chapters)} chapters detected** — "
            f"✅ {sum(1 for c in chapters if c.get('verified'))} verified, "
            f"⚠️ {sum(1 for c in chapters if not c.get('verified'))} unverified"
        )

        col_verify_all, col_filter = st.columns([1, 2])
        with col_verify_all:
            if st.button("✅ Verify All Chapters"):
                for i in range(len(st.session_state.chapters)):
                    st.session_state.chapters[i]["verified"] = True
                save_chapters(st.session_state.pdf_filename, st.session_state.chapters)
                st.rerun()

        with col_filter:
            show_level = st.selectbox(
                "Filter by level",
                ["All levels", "Level 1 (Chapters)", "Level 2 (Sections)"],
                index=0,
            )

        st.divider()

        # Display chapters
        for i, chapter in enumerate(chapters):
            # Apply level filter
            if show_level == "Level 1 (Chapters)" and chapter["level"] != 1:
                continue
            if show_level == "Level 2 (Sections)" and chapter["level"] != 2:
                continue

            verified = chapter.get("verified", False)
            indent = "  " * (chapter["level"] - 1)
            icon = "✅" if verified else "⚠️"
            pages = f"pp. {chapter['start_page'] + 1}–{chapter['end_page'] + 1}"

            with st.container():
                col_info, col_pages, col_actions = st.columns([4, 2, 2])

                with col_info:
                    st.markdown(f"{indent}{icon} **{chapter['title']}**")

                with col_pages:
                    st.caption(pages)

                with col_actions:
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    with btn_col1:
                        if st.button("✓", key=f"verify_{i}", help="Verify this chapter"):
                            st.session_state.chapters[i]["verified"] = not verified
                            save_chapters(st.session_state.pdf_filename, st.session_state.chapters)
                            st.rerun()
                    with btn_col2:
                        if st.button("📖", key=f"select_{i}", help="Select for summary/Q&A"):
                            st.session_state.current_chapter_idx = i
                            st.session_state.chapter_media = []

                            # Load or extract chapter text
                            cached = load_cached_text(st.session_state.pdf_filename, i)
                            if cached:
                                st.session_state.chapter_text = cached
                            else:
                                text = st.session_state.parser.extract_text(
                                    chapter["start_page"], chapter["end_page"]
                                )
                                st.session_state.chapter_text = text
                                cache_chapter_text(st.session_state.pdf_filename, i, text)

                            # Auto-load cached summary (try standard first, then any depth)
                            loaded_summary = None
                            loaded_depth = ""
                            for try_depth, try_label in [
                                ("standard", "🔵 Standard"),
                                ("detailed", "🟠 Detailed"),
                                ("comprehensive", "🔴 Comprehensive"),
                                ("brief", "🟢 Brief"),
                            ]:
                                cached_sum = load_cached_summary(st.session_state.pdf_filename, i, try_depth)
                                if cached_sum:
                                    loaded_summary = cached_sum
                                    loaded_depth = try_label
                                    break

                            st.session_state.current_summary = loaded_summary or ""
                            st.session_state.current_summary_depth = loaded_depth
                            st.session_state.summary_from_cache = bool(loaded_summary)
                            st.rerun()
                    with btn_col3:
                        if st.button("✏️", key=f"edit_{i}", help="Edit page range"):
                            st.session_state[f"editing_{i}"] = True

                # Edit page range (expandable)
                if st.session_state.get(f"editing_{i}", False):
                    with st.expander("Edit Page Range", expanded=True):
                        ec1, ec2, ec3 = st.columns([1, 1, 1])
                        with ec1:
                            new_start = st.number_input(
                                "Start", value=chapter["start_page"] + 1, min_value=1, key=f"start_{i}"
                            )
                        with ec2:
                            new_end = st.number_input(
                                "End", value=chapter["end_page"] + 1, min_value=1, key=f"end_{i}"
                            )
                        with ec3:
                            if st.button("Save", key=f"save_edit_{i}"):
                                update_chapter_pages(
                                    st.session_state.pdf_filename, i, new_start - 1, new_end - 1
                                )
                                st.session_state.chapters[i]["start_page"] = new_start - 1
                                st.session_state.chapters[i]["end_page"] = new_end - 1
                                st.session_state[f"editing_{i}"] = False
                                st.rerun()

    # Show selected chapter info
    if st.session_state.current_chapter_idx is not None:
        idx = st.session_state.current_chapter_idx
        ch = st.session_state.chapters[idx]
        st.divider()
        st.success(f"📖 Selected: **{ch['title']}** (pp. {ch['start_page']+1}–{ch['end_page']+1})")
        char_count = len(st.session_state.chapter_text)
        st.caption(f"Extracted text: {char_count:,} characters (~{char_count // 4:,} tokens)")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: Summary
# ═══════════════════════════════════════════════════════════════════════════════

with tab_summary:
    st.header("📝 Chapter Summary")

    if st.session_state.current_chapter_idx is None:
        st.info("👈 Select a chapter from the **Chapters** tab first (click the 📖 button)")
        st.stop()

    idx = st.session_state.current_chapter_idx
    chapter = st.session_state.chapters[idx]
    text = st.session_state.chapter_text

    st.markdown(f"### {chapter['title']}")
    st.caption(f"Pages {chapter['start_page']+1}–{chapter['end_page']+1} • {len(text):,} characters")

    # Depth selector
    col_depth, col_custom = st.columns([1, 2])

    with col_depth:
        depth_options = {
            "🟢 Brief": SummaryDepth.BRIEF,
            "🔵 Standard": SummaryDepth.STANDARD,
            "🟠 Detailed": SummaryDepth.DETAILED,
            "🔴 Comprehensive": SummaryDepth.COMPREHENSIVE,
        }
        depth_labels = {
            "🟢 Brief": "3-5 key takeaways only",
            "🔵 Standard": "Main points with explanations",
            "🟠 Detailed": "All points + supporting details",
            "🔴 Comprehensive": "Everything — miss nothing",
        }

        selected_depth_name = st.radio(
            "Summary Depth",
            list(depth_options.keys()),
            index=1,
            help="Control how detailed the summary should be",
        )
        selected_depth = depth_options[selected_depth_name]
        st.caption(depth_labels[selected_depth_name])

    with col_custom:
        custom_instructions = st.text_area(
            "Custom Instructions (optional)",
            placeholder="e.g., 'Focus on networking commands', 'Include all code examples', 'Explain like I'm a beginner'",
            height=100,
        )

    # Image & Table toggle
    include_media = st.checkbox(
        "🖼️ Include images & tables",
        value=False,
        help="Extract figures and tables from the chapter, send each to Gemini Vision for a description, and include them in the summary.",
    )

    # ── Cache status & action buttons ─────────────────────────────────────
    cached_exists = load_cached_summary(
        st.session_state.pdf_filename, idx, selected_depth.value
    ) if not custom_instructions else None

    if cached_exists:
        st.info(
            f"💾 A **{selected_depth_name}** summary is already cached for this chapter. "
            f"Click **Generate** to load it, or **🔄 Re-summarize** to create a fresh one."
        )

    btn_col_gen, btn_col_regen = st.columns([2, 1])
    with btn_col_gen:
        generate_clicked = st.button("✨ Generate Summary", type="primary", use_container_width=True)
    with btn_col_regen:
        resummrize_clicked = st.button(
            "🔄 Re-summarize",
            use_container_width=True,
            help="Ignore cached summary and regenerate from scratch",
            disabled=not st.session_state.summarizer,
        )

    force_regenerate = resummrize_clicked
    action_clicked = generate_clicked or resummrize_clicked

    if action_clicked:
        if not st.session_state.summarizer:
            st.error("❌ Please enter your Gemini API key in the sidebar first")
        else:
            # Use cache unless force-regenerating or custom instructions present
            if cached_exists and not custom_instructions and not force_regenerate:
                st.session_state.current_summary = cached_exists
                st.session_state.current_summary_depth = selected_depth_name
                st.session_state.summary_from_cache = True
            else:
                with st.spinner(f"Generating {selected_depth.value} summary with Gemini..."):
                    # Detect sub-sections within the chapter
                    parser = st.session_state.parser
                    sections = parser.extract_sections(
                        chapter["start_page"], chapter["end_page"]
                    )

                    if len(sections) > 1:
                        st.caption(f"📑 Detected **{len(sections)} sections** — summarizing each individually...")

                        # Show section names
                        with st.expander("Detected sections"):
                            for s in sections:
                                st.markdown(f"- **{s['title']}** ({len(s['text']):,} chars)")

                        # Progress bar
                        progress_bar = st.progress(0, text="Starting...")

                        def update_progress(current, total, section_title):
                            pct = current / (total + 1)  # +1 for the combine step
                            if current < total:
                                progress_bar.progress(pct, text=f"Summarizing: {section_title} ({current+1}/{total})")
                            else:
                                progress_bar.progress(pct, text="Combining sections into final summary...")

                        summary = st.session_state.summarizer.summarize_by_sections(
                            sections,
                            chapter["title"],
                            selected_depth,
                            custom_instructions,
                            progress_callback=update_progress,
                        )
                        progress_bar.progress(1.0, text="✅ Done!")
                    else:
                        # Single section or short chapter — summarize directly
                        summary = st.session_state.summarizer.summarize(
                            text, chapter["title"], selected_depth, custom_instructions
                        )

                    # Cache it (only if no custom instructions)
                    if not custom_instructions:
                        cache_summary(
                            st.session_state.pdf_filename, idx, selected_depth.value, summary
                        )

                    st.session_state.current_summary = summary
                    st.session_state.current_summary_depth = selected_depth_name
                    st.session_state.summary_from_cache = False

            # ── Extract & describe images and tables ──
            if include_media:
                st.session_state.chapter_media = []
                parser = st.session_state.parser
                summarizer = st.session_state.summarizer

                with st.spinner("🖼️ Extracting images and tables from chapter..."):
                    images = parser.extract_images(chapter["start_page"], chapter["end_page"])
                    tables = parser.extract_table_images(chapter["start_page"], chapter["end_page"])

                all_media = images + tables

                if all_media:
                    st.caption(f"Found **{len(images)} images** and **{len(tables)} tables** — analyzing with Gemini Vision...")
                    media_progress = st.progress(0, text="Analyzing visuals...")

                    for m_idx, media in enumerate(all_media):
                        pct = (m_idx + 1) / len(all_media)
                        media_progress.progress(pct, text=f"Analyzing {media['label']} ({m_idx+1}/{len(all_media)})...")

                        if media["type"] == "image":
                            description = summarizer.describe_image(
                                media["bytes"], chapter["title"], media["mime_type"]
                            )
                        else:
                            description = summarizer.describe_table(
                                media["bytes"], media.get("text", ""),
                                chapter["title"], media["mime_type"]
                            )

                        st.session_state.chapter_media.append({
                            "type": media["type"],
                            "bytes": media["bytes"],
                            "description": description,
                            "page": media["page"],
                            "label": media["label"],
                        })

                    media_progress.progress(1.0, text="✅ All visuals analyzed!")
                else:
                    st.caption("No significant images or tables found in this chapter.")
            else:
                st.session_state.chapter_media = []

    # Display summary with inline media
    if st.session_state.get("current_summary"):
        st.divider()

        # ── Cached vs fresh indicator ──
        depth_badge = st.session_state.get("current_summary_depth", "")
        if st.session_state.get("summary_from_cache"):
            st.success(f"💾 Showing **cached** {depth_badge} summary — click **🔄 Re-summarize** above to regenerate.")
        else:
            st.success(f"✨ Freshly generated {depth_badge} summary.")

        media_items = st.session_state.get("chapter_media", [])
        summary_text = st.session_state.current_summary

        # ── Category Filter Controls ─────────────────────────────────
        parsed_sections = parse_categorized_summary(summary_text)
        active_cats = get_active_categories(parsed_sections)

        if len(active_cats) > 1:
            st.markdown("**📊 Filter by category:**")
            filter_options = {
                f"{get_category_icon(tag)} {get_category_display(tag).split(' ', 1)[1]}": tag
                for tag in active_cats
            }
            selected_labels = st.multiselect(
                "Show categories",
                options=list(filter_options.keys()),
                default=list(filter_options.keys()),
                label_visibility="collapsed",
            )
            selected_tags = [filter_options[lbl] for lbl in selected_labels]

            # Count sections per category
            cat_counts = {}
            for s in parsed_sections:
                cat_counts[s.category_tag] = cat_counts.get(s.category_tag, 0) + 1

            # Show category badge counts
            badge_parts = []
            for tag in active_cats:
                icon = get_category_icon(tag)
                count = cat_counts.get(tag, 0)
                name = get_category_display(tag).split(" ", 1)[1]
                if tag in selected_tags:
                    badge_parts.append(f"**{icon} {name}** ({count})")
                else:
                    badge_parts.append(f"~~{icon} {name}~~ ({count})")
            st.caption(" • ".join(badge_parts))

            # Filter sections
            filtered = filter_sections(parsed_sections, selected_tags)
            filtered_text = rebuild_summary_text(filtered)
        else:
            filtered_text = summary_text

        if media_items:
            # Split summary into sections and interleave media at correct positions
            _display_summary_with_inline_media(filtered_text, media_items, chapter)
        else:
            st.markdown(filtered_text)

        # Export to PDF
        st.divider()
        col_export, col_spacer = st.columns([1, 2])
        with col_export:
            exporter = SummaryPDFExporter()
            book_title = ""
            if st.session_state.parser:
                meta = st.session_state.parser.get_metadata()
                book_title = meta.get("title", "")
            pdf_bytes = exporter.export(
                chapter_title=chapter["title"],
                chapter_info=f"Pages {chapter['start_page']+1}-{chapter['end_page']+1}",
                summary_text=st.session_state.current_summary,
                depth_label=st.session_state.get("current_summary_depth", ""),
                book_title=book_title,
                media_items=media_items,
                chapter_start_page=chapter["start_page"],
                chapter_end_page=chapter["end_page"],
            )
            safe_title = re.sub(r'[^\w\s-]', '', chapter["title"]).strip().replace(' ', '_')
            st.download_button(
                "📥 Export Summary to PDF",
                data=pdf_bytes,
                file_name=f"StudySage_{safe_title}_summary.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    # ── Cached Summaries Browser ──────────────────────────────────────────────
    st.divider()
    st.subheader("📚 All Cached Summaries")
    st.caption("Previously generated summaries for all chapters — click to view without regenerating.")

    cached_found = []
    for ch_i, ch in enumerate(st.session_state.chapters):
        for depth_val, depth_label in [
            ("brief", "🟢 Brief"),
            ("standard", "🔵 Standard"),
            ("detailed", "🟠 Detailed"),
            ("comprehensive", "🔴 Comprehensive"),
        ]:
            cached_sum = load_cached_summary(st.session_state.pdf_filename, ch_i, depth_val)
            if cached_sum:
                cached_found.append({
                    "ch_idx": ch_i,
                    "title": ch["title"],
                    "depth": depth_label,
                    "depth_val": depth_val,
                    "summary": cached_sum,
                    "length": len(cached_sum),
                })

    if cached_found:
        st.markdown(f"**{len(cached_found)}** cached summaries across **{len(set(c['ch_idx'] for c in cached_found))}** chapters")
        for item in cached_found:
            is_current = (item["ch_idx"] == idx and item["depth"] == st.session_state.get("current_summary_depth", ""))
            icon = "📖" if is_current else "📄"
            with st.expander(
                f"{icon} {item['title']} — {item['depth']} ({item['length']:,} chars)",
                expanded=False,
            ):
                if st.button(
                    f"Load this summary",
                    key=f"load_cached_{item['ch_idx']}_{item['depth_val']}",
                    use_container_width=True,
                ):
                    # Switch to this chapter + summary
                    st.session_state.current_chapter_idx = item["ch_idx"]
                    st.session_state.current_summary = item["summary"]
                    st.session_state.current_summary_depth = item["depth"]
                    st.session_state.summary_from_cache = True
                    # Load chapter text too
                    ch_text = load_cached_text(st.session_state.pdf_filename, item["ch_idx"])
                    if ch_text:
                        st.session_state.chapter_text = ch_text
                    st.rerun()
                st.markdown(item["summary"][:2000] + ("\n\n*... (preview truncated)*" if len(item["summary"]) > 2000 else ""))
    else:
        st.caption("_No cached summaries yet. Generate a summary above and it will appear here._")

    # Show raw text option
    with st.expander("📄 View Raw Chapter Text"):
        st.text(text[:5000] + ("\n\n... (truncated)" if len(text) > 5000 else ""))

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: Q&A
# ═══════════════════════════════════════════════════════════════════════════════

with tab_qa:
    st.header("❓ Ask Questions About This Chapter")

    if st.session_state.current_chapter_idx is None:
        st.info("👈 Select a chapter from the **Chapters** tab first (click the 📖 button)")
        st.stop()

    idx = st.session_state.current_chapter_idx
    chapter = st.session_state.chapters[idx]
    text = st.session_state.chapter_text

    st.markdown(f"**Asking about:** {chapter['title']}")

    # Initialize chat history in session state
    if "qa_history" not in st.session_state:
        st.session_state.qa_history = []

    # Display chat history
    for msg in st.session_state.qa_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    question = st.chat_input("Ask a question about this chapter...")

    if question:
        if not st.session_state.summarizer:
            st.error("❌ Please enter your Gemini API key in the sidebar first")
        else:
            # Add user message
            st.session_state.qa_history.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            # Generate answer
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    # Truncate text if too long for a single query
                    query_text = text[:30000] if len(text) > 30000 else text
                    answer = st.session_state.summarizer.ask_question(
                        query_text, question, chapter["title"]
                    )
                    st.markdown(answer)

            st.session_state.qa_history.append({"role": "assistant", "content": answer})

    # Quick question buttons
    st.divider()
    st.caption("Quick questions:")
    quick_cols = st.columns(4)
    quick_questions = [
        "What are the main concepts?",
        "List all commands mentioned",
        "What are the key takeaways?",
        "Explain the most important point",
    ]
    for i, qq in enumerate(quick_questions):
        with quick_cols[i]:
            if st.button(qq, key=f"quick_{i}", use_container_width=True):
                st.session_state.qa_history.append({"role": "user", "content": qq})
                st.rerun()

    # Clear chat
    if st.session_state.qa_history:
        if st.button("🗑️ Clear Chat"):
            st.session_state.qa_history = []
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: Extract
# ═══════════════════════════════════════════════════════════════════════════════

with tab_extract:
    st.header("🔍 Extract Key Information")

    if st.session_state.current_chapter_idx is None:
        st.info("👈 Select a chapter from the **Chapters** tab first (click the 📖 button)")
        st.stop()

    idx = st.session_state.current_chapter_idx
    chapter = st.session_state.chapters[idx]
    text = st.session_state.chapter_text

    st.markdown(f"**Extracting from:** {chapter['title']}")

    extract_col1, extract_col2 = st.columns(2)

    # ── Local regex-based command extraction ──
    with extract_col1:
        st.subheader("⚡ Quick Extract (Local)")
        st.caption("Uses pattern matching — instant, no API needed")

        if st.button("Extract Commands (Regex)", use_container_width=True):
            extractor = CommandExtractor()
            commands = extractor.extract_from_text(text)

            if commands:
                st.success(f"Found **{len(commands)}** commands")
                st.markdown(extractor.format_commands_table(commands))

                # Auto-register in the command registry and persist
                st.session_state.command_registry.register_commands(
                    commands, idx, chapter["title"]
                )
                save_command_registry(
                    st.session_state.pdf_filename,
                    st.session_state.command_registry.to_dict(),
                )
                st.caption("✅ Commands registered & saved to disk")
            else:
                st.warning("No commands detected via pattern matching")

        # Also try with font analysis if parser available
        if st.button("Extract Commands (Font Analysis)", use_container_width=True):
            if st.session_state.parser:
                with st.spinner("Analyzing fonts..."):
                    blocks = st.session_state.parser.extract_text_blocks(
                        chapter["start_page"], chapter["end_page"]
                    )
                    extractor = CommandExtractor()
                    commands = extractor.extract_from_blocks(blocks)

                    if commands:
                        st.success(f"Found **{len(commands)}** commands via font analysis")
                        st.markdown(extractor.format_commands_table(commands))

                        # Auto-register in the command registry and persist
                        st.session_state.command_registry.register_commands(
                            commands, idx, chapter["title"]
                        )
                        save_command_registry(
                            st.session_state.pdf_filename,
                            st.session_state.command_registry.to_dict(),
                        )
                        st.caption("✅ Commands registered & saved to disk")
                    else:
                        st.warning("No monospace/code-formatted commands detected")

    # ── AI-powered extraction ──
    with extract_col2:
        st.subheader("🤖 AI Extract (Gemini)")
        st.caption("Uses Gemini for deeper, contextual extraction")

        extract_type = st.selectbox(
            "What to extract",
            ["commands", "terms", "concepts", "examples"],
            format_func=lambda x: {
                "commands": "🖥️ Commands & Flags",
                "terms": "📖 Key Terms & Definitions",
                "concepts": "💡 Concepts & Ideas",
                "examples": "📋 Examples & Code Snippets",
            }[x],
        )

        if st.button("🤖 Extract with AI", type="primary", use_container_width=True):
            if not st.session_state.summarizer:
                st.error("❌ Please enter your Gemini API key in the sidebar")
            else:
                with st.spinner(f"Extracting {extract_type} with Gemini..."):
                    query_text = text[:30000] if len(text) > 30000 else text
                    result = st.session_state.summarizer.extract_key_items(
                        query_text, extract_type, chapter["title"]
                    )
                    st.markdown(result)

    # ── Command Tracking Index ─────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Command Tracking Index")
    st.caption(
        "Running index of all commands organized by the chapter they were first introduced. "
        "This persists across sessions — extract commands from any chapter to grow the index."
    )

    registry = st.session_state.command_registry
    chapters_list = st.session_state.chapters

    # Show the full index across ALL chapters (not just up to current)
    all_by_chapter = registry.get_all_commands_by_chapter()

    if all_by_chapter:
        total_cmds = len(registry.get_all_commands())
        new_in_current = registry.get_new_commands(idx)
        st.markdown(
            f"**{total_cmds} total commands tracked** across "
            f"**{len(all_by_chapter)} chapters** • "
            f"**{len(new_in_current)} new** in current chapter"
        )

        for ch_idx in sorted(all_by_chapter.keys()):
            cmds = sorted(all_by_chapter[ch_idx])
            if not cmds:
                continue
            ch_title = chapters_list[ch_idx]["title"] if ch_idx < len(chapters_list) else f"Chapter {ch_idx + 1}"
            is_current = ch_idx == idx
            icon = "📗" if is_current else "📘"
            label = "**← current**" if is_current else ""

            with st.expander(
                f"{icon} {ch_title} — {len(cmds)} commands {label}",
                expanded=is_current,
            ):
                # Display as a compact grid of command badges
                cmd_cols = st.columns(min(len(cmds), 5) or 1)
                for c_idx, cmd_name in enumerate(cmds):
                    col = cmd_cols[c_idx % len(cmd_cols)]
                    with col:
                        info = registry.get_command_info(cmd_name)
                        n_chapters = len(info["chapters"]) if info else 1
                        badge = "📌" if n_chapters == 1 else f"🔄 ×{n_chapters}"
                        st.markdown(f"`{cmd_name}` {badge}")
    else:
        st.info(
            "No commands tracked yet. Use **Extract Commands (Regex)** or "
            "**Extract Commands (Font Analysis)** above on any chapter to start "
            "building the index. It persists across sessions automatically."
        )

    # ── Man Page Lookup ───────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📖 Man Page Lookup")
    st.caption(
        "Look up any Linux command — fetches the real man page, then summarizes it "
        "into a simple reference with the most useful flags and examples. "
        "No more deciphering cryptic man pages!"
    )

    man_col_input, man_col_quick = st.columns([1, 2])

    with man_col_input:
        man_command = st.text_input(
            "Command to look up",
            placeholder="e.g., grep, chmod, tar, awk",
            key="man_command_input",
        )
        man_lookup_btn = st.button("📖 Look Up Man Page", use_container_width=True, type="primary")

    with man_col_quick:
        # Auto-detect commands from chapter for quick buttons
        st.caption("Quick lookup — commands found in this chapter:")
        extractor = CommandExtractor()
        detected = extractor.extract_from_text(text)
        detected_names = sorted(set(c.command for c in detected))[:20]

        if detected_names:
            # Render as a grid of buttons
            btn_cols = st.columns(min(len(detected_names), 6))
            for c_idx, cmd_name in enumerate(detected_names):
                col = btn_cols[c_idx % len(btn_cols)]
                with col:
                    cached = st.session_state.man_summaries.get(cmd_name)
                    icon = "✅" if cached and cached.get("status") == "success" else "❌" if cached and cached.get("status") == "error" else "📌"
                    if st.button(f"{icon} {cmd_name}", key=f"man_quick_{cmd_name}", use_container_width=True):
                        man_command = cmd_name
                        man_lookup_btn = True
        else:
            st.caption("_No commands detected yet — run an extraction above first, or type a command manually._")

    # Process man page lookup
    if man_lookup_btn and man_command:
        cmd = man_command.strip().split()[0]  # Take first word only

        # Check cache first
        if cmd in st.session_state.man_summaries:
            cached = st.session_state.man_summaries[cmd]
            if cached["status"] == "success":
                st.markdown(cached["summary"])
                st.caption(f"_Source: {cached.get('source', 'cached')} man page • Cached_")
            else:
                st.error(cached["summary"])
        else:
            if not st.session_state.summarizer:
                st.error("❌ Please enter your Gemini API key in the sidebar first")
            else:
                with st.spinner(f"Fetching man page for `{cmd}`..."):
                    result = fetch_man_page(cmd)

                if result["success"]:
                    with st.spinner(f"Summarizing `{cmd}` man page with Gemini..."):
                        summary = st.session_state.summarizer.summarize_man_page(
                            cmd, result["text"]
                        )
                        st.session_state.man_summaries[cmd] = {
                            "status": "success",
                            "summary": summary,
                            "source": result["source"],
                        }
                        st.markdown(summary)
                        st.caption(f"_Source: {result['source']} man page_")

                    # Offer to see the raw man page
                    with st.expander(f"📄 View raw man page for `{cmd}`"):
                        st.code(result["text"][:8000], language="text")
                else:
                    st.session_state.man_summaries[cmd] = {
                        "status": "error",
                        "summary": result["text"],
                    }
                    st.error(f"❌ `{cmd}` — {result['text']}")

    # Show all cached man summaries
    cached_cmds = [
        k for k, v in st.session_state.man_summaries.items()
        if v.get("status") == "success"
    ]
    if cached_cmds:
        st.divider()
        st.caption(f"📚 **{len(cached_cmds)} commands summarized** this session — click to review:")
        for cmd_name in sorted(cached_cmds):
            with st.expander(f"`{cmd_name}`"):
                st.markdown(st.session_state.man_summaries[cmd_name]["summary"])

# ── Footer ───────────────────────────────────────────────────────────────────

st.divider()
st.caption("📚 StudySage — Built with Streamlit + PyMuPDF + Google Gemini")
