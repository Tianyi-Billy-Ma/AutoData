"""Helpers for merging configuration payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
import warnings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from autodata.configs.schemas import AutoDataConfig


def split_browser_agent_arguments(
    data: Mapping[str, Any],
    *,
    browser_keys: set[str],
    agent_keys: set[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Partition raw browser configuration into browser-use Browser and Agent sections."""

    browser_args: dict[str, Any] = {}
    agent_args: dict[str, Any] = {}
    extras: dict[str, Any] = {}

    for key, value in data.items():
        if key == "browser" and isinstance(value, Mapping):
            nested_browser, nested_agent, nested_extras = split_browser_agent_arguments(
                value,
                browser_keys=browser_keys,
                agent_keys=agent_keys,
            )
            browser_args.update(nested_browser)
            agent_args.update(nested_agent)
            extras.update(nested_extras)
            continue

        if key == "agent" and isinstance(value, Mapping):
            nested_browser, nested_agent, nested_extras = split_browser_agent_arguments(
                value,
                browser_keys=browser_keys,
                agent_keys=agent_keys,
            )
            browser_args.update(nested_browser)
            agent_args.update(nested_agent)
            extras.update(nested_extras)
            continue

        if key in browser_keys:
            browser_args[key] = value
        elif key in agent_keys:
            agent_args[key] = value
        else:
            extras[key] = value

    return browser_args, agent_args, extras


def apply_cli_overrides(
    config_cls: type[AutoDataConfig],
    base_config: AutoDataConfig,
    overrides: Mapping[str, Any],
    cli_args: Mapping[str, Any],
) -> AutoDataConfig:
    """Merge CLI overrides into a base :class:`AutoDataConfig` instance.

    .. deprecated:: 0.2.0
        This function is deprecated. Use the new dataclass-based configuration
        system in autodata.configs.initialize instead.
    """
    warnings.warn(
        "apply_cli_overrides is deprecated and will be removed in a future version. "
        "Use autodata.configs.initialize instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    config_dict = base_config.model_dump()

    for key, value in overrides.items():
        if (
            key in config_dict
            and isinstance(config_dict[key], dict)
            and isinstance(value, Mapping)
        ):
            config_dict[key].update(value)
        else:
            config_dict[key] = value

    config_dict["args"] = dict(cli_args)
    return config_cls(**config_dict)


__all__ = ["apply_cli_overrides", "split_browser_agent_arguments"]
