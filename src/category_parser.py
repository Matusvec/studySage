"""
Category Parser Module
Parses and assigns content categories to summary sections.
Supports both tag-based (from AI-generated summaries) and keyword-based
(fallback) categorization.

Tag format in summaries:
    ## [CMD] The `ls` Command
    ## [CONCEPT] Understanding File Permissions
"""

import re
from dataclasses import dataclass, field


# ── Category Definitions ─────────────────────────────────────────────────────

@dataclass
class Category:
    """A content category with display info and keyword matching rules."""
    tag: str            # Short tag used in headings, e.g. "CMD"
    label: str          # Display label with icon
    icon: str           # Emoji icon
    keywords: list[str] = field(default_factory=list)  # Keywords for fallback matching
    priority: int = 10  # Lower = higher priority for ambiguous matches


CATEGORIES: dict[str, Category] = {
    "CMD": Category(
        tag="CMD",
        label="🖥️ Commands & Utilities",
        icon="🖥️",
        keywords=[
            "command", "utility", "flag", "option", "syntax",
            "usage", "the `", "arguments", "switches",
        ],
        priority=1,
    ),
    "SCRIPT": Category(
        tag="SCRIPT",
        label="📜 Shell Scripting",
        icon="📜",
        keywords=[
            "script", "bash", "shell script", "shebang", "#!/",
            "loop", "for loop", "while loop", "if statement",
            "case statement", "function", "shell function",
            "control flow", "variable", "shell variable",
        ],
        priority=2,
    ),
    "PROG": Category(
        tag="PROG",
        label="🐍 Programming",
        icon="🐍",
        keywords=[
            "python", "program", "programming", "code", "class",
            "import", "module", "library", "api", "compile",
            "interpreter", "debug", "algorithm",
        ],
        priority=3,
    ),
    "FS": Category(
        tag="FS",
        label="📁 File System",
        icon="📁",
        keywords=[
            "file", "directory", "folder", "path", "permission",
            "owner", "group", "link", "symlink", "mount", "inode",
            "filesystem", "file system", "rwx", "chmod", "chown",
        ],
        priority=4,
    ),
    "NET": Category(
        tag="NET",
        label="🌐 Networking",
        icon="🌐",
        keywords=[
            "network", "ip address", "port", "socket", "http",
            "ssh", "dns", "tcp", "udp", "firewall", "protocol",
            "remote", "download", "upload", "url", "ftp",
        ],
        priority=5,
    ),
    "SYS": Category(
        tag="SYS",
        label="⚙️ System Admin",
        icon="⚙️",
        keywords=[
            "process", "service", "daemon", "systemd", "cron",
            "user account", "package", "install", "boot", "kernel",
            "system", "admin", "root", "sudo", "service",
            "scheduling", "startup", "environment",
        ],
        priority=6,
    ),
    "IO": Category(
        tag="IO",
        label="🔄 I/O & Redirection",
        icon="🔄",
        keywords=[
            "redirect", "pipe", "stdin", "stdout", "stderr",
            "input", "output", "stream", "tee", "> ", ">>",
            "piping", "redirection", "standard input",
            "standard output", "standard error",
        ],
        priority=7,
    ),
    "TEXT": Category(
        tag="TEXT",
        label="📝 Text Processing",
        icon="📝",
        keywords=[
            "regex", "regular expression", "pattern matching",
            "sed", "awk", "grep", "text processing", "filter",
            "sort", "string", "search", "replace", "transform",
        ],
        priority=8,
    ),
    "EXAMPLE": Category(
        tag="EXAMPLE",
        label="📋 Examples",
        icon="📋",
        keywords=[
            "example", "demonstration", "practice", "exercise",
            "walkthrough", "step-by-step", "tutorial", "hands-on",
            "try this", "let's",
        ],
        priority=9,
    ),
    "TIP": Category(
        tag="TIP",
        label="💎 Tips & Notes",
        icon="💎",
        keywords=[
            "tip", "trick", "best practice", "warning", "caution",
            "note", "remember", "important", "gotcha", "common mistake",
            "pro tip", "avoid",
        ],
        priority=10,
    ),
    "CONCEPT": Category(
        tag="CONCEPT",
        label="💡 Concepts & Theory",
        icon="💡",
        keywords=[
            "concept", "theory", "overview", "introduction",
            "understanding", "what is", "definition", "principle",
            "architecture", "design", "philosophy", "history",
            "how it works",
        ],
        priority=11,
    ),
    "OVERVIEW": Category(
        tag="OVERVIEW",
        label="📖 Overview",
        icon="📖",
        keywords=[
            "chapter overview", "summary", "recap", "review",
            "key takeaway", "conclusion", "introduction",
        ],
        priority=12,
    ),
}

# Regex to detect tagged headings: ## [TAG] Title Text
TAG_PATTERN = re.compile(r'^##\s+\[([A-Z]+)\]\s+(.+)$', re.MULTILINE)

# All valid tag names for prompt generation
ALL_TAGS = list(CATEGORIES.keys())


# ── Parsed Section ───────────────────────────────────────────────────────────

@dataclass
class CategorizedSection:
    """A section of the summary with its assigned category."""
    category_tag: str       # e.g. "CMD", "CONCEPT"
    title: str              # Section heading (without tag)
    content: str            # Full section content including heading
    raw_heading: str = ""   # Original heading line


# ── Parsing Functions ────────────────────────────────────────────────────────

def get_category_tags_prompt() -> str:
    """
    Generate the instruction text for the AI summarizer to include
    category tags in headings.
    """
    tag_list = "\n".join(
        f"  - `[{cat.tag}]` — {cat.label.split(' ', 1)[1]}"
        for cat in CATEGORIES.values()
    )
    return (
        "IMPORTANT: Prefix EVERY `## ` heading with a category tag in square brackets. "
        "Choose the most appropriate tag from this list:\n"
        f"{tag_list}\n\n"
        "Example headings:\n"
        "  ## [CMD] The `ls` Command — Listing Files\n"
        "  ## [CONCEPT] Understanding File Permissions\n"
        "  ## [SCRIPT] Writing a Backup Script\n"
        "  ## [IO] Pipes and Redirection\n"
        "  ## [OVERVIEW] Chapter Summary\n\n"
        "Every section MUST have exactly one tag. Pick the best fit."
    )


def parse_categorized_summary(summary_text: str) -> list[CategorizedSection]:
    """
    Parse a summary into categorized sections.

    Works with both tagged summaries (from AI with [TAG] prefixes)
    and untagged summaries (uses keyword-based fallback).
    """
    # Split by ## headings
    sections_raw = re.split(r'(?=^## )', summary_text, flags=re.MULTILINE)
    sections_raw = [s for s in sections_raw if s.strip()]

    # Check if the first chunk is a preamble (no ## heading)
    result = []
    for section_text in sections_raw:
        lines = section_text.strip().split('\n')
        first_line = lines[0].strip()

        if not first_line.startswith('## '):
            # Preamble / intro text without a heading
            result.append(CategorizedSection(
                category_tag="OVERVIEW",
                title="Introduction",
                content=section_text.strip(),
                raw_heading="",
            ))
            continue

        # Try to extract tag from heading: ## [TAG] Title
        tag_match = TAG_PATTERN.match(first_line)
        if tag_match:
            tag = tag_match.group(1).upper()
            title = tag_match.group(2).strip()
            # Validate tag
            if tag not in CATEGORIES:
                tag = _categorize_by_keywords(title, section_text)
        else:
            # No tag found — use keyword-based categorization
            title = first_line[3:].strip()  # Remove "## "
            tag = _categorize_by_keywords(title, section_text)

        result.append(CategorizedSection(
            category_tag=tag,
            title=title,
            content=section_text.strip(),
            raw_heading=first_line,
        ))

    return result


def _categorize_by_keywords(heading: str, content: str) -> str:
    """
    Fallback categorization using keyword matching on heading + content.
    Returns the best-matching category tag.
    """
    # Combine heading (weighted more) and first ~500 chars of content
    search_text = (heading.lower() + " " + heading.lower() + " " +
                   content[:500].lower())

    best_tag = "CONCEPT"
    best_score = 0

    for tag, cat in CATEGORIES.items():
        score = 0
        for kw in cat.keywords:
            if kw.lower() in search_text:
                score += 1
                # Bonus for keywords appearing in the heading itself
                if kw.lower() in heading.lower():
                    score += 2
        # Adjust by priority (lower priority value = small bonus)
        score += (15 - cat.priority) * 0.1

        if score > best_score:
            best_score = score
            best_tag = tag

    return best_tag


def get_active_categories(sections: list[CategorizedSection]) -> list[str]:
    """Get unique category tags present in the parsed sections, in order."""
    seen = set()
    result = []
    for s in sections:
        if s.category_tag not in seen:
            seen.add(s.category_tag)
            result.append(s.category_tag)
    return result


def filter_sections(
    sections: list[CategorizedSection],
    selected_tags: list[str],
) -> list[CategorizedSection]:
    """Filter sections to only include those matching selected category tags."""
    if not selected_tags:
        return sections
    return [s for s in sections if s.category_tag in selected_tags]


def rebuild_summary_text(sections: list[CategorizedSection]) -> str:
    """Reconstruct summary markdown from categorized sections."""
    parts = [s.content for s in sections]
    return "\n\n".join(parts)


def get_category_display(tag: str) -> str:
    """Get the display label for a category tag."""
    cat = CATEGORIES.get(tag)
    return cat.label if cat else f"❓ {tag}"


def get_category_icon(tag: str) -> str:
    """Get the emoji icon for a category tag."""
    cat = CATEGORIES.get(tag)
    return cat.icon if cat else "❓"
