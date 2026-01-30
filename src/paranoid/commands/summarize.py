"""Core summarization logic (tree walk, Ollama, progress)."""

from argparse import Namespace


def run(args: Namespace) -> None:
    """Run the summarize command. Stub: not yet implemented."""
    print("summarize: not yet implemented")
    print(f"  paths: {args.paths}")
    print(f"  model: {getattr(args, 'model', None)}")
