# 📚 StudySage

### Your AI-Powered Study Companion for PDF Textbooks

**Stop copy-pasting chapters into ChatGPT.** Upload your textbook once, and StudySage does the rest — chapter detection, smart summaries, image analysis, Q&A, and PDF export. All in one click.

---

## 🤔 Why StudySage?

| Manually using AI chatbots | Using StudySage |
|---|---|
| Copy-paste pages one at a time | Upload the whole PDF once |
| Lose all images, diagrams, and tables | Extracts & explains every figure with AI Vision |
| Re-paste text every new session | Caches everything — come back anytime |
| One generic summary | 4 depth levels: quick review → full exam prep |
| No way to export | One-click PDF export with images included |
| Guessing where chapters start/end | Auto-detects chapters from the book's table of contents |
| Man pages are cryptic and overwhelming | One-click man page summaries in plain English |

> *"Gemini is the engine. StudySage is the car."*

---

## ✨ Features

### 📄 Smart PDF Upload
Upload any PDF textbook and StudySage automatically detects every chapter and section from the table of contents. No manual page hunting — just upload and go.

### 📝 Summaries at Your Depth
Choose how deep you want to go:

- **🟢 Brief** — 3-5 key takeaways. Perfect for quick review before class.
- **🔵 Standard** — Main points with explanations. Great for regular studying.
- **🟠 Detailed** — Every point with supporting details. Ideal for assignments.
- **🔴 Comprehensive** — Misses nothing. Built for exam prep.

Long chapters are automatically split into sections and summarized individually, then merged into one clean summary. No information gets lost.

### 🖼️ Image & Table Analysis
Diagrams, charts, and tables are often the most important part of a textbook — and they're the first thing lost when you paste text into a chatbot. StudySage extracts every figure and table from the PDF, sends each one to Google's AI Vision, and places them **inline in the summary at their correct position** with a clear description. Images appear as compact thumbnails you can click to enlarge.

### ❓ Chapter Q&A
Ask specific questions about any chapter and get answers grounded in the actual text. Built-in chat with history — no context pollution from other conversations.

### 🔍 Key Item Extraction
Pull out organized reference lists of:
- **Commands & syntax** (great for technical books)
- **Key terms & definitions**
- **Core concepts & ideas**
- **Examples & code snippets**

Works both instantly (offline pattern matching) and with AI for deeper analysis.

### 📖 Man Page Lookup
Studying a book with Linux commands? Click any command to fetch its real man page, then get an AI-generated **plain-English summary** with:
- What the command does in simple terms
- The most useful flags in a clean table (no more scrolling through 200 options)
- Real-world examples you can actually use
- A beginner-friendly pro tip

If a command isn't recognized, StudySage tells you — so you know it's not a real command. All summaries are cached for the session, so you can flip between them instantly.

### 📥 One-Click PDF Export
Export your summary — complete with figures, tables, and AI descriptions — to a clean, formatted PDF. Print it, share it with your study group, or save it to your notes app.

### 💾 Smart Caching
Every chapter, summary, and extraction is cached locally. Close the app, come back tomorrow, and everything is still there. No re-uploading, no re-generating, no wasted API calls.

---

## 🚀 Getting Started

### Step 1: Get a Free API Key
Go to [Google AI Studio](https://aistudio.google.com/apikey) and create a free Gemini API key. Takes 30 seconds.

### Step 2: Install StudySage

```bash
git clone https://github.com/YOUR_USERNAME/studySage.git
cd studySage
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### Step 3: Run

```bash
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`. Enter your API key in the sidebar, upload a PDF, and start studying.

---

## 📖 How to Use

1. **Enter your API key** in the sidebar (or save it to a `.env` file to auto-load)
2. **Upload your PDF** — chapters are detected automatically
3. **Verify chapters** — review the detected structure, fix any page ranges if needed
4. **Select a chapter** — click the 📖 button next to any chapter
5. **Generate a summary** — pick your depth level, optionally enable image/table analysis
6. **Ask questions** — switch to the Q&A tab and chat about the chapter
7. **Extract key info** — pull out commands, terms, or concepts from the Extract tab
8. **Look up commands** — click any detected command to get a plain-English man page summary
9. **Export to PDF** — download your summary as a formatted PDF with all visuals included

---

## 🛡️ Privacy

Your books stay on your machine. StudySage only sends chapter text and images to Google's Gemini API for processing — nothing is stored on any server. All caching is local.

---

## 🧰 Built With

- [Streamlit](https://streamlit.io/) — Web interface
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF parsing and image extraction
- [Google Gemini API](https://ai.google.dev/) — AI summaries, vision, and Q&A
- [fpdf2](https://py-pdf.github.io/fpdf2/) — PDF export

---

## 📄 License

MIT — free to use, modify, and share.
