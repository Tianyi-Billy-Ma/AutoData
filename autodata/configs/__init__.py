"""Configuration utilities and schemas for the AutoData runtime."""

from __future__ import annotations

from .api_registry import API_INFO, APIMetadata, get_api_info, iter_api_metadata
from .args import (
    AutoDataConfig,
    BrowserUseAgentConfig,
    BrowserUseBrowserConfig,
    CheckpointConfig,
    HyperedgeConfig,
    LLMConfig,
    LogConfig,
    OHCacheConfig,
    PluginConfig,
    StorageConfig,
    TaskConfig,
    ToolConfig,
)
from .browser import BrowserUseConfig
from .initialize import initialize
from .mergers import split_browser_agent_arguments
from .helper import (
    SUPPORTED_CONFIG_FORMATS,
    dump_config_data,
    load_config_data,
    load_environment_variables_from_file,
    normalize_config_format,
    verify_environment_variables,
)

__all__ = [
    # Schemas (dataclass-based)
    "AutoDataConfig",
    "BrowserUseAgentConfig",
    "BrowserUseBrowserConfig",
    "BrowserUseConfig",
    "CheckpointConfig",
    "HyperedgeConfig",
    "LLMConfig",
    "LogConfig",
    "OHCacheConfig",
    "PluginConfig",
    "StorageConfig",
    "TaskConfig",
    "ToolConfig",
    # Initialization
    "initialize",
    # Sources / utilities
    "SUPPORTED_CONFIG_FORMATS",
    "dump_config_data",
    "load_config_data",
    "load_environment_variables_from_file",
    "normalize_config_format",
    "verify_environment_variables",
    # Mergers
    "split_browser_agent_arguments",
    # API registry
    "APIMetadata",
    "API_INFO",
    "get_api_info",
    "iter_api_metadata",
]
