"""Validate that dataclass defaults match default.yaml configuration.

This script helps ensure consistency between:
1. Dataclass field defaults in autodata/configs/args/
2. Configuration values in configs/default.yaml

Usage:
    python -m autodata.scripts.validate_config_defaults
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Import all config dataclasses
from autodata.configs.args.autodata_config import AutoDataConfig
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

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_YAML = REPO_ROOT / "configs" / "default.yaml"


def load_yaml_config() -> dict:
    """Load the default.yaml configuration."""
    with open(DEFAULT_YAML) as f:
        return yaml.safe_load(f)


def validate_config_section(
    dataclass_instance: object,
    yaml_section: dict,
    section_name: str,
) -> list[str]:
    """Validate that dataclass defaults match YAML values.

    Args:
        dataclass_instance: Instance of the config dataclass with default values
        yaml_section: Dictionary from the YAML file for this section
        section_name: Name of the config section for error reporting

    Returns:
        List of mismatch descriptions (empty if all match)
    """
    mismatches = []

    for field_name, yaml_value in yaml_section.items():
        if not hasattr(dataclass_instance, field_name):
            continue  # Skip fields not in dataclass

        dataclass_value = getattr(dataclass_instance, field_name)

        # Compare values (handle None and type differences)
        if dataclass_value != yaml_value:
            mismatches.append(
                f"  {section_name}.{field_name}: "
                f"dataclass={dataclass_value!r}, yaml={yaml_value!r}"
            )

    return mismatches


def main() -> int:
    """Main validation entry point."""
    print(f"Validating config defaults against {DEFAULT_YAML}")
    print("=" * 80)

    yaml_data = load_yaml_config()
    all_mismatches: list[str] = []

    # Define config sections to validate
    configs_to_check = [
        (TaskConfig(), yaml_data.get("task_config", {}), "TaskConfig"),
        (StorageConfig(), yaml_data.get("storage_config", {}), "StorageConfig"),
        (LogConfig(), yaml_data.get("log_config", {}), "LogConfig"),
        (LLMConfig(), yaml_data.get("llm_config", {}), "LLMConfig"),
        (ToolConfig(), yaml_data.get("tool_config", {}), "ToolConfig"),
        (OHCacheConfig(), yaml_data.get("ohcache_config", {}), "OHCacheConfig"),
        (CheckpointConfig(), yaml_data.get("checkpoint_config", {}), "CheckpointConfig"),
        (PluginConfig(), yaml_data.get("plugin_config", {}), "PluginConfig"),
        (BrowserUseBrowserConfig(), yaml_data.get("browser_use_browser_config", {}), "BrowserUseBrowserConfig"),
        (BrowserUseAgentConfig(), yaml_data.get("browser_use_agent_config", {}), "BrowserUseAgentConfig"),
    ]

    for dataclass_instance, yaml_section, section_name in configs_to_check:
        mismatches = validate_config_section(dataclass_instance, yaml_section, section_name)
        all_mismatches.extend(mismatches)

    if all_mismatches:
        print("❌ Found mismatches between dataclass defaults and default.yaml:\n")
        for mismatch in all_mismatches:
            print(mismatch)
        print("\n" + "=" * 80)
        print("Please update the dataclass field defaults to match default.yaml values.")
        return 1
    else:
        print("✅ All dataclass defaults match default.yaml!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
