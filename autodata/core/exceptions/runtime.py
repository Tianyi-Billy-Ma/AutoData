"""Runtime-oriented exception classes for AutoData."""

from __future__ import annotations

import logging

from .base import AutoDataError


class ConfigurationError(AutoDataError):
    """Configuration-related errors."""

    default_message = "Configuration error."


class ExecutionError(AutoDataError):
    """Task execution errors."""

    default_message = "Execution error."


class CacheError(AutoDataError):
    """Cache system errors."""

    default_message = "Cache operation failed."


class GraphError(AutoDataError):
    """Graph construction and execution errors."""

    default_message = "Graph construction error."


class AutoDataInitializationError(AutoDataError):
    """Initialization failures raised during startup."""

    default_message = "AutoData initialization failed."
    default_code = "autodata_initialization_failed"


def log_and_raise(
    logger: logging.Logger,
    message: str,
    exception_class: type[AutoDataError] = AutoDataError,
    original_exception: Exception | None = None,
    log_level: int = logging.ERROR,
) -> None:
    """Log a message and raise the provided exception."""

    logger.log(log_level, message, exc_info=True)
    if original_exception:
        raise exception_class(message) from original_exception
    raise exception_class(message)


__all__ = [
    "ConfigurationError",
    "ExecutionError",
    "CacheError",
    "GraphError",
    "AutoDataInitializationError",
    "log_and_raise",
]
