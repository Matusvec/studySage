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
from dotenv import load_dotenv

load_dotenv()

from src.pdf_parser import PDFParser
from src.summarizer import GeminiSummarizer, SummaryDepth
from src.command_extractor import CommandExtractor
from src.pdf_exporter import SummaryPDFExporter
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
</style>
""", unsafe_allow_html=True)

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
        # Save to temp file
        if st.session_state.pdf_filename != uploaded_file.name:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name

            # Parse PDF
            if st.session_state.parser:
                st.session_state.parser.close()

            st.session_state.parser = PDFParser(tmp_path)
            st.session_state.pdf_filename = uploaded_file.name

            # Try to load cached chapters first
            cached_chapters = load_chapters(uploaded_file.name)
            if cached_chapters:
                st.session_state.chapters = cached_chapters
                st.success(f"📖 Loaded {len(cached_chapters)} cached chapters")
            else:
                # Extract chapters from TOC
                chapters = st.session_state.parser.extract_chapters(max_level=2)
                if not chapters:
                    chapters = st.session_state.parser.fallback_chapter_detection()
                st.session_state.chapters = chapters
                save_chapters(uploaded_file.name, chapters)

            st.session_state.current_chapter_idx = None
            st.session_state.chapter_text = ""

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

# ── Main Content Area ────────────────────────────────────────────────────────

if not st.session_state.parser:
    # Welcome screen
    st.markdown("""
    # 📚 Welcome to StudySage

    **Your AI-powered study companion for PDF textbooks.**

    ### How it works:
    1. **Upload** your PDF book using the sidebar
    2. **Review & verify** the auto-detected chapter structure
    3. **Select a chapter** to explore
    4. **Get summaries** at your preferred depth (brief → comprehensive)
    5. **Ask questions** about specific chapters
    6. **Extract** key commands, terms, and concepts

    ### Getting Started:
    - Get a free **Gemini API key** at [Google AI Studio](https://aistudio.google.com/apikey)
    - Enter it in the sidebar
    - Upload any PDF book

    ---
    *StudySage uses Google Gemini to generate summaries while keeping your book data local.*
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
                            st.session_state.current_summary = ""
                            st.session_state.current_summary_depth = ""

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

    # Generate or load summary
    if st.button("✨ Generate Summary", type="primary", use_container_width=True):
        if not st.session_state.summarizer:
            st.error("❌ Please enter your Gemini API key in the sidebar first")
        else:
            # Check cache first
            cached = load_cached_summary(
                st.session_state.pdf_filename, idx, selected_depth.value
            )

            if cached and not custom_instructions:
                st.session_state.current_summary = cached
                st.session_state.current_summary_depth = selected_depth_name
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

    # Display summary and export option
    if st.session_state.get("current_summary"):
        st.divider()
        st.markdown(st.session_state.current_summary)

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
            )
            safe_title = re.sub(r'[^\w\s-]', '', chapter["title"]).strip().replace(' ', '_')
            st.download_button(
                "📥 Export Summary to PDF",
                data=pdf_bytes,
                file_name=f"StudySage_{safe_title}_summary.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

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

# ── Footer ───────────────────────────────────────────────────────────────────

st.divider()
st.caption("📚 StudySage — Built with Streamlit + PyMuPDF + Google Gemini")
