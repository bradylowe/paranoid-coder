"""
Command-line interface for the application.
"""

import argparse
from app.main import run


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test application for paranoid-coder")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file (default: config.yaml in cwd)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point: parse args and run the application."""
    args = parse_args()
    if args.dry_run:
        print("Dry run: no changes will be made.")
    return run(args.config)


if __name__ == "__main__":
    exit(main())
