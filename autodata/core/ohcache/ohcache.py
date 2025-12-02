"""
OHCache Integration Module.

This module provides integration between the OHCache system and the existing
AutoData multi-agent system, enabling seamless communication and caching
in the BaseAgent and AutoDataGraph classes.
"""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from easydict import EasyDict

from autodata.core.mixins.ohcache_mixin import OHCacheAgentMixin

if TYPE_CHECKING:
    from autodata.core.config import OHCacheConfig
    from autodata.core.graph import AutoDataGraph
from autodata.core.ohcache.cache import CacheEntry, LocalCacheSystem
from autodata.core.ohcache.formatter import BaseResponse, CacheNotice
from autodata.core.ohcache.hypergraph import OrientedMessageHypergraph

logger = logging.getLogger("AutoData.core")


class OHCache:
    """Integration class for OHCache system with AutoData agents.

    This class provides methods to integrate the OHCache system (hypergraph
    and cache) with the existing BaseAgent and AutoDataGraph infrastructure.
    """

    def __init__(
        self,
        config: "OHCacheConfig",
    ):
        """Initialize OHCache integration.

        Args:
            config: OHCache configuration (required)
        """
        # Use provided config
        self.config = config
        self.enable_ohcache = config.enable_ohcache

        # Initialize components
        self.cache_system = LocalCacheSystem(
            cache_dir=config.cache_dir,
            auto_cleanup=config.auto_cleanup,
        )
        self.hypergraph = OrientedMessageHypergraph()
        # Simple routing map: source agent -> set(target agents)
        self.routing_map: dict[str, set[str]] = {}

        # Artifact tracking
        self._new_artifact_keys: list[str] = []
        self._reuse_counters: dict[str, int] = {}
        self._reused_keys: list[str] = []
        self._reuse_events: list[dict[str, Any]] = []

        logger.info("OHCache integration initialized (enabled=%s)", self.enable_ohcache)

    # ------------------------------------------------------------------
    # Unified Cache Interface
    # ------------------------------------------------------------------

    def set_cache(
        self,
        key: str,
        value: Any,
        *,
        cache_type: str = "general",
        metadata: dict[str, Any] | None = None,
        ttl: int | None = None,
        tags: set[str] | None = None,
    ) -> None:
        """Set value in cache with simple key.

        This is the unified interface for caching artifacts. Use this method
        instead of accessing cache_system.set() directly.

        Args:
            key: Unique cache key (should be descriptive and specific)
            value: Value to cache
            cache_type: Type of cached content (metadata for filtering)
            metadata: Optional metadata about the entry
            ttl: Time to live in seconds (None for no expiration)
            tags: Optional tags for categorization
        """
        self.cache_system.set(
            key=key,
            value=value,
            cache_type=cache_type,
            metadata=metadata or {},
            ttl=ttl,
            tags=tags,
        )

        if key not in self._new_artifact_keys:
            self._new_artifact_keys.append(key)

    def get_cache(self, key: str, *, default: Any = None) -> Any:
        """Get value from cache.

        This is the unified interface for retrieving cached artifacts.
        Use this method instead of accessing cache_system.get() directly.

        Args:
            key: Cache key to retrieve
            default: Default value if key not found

        Returns:
            The cached value or default
        """
        return self.cache_system.get(key=key, cache_type="general", default=default)

    def get_cache_entry(
        self, key: str, *, cache_type: str = "general"
    ) -> CacheEntry | None:
        return self.cache_system.get_entry(key=key, cache_type=cache_type)

    # ------------------------------------------------------------------
    # Hypergraph Message Retrieval
    # ------------------------------------------------------------------

    def get_agent_hypergraph_messages(
        self,
        agent_name: str,
        *,
        message_types: set[str] | None = None,
        clear_buffers: bool = False,
    ) -> list[dict[str, Any]]:
        """Collect hypergraph messages destined for the provided agent.

        Args:
            agent_name: Name of the agent receiving messages.
            message_types: Optional subset of message types to retrieve.
            clear_buffers: Whether to clear the hypergraph buffers after retrieval.

        Returns:
            List of dictionaries containing ``from_agent``, ``message_type``, ``edge_id``,
            and ``message`` (the BaseResponse instance).
        """
        if not self.enable_ohcache:
            return []

        aggregated: list[dict[str, Any]] = []

        if not message_types:
            aggregated = self.hypergraph.receive_messages(
                agent_name=agent_name,
                message_type=None,
                clear_buffers=clear_buffers,
            )
        else:
            filtered_types = {mt for mt in message_types if mt}
            if not filtered_types:
                aggregated = self.hypergraph.receive_messages(
                    agent_name=agent_name,
                    message_type=None,
                    clear_buffers=clear_buffers,
                )
            else:
                for message_type in filtered_types:
                    aggregated.extend(
                        self.hypergraph.receive_messages(
                            agent_name=agent_name,
                            message_type=message_type,
                            clear_buffers=clear_buffers,
                        )
                    )

        aggregated.sort(key=lambda item: item.get("created_at", 0.0))

        return aggregated

    def receive_cache_notices(
        self,
        agent_name: str,
        *,
        clear_buffers: bool = False,
    ) -> list[CacheNotice]:
        """Return cache notices destined for the given agent."""

        if not self.enable_ohcache:
            return []

        payloads = self.get_agent_hypergraph_messages(
            agent_name,
            message_types={"cache_notice"},
            clear_buffers=clear_buffers,
        )

        notices: list[CacheNotice] = []
        for payload in payloads:
            message = payload.get("message")
            owner = payload.get("from_agent", "unknown")
            if isinstance(message, CacheNotice):
                update_owner = owner if getattr(message, "owner", "unknown") == "unknown" else message.owner
                notices.append(
                    message.model_copy(update={"owner": update_owner})
                )
            elif isinstance(message, dict):
                notices.append(
                    CacheNotice(
                        owner=owner,
                        cache_key=message.get("cache_key"),
                        cache_type=message.get("cache_type"),
                        summary=message.get("summary"),
                    )
                )

        return notices

    def setup_agent_caching(self, agent: "AgentProtocol") -> None:
        """Set up caching capabilities for an agent.

        Args:
            agent: The agent to set up caching for
        """
        if not self.enable_ohcache:
            return

        # Add cache-related reference to the agent
        agent.ohcache = self

        logger.debug(f"Set up caching for agent: {agent.agent_name}")

    def setup_agent_hypergraph(self, agent: "AgentProtocol") -> None:
        """Set up hypergraph communication for an agent.

        Args:
            agent: The agent to set up hypergraph communication for
        """
        if not self.enable_ohcache:
            return

        # Add the agent to the hypergraph
        self.hypergraph.add_node(agent.agent_name)

        # Note: send_message and receive_messages are now provided by OHCacheAgentMixin
        # The legacy instance methods have been removed in favor of mixin methods

        logger.debug(f"Set up hypergraph communication for agent: {agent.agent_name}")

    def setup_agent_integration(self, agent: "AgentProtocol") -> None:
        """Set up complete OHCache integration for an agent.

        Args:
            agent: The agent to set up integration for
        """
        # Always attach the OHCache pointer so mixins can access it
        agent.ohcache = self

        # Install feature-specific integrations
        self.setup_agent_caching(agent)
        self.setup_agent_hypergraph(agent)

        # Mark as integrated (for introspection)
        agent.ohcache_enabled = True

        logger.info(
            f"Set up complete OHCache integration for agent: {agent.agent_name}"
        )

    def setup_graph_integration(self, graph: "AutoDataGraph") -> None:
        """Set up OHCache integration for an AutoDataGraph.

        Args:
            graph: The graph to set up integration for
        """
        # Add all agents from the graph to the hypergraph
        agent_names = list(graph.node_names)
        self.hypergraph.add_nodes(agent_names)

        # Set up integration for each agent (handle StateNodeSpec wrappers)
        for node_name, node_obj in graph.nodes.items():
            agent = self._resolve_agent_instance(node_obj)
            if agent is not None and hasattr(agent, "agent_name"):
                self.setup_agent_integration(agent)
            else:
                raise TypeError(
                    f"Node '{node_name}' is not resolvable to an agent instance; got: {type(node_obj).__name__}"
                )

        # Build a simple routing map from config (no template hyperedges)
        try:
            known_agents = set(graph.node_names)
            routing: dict[str, set[str]] = {}
            for item in self.config.hyperedges or []:
                for src in item.source:
                    if src not in known_agents:
                        logger.debug("Routing: skipping unknown source agent '%s'", src)
                        continue
                    targets = {t for t in item.target if t in known_agents and t != src}
                    if not targets:
                        continue
                    bucket = routing.setdefault(src, set())
                    bucket.update(targets)
            self.routing_map = routing
            logger.info(
                "OHCache routing map initialized with %d sources", len(self.routing_map)
            )
        except Exception as e:
            logger.error(f"Failed to build routing map from config: {e}")

        # Attach integration
        graph.ohcache = self
        graph.ohcache_enabled = True

        logger.info(
            f"Set up OHCache integration for graph with {len(agent_names)} agents"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_agent_instance(self, node_obj: Any) -> "AgentProtocol | None":
        """Resolve an AgentProtocol instance from a graph node spec or wrapper.

        Supports common patterns:
        - Direct AgentProtocol instance
        - Node spec exposing `.runnable`
        - Runnable bound agent under `.bound`, `.node`, `.obj`, `.target`
        - Runnable function with `__self__` (bound methods) or captured in closure
        - Fallback attributes on node spec: `.node`, `.value`
        """
        # Direct instance or compatible object exposing agent_name
        if hasattr(node_obj, "agent_name") and hasattr(node_obj, "forward"):
            return node_obj

        # Access runnable
        runnable = getattr(node_obj, "runnable", None)

        # Runnable could itself be the agent
        if (
            runnable
            and hasattr(runnable, "agent_name")
            and hasattr(runnable, "forward")
        ):
            return runnable

        # Common attributes on runnable wrappers
        for attr in ["func", "afunc"]:
            candidate = getattr(runnable, attr, None)
            if (
                candidate
                and hasattr(candidate, "agent_name")
                and hasattr(candidate, "forward")
            ):
                return candidate

        return None

    # Removed: cache_agent_response(...) in favor of direct use of cache_system
    # via `ohcache.cache_system.set(...)` when needed.

    # Note: Previously provided a get_cached_responses(...) helper to proxy cache queries.
    # It was unused by the core system and removed to simplify the API. Use
    # `ohcache.cache_system.get_by_type(...)` or `get_by_tags(...)` directly if needed.

    def broadcast_message(
        self,
        from_agent: str,
        message: BaseResponse,
        target_agents: set[str] | None = None,
        message_type: str = "broadcast",
    ) -> EasyDict:
        """Broadcast using explicit targets or routing_map fallback.

        Returns:
            EasyDict with ``hyperedges`` (list[str]) and ``target_agents`` (set[str]).
        """

        metadata = EasyDict(
            {
                "hyperedge_id": None,
                "hyperedges": [],
                "target_agents": set(),
            }
        )

        if not self.enable_ohcache:
            return metadata

        if target_agents is not None:
            resolved_targets = set(target_agents)
        else:
            resolved_targets = set(self.routing_map.get(from_agent, set()))

        if not resolved_targets:
            logger.debug(
                "No targets resolved for '%s'; message_type='%s'",
                from_agent,
                message_type,
            )
            return metadata

        hyperedge_id = self.hypergraph.send_message(
            from_agent=from_agent,
            message=message,
            target_agents=resolved_targets,
            message_type=message_type,
        )

        metadata.hyperedge_id = hyperedge_id
        metadata.hyperedges = [hyperedge_id] if hyperedge_id else []
        metadata.target_agents = set(resolved_targets)
        return metadata

    def publish_cache_notice(
        self,
        *,
        owner: str,
        cache_key: str,
        cache_type: str,
        summary: str,
        target_agents: set[str] | None = None,
    ) -> None:
        """Emit a cache notice message through the hypergraph."""

        if not (self.enable_ohcache and summary):
            return

        notice = CacheNotice(
            owner=owner,
            cache_key=cache_key,
            cache_type=cache_type,
            summary=summary,
        )

        if target_agents is None:
            target_agents = set(self.hypergraph.nodes)

        if not target_agents:
            return

        self.hypergraph.send_message(
            from_agent=owner,
            message=notice,
            target_agents=target_agents,
            message_type="cache_notice",
        )

    @property
    def integration_stats(self) -> dict[str, Any]:
        """Statistics describing the OHCache integration."""
        stats = {
            "ohcache_enabled": self.enable_ohcache,
        }

        if self.enable_ohcache:
            stats["cache_stats"] = self.cache_system.stats
            stats["hypergraph_stats"] = self.hypergraph.hypergraph_stats
            stats["reuse_summary"] = self.get_reuse_summary()

        return stats

    def to_easydict(self) -> EasyDict:
        """Convert integration to EasyDict format.

        Returns:
            EasyDict representation of the integration
        """
        return EasyDict(self.integration_stats)

    # ------------------------------------------------------------------
    # Artifact reuse tracking
    # ------------------------------------------------------------------

    def record_artifact_reuse(self, key: str, agent: str | None = None) -> None:
        if key not in self._reuse_counters:
            self._reuse_counters[key] = 0
        self._reuse_counters[key] += 1

        if key not in self._reused_keys:
            self._reused_keys.append(key)

        self._reuse_events.append(
            {
                "key": key,
                "agent": agent,
                "timestamp": time.time(),
            }
        )

    def get_reuse_summary(self) -> dict[str, Any]:
        total_reuse_events = sum(self._reuse_counters.values())
        return {
            "new_artifacts": list(self._new_artifact_keys),
            "reused_artifacts": list(self._reused_keys),
            "reuse_counts": dict(self._reuse_counters),
            "total_reuse_events": total_reuse_events,
            "reuse_events": list(self._reuse_events[-20:]),
        }

    # ------------------------------------------------------------------
    # Hyperedge ledger utilities
    # ------------------------------------------------------------------

    def export_hyperedge_ledger(self) -> list[dict[str, Any]]:
        return self.hypergraph.export_message_history()

    def write_hyperedge_ledger(self, path: Path) -> None:
        self.hypergraph.write_ledger(path)


# Export classes
__all__ = ["OHCache", "OHCacheAgentMixin"]
