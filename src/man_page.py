"""
Man Page Module
Fetches and parses man page text for Linux/Unix commands.
Uses local `man` command if available, otherwise falls back to online sources.
"""

import subprocess
import re
import platform
from typing import Optional


def fetch_man_page(command: str, timeout: int = 10) -> dict:
    """
    Fetch the man page text for a command.

    Tries (in order):
    1. Local `man` command
    2. Online man page from man.cx (web fallback)

    Args:
        command: The command name (e.g., "ls", "grep")
        timeout: Timeout in seconds

    Returns:
        dict with keys:
            - success: bool
            - text: str (man page text or error message)
            - source: str ("local", "online", or "error")
    """
    # Sanitize command name — only allow safe characters
    if not re.match(r'^[a-zA-Z0-9_.\-]+$', command):
        return {
            "success": False,
            "text": f"Invalid command name: {command}",
            "source": "error",
        }

    # Try local man command
    result = _fetch_local_man(command, timeout)
    if result["success"]:
        return result

    # Fallback to online
    result = _fetch_online_man(command, timeout)
    if result["success"]:
        return result

    return {
        "success": False,
        "text": (
            f"`{command}` does not appear to be a recognized command.\n\n"
            f"No man page found locally or online. This may be:\n"
            f"- A built-in shell command (try `help {command}` in bash)\n"
            f"- A custom alias or script\n"
            f"- Not a valid command"
        ),
        "source": "error",
    }


def _fetch_local_man(command: str, timeout: int) -> dict:
    """Try fetching man page from local system."""
    system = platform.system()

    # On Windows, try WSL first, then MSYS2/Git Bash
    if system == "Windows":
        # Try WSL
        for shell in ["wsl", "bash"]:
            try:
                result = subprocess.run(
                    [shell, "-c", f"man {command} 2>/dev/null | col -bx 2>/dev/null || man {command} 2>/dev/null"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if result.returncode == 0 and len(result.stdout.strip()) > 50:
                    return {
                        "success": True,
                        "text": _clean_man_text(result.stdout),
                        "source": "local",
                    }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return {"success": False, "text": "", "source": "error"}

    # On Linux/macOS — use man directly
    try:
        result = subprocess.run(
            ["man", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={"MANPAGER": "cat", "COLUMNS": "120", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        if result.returncode == 0 and len(result.stdout.strip()) > 50:
            return {
                "success": True,
                "text": _clean_man_text(result.stdout),
                "source": "local",
            }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {"success": False, "text": "", "source": "error"}


def _fetch_online_man(command: str, timeout: int) -> dict:
    """Fetch man page text from an online source."""
    import urllib.request
    import urllib.error

    # Try man.cx (returns plain text with ?f=t)
    url = f"https://man.cx/{command}?f=t"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StudySage/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")

            # Basic HTML-to-text: strip tags
            text = re.sub(r'<[^>]+>', '', html)
            text = re.sub(r'&[a-z]+;', ' ', text)
            text = text.strip()

            # Check if we got a real man page (not a 404 page)
            if len(text) > 200 and ("SYNOPSIS" in text.upper() or "DESCRIPTION" in text.upper()):
                return {
                    "success": True,
                    "text": _clean_man_text(text),
                    "source": "online",
                }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        pass

    return {"success": False, "text": "", "source": "error"}


def _clean_man_text(text: str) -> str:
    """Clean up man page text: remove backspace overstrikes, extra whitespace."""
    # Remove backspace overstrikes (bold/underline in man pages)
    text = re.sub(r'.\x08', '', text)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove trailing whitespace per line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    # Truncate very long man pages (keep first ~15k chars — enough for AI)
    if len(text) > 15000:
        text = text[:15000] + "\n\n[... truncated for brevity ...]"
    return text.strip()
