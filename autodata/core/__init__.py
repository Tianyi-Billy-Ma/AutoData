"""AutoData core module containing main classes and utilities.

This package-level initializer avoids importing heavy, optional dependencies
at import time (e.g., graph execution engine) to keep lightweight consumers
like config loading and unit tests decoupled.
"""

from autodata.core.config import AutoDataConfig, LLMConfig

__all__ = [
    "AutoDataConfig",
    "LLMConfig",
]
