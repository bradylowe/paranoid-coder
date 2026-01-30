"""
Main application logic: loads config and runs the primary workflow.
"""

from core import load_config
from core.utils import ensure_dir
from core.io import read_text, write_text


def run(config_path: str | None = None) -> int:
    """
    Run the application. Loads configuration, sets up directories,
    and executes the main workflow. Returns exit code (0 = success).
    """
    config = load_config(config_path)
    data_dir = config.get("data_dir", "./data")
    ensure_dir(data_dir)

    if config.get("debug"):
        print(f"Debug mode. Data dir: {data_dir}")

    # Placeholder: real workflow would do something here
    return 0


if __name__ == "__main__":
    exit(run())
