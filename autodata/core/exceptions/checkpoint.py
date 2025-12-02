"""Checkpoint-related exception types."""

from __future__ import annotations

from .base import AutoDataError


class CheckpointError(AutoDataError):
    """Base exception raised for checkpoint lifecycle failures."""

    default_code = "checkpoint_error"


class CheckpointSaveError(CheckpointError):
    """Raised when persisting a checkpoint fails."""

    default_code = "checkpoint_save_error"
    default_message = "Unable to save checkpoint."


class CheckpointLoadError(CheckpointError):
    """Raised when restoring a checkpoint fails."""

    default_code = "checkpoint_load_error"
    default_message = "Unable to load checkpoint."


class CheckpointNotFoundError(CheckpointLoadError):
    """Raised when a requested checkpoint file is missing."""

    default_code = "checkpoint_not_found"
    default_message = "Checkpoint file not found."

    def __init__(self, path: str, *, hint: str | None = None) -> None:
        super().__init__(
            f"Checkpoint file not found: {path}",
            details={"path": path},
            hint=hint
            or "Run `autodata.checkpoint list` to inspect available checkpoints.",
        )


class CheckpointVersionError(CheckpointLoadError):
    """Raised when checkpoint schema version is incompatible with the runtime."""

    default_code = "checkpoint_version_error"
    default_message = "Checkpoint schema version is not supported."


class CheckpointIntegrityError(CheckpointLoadError):
    """Raised when checkpoint contents are corrupted or incomplete."""

    default_code = "checkpoint_integrity_error"
    default_message = "Checkpoint contents failed integrity checks."


class CheckpointValidationError(CheckpointError):
    """Raised when checkpoint metadata or configuration is invalid."""

    default_code = "checkpoint_validation_error"
    default_message = "Checkpoint metadata failed validation."


__all__ = [
    "CheckpointError",
    "CheckpointSaveError",
    "CheckpointLoadError",
    "CheckpointNotFoundError",
    "CheckpointVersionError",
    "CheckpointIntegrityError",
    "CheckpointValidationError",
]
