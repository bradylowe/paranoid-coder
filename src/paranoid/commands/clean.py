"""Clean stale or ignored summaries."""

from argparse import Namespace

from paranoid.config import require_project_root


def run(args: Namespace) -> None:
    """Run the clean command. Stub: not yet implemented."""
    require_project_root(args.path)
    print("clean: not yet implemented")
    print(f"  path: {args.path}")
    print(f"  --pruned: {args.pruned}")
    print(f"  --stale: {args.stale}")
