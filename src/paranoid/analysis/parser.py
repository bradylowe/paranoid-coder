"""Generic parser interface that dispatches to language-specific parsers."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .entities import CodeEntity
from .javascript_parser import JavaScriptParser
from .python_parser import PythonParser
from .relationships import Relationship
from .typescript_parser import TypeScriptParser


# Map detect_language keys to parser keys (javascript-react -> javascript, etc.)
_LANGUAGE_TO_PARSER: dict[str, str] = {
    "python": "python",
    "javascript": "javascript",
    "javascript-react": "javascript",
    "typescript": "typescript",
    "typescript-react": "typescript",
}


class Parser:
    """Multi-language parser that dispatches to language-specific parsers."""

    def __init__(self) -> None:
        self._parsers: dict[str, PythonParser | JavaScriptParser | TypeScriptParser] = {
            "python": PythonParser(),
            "javascript": JavaScriptParser(),
            "typescript": TypeScriptParser(),
        }

    def parse_file(
        self, file_path: str, language: str
    ) -> Tuple[List[CodeEntity], List[Relationship]]:
        """
        Parse a file and extract entities and relationships.

        Args:
            file_path: Absolute path to file (normalized posix string).
            language: Language key ('python', 'javascript', etc.).

        Returns:
            Tuple of (entities, relationships).

        Raises:
            ValueError: If language is not supported.
        """
        parser_key = _LANGUAGE_TO_PARSER.get(language, language)
        parser = self._parsers.get(parser_key)
        if not parser:
            raise ValueError(f"No parser available for language: {language!r}")
        return parser.parse_file(file_path)

    def supports_language(self, language: str) -> bool:
        """Return True if the given language is supported."""
        parser_key = _LANGUAGE_TO_PARSER.get(language, language)
        return parser_key in self._parsers

    def supported_languages(self) -> List[str]:
        """Return list of supported language keys (from detect_language)."""
        return list(_LANGUAGE_TO_PARSER.keys())
