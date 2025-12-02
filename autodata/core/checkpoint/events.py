"""Checkpoint event recording utilities."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

Stage = Literal["pre-execution", "post-execution"]
InvocationPath = Literal["sync", "async"]


class BaseAgentProtocol(Protocol):
    agent_name: str
    config: Any


@dataclass(slots=True)
class CheckpointEvent:
    """Structured checkpoint event payload persisted for audits."""

    event_id: str
    agent_name: str
    timestamp: str
    stage: Stage
    artifacts: list[str] = field(default_factory=list)
    resume_token: str | None = None
    invocation_path: InvocationPath | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp,
            "stage": self.stage,
            "artifacts": list(self.artifacts),
            "resume_token": self.resume_token,
            "invocation_path": self.invocation_path,
        }


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
    ) as fd:
        fd.write(content)
        fd.flush()
        os.fsync(fd.fileno())
        tmp_path = Path(fd.name)
    os.replace(tmp_path, path)


def _atomic_append_json_line(path: Path, payload: dict[str, Any]) -> None:
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
    line = json.dumps(payload)
    _atomic_write_text(path, f"{existing}{line}\n")


def _update_checkpoint_matrix(
    event: CheckpointEvent,
    *,
    matrix_path: Path,
) -> None:
    payload = {
        "generated_at": event.timestamp,
        "agents": {},
    }
    if matrix_path.exists():
        try:
            payload = json.loads(matrix_path.read_text())
        except json.JSONDecodeError:
            pass

    agents = payload.setdefault("agents", {})
    agent_entry = agents.setdefault(
        event.agent_name,
        {
            "sync": {"pre-execution": 0, "post-execution": 0},
            "async": {"pre-execution": 0, "post-execution": 0},
            "unknown": {"pre-execution": 0, "post-execution": 0},
        },
    )

    invocation_key = event.invocation_path or "unknown"
    stage_counts = agent_entry.setdefault(
        invocation_key,
        {"pre-execution": 0, "post-execution": 0},
    )
    stage_counts[event.stage] = stage_counts.get(event.stage, 0) + 1

    payload["generated_at"] = event.timestamp
    _atomic_write_text(matrix_path, json.dumps(payload, indent=2))


class CheckpointEventRecorder:
    """Records checkpoint events to disk for auditing."""

    def __init__(self, *, events_path: Path) -> None:
        self.events_path = events_path
        self.events_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        agent: BaseAgentProtocol,
        stage: Stage,
        *,
        artifacts: Iterable[str] | None = None,
        resume_token: str | None = None,
        invocation_path: InvocationPath | None = None,
    ) -> CheckpointEvent:
        event = CheckpointEvent(
            event_id=str(uuid.uuid4()),
            agent_name=getattr(agent, "agent_name", agent.__class__.__name__),
            timestamp=datetime.now(tz=UTC).isoformat(),
            stage=stage,
            artifacts=list(artifacts or []),
            resume_token=resume_token,
            invocation_path=invocation_path,
        )

        payload = event.to_payload()
        _atomic_append_json_line(self.events_path, payload)
        return event


__all__ = [
    "CheckpointEvent",
    "CheckpointEventRecorder",
    "InvocationPath",
    "Stage",
    "_update_checkpoint_matrix",
]
