"""Shared agent mixins for the AutoData core."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = (
    "BaseAgentMixin",
    "CheckpointAgentMixin",
    "LogMixin",
    "OHCacheAgentMixin",
    "ThinkAgentMixin",
)


def __getattr__(name: str) -> Any:
    if name == "BaseAgentMixin":
        return import_module("autodata.core.mixins.base_mixin").BaseAgentMixin
    if name == "CheckpointAgentMixin":
        return import_module("autodata.core.mixins.checkpoint_mixin").CheckpointAgentMixin
    if name == "LogMixin":
        return import_module("autodata.core.mixins.log_mixin").LogMixin
    if name == "OHCacheAgentMixin":
        return import_module("autodata.core.mixins.ohcache_mixin").OHCacheAgentMixin
    if name == "ThinkAgentMixin":
        return import_module("autodata.core.mixins.think_mixin").ThinkAgentMixin
    raise AttributeError(f"module 'autodata.core.mixins' has no attribute {name!r}")
