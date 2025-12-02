"""Configuration validation helpers.

This module provides validate_config and section-level validators that
check configuration consistency and requirements.
"""

import logging
from pathlib import Path

from autodata.configs.args import (
    BrowserUseAgentConfig,
    BrowserUseBrowserConfig,
    CheckpointConfig,
    LLMConfig,
    LogConfig,
    OHCacheConfig,
    HyperedgeConfig,
    PluginConfig,
    StorageConfig,
    ToolConfig,
)

logger = logging.getLogger("AutoData.configs")


def validate_config(config: "AutoDataConfig") -> None:
    """Validate the entire configuration.

    Args:
        config: Configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    from autodata.configs.args import AutoDataConfig

    validate_storage_config(config.storage_config)
    validate_log_config(config.log_config)
    validate_llm_config(config.llm_config)
    validate_tool_config(config.tool_config)
    validate_ohcache_config(config.ohcache_config)
    validate_checkpoint_config(config.checkpoint_config)
    validate_plugin_config(config.plugin_config)
    validate_browser_use_browser_config(config.browser_use_browser_config)
    validate_browser_use_agent_config(config.browser_use_agent_config)


def validate_storage_config(storage_config: StorageConfig) -> None:
    """Validate storage configuration.

    Args:
        storage_config: Storage configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    # Validate output directory is writable
    if storage_config.type == "file":
        output_dir = Path(storage_config.output_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            test_file = output_dir / ".test"
            test_file.touch()
            test_file.unlink()
        except (OSError, PermissionError) as e:
            raise ValueError(f"Output directory is not writable: {e}") from e

    # Validate force_overwrite requires overwrite
    if storage_config.force_overwrite and not storage_config.overwrite:
        raise ValueError("force_overwrite requires overwrite=True")


def validate_log_config(log_config: LogConfig) -> None:
    """Validate log configuration.

    Args:
        log_config: Log configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
    if log_config.log_level not in valid_levels:
        raise ValueError(
            f"log_level must be one of {valid_levels}, got '{log_config.log_level}'"
        )


def validate_llm_config(llm_config: LLMConfig) -> None:
    """Validate LLM configuration.

    Args:
        llm_config: LLM configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    if not 0.0 <= llm_config.temperature <= 2.0:
        raise ValueError(
            f"temperature must be between 0.0 and 2.0, got {llm_config.temperature}"
        )


def validate_tool_config(tool_config: ToolConfig) -> None:
    """Validate tool configuration.

    Args:
        tool_config: Tool configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    # No specific validation needed currently
    pass


def validate_ohcache_config(ohcache_config: OHCacheConfig) -> None:
    """Validate OHCache configuration.

    Args:
        ohcache_config: OHCache configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    
    if not ohcache_config.enable_ohcache: 
        return

    if not all([isinstance(hyperedge, HyperedgeConfig) for hyperedge in ohcache_config.hyperedges]):
        raise ValueError("hyperedges must be a list of HyperedgeConfig")

    


def validate_checkpoint_config(checkpoint_config: CheckpointConfig) -> None:
    """Validate checkpoint configuration.

    Args:
        checkpoint_config: Checkpoint configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    if checkpoint_config.max_checkpoints is not None:
        if checkpoint_config.max_checkpoints <= 0:
            raise ValueError("max_checkpoints must be a positive integer")


def validate_plugin_config(plugin_config: PluginConfig) -> None:
    """Validate plugin configuration.

    Args:
        plugin_config: Plugin configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    # No specific validation needed currently
    pass


def validate_browser_use_browser_config(browser_config: BrowserUseBrowserConfig) -> None:
    """Validate browser-use browser configuration.

    Args:
        browser_config: Browser configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    # No specific validation needed currently
    pass


def validate_browser_use_agent_config(agent_config: BrowserUseAgentConfig) -> None:
    """Validate browser-use agent configuration.

    Args:
        agent_config: Agent configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    if agent_config.max_steps <= 0:
        raise ValueError("max_steps must be positive")

    if agent_config.max_actions_per_step <= 0:
        raise ValueError("max_actions_per_step must be positive")
