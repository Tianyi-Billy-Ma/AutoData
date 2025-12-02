"""OHCache mixin providing cache and hypergraph helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from easydict import EasyDict
from langchain_core.messages import BaseMessage, HumanMessage

from autodata.core.mixins.base_mixin import BaseAgentMixin
from autodata.core.ohcache.formatter import BaseResponse
from autodata.utils.type_utils import ensure_serializable

logger = logging.getLogger("AutoData.core")

if TYPE_CHECKING:
    from autodata.agents.types import AgentState
    from autodata.core.ohcache.ohcache import OHCache


class OHCacheAgentMixin(BaseAgentMixin):
    """Mixin supplying cache and hypergraph helpers for agents."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[misc]
        self.ohcache: OHCache | None = None

    # ---------------------------------------------------------------------
    # Cache operations
    # ---------------------------------------------------------------------

    def cache_artifact(
        self,
        key: str,
        value: Any,
        *,
        cache_type: str = "general",
        summary: str | None = None,
        ttl: int | None = None,
        tags: set[str] | None = None,
        target_agents: set[str] | None = None,
    ) -> None:
        """Persist an artifact and optionally announce it to collaborators."""

        if not (self.ohcache and self.ohcache.enable_ohcache):
            return

        if key.startswith("checkpoint::") or cache_type.startswith("checkpoint"):
            logger.warning(
                "Skipping attempt to cache checkpoint data via OHCache: key=%s type=%s",
                key,
                cache_type,
            )
            return

        metadata = {
            "agent_name": self.agent_name,
        }
        if summary:
            metadata["summary"] = summary

        normalised_value = ensure_serializable(value)

        self.ohcache.set_cache(
            key=key,
            value=normalised_value,
            cache_type=cache_type,
            metadata=metadata,
            ttl=ttl,
            tags=tags,
        )

        if summary and self.ohcache.enable_ohcache:
            self.ohcache.publish_cache_notice(
                owner=self.agent_name,
                cache_key=key,
                cache_type=cache_type,
                summary=summary,
                target_agents=target_agents,
            )

    def fetch_artifact(self, key: str, *, default: Any = None) -> Any:
        """Retrieve an artifact from cache."""

        if not (self.ohcache and self.ohcache.enable_ohcache):
            return default

        cache_entry = self.ohcache.get_cache_entry(key)
        if cache_entry is None:
            return default

        value = self.ohcache.get_cache(key=key, default=default)
        if value is default:
            return default

        agent_name = getattr(self, "agent_name", "Agent")
        self.ohcache.record_artifact_reuse(key, agent=agent_name)
        logger.info("%s reused cached artifact '%s'", agent_name, key)
        return value

    # ---------------------------------------------------------------------
    # Hypergraph messaging helpers
    # ---------------------------------------------------------------------

    def send_message(
        self,
        message: BaseResponse | BaseMessage | str,
        *,
        target_agents: set[str] | None = None,
        message_type: str = "default",
    ) -> EasyDict:
        """Publish a message to collaborators via the hypergraph."""

        metadata = EasyDict(
            {
                "hyperedge_id": None,
                "hyperedges": [],
                "target_agents": set(target_agents or []),
            }
        )

        if not (self.ohcache and self.ohcache.enable_ohcache):
            return metadata

        target_set = None if target_agents is None else set(target_agents)
        result = self.ohcache.broadcast_message(
            from_agent=self.agent_name,
            message=message,
            target_agents=target_set,
            message_type=message_type,
        )

        if isinstance(result, EasyDict):
            metadata.hyperedge_id = result.get("hyperedge_id")
            hyperedge_id = metadata.hyperedge_id
            metadata.hyperedges = [hyperedge_id] if hyperedge_id else []
            metadata.target_agents = set(result.get("target_agents", set()))

        return metadata

    def receive_messages(
        self,
        *,
        message_type: str | set | None = None,
        clear_buffers: bool = False,
        as_base_message: bool = False,
        exclude_message_types: set[str] | None = None,
    ) -> list[BaseMessage]:
        """Pull pending messages targeting this agent."""

        if not (self.ohcache and self.ohcache.enable_ohcache):
            return []

        message_types = (
            None
            if message_type is None
            else (
                {message_type} if isinstance(message_type, str) else set(message_type)
            )
        )
        payloads = self.ohcache.get_agent_hypergraph_messages(
            self.agent_name,
            message_types=message_types,
            clear_buffers=clear_buffers,
        )

        exclusion = {mt for mt in (exclude_message_types or set()) if mt}
        if exclusion:
            payloads = [
                payload
                for payload in payloads
                if payload.get("message_type") not in exclusion
            ]

        if not as_base_message:
            return payloads

        prepared: list[BaseMessage] = []
        for payload in payloads:
            message = payload.get("message")

            if not isinstance(message, BaseResponse | BaseMessage | str):
                from_agent = payload.get("from_agent", "unknown")
                msg_type = payload.get("message_type", "unknown")
                logger.warning(
                    f"Unexpected message type {type(message).__name__} "
                    f"from agent '{from_agent}' (message_type='{msg_type}'). "
                    f"Expected BaseResponse, BaseMessage, or str. Skipping message."
                )
                continue

            sender = payload.get("from_agent", "unknown")
            if isinstance(message, BaseResponse):
                message = HumanMessage(content=message.to_message(), name=sender)
            elif isinstance(message, BaseMessage):
                message = message
            elif isinstance(message, str):
                message = HumanMessage(content=message, name=sender)
            prepared.append(message)

        return prepared

    def receive_cache_notices(
        self, *, clear_buffers: bool = False
    ) -> list[HumanMessage]:
        """Return cache notices as ``HumanMessage`` instances."""

        if not (self.ohcache and self.ohcache.enable_ohcache):
            return []

        raw_notices = self.ohcache.receive_cache_notices(  # type: ignore[attr-defined]
            self.agent_name,
            clear_buffers=clear_buffers,
        )

        messages: list[HumanMessage] = []
        for notice in raw_notices:
            content = (
                f"[CACHE NOTICE] key={notice.cache_key}"
                f"\ncache_type: {notice.cache_type or 'general'}"
                f"\nsummary: {notice.summary or '(none)'}"
            )
            messages.append(HumanMessage(content=content, name=notice.owner))

        return messages

    def pull_cache_notices(
        self, *, clear_buffers: bool = True
    ) -> list[dict[str, Any]]:
        """Return cache notices as dictionaries for think-and-fetch workflows."""

        if not (self.ohcache and self.ohcache.enable_ohcache):
            return []

        raw_notices = self.ohcache.receive_cache_notices(
            self.agent_name,
            clear_buffers=clear_buffers,
        )

        structured: list[dict[str, Any]] = []
        for notice in raw_notices:
            if hasattr(notice, "model_dump"):
                payload = notice.model_dump()
            elif isinstance(notice, dict):
                payload = dict(notice)
            else:
                payload = {
                    "owner": getattr(notice, "owner", "unknown"),
                    "cache_key": getattr(notice, "cache_key", ""),
                    "cache_type": getattr(notice, "cache_type", ""),
                    "summary": getattr(notice, "summary", ""),
                }

            payload.setdefault("owner", getattr(notice, "owner", "unknown"))
            payload.setdefault("cache_key", getattr(notice, "cache_key", ""))
            payload.setdefault("cache_type", getattr(notice, "cache_type", ""))
            payload.setdefault("summary", getattr(notice, "summary", ""))
            structured.append(payload)

        return structured

    # ---------------------------------------------------------------------
    # Cache utility helpers
    # ---------------------------------------------------------------------

    def save_cache(self) -> None:
        """Persist cache to disk if cache system is available."""
        if self.ohcache and self.ohcache.enable_ohcache:
            self.ohcache.cache_system.save()

    @property
    def cache_dir(self) -> str | None:
        """Get the cache directory path."""
        if self.ohcache and self.ohcache.enable_ohcache:
            cache_dir = self.ohcache.cache_system._cache_dir
            return str(cache_dir) if cache_dir else None
        return None

    @property
    def enable_ohcache(self) -> bool:
        """Check if OHCache is enabled."""
        return bool(self.ohcache and self.ohcache.enable_ohcache)

    def _prepare_state_with_context(self, state: AgentState) -> AgentState:
        """Append cached context and hypergraph updates before LLM calls."""

        if not self.ohcache:
            return state

        supplemental_messages = self._collect_context_messages()
        if not supplemental_messages:
            return state

        enriched_state: AgentState = cast("AgentState", dict(state))
        enriched_state["messages"] = supplemental_messages
        return enriched_state

    def _collect_context_messages(self) -> list[BaseMessage]:
        """Collect hypergraph messages for LLM context."""
        if not (self.ohcache and self.ohcache.enable_ohcache):
            return []

        return self.receive_messages(
            as_base_message=True,
            exclude_message_types={"cache_notice"},
        )  # type: ignore[return-value]

    def on_forward_start(self, context: EasyDict) -> EasyDict:
        context = super().on_forward_start(context)
        state = context.get("state")
        if state is not None:
            context.state = self._prepare_state_with_context(state)
        return context


__all__ = ["OHCacheAgentMixin"]
