"""Configuration patching and post-processing helpers."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from easydict import EasyDict

from autodata.configs.args import (
    AutoDataConfig,
    BrowserUseAgentConfig,
    BrowserUseBrowserConfig,
    CheckpointConfig,
    LLMConfig,
    LogConfig,
    OHCacheConfig,
    HyperedgeConfig,
    PluginConfig,
    StorageConfig,
    TaskConfig,
    ToolConfig,
)

logger = logging.getLogger("AutoData.configs")


def patch_config(sections: EasyDict) -> AutoDataConfig:
    """Patch and assemble the final AutoDataConfig instance."""

    task_config = patch_task_config(sections.task_config)
    storage_config = patch_storage_config(task_config, sections.storage_config)
    log_config = patch_log_config(task_config, sections.log_config)
    llm_config = patch_llm_config(sections.llm_config)
    tool_config = sections.tool_config
    ohcache_config = sections.ohcache_config
    checkpoint_config = patch_checkpoint_config(sections.checkpoint_config)
    plugin_config = patch_plugin_config(sections.plugin_config)
    browser_use_browser_config = patch_browser_use_browser_config(sections.browser_use_browser_config)
    browser_use_agent_config = sections.browser_use_agent_config

    config = AutoDataConfig(
        task_config=task_config,
        storage_config=storage_config,
        log_config=log_config,
        llm_config=llm_config,
        tool_config=tool_config,
        ohcache_config=ohcache_config,
        checkpoint_config=checkpoint_config,
        plugin_config=plugin_config,
        browser_use_browser_config=browser_use_browser_config,
        browser_use_agent_config=browser_use_agent_config,
    )

    if config.run_name:
        run_dir = config.run_dir
        config.tool_config = patch_tool_config(
            config.tool_config,
            run_dir=run_dir,
            work_dir=config.work_dir,
            cache_dir=config.cache_dir,
        )
        config.ohcache_config = patch_ohcache_config(
            config.ohcache_config,
            cache_dir=config.cache_dir,
        )
        config.browser_use_agent_config = patch_browser_use_agent_config(
            config.browser_use_agent_config,
            run_dir=run_dir,
        )

    return config


def patch_task_config(task_config: TaskConfig) -> TaskConfig:
    """Normalize task-level flags."""

    if task_config.run_name:
        task_config.run_name = task_config.run_name.strip() or None
    return task_config


def patch_storage_config(
    task_config: TaskConfig,
    storage_config: StorageConfig,
) -> StorageConfig:
    """Patch storage configuration."""

    if storage_config.force_overwrite and not storage_config.overwrite:
        logger.warning("force_overwrite is enabled without overwrite; disabling force flag.")
        storage_config.force_overwrite = False

    return storage_config


def patch_log_config(
    task_config: TaskConfig,
    log_config: LogConfig,
) -> LogConfig:
    """Patch log configuration with CLI overrides."""

    if task_config.verbose:
        log_config.log_level = "DEBUG"
    return log_config


def patch_llm_config(llm_config: LLMConfig) -> LLMConfig:
    """Patch LLM configuration with environment variable auto-detection."""

    if llm_config.api_key is None:
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_url = os.getenv("OPENROUTER_BASE_URL")
        if openrouter_key and openrouter_url:
            llm_config.api_key = openrouter_key
            logger.info("🔑 Auto-detected OPENROUTER_API_KEY from environment")
            llm_config.base_url = openrouter_url
            logger.info("🌐 Auto-detected OPENROUTER_BASE_URL from environment")
    return llm_config


def patch_tool_config(
    tool_config: ToolConfig,
    run_dir: Path | None = None,
    work_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> ToolConfig:
    """Patch tool configuration with derived paths."""

    if run_dir and not tool_config.run_dir:
        tool_config.run_dir = str(run_dir)
    if work_dir and not tool_config.work_dir:
        tool_config.work_dir = str(work_dir)
    if cache_dir and not tool_config.tools_cache_dir:
        tool_config.tools_cache_dir = str(cache_dir)
    return tool_config


def patch_ohcache_config(
    ohcache_config: OHCacheConfig,
    cache_dir: Path | None = None,
) -> OHCacheConfig:
    """Patch OHCache configuration with derived cache directory."""

    if cache_dir and not ohcache_config.cache_dir:
        ohcache_config.cache_dir = str(cache_dir)
    if not all(isinstance(hyperedge, HyperedgeConfig) for hyperedge in ohcache_config.hyperedges):
        ohcache_config.hyperedges = [
            HyperedgeConfig(
                source=hyperedge["source"],
                target=hyperedge["target"],
                id=hyperedge.get("id"),
                message_type=hyperedge.get("message_type"),
                metadata=hyperedge.get("metadata"),
            )
            for hyperedge in ohcache_config.hyperedges
        ]
    return ohcache_config


def patch_checkpoint_config(
    checkpoint_config: CheckpointConfig,
) -> CheckpointConfig:
    """Patch checkpoint configuration."""

    if checkpoint_config.max_checkpoints is not None and checkpoint_config.max_checkpoints <= 0:
        logger.warning("max_checkpoints must be positive; ignoring invalid value")
        checkpoint_config.max_checkpoints = None
    return checkpoint_config


def patch_plugin_config(
    plugin_config: PluginConfig,
) -> PluginConfig:
    """Patch plugin configuration."""

    return plugin_config


def patch_browser_use_browser_config(
    browser_config: BrowserUseBrowserConfig,
) -> BrowserUseBrowserConfig:
    """Patch browser-use browser configuration."""

    return browser_config


def patch_browser_use_agent_config(
    agent_config: BrowserUseAgentConfig,
    run_dir: Path | None = None,
) -> BrowserUseAgentConfig:
    """Patch browser-use agent configuration with derived paths."""

    if run_dir and not agent_config.file_system_path:
        agent_config.file_system_path = str(run_dir / "browser")
    return agent_config


__all__ = [
    "patch_config",
    "patch_task_config",
    "patch_storage_config",
    "patch_log_config",
    "patch_llm_config",
    "patch_tool_config",
    "patch_ohcache_config",
    "patch_checkpoint_config",
    "patch_plugin_config",
    "patch_browser_use_browser_config",
    "patch_browser_use_agent_config",
]
