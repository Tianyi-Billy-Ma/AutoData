"""Model-related exceptions for AutoData agents."""

from __future__ import annotations

from .base import AutoDataError


class AutoDataModelError(AutoDataError):
    """Raised when agent models are unavailable or invalid."""


__all__ = ["AutoDataModelError"]
