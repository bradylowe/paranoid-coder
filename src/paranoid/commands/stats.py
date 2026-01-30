"""Show summary statistics."""

from argparse import Namespace

from paranoid.config import require_project_root


def run(args: Namespace) -> None:
    """Run the stats command. Stub: not yet implemented."""
    require_project_root(args.path)
    print("stats: not yet implemented")
    print(f"  path: {args.path}")
