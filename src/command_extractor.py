"""
Command Extractor Module
Extracts Linux commands, flags, syntax from chapter text using
regex patterns and font analysis (monospace detection).
Includes CommandRegistry for tracking commands across chapters.
"""

import re
from dataclasses import dataclass, field
from collections import OrderedDict


@dataclass
class ExtractedCommand:
    """Represents an extracted command with context."""
    command: str
    flags: list[str] = field(default_factory=list)
    context: str = ""  # Surrounding text for context
    page: int = -1

    def __str__(self):
        flags_str = ", ".join(self.flags) if self.flags else "none"
        return f"`{self.command}` (flags: {flags_str})"


class CommandRegistry:
    """
    Tracks which commands were first introduced in which chapter.
    Maintains a running index across all processed chapters.
    """

    def __init__(self):
        # command_name -> {"first_chapter_idx": int, "first_chapter_title": str,
        #                  "chapters": [int], "flags_by_chapter": {idx: [flags]}}
        self._registry: dict[str, dict] = {}
        # chapter_idx -> [command_names first introduced in this chapter]
        self._introduced_in: dict[int, list[str]] = {}

    def register_commands(
        self,
        commands: list[ExtractedCommand],
        chapter_idx: int,
        chapter_title: str,
    ):
        """Register extracted commands from a chapter."""
        for cmd in commands:
            name = cmd.command
            if name not in self._registry:
                # First time seeing this command
                self._registry[name] = {
                    "first_chapter_idx": chapter_idx,
                    "first_chapter_title": chapter_title,
                    "chapters": [chapter_idx],
                    "flags_by_chapter": {chapter_idx: cmd.flags},
                }
                self._introduced_in.setdefault(chapter_idx, []).append(name)
            else:
                entry = self._registry[name]
                if chapter_idx not in entry["chapters"]:
                    entry["chapters"].append(chapter_idx)
                # Merge new flags
                existing = set(entry["flags_by_chapter"].get(chapter_idx, []))
                existing.update(cmd.flags)
                entry["flags_by_chapter"][chapter_idx] = list(existing)

    def get_new_commands(self, chapter_idx: int) -> list[str]:
        """Get commands first introduced in a specific chapter."""
        return sorted(self._introduced_in.get(chapter_idx, []))

    def get_all_commands_by_chapter(self) -> dict[int, list[str]]:
        """Get all commands grouped by the chapter they were introduced in."""
        result = {}
        for ch_idx in sorted(self._introduced_in.keys()):
            result[ch_idx] = sorted(self._introduced_in[ch_idx])
        return result

    def get_command_info(self, command: str) -> dict | None:
        """Get tracking info for a specific command."""
        return self._registry.get(command)

    def get_all_commands(self) -> list[str]:
        """Get all registered command names sorted."""
        return sorted(self._registry.keys())

    def get_running_index(self, up_to_chapter: int, chapters: list[dict]) -> list[dict]:
        """
        Get a running index of commands up to and including the given chapter.
        Returns list of dicts: {chapter_idx, chapter_title, commands: [str]}
        """
        result = []
        for ch_idx in sorted(self._introduced_in.keys()):
            if ch_idx > up_to_chapter:
                break
            title = chapters[ch_idx]["title"] if ch_idx < len(chapters) else f"Chapter {ch_idx + 1}"
            cmds = sorted(self._introduced_in[ch_idx])
            if cmds:
                result.append({
                    "chapter_idx": ch_idx,
                    "chapter_title": title,
                    "commands": cmds,
                    "is_current": ch_idx == up_to_chapter,
                })
        return result

    def to_dict(self) -> dict:
        """Serialize for caching."""
        return {
            "registry": self._registry,
            "introduced_in": {str(k): v for k, v in self._introduced_in.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CommandRegistry":
        """Deserialize from cache."""
        obj = cls()
        obj._registry = data.get("registry", {})
        obj._introduced_in = {int(k): v for k, v in data.get("introduced_in", {}).items()}
        return obj


class CommandExtractor:
    """Extracts commands, flags, and code patterns from text."""

    # Common Linux/Unix commands for pattern matching
    KNOWN_COMMANDS = {
        "ls", "cd", "pwd", "mkdir", "rmdir", "rm", "cp", "mv", "touch",
        "cat", "less", "more", "head", "tail", "grep", "find", "locate",
        "which", "whereis", "man", "info", "help", "type", "alias",
        "echo", "printf", "read", "export", "set", "unset", "env",
        "chmod", "chown", "chgrp", "umask", "su", "sudo", "passwd",
        "ps", "top", "htop", "kill", "killall", "jobs", "bg", "fg",
        "nohup", "nice", "renice", "wait",
        "tar", "gzip", "gunzip", "bzip2", "zip", "unzip", "xz",
        "wget", "curl", "ssh", "scp", "rsync", "ftp", "sftp",
        "apt", "apt-get", "yum", "dnf", "pacman", "snap", "flatpak",
        "pip", "npm", "gem",
        "sed", "awk", "sort", "uniq", "wc", "cut", "paste", "tr",
        "diff", "comm", "patch", "tee", "xargs",
        "date", "cal", "uptime", "free", "df", "du", "mount", "umount",
        "ifconfig", "ip", "ping", "netstat", "ss", "traceroute", "dig",
        "nslookup", "host",
        "git", "docker", "make", "gcc", "python", "bash", "sh", "zsh",
        "vim", "vi", "nano", "emacs", "ed",
        "history", "fc", "source", "exec", "eval",
        "test", "expr", "bc", "file", "stat", "ln", "readlink",
        "tput", "clear", "reset", "stty",
        "crontab", "at", "systemctl", "service", "journalctl",
    }

    # Common flags/options patterns
    FLAG_PATTERN = re.compile(r'(?<!\w)-{1,2}[a-zA-Z][\w-]*')

    def __init__(self):
        pass

    def extract_from_text(self, text: str) -> list[ExtractedCommand]:
        """
        Extract commands from plain text using pattern matching.

        Looks for:
        - Known command names
        - Command-like patterns (word followed by flags)
        - Code block patterns (indented or backtick-wrapped)
        """
        commands = []
        seen = set()

        # Pattern 1: backtick-wrapped commands like `ls -la`
        backtick_cmds = re.findall(r'`([^`]+)`', text)
        for cmd_text in backtick_cmds:
            cmd = self._parse_command_string(cmd_text)
            if cmd and cmd.command not in seen:
                seen.add(cmd.command)
                commands.append(cmd)

        # Pattern 2: Lines that look like shell commands
        # (start with $ or # prompt, or are indented code)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Shell prompt lines
            if stripped.startswith('$ ') or stripped.startswith('# '):
                cmd_text = stripped[2:].strip()
                cmd = self._parse_command_string(cmd_text)
                if cmd and cmd.command not in seen:
                    # Get surrounding context
                    context_start = max(0, i - 1)
                    context_end = min(len(lines), i + 2)
                    cmd.context = '\n'.join(lines[context_start:context_end])
                    seen.add(cmd.command)
                    commands.append(cmd)

            # Indented lines that start with a known command
            elif (line.startswith('    ') or line.startswith('\t')) and stripped:
                first_word = stripped.split()[0] if stripped.split() else ""
                if first_word in self.KNOWN_COMMANDS:
                    cmd = self._parse_command_string(stripped)
                    if cmd and cmd.command not in seen:
                        seen.add(cmd.command)
                        commands.append(cmd)

        # Pattern 3: Known commands mentioned in prose
        for cmd_name in self.KNOWN_COMMANDS:
            # Look for the command as a standalone word
            pattern = rf'\b{re.escape(cmd_name)}\b'
            matches = list(re.finditer(pattern, text))
            if matches and cmd_name not in seen:
                # Check if followed by flags
                for match in matches:
                    after = text[match.end():match.end() + 50]
                    flags = self.FLAG_PATTERN.findall(after)
                    flags = [f for f in flags if len(f) <= 20]  # Filter noise

                    # Get context (surrounding sentence)
                    start = max(0, match.start() - 80)
                    end = min(len(text), match.end() + 80)
                    context = text[start:end].strip()

                    if cmd_name not in seen:
                        commands.append(ExtractedCommand(
                            command=cmd_name,
                            flags=flags[:10],
                            context=context
                        ))
                        seen.add(cmd_name)
                    break

        return sorted(commands, key=lambda c: c.command)

    def extract_from_blocks(self, blocks: list[dict]) -> list[ExtractedCommand]:
        """
        Extract commands using text block info (with font analysis).
        Monospace fonts strongly indicate commands/code.

        Improved: handles multi-line mono text, shell prompts,
        and tries multiple strategies to find commands in code-formatted text.
        """
        commands = []
        seen = set()

        for block in blocks:
            text = block["text"]
            is_mono = block.get("is_mono", False)
            page = block.get("page", -1)

            if is_mono:
                # Strategy 1: Try to parse each line as a command
                for line in text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue

                    # Strip shell prompts
                    for prefix in ['$ ', '# ', '% ', '> ']:
                        if line.startswith(prefix):
                            line = line[len(prefix):]
                            break

                    # Try parsing the line as a command
                    cmd = self._parse_command_string(line)
                    if cmd and cmd.command not in seen:
                        cmd.page = page
                        seen.add(cmd.command)
                        commands.append(cmd)
                        continue

                    # Strategy 2: Check if any known command appears in this line
                    words = re.findall(r'\b[a-zA-Z_][\w.-]*\b', line)
                    for word in words:
                        if word in self.KNOWN_COMMANDS and word not in seen:
                            # Extract flags from the rest of the line
                            flags = self.FLAG_PATTERN.findall(line)
                            flags = [f for f in flags if len(f) <= 20]
                            commands.append(ExtractedCommand(
                                command=word,
                                flags=flags[:10],
                                context=line[:120],
                                page=page,
                            ))
                            seen.add(word)

                # Strategy 3: Even single-word mono text might be a command
                stripped = text.strip()
                if ' ' not in stripped and stripped in self.KNOWN_COMMANDS and stripped not in seen:
                    commands.append(ExtractedCommand(command=stripped, page=page))
                    seen.add(stripped)

            else:
                # Non-mono text: check for inline backtick commands
                backtick_cmds = re.findall(r'`([^`]+)`', text)
                for cmd_text in backtick_cmds:
                    cmd = self._parse_command_string(cmd_text)
                    if cmd and cmd.command not in seen:
                        cmd.page = page
                        seen.add(cmd.command)
                        commands.append(cmd)

                    # Also check for known commands inside backticks
                    if not cmd:
                        for word in cmd_text.split():
                            clean = word.strip('`').split('/').pop()
                            if clean in self.KNOWN_COMMANDS and clean not in seen:
                                commands.append(ExtractedCommand(
                                    command=clean, page=page, context=cmd_text[:80]
                                ))
                                seen.add(clean)

        return sorted(commands, key=lambda c: c.command)

    def _parse_command_string(self, cmd_string: str) -> ExtractedCommand | None:
        """
        Parse a command string like 'ls -la --color=auto /home'
        into an ExtractedCommand.
        """
        cmd_string = cmd_string.strip()
        if not cmd_string:
            return None

        # Handle pipes — take first command
        if '|' in cmd_string:
            parts = cmd_string.split('|')
            cmd_string = parts[0].strip()

        # Handle redirects
        for redir in ['>>>', '>>', '>', '2>', '&>', '<<<', '<<', '<']:
            if redir in cmd_string:
                cmd_string = cmd_string.split(redir)[0].strip()

        # Handle command chaining
        for sep in ['&&', '||', ';']:
            if sep in cmd_string:
                cmd_string = cmd_string.split(sep)[0].strip()

        tokens = cmd_string.split()
        if not tokens:
            return None

        # Skip env vars, assignments, comments
        first = tokens[0]
        if '=' in first or first.startswith('#'):
            return None

        # Skip common non-command prefixes
        skip_prefixes = ['sudo', 'env', 'time', 'nice', 'nohup']
        while first in skip_prefixes and len(tokens) > 1:
            tokens = tokens[1:]
            first = tokens[0]

        # Validate it looks like a command
        cmd_name = first.split('/')[-1]  # Handle /usr/bin/ls → ls

        if not re.match(r'^[a-zA-Z_][\w.-]*$', cmd_name):
            return None
        if len(cmd_name) > 30:
            return None

        # Extract flags
        flags = []
        for token in tokens[1:]:
            if token.startswith('-') and len(token) <= 25:
                flags.append(token)

        return ExtractedCommand(
            command=cmd_name,
            flags=flags
        )

    def format_commands_table(self, commands: list[ExtractedCommand]) -> str:
        """Format extracted commands as a Markdown table."""
        if not commands:
            return "_No commands detected in this section._"

        lines = ["| Command | Flags | Context |", "|---------|-------|---------|"]
        for cmd in commands:
            flags = ", ".join(cmd.flags) if cmd.flags else "—"
            context = cmd.context[:80].replace("|", "\\|").replace("\n", " ") if cmd.context else "—"
            lines.append(f"| `{cmd.command}` | `{flags}` | {context} |")

        return "\n".join(lines)
