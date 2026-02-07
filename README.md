# 📚 StudySage

**AI-powered PDF study companion** — Upload books, detect chapters, get summaries at adjustable depth, ask questions, and extract key commands/terms.

## Features

- **📄 PDF Upload & TOC Detection** — Auto-detects chapters from PDF metadata; falls back to pattern matching for books without embedded TOC
- **✅ Chapter Verification** — Review detected chapters, edit page ranges, verify structure before studying
- **📝 Adjustable-Depth Summaries** — 4 depth levels: Brief → Standard → Detailed → Comprehensive
- **❓ Chapter Q&A** — Ask questions about specific chapters with full context
- **🔍 Key Item Extraction** — Extract commands, terms, concepts, and examples (local regex + AI-powered)
- **💾 Smart Caching** — Caches chapter text and summaries to avoid re-processing
- **🖥️ Linux Command Extraction** — Special regex patterns tuned for technical books (monospace font detection, shell prompt patterns)

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/studySage.git
cd studySage
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Get a Gemini API Key

- Go to [Google AI Studio](https://aistudio.google.com/apikey)
- Create a free API key
- You'll enter it in the app sidebar (or save to `.streamlit/secrets.toml`)

### 3. Run

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Usage

1. **Enter your Gemini API key** in the sidebar
2. **Upload a PDF** book
3. **Review chapters** in the Chapters tab — verify or edit page ranges
4. **Click 📖** on any chapter to select it
5. **Go to Summary tab** — choose depth level and generate
6. **Go to Q&A tab** — ask specific questions about the chapter
7. **Go to Extract tab** — pull out commands, terms, concepts

## Summary Depth Levels

| Level | Description |
|-------|-------------|
| 🟢 **Brief** | 3-5 key takeaways only |
| 🔵 **Standard** | Main points with explanations |
| 🟠 **Detailed** | All main + supporting details |
| 🔴 **Comprehensive** | Everything — miss nothing |

## Project Structure

```
studySage/
├── app.py                      # Main Streamlit app
├── requirements.txt            # Python dependencies
├── .gitignore
├── .streamlit/
│   └── secrets.toml.example    # API key template
└── src/
    ├── __init__.py
    ├── pdf_parser.py           # PDF loading, TOC extraction, text extraction
    ├── summarizer.py           # Gemini API integration, depth-adjustable summaries
    ├── chapter_manager.py      # Chapter state, caching, verification
    └── command_extractor.py    # Regex + font-based command extraction
```

## Tech Stack

- **[Streamlit](https://streamlit.io/)** — Web UI
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** — PDF parsing (fast, reliable, extracts TOC + fonts)
- **[Google Gemini API](https://ai.google.dev/)** — AI summaries, Q&A, and extraction

## License

MIT
