"""Checkpoint mixin for AutoData agents."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from easydict import EasyDict

from autodata.core.checkpoint.events import (
    CheckpointEvent,
    CheckpointEventRecorder,
    InvocationPath,
    Stage,
    _update_checkpoint_matrix,
)
from autodata.core.checkpoint.manager import CheckpointManager
from autodata.core.exceptions import AutoDataError
from autodata.core.mixins.base_mixin import BaseAgentMixin

logger = logging.getLogger("AutoData.core")

class CheckpointAgentMixin(BaseAgentMixin):
    """Mixin providing checkpoint helpers for AutoData agents."""

    _checkpoint_manager: CheckpointManager | None = None
    _checkpoint_event_recorder: CheckpointEventRecorder | None = None

    def _initialise_checkpointing(self, config: Any) -> None:
        manager = getattr(config, "_checkpoint_manager", None)
        if isinstance(manager, CheckpointManager):
            self._checkpoint_manager = manager
            events_path = manager.checkpoint_dir / "checkpoint_events.jsonl"
            self._checkpoint_event_recorder = CheckpointEventRecorder(
                events_path=events_path
            )
        else:
            self._checkpoint_manager = None
            self._checkpoint_event_recorder = None

    def _checkpoint_pre(self, invocation_path: InvocationPath) -> None:
        event = self._record_checkpoint_event("pre-execution", invocation_path)
        if event:
            logger.info(
                "[CHECKPOINT] pre-execution stage recorded for %s",
                event.agent_name,
            )

    def _checkpoint_post(
        self, invocation_path: InvocationPath, auto_checkpoint: bool
    ) -> None:
        event = self._record_checkpoint_event("post-execution", invocation_path)
        if event:
            logger.info(
                "[CHECKPOINT] post-execution stage recorded for %s",
                event.agent_name,
            )

        if auto_checkpoint and self._should_auto_checkpoint():
            self._persist_checkpoint(invocation_path)

    def _record_checkpoint_event(
        self,
        stage: Stage,
        invocation_path: InvocationPath,
    ) -> CheckpointEvent | None:
        config = getattr(self, "config", None)
        cp_config = getattr(config, "checkpoint_config", None)
        if cp_config is not None and not getattr(cp_config, "checkpoint_enabled", True):
            return None

        recorder = self._checkpoint_event_recorder
        manager = self._checkpoint_manager
        if recorder is None or manager is None:
            return None

        event = recorder.record(
            self,
            stage,
            invocation_path=invocation_path,
        )
        matrix_path = manager.checkpoint_dir / "checkpoint_matrix.json"
        _update_checkpoint_matrix(event, matrix_path=matrix_path)
        return event

    def _should_auto_checkpoint(self) -> bool:
        config = getattr(self, "config", None)
        cp_config = getattr(config, "checkpoint_config", None)
        return bool(
            cp_config
            and getattr(cp_config, "checkpoint_enabled", True)
            and cp_config.auto_checkpoint
        )

    def _persist_checkpoint(self, invocation_path: InvocationPath) -> None:
        manager = self._checkpoint_manager
        if manager is None:
            return

        ohcache = getattr(self, "ohcache", None)
        autodata_stub = SimpleNamespace(
            config=self.config,
            graph=SimpleNamespace(ohcache=ohcache),
        )

        try:
            manager.save(
                autodata_stub,
                pipeline_stage=getattr(self, "agent_name", self.__class__.__name__),
                metadata={
                    "trigger": "agent_auto_checkpoint",
                    "invocation_path": invocation_path,
                },
            )
        except AutoDataError:
            logger.exception(
                "[CHECKPOINT] Auto-checkpoint failed for %s",
                getattr(self, "agent_name", self.__class__.__name__),
            )


    def on_forward_start(self, context: EasyDict) -> EasyDict:
        self._checkpoint_pre("sync")
        return super().on_forward_start(context)

    async def on_forward_start_async(self, context: EasyDict) -> EasyDict:
        self._checkpoint_pre("async")
        return await super().on_forward_start_async(context)

    def on_forward_end(self, context: EasyDict) -> EasyDict:
        auto_checkpoint = bool(context.get("auto_checkpoint", True))
        try:
            return super().on_forward_end(context)
        finally:
            should_auto = auto_checkpoint and context.get("exception") is None
            self._checkpoint_post(
                "sync",
                auto_checkpoint=should_auto,
            )

    async def on_forward_end_async(self, context: EasyDict) -> EasyDict:
        auto_checkpoint = bool(context.get("auto_checkpoint", True))
        try:
            return await super().on_forward_end_async(context)
        finally:
            should_auto = auto_checkpoint and context.get("exception") is None
            self._checkpoint_post(
                "async",
                auto_checkpoint=should_auto,
            )


__all__ = ["CheckpointAgentMixin"]
