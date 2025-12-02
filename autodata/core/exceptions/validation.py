"""Validation pipeline exception definitions."""

from __future__ import annotations

from .base import AutoDataError


class ValidationError(AutoDataError):
    """Base exception for validation workflow failures."""

    default_code = "validation_error"


class ValidationSetupError(ValidationError):
    """Raised when validation prerequisites are not satisfied."""

    default_code = "validation_setup_error"
    default_message = "Validation environment setup failed."


class ValidationTimeoutError(ValidationError):
    """Raised when validation tasks exceed the allotted time."""

    default_code = "validation_timeout_error"
    default_message = "Validation step exceeded its time limit."


class ValidationRuleError(ValidationError):
    """Raised when validation rules are misconfigured or inconsistent."""

    default_code = "validation_rule_error"
    default_message = "Validation rules are invalid or inconsistent."


class ValidationAssertionError(ValidationError):
    """Raised when validation assertions fail."""

    default_code = "validation_assertion_error"
    default_message = "Validation assertion failed."


__all__ = [
    "ValidationError",
    "ValidationSetupError",
    "ValidationTimeoutError",
    "ValidationRuleError",
    "ValidationAssertionError",
]
