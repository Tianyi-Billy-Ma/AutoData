"""Browser-Use configuration dataclass.

This module provides the BrowserUseConfig dataclass that aggregates
browser and agent configuration for browser-use integration.
"""

from dataclasses import dataclass, field

from autodata.configs.args.browser import BrowserUseAgentConfig, BrowserUseBrowserConfig


@dataclass
class BrowserUseConfig:
    """Aggregated Browser-Use configuration with dedicated sections.

    This dataclass combines browser and agent configurations for
    convenient management of browser-use settings.
    """

    browser: BrowserUseBrowserConfig = field(
        default_factory=BrowserUseBrowserConfig,
        metadata={"help": "Settings forwarded to the browser-use Browser instance."},
    )
    agent: BrowserUseAgentConfig = field(
        default_factory=BrowserUseAgentConfig,
        metadata={"help": "Settings forwarded to the browser-use Agent instance."},
    )
