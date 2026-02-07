"""
Summarizer Module
Handles AI-powered summarization using Google Gemini API.
Supports adjustable summary depth levels with content categorization.
"""

from google import genai
from google.genai import types
import time
from enum import Enum
from src.category_parser import get_category_tags_prompt


class SummaryDepth(Enum):
    """Summary depth levels for adjustable detail."""
    BRIEF = "brief"         # Key takeaways only (3-5 bullet points)
    STANDARD = "standard"   # Main points with brief explanations
    DETAILED = "detailed"   # All main + supporting points
    COMPREHENSIVE = "comprehensive"  # Everything: main points, sub-points, examples, commands


DEPTH_PROMPTS = {
    SummaryDepth.BRIEF: (
        "Provide a BRIEF summary with only the 3-5 most important key takeaways. "
        "Keep it concise — one sentence per point."
    ),
    SummaryDepth.STANDARD: (
        "Provide a STANDARD summary covering all main points with brief explanations. "
        "Include key concepts, important terms, and notable examples. "
        "Use bullet points organized by topic."
    ),
    SummaryDepth.DETAILED: (
        "Provide a DETAILED summary covering ALL main points AND supporting details. "
        "Include: key concepts with explanations, important terms and definitions, "
        "examples and use cases, any commands/syntax/code mentioned, and relationships "
        "between concepts. Organize with clear headings and sub-bullets."
    ),
    SummaryDepth.COMPREHENSIVE: (
        "Provide an EXHAUSTIVE, COMPREHENSIVE summary that captures EVERYTHING in this text. "
        "Include: every main point and sub-point, all definitions and explanations, "
        "every example and use case mentioned, all commands/flags/syntax with descriptions, "
        "tips/warnings/notes, relationships and comparisons between concepts, "
        "and any practical advice given. Miss NOTHING — even small details matter. "
        "Organize with clear headings, sub-headings, and nested bullet points."
    ),
}


class GeminiSummarizer:
    """Summarizes text using Google Gemini API with adjustable depth."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the Gemini summarizer.

        Args:
            api_key: Google Gemini API key
            model_name: Gemini model to use (default: gemini-2.5-flash)
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.max_retries = 3
        self.retry_base_delay = 40  # seconds — matches Gemini's suggested retry

    def _call_with_retry(self, config, contents) -> str:
        """Call Gemini API with automatic retry on rate limit (429) errors."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower():
                    wait = self.retry_base_delay * (attempt + 1)
                    if attempt < self.max_retries - 1:
                        print(f"⏳ Rate limited — waiting {wait}s before retry {attempt + 2}/{self.max_retries}...")
                        time.sleep(wait)
                    else:
                        return (
                            f"❌ Rate limit exceeded after {self.max_retries} retries. "
                            f"Try switching to a different model (e.g. gemini-1.5-flash) "
                            f"in the sidebar, or wait a minute and try again.\n\n"
                            f"Error: {error_str[:200]}"
                        )
                else:
                    return f"❌ Error: {error_str}"
        return "❌ Unexpected error during retry."

    def summarize(
        self,
        text: str,
        chapter_title: str = "",
        depth: SummaryDepth = SummaryDepth.STANDARD,
        custom_instructions: str = "",
        categorize: bool = True,
    ) -> str:
        """
        Summarize text with the specified depth level.

        Args:
            text: The chapter/section text to summarize
            chapter_title: Optional chapter title for context
            depth: How detailed the summary should be
            custom_instructions: Any additional user instructions
            categorize: Whether to include category tags in headings

        Returns:
            Formatted summary string
        """
        depth_instruction = DEPTH_PROMPTS[depth]

        category_instruction = ""
        if categorize:
            category_instruction = "\n\n" + get_category_tags_prompt()

        system_prompt = (
            "You are StudySage, an expert study assistant. Your job is to create "
            "clear, well-organized summaries of book chapters that help students "
            "learn and review material efficiently.\n\n"
            "Format your response in clean Markdown with:\n"
            "- Clear headings (##, ###)\n"
            "- Bullet points for lists\n"
            "- **Bold** for key terms and commands\n"
            "- `code formatting` for commands, syntax, file paths\n"
            "- Numbered lists for sequential steps or processes\n"
            + category_instruction
        )

        user_prompt = f"{depth_instruction}\n\n"

        if chapter_title:
            user_prompt += f"Chapter: **{chapter_title}**\n\n"

        if custom_instructions:
            user_prompt += f"Additional instructions: {custom_instructions}\n\n"

        user_prompt += f"Text to summarize:\n\n{text}"

        return self._call_with_retry(
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=65536,
            ),
            contents=system_prompt + "\n\n" + user_prompt,
        )

    def ask_question(self, text: str, question: str, chapter_title: str = "") -> str:
        """
        Answer a specific question about the chapter text.

        Args:
            text: The chapter text for context
            question: The user's question
            chapter_title: Optional chapter title

        Returns:
            Answer string
        """
        system_prompt = (
            "You are StudySage, an expert study assistant. Answer the user's question "
            "based ONLY on the provided chapter text. If the answer isn't in the text, "
            "say so clearly. Use Markdown formatting for clarity.\n"
            "Cite specific parts of the text when possible."
        )

        user_prompt = ""
        if chapter_title:
            user_prompt += f"Chapter: **{chapter_title}**\n\n"

        user_prompt += f"Chapter text:\n{text}\n\n"
        user_prompt += f"Question: {question}"

        return self._call_with_retry(
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
            ),
            contents=system_prompt + "\n\n" + user_prompt,
        )

    def describe_image(
        self,
        image_bytes: bytes,
        chapter_title: str = "",
        mime_type: str = "image/png",
    ) -> str:
        """
        Describe an image from the PDF using Gemini Vision.

        Args:
            image_bytes: Raw image bytes (PNG)
            chapter_title: Chapter context
            mime_type: Image MIME type

        Returns:
            AI-generated description of the image
        """
        system_prompt = (
            "You are StudySage, an expert study assistant. Analyze this image from "
            "a textbook and provide a clear, concise description that helps a student "
            "understand what the image shows.\n\n"
            "Include:\n"
            "- What the image depicts (diagram, chart, screenshot, illustration, etc.)\n"
            "- Key information or data shown\n"
            "- How it relates to the chapter content\n"
            "- Any labels, legends, or annotations\n\n"
            "Keep the description to 2-4 sentences. Use Markdown formatting."
        )

        context = ""
        if chapter_title:
            context = f"This image is from the chapter: **{chapter_title}**\n\n"

        prompt_text = system_prompt + "\n\n" + context + "Describe this image:"

        return self._call_with_retry(
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1024,
            ),
            contents=[
                prompt_text,
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
        )

    def describe_table(
        self,
        table_image_bytes: bytes,
        table_text: str = "",
        chapter_title: str = "",
        mime_type: str = "image/png",
    ) -> str:
        """
        Describe/summarize a table from the PDF using Gemini Vision.

        Args:
            table_image_bytes: Table rendered as PNG bytes
            table_text: Raw text extraction of the table (for additional context)
            chapter_title: Chapter context
            mime_type: Image MIME type

        Returns:
            AI-generated summary of the table
        """
        system_prompt = (
            "You are StudySage, an expert study assistant. Analyze this table from "
            "a textbook and provide a clear summary that helps a student understand "
            "the key information.\n\n"
            "Include:\n"
            "- What the table is about (its purpose)\n"
            "- Key data points, comparisons, or relationships shown\n"
            "- Any important patterns or takeaways\n\n"
            "Keep it concise but informative (3-5 sentences). Use Markdown formatting."
        )

        context = ""
        if chapter_title:
            context += f"This table is from the chapter: **{chapter_title}**\n\n"
        if table_text:
            context += f"Raw table text (for reference):\n```\n{table_text[:2000]}\n```\n\n"

        prompt_text = system_prompt + "\n\n" + context + "Summarize this table:"

        return self._call_with_retry(
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1024,
            ),
            contents=[
                prompt_text,
                types.Part.from_bytes(data=table_image_bytes, mime_type=mime_type),
            ],
        )

    def summarize_man_page(self, command: str, man_text: str) -> str:
        """
        Summarize a man page into a clear, simple reference.

        Args:
            command: The command name
            man_text: Raw man page text

        Returns:
            Formatted summary with description, usage, and flags
        """
        system_prompt = (
            "You are StudySage, an expert Linux/Unix study assistant. "
            "A student is learning about commands from a textbook and wants to "
            "understand this command clearly.\n\n"
            "Summarize this man page into a SIMPLE, CLEAR reference card. "
            "The original man page is often overly technical and intimidating — "
            "your job is to make it approachable.\n\n"
            "Format your response EXACTLY like this:\n\n"
            "## `command` — One-Line Description\n\n"
            "**What it does:** 1-2 sentence plain-English explanation.\n\n"
            "**Basic usage:**\n"
            "```\ncommand [common usage pattern]\n```\n\n"
            "**Most useful flags:**\n"
            "| Flag | What it does |\n"
            "|------|-------------|\n"
            "| `-x` | Simple explanation |\n\n"
            "**Common examples:**\n"
            "```bash\n# Example with explanation\ncommand -flags args\n```\n\n"
            "**Pro tip:** One helpful tip for beginners.\n\n"
            "Rules:\n"
            "- Keep explanations simple — imagine explaining to someone who just started learning Linux\n"
            "- Only include the 8-12 most useful/common flags, not all of them\n"
            "- Give 3-5 real-world examples\n"
            "- If a flag is rarely used or very advanced, skip it\n"
            "- Use plain English, avoid jargon where possible\n"
        )

        user_prompt = (
            f"Summarize this man page for the `{command}` command:\n\n"
            f"{man_text}"
        )

        return self._call_with_retry(
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
            ),
            contents=system_prompt + "\n\n" + user_prompt,
        )

    def extract_key_items(self, text: str, item_type: str = "commands", chapter_title: str = "") -> str:
        """
        Extract specific types of items from the text (commands, terms, concepts, etc.)

        Args:
            text: The chapter text
            item_type: What to extract — "commands", "terms", "concepts", "examples"
            chapter_title: Optional chapter title

        Returns:
            Formatted list of extracted items
        """
        type_prompts = {
            "commands": (
                "Extract ALL commands, flags, and syntax mentioned in this text. "
                "For each command, provide:\n"
                "- The command name and syntax\n"
                "- What it does (brief description)\n"
                "- Any flags/options mentioned with their purposes\n"
                "- Example usage if given in the text\n"
                "Format as a reference table or organized list."
            ),
            "terms": (
                "Extract ALL key terms, definitions, and vocabulary from this text. "
                "For each term, provide the definition or explanation given in the text. "
                "Format as a glossary list."
            ),
            "concepts": (
                "Extract ALL key concepts and ideas from this text. "
                "For each concept, provide a brief explanation and how it relates "
                "to other concepts mentioned. Organize hierarchically."
            ),
            "examples": (
                "Extract ALL examples, code snippets, and practical demonstrations "
                "from this text. For each, explain what it demonstrates and the "
                "expected output or result."
            ),
        }

        prompt = type_prompts.get(item_type, type_prompts["concepts"])

        system_prompt = (
            "You are StudySage, an expert study assistant. Extract and organize "
            "information precisely from the provided text. Only include items "
            "actually present in the text — do not add external knowledge."
        )

        user_prompt = ""
        if chapter_title:
            user_prompt += f"Chapter: **{chapter_title}**\n\n"

        user_prompt += f"{prompt}\n\nText:\n{text}"

        return self._call_with_retry(
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=65536,
            ),
            contents=system_prompt + "\n\n" + user_prompt,
        )

    def summarize_long_text(
        self,
        chunks: list[str],
        chapter_title: str = "",
        depth: SummaryDepth = SummaryDepth.STANDARD,
        categorize: bool = True,
    ) -> str:
        """
        Summarize text that's been split into chunks.
        Summarizes each chunk, then combines into a final summary.
        """
        if len(chunks) == 1:
            return self.summarize(chunks[0], chapter_title, depth, categorize=categorize)

        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            summary = self.summarize(
                chunk,
                chapter_title=f"{chapter_title} (Part {i+1}/{len(chunks)})" if chapter_title else f"Part {i+1}/{len(chunks)}",
                depth=depth,
                categorize=False,  # Don't tag individual chunks
            )
            chunk_summaries.append(summary)

        combined_text = "\n\n---\n\n".join(chunk_summaries)

        combine_prompt = (
            f"The following are summaries of different parts of the same chapter. "
            f"Combine them into ONE cohesive, well-organized summary. "
            f"Remove duplicates, merge related points, and maintain the "
            f"{depth.value} depth level.\n\n{combined_text}"
        )

        return self.summarize(combine_prompt, chapter_title, depth, categorize=categorize)

    def summarize_by_sections(
        self,
        sections: list[dict],
        chapter_title: str = "",
        depth: SummaryDepth = SummaryDepth.STANDARD,
        custom_instructions: str = "",
        progress_callback=None,
        categorize: bool = True,
    ) -> str:
        """
        Summarize a chapter by its detected sub-sections, then combine.

        This produces much better results than raw-text summarization because:
        - Each section is summarized with full attention (no "lost in the middle")
        - Section titles provide structural context to the model
        - The final combine step creates a cohesive, well-organized summary

        Args:
            sections: List of dicts from PDFParser.extract_sections()
                      Each has: {title, text, page}
            chapter_title: The parent chapter title
            depth: Summary depth level
            custom_instructions: Any additional user instructions
            progress_callback: Optional callable(current, total, section_title)
            categorize: Whether to include category tags in headings

        Returns:
            Combined summary string
        """
        if len(sections) == 1:
            return self.summarize(
                sections[0]["text"], chapter_title, depth, custom_instructions,
                categorize=categorize,
            )

        # Phase 1: Summarize each section individually
        section_summaries = []
        for i, section in enumerate(sections):
            if progress_callback:
                progress_callback(i, len(sections), section["title"])

            section_prompt = (
                f"This is section \"{section['title']}\" from the chapter "
                f"\"{chapter_title}\". Summarize this section specifically.\n\n"
                f"{section['text']}"
            )

            summary = self.summarize(
                section_prompt,
                chapter_title=f"{chapter_title} → {section['title']}",
                depth=depth,
                custom_instructions=custom_instructions,
                categorize=False,  # Don't tag individual sections
            )
            section_summaries.append({
                "title": section["title"],
                "summary": summary,
            })

        if progress_callback:
            progress_callback(len(sections), len(sections), "Combining sections...")

        # Phase 2: Combine all section summaries into one cohesive chapter summary
        parts = []
        for s in section_summaries:
            parts.append(f"### {s['title']}\n\n{s['summary']}")
        combined_text = "\n\n---\n\n".join(parts)

        depth_instruction = DEPTH_PROMPTS[depth]

        category_instruction = ""
        if categorize:
            category_instruction = "\n" + get_category_tags_prompt()

        combine_system = (
            "You are StudySage, an expert study assistant. You are given summaries "
            "of individual sections from a single book chapter. Your job is to "
            "combine them into ONE cohesive, well-organized chapter summary.\n\n"
            "Rules:\n"
            "- Keep the section structure (use headings for each section)\n"
            "- Remove any duplicate points that appear across sections\n"
            "- Add a brief chapter overview at the top (2-3 sentences)\n"
            "- Maintain all key details — don't lose information in the merge\n"
            "- Format in clean Markdown with headings, bullets, bold, and code formatting\n"
            + category_instruction
        )

        combine_user = (
            f"{depth_instruction}\n\n"
            f"Chapter: **{chapter_title}**\n\n"
            f"The following are summaries of each section in this chapter. "
            f"Combine into one cohesive summary:\n\n{combined_text}"
        )

        if custom_instructions:
            combine_user += f"\n\nAdditional instructions: {custom_instructions}"

        return self._call_with_retry(
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=65536,
            ),
            contents=combine_system + "\n\n" + combine_user,
        )
