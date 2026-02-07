<p align="center">
  <img src="https://img.icons8.com/fluency/128/book-shelf.png" alt="StudySage" />
</p>

<h1 align="center">📚 StudySage</h1>

<p align="center">
  <strong>Your AI-Powered Study Companion for PDF Textbooks</strong><br/>
  Upload a book. Get instant summaries, visual analysis, Q&A, command references, and more — all in one place.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Powered%20by-Google%20Gemini-4285F4?logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-green" />
</p>

---

## 💡 The Problem

You're studying from a 600-page PDF. You copy a chapter into ChatGPT, but the images disappear, the formatting breaks, you hit the token limit, and tomorrow you have to do it all over again.

**StudySage fixes that.**

Upload your textbook once. Every chapter, summary, image, and extraction is cached permanently. Come back next week and pick up exactly where you left off — your entire personal study library, ready to go.

---

## 🤔 StudySage vs. Doing It Yourself

| The old way | The StudySage way |
|---|---|
| Copy-paste pages into a chatbot one at a time | Upload the whole PDF once — chapters auto-detected |
| Lose every diagram, chart, and table | AI Vision extracts & explains every figure inline |
| Re-paste text every new session | Everything cached — close the app, come back anytime |
| One generic summary with no control | 4 depth levels from quick recap to full exam prep |
| No idea what you already summarized | Visual book library with covers and history |
| Can't export anything useful | One-click PDF export with images included |
| Man pages are walls of cryptic text | Plain-English summaries with the flags you actually need |
| Lose track of commands across chapters | Running command index with instant descriptions |

---

## ✨ Features

### 📚 Personal Book Library
Open StudySage and see all your books at a glance — complete with cover thumbnails, page counts, chapter counts, and the last time you opened each one. Click to jump right back in. Delete books you're done with. Your study shelf, always ready.

### 📄 Smart Chapter Detection
Upload any PDF and StudySage reads the table of contents to detect every chapter and section automatically. Review the structure, verify page ranges, and edit anything that looks off. No more guessing where Chapter 7 starts.

### 📝 Summaries — Your Depth, Your Way

| Level | Best for |
|-------|----------|
| 🟢 **Brief** | Quick review before class — 3-5 key takeaways |
| 🔵 **Standard** | Regular studying — main points with explanations |
| 🟠 **Detailed** | Assignments — all points with supporting details |
| 🔴 **Comprehensive** | Exam prep — misses nothing |

Long chapters are split into sections, summarized individually, then merged into one clean result. Add **custom instructions** like *"focus on networking commands"* or *"explain like I'm a beginner"* to tailor the output.

**Already summarized?** StudySage tells you a cached version exists and lets you load it instantly — or hit **🔄 Re-summarize** to generate a fresh one if you're not happy with it.

### 🏷️ Categorized & Filterable Summaries
Every summary is organized into tagged categories — Commands, Scripting, Networking, File Systems, Concepts, Tips, and more. Use the **category filter** to show only what you care about. Studying for a networking exam? Filter to just the networking sections. Writing a script? Show only scripting and examples.

### 🖼️ Image & Table Analysis
Diagrams and tables are the first thing lost when you paste text into a chatbot. StudySage extracts every figure and table from the PDF, sends each to **Google AI Vision** for analysis, and places them **inline at their correct position** in the summary — with clear descriptions. Click any thumbnail to enlarge.

### ❓ Chapter Q&A
Ask specific questions about any chapter and get answers grounded in the actual text. Full chat history, no context pollution from other conversations. It's like having a tutor who actually read the book.

### 🔍 Key Item Extraction
Pull organized reference lists from any chapter:

| Extraction Type | What You Get |
|-----------------|-------------|
| 🖥️ **Commands & Flags** | Every command with its options and a short description |
| 📖 **Key Terms** | Definitions for the vocabulary that matters |
| 💡 **Concepts & Ideas** | The big-picture takeaways |
| 📋 **Examples & Code** | Ready-to-use snippets and code blocks |

Two extraction modes: **⚡ Quick Extract** runs locally with pattern matching (instant, no API needed) and **🤖 AI Extract** uses Gemini for deeper contextual analysis.

### 📊 Command Tracking Index
Every command you extract is registered into a **running index** that tracks which chapter each command was introduced in. Each command shows a clean one-liner description and a badge showing if it appears in multiple chapters. The index **persists across sessions** — build it up over time as you work through the book.

### 📖 Man Page Lookup
Click any detected command — or type one in — to fetch its real man page and get an AI-generated **plain-English summary** with:
- What the command does (no jargon)
- A clean table of the most useful flags
- Real-world examples you can copy and run
- A beginner-friendly pro tip

Quick-lookup buttons are auto-generated from the commands found in the current chapter.

### 📥 One-Click PDF Export
Export any summary — complete with figures, tables, and AI descriptions — to a clean, formatted PDF. Print it, share it with your study group, or save it to your notes app.

### 💾 Persistent Smart Caching
Every summary, chapter extraction, and command registry is saved to disk automatically. Close the app, reboot your machine, come back next week — **everything is exactly where you left it**. Your book library, summaries, and command index survive across sessions with zero effort.

### 📚 Cached Summaries Browser
At the bottom of the Summary tab, browse **all previously generated summaries** across every chapter and depth level. Click any one to load it instantly — no regeneration, no API calls, no waiting.

---

## 🚀 Getting Started

### 1. Get a Free API Key
Go to **[Google AI Studio](https://aistudio.google.com/apikey)** and create a free Gemini API key. It takes 30 seconds.

### 2. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/studySage.git
cd studySage
pip install -r requirements.txt
```

### 3. Add Your API Key

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

Or paste it directly in the sidebar when the app opens.

### 4. Run

```bash
streamlit run app.py
```

Opens at `http://localhost:8501` in your browser. Upload a book and start studying.

---

## 📖 Quick Walkthrough

1. **Launch** → Your book library appears. Open a previous book or upload a new one.
2. **Chapters tab** → Review detected chapters. Verify structure, edit page ranges if needed.
3. **Select a chapter** → Click 📖 next to any chapter.
4. **Summary tab** → Pick a depth level, add custom instructions, generate. Already cached? Load it instantly or re-summarize.
5. **Filter** → Use category tags to focus on specific topics.
6. **Q&A tab** → Ask questions about the chapter.
7. **Extract tab** → Pull out commands, terms, concepts, or examples.
8. **Command Index** → See all tracked commands across every chapter.
9. **Man Pages** → Click any command for a plain-English breakdown.
10. **Export** → Download your summary as a formatted PDF.

---

## 🛡️ Privacy

Your books stay on your machine. StudySage only sends chapter text and images to Google's Gemini API for processing. **Nothing is stored on any external server.** All caching is local to your computer.

---

## 🧰 Built With

| Technology | Role |
|-----------|------|
| [Streamlit](https://streamlit.io/) | Web interface |
| [PyMuPDF](https://pymupdf.readthedocs.io/) | PDF parsing & image extraction |
| [Google Gemini API](https://ai.google.dev/) | Summaries, vision, Q&A, and extraction |
| [fpdf2](https://py-pdf.github.io/fpdf2/) | PDF export |

---

## 📄 License

MIT — free to use, modify, and share.
