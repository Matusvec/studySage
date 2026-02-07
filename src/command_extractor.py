"""
Command Extractor Module
Extracts Linux commands, flags, syntax from chapter text using
regex patterns and font analysis (monospace detection).
"""

import re
from dataclasses import dataclass, field


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
        """
        commands = []
        seen = set()

        for block in blocks:
            text = block["text"]
            is_mono = block.get("is_mono", False)

            if is_mono:
                # Monospace text — likely a command or code
                cmd = self._parse_command_string(text)
                if cmd and cmd.command not in seen:
                    cmd.page = block.get("page", -1)
                    seen.add(cmd.command)
                    commands.append(cmd)
            else:
                # Check for inline command references
                backtick_cmds = re.findall(r'`([^`]+)`', text)
                for cmd_text in backtick_cmds:
                    cmd = self._parse_command_string(cmd_text)
                    if cmd and cmd.command not in seen:
                        cmd.page = block.get("page", -1)
                        seen.add(cmd.command)
                        commands.append(cmd)

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
