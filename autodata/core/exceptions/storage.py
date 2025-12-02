"""Exceptions for AutoData path governance violations.

These errors are raised when runtime components attempt to read or write
artifacts outside the directories resolved from the active ``AutoDataConfig``.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from .base import AutoDataError


class PathGovernanceError(AutoDataError):
    """Base exception for configuration path violations."""

    default_message = "Invalid path usage detected."
    default_code = "path_governance_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        path: Path | str | None = None,
        details: dict[str, Any] | None = None,
        hint: str | None = None,
    ) -> None:
        merged_details = dict(details or {})
        if path is not None:
            merged_details.setdefault("path", str(path))
        super().__init__(
            message or self.default_message,
            code=self.default_code,
            details=merged_details,
            hint=hint,
        )


class DirectoryCreationError(PathGovernanceError):
    """Raised when AutoData fails to create a configuration-owned directory."""

    default_message = "Failed to create required run directory."
    default_code = "directory_creation_error"

    def __init__(
        self,
        path: Path | str,
        *,
        reason: str | None = None,
        hint: str | None = None,
        include_stack: bool = True,
    ) -> None:
        derived_hint = hint or "Check filesystem permissions and available space."
        details: dict[str, Any] = {}
        if reason:
            details["reason"] = reason
        if include_stack:
            details["debug_stack"] = traceback.format_stack()
        super().__init__(
            self.default_message,
            path=path,
            details=details,
            hint=derived_hint,
        )


class InvalidRunNameError(PathGovernanceError):
    """Raised when ``run_name`` is missing or fails validation rules."""

    default_message = "Invalid or missing run_name in configuration."
    default_code = "invalid_run_name_error"

    def __init__(
        self,
        run_name: str | None,
        *,
        hint: str | None = None,
        include_stack: bool = True,
    ) -> None:
        details: dict[str, Any] = {"run_name": run_name}
        if include_stack:
            details["debug_stack"] = traceback.format_stack()
        derived_hint = (
            hint
            or "Provide a non-empty run_name using letters, numbers, underscores, or hyphens."
        )
        super().__init__(
            self.default_message,
            details=details,
            hint=derived_hint,
        )


__all__ = [
    "PathGovernanceError",
    "DirectoryCreationError",
    "InvalidRunNameError",
]
