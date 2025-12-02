"""System utilities for AutoData initialization.

This module provides backward-compatible re-exports of AutoData initialization
functions. The actual implementation has moved to autodata.configs.initialize.
"""

import logging

from autodata.configs.initialize import (
    initialize,
    load_and_merge_configuration,
    save_config,
    setup_output_directory,
)

logger = logging.getLogger("AutoData.utils")

# Re-export for backward compatibility
__all__ = [
    "initialize",
    "load_and_merge_configuration",
    "setup_output_directory",
    "save_config",
]
