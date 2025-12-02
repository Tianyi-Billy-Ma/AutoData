"""Checkpoint configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class CheckpointConfig:
    """Configuration controlling checkpoint save/load behaviour.

    Enables saving and resuming pipeline state at agent boundaries.
    """

    checkpoint_enabled: bool = field(
        default=False,
        metadata={"help": "Enable checkpoint system for pipeline runs."},
    )
    auto_checkpoint: bool = field(
        default=False,
        metadata={"help": "Automatically save checkpoints at agent boundaries."},
    )
    checkpoint_dir: str | None = field(
        default=None,
        metadata={"help": "Override directory for checkpoint artifacts."},
    )
    export_json: bool = field(
        default=False,
        metadata={"help": "Export human-readable JSON alongside binary checkpoints."},
    )
    resume_from: str | None = field(
        default=None,
        metadata={"help": "Checkpoint filename to resume from."},
    )
    max_checkpoints: int | None = field(
        default=None,
        metadata={"help": "Maximum number of checkpoints to retain (None for unlimited)."},
    )
