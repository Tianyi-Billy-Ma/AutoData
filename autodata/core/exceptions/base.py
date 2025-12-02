"""Base exception types for the AutoData platform."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AutoDataError(Exception):
    """Root exception for all AutoData-specific failures.

    Args:
        message: Human-readable description of the failure.
        code: Stable machine-consumable error code (defaults to ``autodata_error``).
        details: Optional structured metadata that may assist with debugging.
        hint: Optional remediation suggestion or follow-up action.
    """

    default_message = "An AutoData error occurred."
    default_code = "autodata_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
        hint: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details: dict[str, Any] = dict(details or {})
        self.hint = hint
        super().__init__(self.message)

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.hint:
            return f"{base} (hint: {self.hint})"
        return base

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error into a structured dictionary."""

        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        if self.hint:
            payload["hint"] = self.hint
        return payload

    def with_details(self, **details: Any) -> AutoDataError:
        """Return a new error instance enriched with additional details."""

        merged = {**self.details, **details}
        return self.__class__(
            self.message,
            code=self.code,
            details=merged,
            hint=self.hint,
        )


__all__ = ["AutoDataError"]
