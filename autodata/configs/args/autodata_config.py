"""Main AutoData configuration dataclass."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autodata.configs.args.browser.agent_config import BrowserUseAgentConfig
from autodata.configs.args.browser.browser_config import BrowserUseBrowserConfig
from autodata.configs.args.checkpoint_config import CheckpointConfig
from autodata.configs.args.llm_config import LLMConfig
from autodata.configs.args.log_config import LogConfig
from autodata.configs.args.ohcache_config import OHCacheConfig
from autodata.configs.args.plugin_config import PluginConfig
from autodata.configs.args.storage_config import StorageConfig
from autodata.configs.args.task_config import TaskConfig
from autodata.configs.args.tool_config import ToolConfig

_SECTION_NAMES: tuple[str, ...] = (
    "task_config",
    "storage_config",
    "log_config",
    "llm_config",
    "tool_config",
    "ohcache_config",
    "checkpoint_config",
    "plugin_config",
    "browser_use_browser_config",
    "browser_use_agent_config",
)


@dataclass
class AutoDataConfig:
    """Main AutoData configuration aggregating all sections."""

    task_config: TaskConfig = field(default_factory=TaskConfig)
    storage_config: StorageConfig = field(default_factory=StorageConfig)
    log_config: LogConfig = field(default_factory=LogConfig)
    llm_config: LLMConfig = field(default_factory=LLMConfig)
    tool_config: ToolConfig = field(default_factory=ToolConfig)
    ohcache_config: OHCacheConfig = field(default_factory=OHCacheConfig)
    checkpoint_config: CheckpointConfig = field(default_factory=CheckpointConfig)
    plugin_config: PluginConfig = field(default_factory=PluginConfig)
    browser_use_browser_config: BrowserUseBrowserConfig = field(default_factory=BrowserUseBrowserConfig)
    browser_use_agent_config: BrowserUseAgentConfig = field(default_factory=BrowserUseAgentConfig)

    def __getattr__(self, item: str) -> Any:
        for section_name in _SECTION_NAMES:
            section = object.__getattribute__(self, section_name)
            if hasattr(section, item):
                return getattr(section, item)
        raise AttributeError(f"{item} is not a valid AutoDataConfig attribute")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {
            "task_config",
            "storage_config",
            "log_config",
            "llm_config",
            "tool_config",
            "ohcache_config",
            "checkpoint_config",
            "plugin_config",
            "browser_use_browser_config",
            "browser_use_agent_config",
        }:
            object.__setattr__(self, name, value)
            return
        for section_name in _SECTION_NAMES:
            section = object.__getattribute__(self, section_name)
            if hasattr(section, name):
                setattr(section, name, value)
                return
        object.__setattr__(self, name, value)

    @property
    def task(self) -> str:
        return self.task_config.task

    @task.setter
    def task(self, value: str) -> None:
        self.task_config.task = value

    @property
    def run_name(self) -> str | None:
        return self.task_config.run_name

    @run_name.setter
    def run_name(self, value: str | None) -> None:
        self.task_config.run_name = value

    @property
    def disable_human(self) -> bool:
        return self.task_config.disable_human

    @disable_human.setter
    def disable_human(self, value: bool) -> None:
        self.task_config.disable_human = value

    @property
    def task_timeout(self) -> int:
        return self.task_config.task_timeout

    @task_timeout.setter
    def task_timeout(self, value: int) -> None:
        self.task_config.task_timeout = value

    @property
    def execution_strategy(self) -> str:
        return self.task_config.execution_strategy

    @execution_strategy.setter
    def execution_strategy(self, value: str) -> None:
        self.task_config.execution_strategy = value

    @property
    def enabled_plugins(self) -> list[str]:
        return self.plugin_config.enabled_plugins

    @enabled_plugins.setter
    def enabled_plugins(self, value: list[str]) -> None:
        self.plugin_config.enabled_plugins = value

    @property
    def run_dir(self) -> Path:
        """Get the current run-specific output directory."""
        if not self.run_name:
            raise ValueError("run_name must be set before accessing run_dir")
        base = Path(self.storage_config.output_dir)
        if not base.is_absolute():
            base = (Path.cwd() / base).resolve()
        return base / self.run_name

    @property
    def work_dir(self) -> Path:
        """Get the current work directory for Python REPL Tool."""
        return self.run_dir / "work"

    @property
    def checkpoint_dir(self) -> Path:
        """Get the checkpoint directory for pipeline state snapshots."""
        override = self.checkpoint_config.checkpoint_dir
        if override is not None:
            path = Path(str(override))
            if path.is_absolute():
                return path
            return Path.cwd() / path
        return self.run_dir / "checkpoint"

    @property
    def cache_dir(self) -> Path:
        """Get the cache directory for OHCache."""
        return self.run_dir / "cache"

    @property
    def video_dir(self) -> Path:
        """Get the video directory for BrowserAgent."""
        return self.run_dir / "videos"

    @property
    def log_dir(self) -> Path:
        """Get the log directory for the run."""
        return self.run_dir / "logs"

    @property
    def logging_config(self) -> dict[str, Any]:
        """Return the logging configuration as a plain dictionary."""
        return {
            "level": self.log_config.log_level,
            "file": str(self.log_config.log_file) if self.log_config.log_file else None,
        }

    def validate_config(self) -> None:
        """Validate the configuration (compatibility method)."""
        from autodata.configs.validate import validate_storage_config

        validate_storage_config(self.storage_config)
