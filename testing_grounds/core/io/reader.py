"""
File reading utilities with encoding and error handling.
"""

from pathlib import Path


def read_text(path: str | Path, encoding: str = "utf-8") -> str:
    """
    Read entire file as text. Uses the given encoding; replaces
    invalid bytes if errors occur (default: replace).
    """
    path = Path(path)
    return path.read_text(encoding=encoding, errors="replace")


def read_lines(path: str | Path, encoding: str = "utf-8", strip: bool = True) -> list[str]:
    """
    Read file as a list of lines. Optionally strip whitespace from each line.
    """
    text = read_text(path, encoding=encoding)
    lines = text.splitlines()
    if strip:
        lines = [line.strip() for line in lines]
    return lines
