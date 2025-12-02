"""Dataclass-based configuration argument schemas for AutoData.

This package contains HfArgumentParser-compatible dataclass definitions
for all AutoData configuration sections.
"""

from .autodata_config import AutoDataConfig
from .task_config import TaskConfig
from .llm_config import LLMConfig
from .log_config import LogConfig
from .storage_config import StorageConfig
from .tool_config import ToolConfig
from .ohcache_config import OHCacheConfig, HyperedgeConfig
from .checkpoint_config import CheckpointConfig
from .plugin_config import PluginConfig
from .browser.browser_config import BrowserUseBrowserConfig
from .browser.agent_config import BrowserUseAgentConfig

__all__ = [
    "AutoDataConfig",
    "TaskConfig",
    "StorageConfig",
    "LogConfig",
    "LLMConfig",
    "ToolConfig",
    "OHCacheConfig",
    "HyperedgeConfig",
    "CheckpointConfig",
    "PluginConfig",
    "BrowserUseBrowserConfig",
    "BrowserUseAgentConfig",
]
