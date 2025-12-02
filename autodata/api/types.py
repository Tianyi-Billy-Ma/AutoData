"""Legacy compatibility exports for API metadata."""

from autodata.configs.api_registry import (
    API_INFO,
    APIMetadata,
    get_api_info,
    iter_api_metadata,
)

__all__ = ["API_INFO", "APIMetadata", "get_api_info", "iter_api_metadata"]
