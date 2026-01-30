"""
I/O subpackage: file reading and writing helpers.
"""

from core.io.reader import read_text, read_lines
from core.io.writer import write_text, append_line

__all__ = ["read_text", "read_lines", "write_text", "append_line"]
