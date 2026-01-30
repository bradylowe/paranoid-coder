"""Launch the summaries viewer."""

from argparse import Namespace

from paranoid.config import require_project_root


def run(args: Namespace) -> None:
    """Run the view command. Stub: not yet implemented."""
    require_project_root(args.path)
    print("view: not yet implemented")
    print(f"  path: {args.path}")
