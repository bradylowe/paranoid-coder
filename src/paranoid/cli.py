"""CLI entry point: argument parsing and subcommand dispatch."""

import argparse
import sys
from pathlib import Path

from paranoid import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="paranoid",
        description="Local-only codebase summarization and analysis via Ollama.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be done without making changes.",
    )
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument("-v", "--verbose", action="store_true", help="Verbose (DEBUG) output.")
    log_group.add_argument("-q", "--quiet", action="store_true", help="Quiet (errors only).")

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    # summarize
    p_summarize = subparsers.add_parser("summarize", help="Summarize files and directories.")
    p_summarize.add_argument("paths", nargs="+", type=Path, help="Paths to summarize (files or directories).")
    p_summarize.add_argument("--model", "-m", type=str, help="Ollama model name (e.g. qwen3:8b).")
    p_summarize.set_defaults(run="summarize")

    # view
    p_view = subparsers.add_parser("view", help="Launch the summaries viewer.")
    p_view.add_argument("path", type=Path, nargs="?", default=Path("."), help="Project path (default: .).")
    p_view.set_defaults(run="view")

    # stats
    p_stats = subparsers.add_parser("stats", help="Show summary statistics.")
    p_stats.add_argument("path", type=Path, nargs="?", default=Path("."), help="Project path (default: .).")
    p_stats.set_defaults(run="stats")

    # config
    p_config = subparsers.add_parser("config", help="Show or edit configuration.")
    p_config.add_argument("--show", action="store_true", help="Display current settings.")
    p_config.add_argument("--set", dest="set_key", metavar="KEY=VALUE", help="Set a configuration value.")
    p_config.set_defaults(run="config")

    # clean
    p_clean = subparsers.add_parser("clean", help="Clean stale or ignored summaries.")
    p_clean.add_argument("path", type=Path, nargs="?", default=Path("."), help="Project path (default: .).")
    p_clean.add_argument("--pruned", action="store_true", help="Remove summaries for ignored paths.")
    p_clean.add_argument("--stale", action="store_true", help="Remove summaries older than --days.")
    p_clean.add_argument("--days", type=int, default=30, help="Days threshold for --stale (default: 30).")
    p_clean.add_argument("--model", type=str, help="Remove summaries for this model only.")
    p_clean.set_defaults(run="clean")

    # export
    p_export = subparsers.add_parser("export", help="Export summaries to JSON or CSV.")
    p_export.add_argument("path", type=Path, nargs="?", default=Path("."), help="Project path (default: .).")
    p_export.add_argument("--format", "-f", choices=("json", "csv"), default="json", help="Output format.")
    p_export.set_defaults(run="export")

    args = parser.parse_args()
    run = getattr(args, "run", None)
    if not run:
        parser.print_help()
        sys.exit(0)

    # Dispatch to command (stubs will be replaced by real implementations)
    if run == "summarize":
        from paranoid.commands.summarize import run as cmd_run
    elif run == "view":
        from paranoid.commands.view import run as cmd_run
    elif run == "stats":
        from paranoid.commands.stats import run as cmd_run
    elif run == "config":
        from paranoid.commands.config_cmd import run as cmd_run
    elif run == "clean":
        from paranoid.commands.clean import run as cmd_run
    elif run == "export":
        from paranoid.commands.export import run as cmd_run
    else:
        parser.print_help()
        sys.exit(0)

    cmd_run(args)
