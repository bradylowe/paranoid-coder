"""CLI entry point: argument parsing and subcommand dispatch."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from paranoid import __version__
from paranoid.config import load_config, resolve_path


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """
    Configure root logger: level from --verbose/--quiet or config, console handler,
    optional file handler from config. No secrets in log format.
    """
    config = load_config(None)
    log_cfg = config.get("logging") or {}
    if verbose:
        level_name = "DEBUG"
    elif quiet:
        level_name = "ERROR"
    else:
        level_name = (log_cfg.get("level") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger("paranoid")
    root.setLevel(level)
    if not root.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(fmt)
        root.addHandler(console)
        log_file = log_cfg.get("file")
        if log_file:
            try:
                fh = logging.FileHandler(log_file, encoding="utf-8")
                fh.setFormatter(fmt)
                root.addHandler(fh)
            except OSError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="paranoid",
        description="Local-only codebase summarization and analysis via Ollama.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Global flags (before or after subcommand)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be done without making changes.",
    )
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument("-v", "--verbose", action="store_true", help="Verbose (DEBUG) output.")
    log_group.add_argument("-q", "--quiet", action="store_true", help="Quiet (errors only).")

    # Same flags on subparsers so "paranoid summarize . --dry-run" works
    global_flags = argparse.ArgumentParser(add_help=False)
    global_flags.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    log_grp = global_flags.add_mutually_exclusive_group()
    log_grp.add_argument("-v", "--verbose", action="store_true", help=argparse.SUPPRESS)
    log_grp.add_argument("-q", "--quiet", action="store_true", help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    # init (only way to create .paranoid-coder)
    p_init = subparsers.add_parser("init", help="Initialize a paranoid project (creates .paranoid-coder and DB).")
    p_init.add_argument("path", type=Path, nargs="?", default=Path("."), help="Directory to initialize (default: .).")
    p_init.set_defaults(run="init")

    # summarize
    p_summarize = subparsers.add_parser(
        "summarize",
        help="Summarize files and directories.",
        parents=[global_flags],
    )
    p_summarize.add_argument("paths", nargs="+", type=Path, help="Paths to summarize (files or directories).")
    p_summarize.add_argument("--model", "-m", type=str, help="Ollama model name (e.g. qwen3:8b).")
    p_summarize.set_defaults(run="summarize")

    # view
    p_view = subparsers.add_parser("view", help="Launch the summaries viewer.", parents=[global_flags])
    p_view.add_argument("path", type=Path, nargs="?", default=Path("."), help="Project path (default: .).")
    p_view.set_defaults(run="view")

    # stats
    p_stats = subparsers.add_parser("stats", help="Show summary statistics.", parents=[global_flags])
    p_stats.add_argument("path", type=Path, nargs="?", default=Path("."), help="Project path (default: .).")
    p_stats.set_defaults(run="stats")

    # config
    p_config = subparsers.add_parser("config", help="Show or edit configuration.", parents=[global_flags])
    p_config.add_argument("--show", action="store_true", help="Display current settings.")
    p_config.add_argument("--set", dest="set_key", metavar="KEY=VALUE", help="Set a configuration value.")
    p_config.set_defaults(run="config")

    # clean
    p_clean = subparsers.add_parser("clean", help="Clean stale or ignored summaries.", parents=[global_flags])
    p_clean.add_argument("path", type=Path, nargs="?", default=Path("."), help="Project path (default: .).")
    p_clean.add_argument("--pruned", action="store_true", help="Remove summaries for ignored paths.")
    p_clean.add_argument("--stale", action="store_true", help="Remove summaries older than --days.")
    p_clean.add_argument("--days", type=int, default=30, help="Days threshold for --stale (default: 30).")
    p_clean.add_argument("--model", type=str, help="Remove summaries for this model only.")
    p_clean.set_defaults(run="clean")

    # export
    p_export = subparsers.add_parser("export", help="Export summaries to JSON or CSV.", parents=[global_flags])
    p_export.add_argument("path", type=Path, nargs="?", default=Path("."), help="Project path (default: .).")
    p_export.add_argument("--format", "-f", choices=("json", "csv"), default="json", help="Output format.")
    p_export.set_defaults(run="export")

    args = parser.parse_args()
    setup_logging(
        verbose=getattr(args, "verbose", False),
        quiet=getattr(args, "quiet", False),
    )
    run = getattr(args, "run", None)
    if not run:
        parser.print_help()
        sys.exit(0)

    # Resolve paths to absolute for commands that take paths
    if hasattr(args, "path"):
        args.path = resolve_path(args.path)
    if hasattr(args, "paths"):
        args.paths = [resolve_path(p) for p in args.paths]

    # Dispatch to command (stubs will be replaced by real implementations)
    if run == "init":
        from paranoid.commands.init_cmd import run as cmd_run
    elif run == "summarize":
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
