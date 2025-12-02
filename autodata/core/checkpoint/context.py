"""Debug context helpers for isolated agent execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast

from langchain_core.messages import BaseMessage, HumanMessage

from autodata.agents.types import AgentState


def _coerce_messages(messages: Sequence[BaseMessage | str] | None) -> list[BaseMessage]:
    """Normalize optional message inputs into cloned message objects."""

    if not messages:
        return []

    normalized: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, BaseMessage):
            normalized.append(deepcopy(message))
        elif isinstance(message, str):
            normalized.append(HumanMessage(content=message))
        else:  # pragma: no cover - defensive
            raise TypeError(f"Unsupported message type: {type(message)!r}")
    return normalized


@dataclass(slots=True)
class DebugContext:
    """Synthetic agent context used for isolated debugging."""

    agent_name: str
    sender: str
    messages: list[BaseMessage] = field(default_factory=list)
    user_task: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_prompt(
        cls,
        *,
        agent_name: str,
        prompt: str,
        sender: str = "DebugRunner",
        user_task: str | None = None,
        extra_messages: Sequence[BaseMessage | str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DebugContext:
        """Create a debug context seeded from a textual prompt."""

        base_message = HumanMessage(content=prompt)
        messages = [base_message, *_coerce_messages(extra_messages)]
        return cls(
            agent_name=agent_name,
            sender=sender,
            messages=messages,
            user_task=user_task or prompt,
            metadata=dict(metadata or {}),
        )

    def to_agent_state(self) -> AgentState:
        """Convert the context into an ``AgentState`` payload."""

        state_dict: dict[str, Any] = {
            "sender": self.sender,
            "next": self.agent_name,
            "messages": list(self.messages),
            "user_task": self.user_task,
            "debug_context": self.to_summary_dict(),
        }
        return cast(AgentState, state_dict)

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a lightweight dictionary representation for logging/debugging."""

        summary: dict[str, Any] = {
            "agent_name": self.agent_name,
            "sender": self.sender,
            "user_task": self.user_task,
        }
        if self.metadata:
            summary["metadata"] = dict(self.metadata)
        summary["message_count"] = len(self.messages)
        return summary


__all__ = ["DebugContext"]
