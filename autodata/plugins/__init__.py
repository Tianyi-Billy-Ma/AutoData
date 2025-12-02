"""Plugin registry scaffolding for AutoData.

This module defines the plugin specification dataclass and helpers for loading
plugins that live under ``autodata.plugins``. Plugins expose optional prompt
injections per agent and additional LangChain tools that can be bound at runtime.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool

logger = logging.getLogger("AutoData.plugins")


@dataclass(slots=True)
class PluginSpec:
    """Structured definition for optional AutoData plugins."""

    name: str
    prompts: dict[str, str] = field(default_factory=dict)
    tool_classes: tuple[type[BaseTool], ...] = field(default_factory=tuple)
    metadata: dict[str, str] = field(default_factory=dict)


def _load_plugin_module(plugin_name: str):
    """Import a plugin module from ``autodata.plugins`` package."""

    return importlib.import_module(f"{__name__}.{plugin_name}")


def load_enabled_plugins(enabled_plugins: Sequence[str]) -> list[PluginSpec]:
    """Import all enabled plugins and return their specifications.

    Plugins are expected to expose either a module-level ``PLUGIN`` variable or a
    ``get_plugin()`` callable that returns a :class:`PluginSpec` instance. Missing
    or malformed plugins are logged and skipped.
    """

    specs: list[PluginSpec] = []
    for plugin_name in enabled_plugins:
        try:
            module = _load_plugin_module(plugin_name)
        except ModuleNotFoundError:
            logger.warning("Plugin '%s' not found in autodata.plugins", plugin_name)
            continue

        spec = getattr(module, "PLUGIN", None)
        if isinstance(spec, PluginSpec):
            specs.append(spec)
            continue

        factory = getattr(module, "get_plugin", None)
        if callable(factory):
            try:
                plugin = factory()
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Plugin '%s' factory raised an exception", plugin_name)
                continue
            if isinstance(plugin, PluginSpec):
                specs.append(plugin)
                continue

        logger.warning(
            "Plugin '%s' does not expose a PluginSpec via PLUGIN or get_plugin()",
            plugin_name,
        )

    return specs


def collect_plugin_prompts(plugins: Iterable[PluginSpec]) -> dict[str, list[str]]:
    """Aggregate prompt injections per agent name across all plugins."""

    aggregated: dict[str, list[str]] = {}
    for plugin in plugins:
        for agent_name, prompt in plugin.prompts.items():
            aggregated.setdefault(agent_name, []).append(prompt)
    return aggregated


def collect_tool_classes(plugins: Iterable[PluginSpec]) -> tuple[type[BaseTool], ...]:
    """Aggregate tool classes contributed by plugins."""

    tool_classes: list[type[BaseTool]] = []
    for plugin in plugins:
        tool_classes.extend(plugin.tool_classes)
    return tuple(tool_classes)


__all__ = [
    "PluginSpec",
    "collect_plugin_prompts",
    "collect_tool_classes",
    "load_enabled_plugins",
]
