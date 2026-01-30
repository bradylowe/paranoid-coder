"""Show or edit configuration (CLI command)."""

from argparse import Namespace


def run(args: Namespace) -> None:
    """Run the config command. Stub: not yet implemented."""
    print("config: not yet implemented")
    print(f"  --show: {getattr(args, 'show', False)}")
    print(f"  --set: {getattr(args, 'set_key', None)}")
