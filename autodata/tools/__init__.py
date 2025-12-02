"""Tool registry and plugin-aware helpers for AutoData."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from langchain_core.tools import BaseTool

from autodata.plugins import load_enabled_plugins
from autodata.tools.python_tool import (
    DEFAULT_IMAGE,
    DockerPythonExecutor,
    PythonExecutionResult,
    PythonExecutor,
    create_requirements_file,
    execute_with_dependencies,
    install_dependencies,
    resolve_work_dir,
    sanitize_python_input,
)
from autodata.tools.search_tool import PerpleixtySearchTool

BASE_TOOL_CLASSES: tuple[type[BaseTool], ...] = (
    PerpleixtySearchTool,
)

logger = logging.getLogger("AutoData.tools")


def _get_plugin_specs(config: Any) -> list:
    """Load and memoize plugin specifications on the config object."""

    plugin_cfg = getattr(config, "plugin_config", None)
    if plugin_cfg and getattr(plugin_cfg, "enabled_plugins", None) is not None:
        enabled_plugins: Sequence[str] = plugin_cfg.enabled_plugins or []
    else:
        enabled_plugins = getattr(config, "enabled_plugins", []) or []

    cache_key = "_plugin_specs"
    cached = getattr(config, cache_key, None)
    if cached is not None:
        return list(cached)

    specs = load_enabled_plugins(enabled_plugins)
    try:
        setattr(config, cache_key, specs)
        config._base_tool_classes = BASE_TOOL_CLASSES
    except Exception:  # pragma: no cover - defensive (config may be immutable)
        pass
    return specs


def _filter_plugin_tool_classes(
    base_tool_classes: tuple[type[BaseTool], ...], specs: list
) -> tuple[type[BaseTool], ...]:
    known_names: set[str] = {
        getattr(cls, "name", cls.__name__) for cls in base_tool_classes
    }
    filtered: list[type[BaseTool]] = []

    for spec in specs:
        plugin_name = getattr(spec, "name", "unknown")
        for tool_cls in getattr(spec, "tool_classes", ()) or ():
            tool_name = getattr(tool_cls, "name", tool_cls.__name__)
            if tool_name in known_names:
                logger.error(
                    "Plugin '%s' tool '%s' conflicts with an existing tool name; rejecting plugin tool.",
                    plugin_name,
                    tool_name,
                )
                continue
            filtered.append(tool_cls)
            known_names.add(tool_name)

    return tuple(filtered)


def get_tool_classes(config: Any) -> tuple[type[BaseTool], ...]:
    """Return base tool classes combined with plugin-provided tools."""

    specs = _get_plugin_specs(config)
    plugin_tool_classes = _filter_plugin_tool_classes(BASE_TOOL_CLASSES, specs)
    if not plugin_tool_classes:
        return BASE_TOOL_CLASSES
    return BASE_TOOL_CLASSES + plugin_tool_classes


__all__ = [
    "BASE_TOOL_CLASSES",
    "DEFAULT_IMAGE",
    "DockerPythonExecutor",
    "PythonExecutionResult",
    "PythonExecutor",
    "create_requirements_file",
    "execute_with_dependencies",
    "get_tool_classes",
    "install_dependencies",
    "resolve_work_dir",
    "sanitize_python_input",
]
