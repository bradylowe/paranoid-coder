"""
Application entry point and CLI.
"""

from app.main import run
from app.cli import parse_args

__all__ = ["run", "parse_args"]
