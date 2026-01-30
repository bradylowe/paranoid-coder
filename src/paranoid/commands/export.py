"""Export summaries to JSON or CSV."""

from argparse import Namespace

from paranoid.config import require_project_root


def run(args: Namespace) -> None:
    """Run the export command. Stub: not yet implemented."""
    require_project_root(args.path)
    print("export: not yet implemented")
    print(f"  path: {args.path}")
    print(f"  format: {args.format}")
