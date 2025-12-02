"""AutoData: A multi-agent system for crawling data from open web sources.

AutoData provides a powerful, scalable, and ethical approach to web data collection
through intelligent multi-agent coordination, rate limiting, and data validation.
"""

__version__ = "0.1.0"
__author__ = "AutoData Contributors"
__email__ = "contributors@autodata.dev"
__license__ = "Apache-2.0"
__description__ = "A multi-agent system for crawling data from open web sources"

# Core imports for easy access
from autodata.core.config import AutoDataConfig

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__description__",
    "AutoDataConfig",
]
