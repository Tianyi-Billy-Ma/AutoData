"""Parser factory for HfArgumentParser-based config loading."""

import logging
from typing import Any

from transformers import HfArgumentParser

from autodata.configs.args import (
    BrowserUseAgentConfig,
    BrowserUseBrowserConfig,
    CheckpointConfig,
    LLMConfig,
    LogConfig,
    OHCacheConfig,
    PluginConfig,
    StorageConfig,
    TaskConfig,
    ToolConfig,
)

logger = logging.getLogger("AutoData.configs")

CONFIG_SECTIONS: tuple[tuple[str, type], ...] = (
    ("task_config", TaskConfig),
    ("storage_config", StorageConfig),
    ("log_config", LogConfig),
    ("llm_config", LLMConfig),
    ("tool_config", ToolConfig),
    ("ohcache_config", OHCacheConfig),
    ("checkpoint_config", CheckpointConfig),
    ("plugin_config", PluginConfig),
    ("browser_use_browser_config", BrowserUseBrowserConfig),
    ("browser_use_agent_config", BrowserUseAgentConfig),
)


def get_section_names() -> tuple[str, ...]:
    """Return the ordered config section names."""

    return tuple(name for name, _ in CONFIG_SECTIONS)


def get_dataclass_types() -> tuple[type, ...]:
    """Return the ordered dataclass types."""

    return tuple(dtype for _, dtype in CONFIG_SECTIONS)


def create_argument_parser(**parser_kwargs: Any) -> HfArgumentParser:
    """Create an HfArgumentParser instance with all config dataclasses."""

    return HfArgumentParser(get_dataclass_types(), **parser_kwargs)


def parse_args_into_dataclasses(
    args: list[str] | None = None,
    *,
    parser_kwargs: dict[str, Any] | None = None,
) -> tuple[
    TaskConfig,
    StorageConfig,
    LogConfig,
    LLMConfig,
    ToolConfig,
    OHCacheConfig,
    CheckpointConfig,
    PluginConfig,
    BrowserUseBrowserConfig,
    BrowserUseAgentConfig,
]:
    """Parse command-line arguments into dataclass instances."""

    parser = create_argument_parser(**(parser_kwargs or {}))
    return parser.parse_args_into_dataclasses(args=args)


def parse_dict_into_dataclasses(
    config_dict: dict[str, Any],
    *,
    parser_kwargs: dict[str, Any] | None = None,
) -> tuple[
    TaskConfig,
    StorageConfig,
    LogConfig,
    LLMConfig,
    ToolConfig,
    OHCacheConfig,
    CheckpointConfig,
    PluginConfig,
    BrowserUseBrowserConfig,
    BrowserUseAgentConfig,
]:
    """Parse a configuration dictionary into dataclass instances."""

    parser = create_argument_parser(**(parser_kwargs or {}))
    return parser.parse_dict(config_dict)


__all__ = [
    "create_argument_parser",
    "get_dataclass_types",
    "get_section_names",
    "parse_args_into_dataclasses",
    "parse_dict_into_dataclasses",
]
