"""Command-line interface utilities for AutoData.

This module provides minimal CLI utilities. The CLIManager has been replaced
by the new dataclass-based configuration system in autodata.configs.initialize.
"""

import logging
from pathlib import Path

logger = logging.getLogger("AutoData.utils")


def prompt_for_overwrite(run_dir: Path) -> bool:
    """Prompt the user to confirm overwriting an existing run directory."""

    logger.warning("⚠️ Run directory already exists: %s", run_dir)
    print("\n" + "=" * 80)
    print("WARNING: Output directory already exists!")
    print(f"Path: {run_dir}")
    print("This directory contains data from a previous run.")
    print("=" * 80 + "\n")
    response = input("Do you want to overwrite it? [y/N]: ").strip().lower()
    return response in {"y", "yes"}
