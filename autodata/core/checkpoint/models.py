"""Data models supporting checkpoint metadata and manifests."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CheckpointMetadata:
    """Metadata describing a single checkpoint artifact."""

    version: str
    autodata_version: str
    created_at: float
    run_name: str
    pipeline_stage: str
    filename: str
    branch: str | None = None
    commit_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def created_at_datetime(self) -> datetime:
        """Return the checkpoint creation time as a datetime."""

        return datetime.fromtimestamp(self.created_at)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this metadata to a dictionary."""

        payload: dict[str, Any] = {
            "version": self.version,
            "autodata_version": self.autodata_version,
            "created_at": self.created_at,
            "run_name": self.run_name,
            "pipeline_stage": self.pipeline_stage,
            "filename": self.filename,
        }
        if self.branch:
            payload["branch"] = self.branch
        if self.commit_hash:
            payload["commit_hash"] = self.commit_hash
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CheckpointMetadata:
        """Create metadata from a dictionary payload."""

        return cls(
            version=str(data["version"]),
            autodata_version=str(data["autodata_version"]),
            created_at=float(data["created_at"]),
            run_name=str(data["run_name"]),
            pipeline_stage=str(data["pipeline_stage"]),
            filename=str(data.get("filename", "")),
            branch=str(data["branch"]) if data.get("branch") is not None else None,
            commit_hash=str(data["commit_hash"])
            if data.get("commit_hash") is not None
            else None,
            metadata=dict(data.get("metadata", {})),
        )

    def with_filename(self, filename: str) -> CheckpointMetadata:
        """Return a copy of the metadata with a specific filename set."""

        return CheckpointMetadata(
            version=self.version,
            autodata_version=self.autodata_version,
            created_at=self.created_at,
            run_name=self.run_name,
            pipeline_stage=self.pipeline_stage,
            filename=filename,
            branch=self.branch,
            commit_hash=self.commit_hash,
            metadata=dict(self.metadata),
        )


@dataclass(slots=True)
class CheckpointPayload:
    """Full checkpoint payload including serialized state segments."""

    header: CheckpointMetadata
    config_dict: dict[str, Any]
    artifacts: dict[str, Any]
    messages: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary matching on-disk representation."""

        payload = self.header.to_dict()
        payload.update(
            {
                "config_dict": self.config_dict,
                "artifacts": self.artifacts,
                "messages": self.messages,
            }
        )
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CheckpointPayload:
        """Reconstruct payload from dictionary representation."""

        header = CheckpointMetadata.from_dict(data)
        artifacts = data.get("artifacts")
        messages = data.get("messages")

        # Backward compatibility: gracefully handle legacy payloads lacking new fields.
        if artifacts is None and "ohcache_state" in data:
            artifacts = {}
        if messages is None and "hypergraph_state" in data:
            messages = {}

        return cls(
            header=header,
            config_dict=dict(data.get("config_dict", {})),
            artifacts=dict(artifacts or {}),
            messages=dict(messages or {}),
            metadata=dict(data.get("metadata", header.metadata)),
        )


@dataclass(slots=True)
class CheckpointEntry:
    """Entry recorded in a checkpoint manifest."""

    filename: str
    created_at: float
    pipeline_stage: str
    version: str
    autodata_version: str
    file_size_bytes: int
    branch: str | None = None
    commit_hash: str | None = None

    @property
    def file_size_mb(self) -> float:
        """Return file size in megabytes with one decimal precision."""

        return round(self.file_size_bytes / (1024 * 1024), 1)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the manifest entry to a dictionary."""

        payload: dict[str, Any] = {
            "filename": self.filename,
            "created_at": self.created_at,
            "pipeline_stage": self.pipeline_stage,
            "file_size_mb": self.file_size_mb,
            "version": self.version,
            "autodata_version": self.autodata_version,
        }
        if self.branch:
            payload["branch"] = self.branch
        if self.commit_hash:
            payload["commit_hash"] = self.commit_hash
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CheckpointEntry:
        """Reconstruct an entry from dictionary representation."""

        file_size_bytes = int(
            float(data.get("file_size_mb", 0)) * 1024 * 1024
        )  # approx if only MB provided
        return cls(
            filename=str(data["filename"]),
            created_at=float(data["created_at"]),
            pipeline_stage=str(data["pipeline_stage"]),
            file_size_bytes=file_size_bytes,
            version=str(data["version"]),
            autodata_version=str(data["autodata_version"]),
            branch=str(data["branch"]) if data.get("branch") is not None else None,
            commit_hash=str(data["commit_hash"])
            if data.get("commit_hash") is not None
            else None,
        )

    @classmethod
    def from_metadata(
        cls,
        metadata: CheckpointMetadata,
        *,
        file_size_bytes: int,
    ) -> CheckpointEntry:
        """Create an entry from checkpoint metadata."""

        return cls(
            filename=metadata.filename,
            created_at=metadata.created_at,
            pipeline_stage=metadata.pipeline_stage,
            version=metadata.version,
            autodata_version=metadata.autodata_version,
            file_size_bytes=file_size_bytes,
            branch=metadata.branch,
            commit_hash=metadata.commit_hash,
        )


@dataclass(slots=True)
class CheckpointManifest:
    """Manifest describing checkpoints stored for a run."""

    run_name: str
    checkpoint_dir: Path
    checkpoints: list[CheckpointEntry] = field(default_factory=list)
    last_updated: float = field(default_factory=lambda: time.time())

    def add_entry(self, entry: CheckpointEntry) -> None:
        """Add or replace a checkpoint entry and refresh ordering."""

        existing_index = next(
            (
                index
                for index, item in enumerate(self.checkpoints)
                if item.filename == entry.filename
            ),
            None,
        )
        if existing_index is not None:
            self.checkpoints[existing_index] = entry
        else:
            self.checkpoints.append(entry)

        self.checkpoints.sort(key=lambda item: item.created_at, reverse=True)
        self.last_updated = max(self.last_updated, entry.created_at, time.time())

    def extend(self, entries: Iterable[CheckpointEntry]) -> None:
        """Add multiple entries to the manifest."""

        for entry in entries:
            self.add_entry(entry)

    def find(self, filename: str) -> CheckpointEntry | None:
        """Find a manifest entry by filename."""

        return next(
            (entry for entry in self.checkpoints if entry.filename == filename),
            None,
        )

    def prune(self, max_keep: int | None) -> list[CheckpointEntry]:
        """Trim manifest to ``max_keep`` entries, returning pruned entries."""

        if max_keep is None or max_keep <= 0:
            return []

        if len(self.checkpoints) <= max_keep:
            return []

        # Entries sorted newest-first; prune from the tail.
        removed = self.checkpoints[max_keep:]
        self.checkpoints = self.checkpoints[:max_keep]
        self.last_updated = time.time()
        return removed

    def remove_older_than(self, cutoff_timestamp: float) -> list[CheckpointEntry]:
        """Remove checkpoints created before ``cutoff_timestamp``."""

        if cutoff_timestamp <= 0:
            return []

        removed = [
            entry for entry in self.checkpoints if entry.created_at < cutoff_timestamp
        ]
        if not removed:
            return []

        filenames = {entry.filename for entry in removed}
        self.checkpoints = [
            entry for entry in self.checkpoints if entry.filename not in filenames
        ]
        self.last_updated = time.time()
        return removed

    def filenames(self) -> list[str]:
        """Return checkpoint filenames sorted newest-first."""

        return [entry.filename for entry in self.checkpoints]

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest to JSON-compatible dictionary."""

        return {
            "run_name": self.run_name,
            "checkpoint_dir": str(self.checkpoint_dir),
            "checkpoints": [entry.to_dict() for entry in self.checkpoints],
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CheckpointManifest:
        """Create a manifest from stored dictionary representation."""

        entries_data: Sequence[Mapping[str, Any]] = data.get("checkpoints", [])  # type: ignore[assignment]
        entries = [CheckpointEntry.from_dict(entry) for entry in entries_data]
        manifest = cls(
            run_name=str(data["run_name"]),
            checkpoint_dir=Path(data["checkpoint_dir"]),
            checkpoints=list(entries),
            last_updated=float(data.get("last_updated", time.time())),
        )
        manifest.checkpoints.sort(key=lambda item: item.created_at, reverse=True)
        return manifest


__all__ = [
    "CheckpointMetadata",
    "CheckpointPayload",
    "CheckpointEntry",
    "CheckpointManifest",
]
