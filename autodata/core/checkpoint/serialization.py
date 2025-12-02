"""Serialization helpers for checkpoint payloads and manifests."""

from __future__ import annotations

import json
import os
import pickle
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

from autodata.core.exceptions import (
    CheckpointIntegrityError,
    CheckpointLoadError,
    CheckpointNotFoundError,
    CheckpointSaveError,
)

from .models import (
    CheckpointManifest,
    CheckpointPayload,
)

PICKLE_PROTOCOL = 5


def dump_checkpoint_payload(path: Path, payload: CheckpointPayload) -> None:
    """Persist a checkpoint payload to ``path`` using pickle protocol 5."""

    data = payload.to_dict()
    try:
        _atomic_write(
            path, "wb", lambda fh: pickle.dump(data, fh, protocol=PICKLE_PROTOCOL)
        )
    except Exception as exc:  # noqa: BLE001 - propagate as domain-specific error
        raise CheckpointSaveError(
            "Failed to write checkpoint payload.",
            details={"path": str(path)},
        ) from exc


def dump_checkpoint_json(path: Path, payload: CheckpointPayload) -> None:
    """Persist a JSON debug representation of the checkpoint payload."""

    data = payload.to_dict()

    def _writer(fh: IO[str]) -> None:
        json.dump(data, fh, indent=2, ensure_ascii=False)

    try:
        _atomic_write(path, "w", _writer)
    except Exception as exc:  # noqa: BLE001
        raise CheckpointSaveError(
            "Failed to write checkpoint JSON export.",
            details={"path": str(path)},
        ) from exc


def load_checkpoint_payload(path: Path) -> CheckpointPayload:
    """Load a checkpoint payload from disk."""

    try:
        with path.open("rb") as fh:
            data = pickle.load(fh)
    except FileNotFoundError as exc:
        raise CheckpointNotFoundError(str(path)) from exc
    except Exception as exc:  # noqa: BLE001
        raise CheckpointLoadError(
            "Failed to load checkpoint payload.",
            details={"path": str(path)},
        ) from exc

    if not isinstance(data, dict):
        raise CheckpointIntegrityError(
            "Checkpoint payload is not a dictionary.",
            details={"path": str(path), "type": type(data).__name__},
        )

    try:
        return CheckpointPayload.from_dict(data)
    except Exception as exc:  # noqa: BLE001
        raise CheckpointIntegrityError(
            "Checkpoint payload is missing required fields.",
            details={"path": str(path)},
        ) from exc


def read_checkpoint_manifest(path: Path) -> CheckpointManifest:
    """Load a checkpoint manifest from disk."""

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise CheckpointNotFoundError(str(path)) from exc
    except json.JSONDecodeError as exc:
        raise CheckpointIntegrityError(
            "Checkpoint manifest JSON is invalid.",
            details={"path": str(path)},
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise CheckpointLoadError(
            "Failed to load checkpoint manifest.",
            details={"path": str(path)},
        ) from exc

    if not isinstance(data, dict):
        raise CheckpointIntegrityError(
            "Checkpoint manifest payload is not a dictionary.",
            details={"path": str(path), "type": type(data).__name__},
        )

    try:
        return CheckpointManifest.from_dict(data)
    except Exception as exc:  # noqa: BLE001
        raise CheckpointIntegrityError(
            "Checkpoint manifest is missing required fields.",
            details={"path": str(path)},
        ) from exc


def write_checkpoint_manifest(path: Path, manifest: CheckpointManifest) -> None:
    """Persist manifest metadata to disk atomically."""

    data = manifest.to_dict()

    def _writer(fh: IO[str]) -> None:
        json.dump(data, fh, indent=2, ensure_ascii=False)

    try:
        _atomic_write(path, "w", _writer)
    except Exception as exc:  # noqa: BLE001
        raise CheckpointSaveError(
            "Failed to write checkpoint manifest.",
            details={"path": str(path)},
        ) from exc


def _atomic_write(path: Path, mode: str, writer: Callable[[IO[Any]], None]) -> None:
    """Write to ``path`` atomically using a temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)

    delete = True
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(mode, dir=path.parent, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            writer(tmp)
            tmp.flush()
            if "b" in mode:
                os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
        delete = False
    finally:
        if delete and tmp_path is not None:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
