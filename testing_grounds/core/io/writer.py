"""
File writing utilities with optional atomic writes.
"""

from pathlib import Path


def write_text(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """
    Write content to a file. Overwrites if the file exists.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)


def append_line(path: str | Path, line: str, encoding: str = "utf-8") -> None:
    """
    Append a single line to a file (adds newline if missing).
    """
    path = Path(path)
    if not line.endswith("\n"):
        line = line + "\n"
    with path.open("a", encoding=encoding) as f:
        f.write(line)
