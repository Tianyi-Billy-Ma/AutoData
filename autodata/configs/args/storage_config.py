"""Storage configuration dataclass."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StorageConfig:
    """Storage configuration for AutoData runs.

    Controls where and how AutoData stores run outputs and artifacts.
    """

    type: str = field(
        default="file",
        metadata={"help": "Storage type (file, database)"},
    )
    output_dir: str = field(
        default="./outputs",
        metadata={"help": "Base output directory for all runs"},
    )
    file_format: str = field(
        default="json",
        metadata={"help": "Output file format (json, csv, parquet)"},
    )
    compression: str | None = field(
        default=None,
        metadata={"help": "Compression type (gzip, bz2, lzma)"},
    )
    database_url: str | None = field(
        default=None,
        metadata={"help": "Database connection URL"},
    )
    overwrite: bool = field(
        default=True,
        metadata={"help": "Enable overwriting an existing run directory"},
    )
    force_overwrite: bool = field(
        default=True,
        metadata={"help": "Skip confirmation when overwriting (requires overwrite=True)"},
    )
