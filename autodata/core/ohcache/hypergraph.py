"""
Oriented Message Hypergraph for OHCache System.

This module provides the OrientedMessageHypergraph class that models inter-agent
message flow as oriented hyperedges, enabling efficient multi-agent communication
and message accumulation in the AutoData system.

The hypergraph structure allows for complex message routing patterns where:
- Nodes represent agents
- Oriented hyperedges represent message flows between multiple agents
- Messages can be accumulated and routed based on hyperedge orientation
"""

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from easydict import EasyDict
from langchain_core.messages import BaseMessage

from autodata.core.ohcache.formatter import BaseResponse

logger = logging.getLogger("AutoData.core")


class OrientedHyperedge:
    """Represents an oriented hyperedge in the message hypergraph.

    An oriented hyperedge connects multiple source agents to multiple target agents,
    allowing for complex message routing patterns in multi-agent systems.
    """

    def __init__(
        self,
        edge_id: str,
        source_agents: set[str],
        target_agents: set[str],
        message_type: str = "default",
        metadata: dict[str, Any] | None = None,
        created_at: float | None = None,
    ):
        """Initialize an oriented hyperedge.

        Args:
            edge_id: Unique identifier for the hyperedge
            source_agents: Set of source agent names
            target_agents: Set of target agent names
            message_type: Type of messages this hyperedge handles
            metadata: Optional metadata for the hyperedge
        """
        self.edge_id = edge_id
        self.source_agents = source_agents
        self.target_agents = target_agents
        self.message_type = message_type
        self.metadata = metadata or {}
        self.sender: str | None = None
        self.message: BaseResponse | None = None
        self.created_at = created_at or time.time()
        self.delivered_targets: set[str] = set()

    def set_message(self, message: BaseResponse, from_agent: str) -> None:
        """Attach a message to this hyperedge.

        Args:
            message: Message payload to attach.
            from_agent: Name of the agent sending the message.
        """
        if self.message is not None:
            raise ValueError("Hyperedge already contains a message")
        self.message = message
        self.sender = from_agent
        self.delivered_targets.clear()
        logger.debug("Set message on hyperedge %s from %s", self.edge_id, from_agent)

    def peek_message(self) -> tuple[str, BaseResponse | BaseMessage] | None:
        """Return the stored sender/message pair without clearing it.

        Returns:
            Tuple of (sender, message) if present, otherwise None.
        """
        if self.message is None or self.sender is None:
            return None
        return (self.sender, self.message)

    def clear_buffer(self) -> None:
        """Clear the message buffer."""
        self.sender = None
        self.message = None
        self.delivered_targets.clear()

    def has_message(self) -> bool:
        """Check if the hyperedge has any messages.

        Returns:
            True if the hyperedge has messages, False otherwise
        """
        return self.message is not None

    def is_source(self, agent_name: str) -> bool:
        """Check if an agent is a source of this hyperedge.

        Args:
            agent_name: Name of the agent to check

        Returns:
            True if the agent is a source, False otherwise
        """
        return agent_name in self.source_agents

    def is_target(self, agent_name: str) -> bool:
        """Check if an agent is a target of this hyperedge.

        Args:
            agent_name: Name of the agent to check

        Returns:
            True if the agent is a target, False otherwise
        """
        return agent_name in self.target_agents

    def to_dict(self) -> dict[str, Any]:
        """Convert the hyperedge to a dictionary representation.

        Returns:
            Dictionary representation of the hyperedge
        """
        return {
            "edge_id": self.edge_id,
            "source_agents": list(self.source_agents),
            "target_agents": list(self.target_agents),
            "message_type": self.message_type,
            "metadata": self.metadata,
            "has_message": self.has_message(),
            "created_at": self.created_at,
        }


class OrientedMessageHypergraph:
    """Oriented message hypergraph for modeling inter-agent communication.

    This class implements a hypergraph structure where:
    - Nodes represent agents in the system
    - Oriented hyperedges represent message flows between agents
    - Messages can be accumulated and routed based on hyperedge orientation
    """

    def __init__(self):
        """Initialize the oriented message hypergraph."""
        self.nodes: set[str] = set()
        self.hyperedges: dict[str, OrientedHyperedge] = {}
        self.agent_to_hyperedges: dict[str, set[str]] = defaultdict(set)
        self.message_history: list[dict[str, Any]] = []

    def add_node(self, agent_name: str) -> None:
        """Add a node (agent) to the hypergraph.

        Args:
            agent_name: Name of the agent to add
        """
        self.nodes.add(agent_name)
        logger.debug(f"Added node: {agent_name}")

    def add_nodes(self, agent_names: list[str]) -> None:
        """Add multiple nodes to the hypergraph.

        Args:
            agent_names: List of agent names to add
        """
        for agent_name in agent_names:
            self.add_node(agent_name)

    def add_hyperedge(
        self,
        edge_id: str,
        source_agents: set[str],
        target_agents: set[str],
        message_type: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add an oriented hyperedge to the hypergraph.

        Args:
            edge_id: Unique identifier for the hyperedge
            source_agents: Set of source agent names
            target_agents: Set of target agent names
            message_type: Type of messages this hyperedge handles
            metadata: Optional metadata for the hyperedge
        """
        # Validate that all agents exist in the hypergraph
        all_agents = source_agents | target_agents
        missing_agents = all_agents - self.nodes
        if missing_agents:
            raise ValueError(f"Agents not found in hypergraph: {missing_agents}")

        # Create the hyperedge
        hyperedge = OrientedHyperedge(
            edge_id=edge_id,
            source_agents=source_agents,
            target_agents=target_agents,
            message_type=message_type,
            metadata=metadata,
            created_at=time.time(),
        )

        self.hyperedges[edge_id] = hyperedge

        # Update agent-to-hyperedge mappings
        for agent in all_agents:
            self.agent_to_hyperedges[agent].add(edge_id)

        logger.debug(f"Added hyperedge {edge_id}: {source_agents} -> {target_agents}")
        return edge_id

    def remove_hyperedge(self, edge_id: str) -> None:
        """Remove a hyperedge from the hypergraph.

        Args:
            edge_id: ID of the hyperedge to remove
        """
        if edge_id not in self.hyperedges:
            logger.warning(f"Hyperedge {edge_id} not found")
            return

        hyperedge = self.hyperedges[edge_id]

        # Update agent-to-hyperedge mappings
        all_agents = hyperedge.source_agents | hyperedge.target_agents
        for agent in all_agents:
            self.agent_to_hyperedges[agent].discard(edge_id)

        del self.hyperedges[edge_id]
        logger.debug(f"Removed hyperedge: {edge_id}")

    def send_message(
        self,
        from_agent: str,
        message: BaseResponse,
        target_agents: set[str] | None = None,
        message_type: str = "default",
    ) -> str:
        """Send a message through the hypergraph.

        Args:
            from_agent: Name of the sending agent
            message: The message to send
            target_agents: Optional set of target agents (if None, uses hyperedge routing)
            message_type: Type of message being sent

        Returns:
            ID of the created hyperedge
        """
        if from_agent not in self.nodes:
            raise ValueError(f"Agent {from_agent} not found in hypergraph")

        if target_agents is None or len(target_agents) == 0:
            raise ValueError(
                "target_agents must be provided when sending messages (no routing templates)"
            )

        new_edge_id = f"msg::{uuid4().hex}"
        new_edge = OrientedHyperedge(
            edge_id=new_edge_id,
            source_agents={from_agent},
            target_agents=set(target_agents),
            message_type=message_type,
            metadata={},
            created_at=time.time(),
        )
        new_edge.set_message(message, from_agent)
        self.hyperedges[new_edge_id] = new_edge
        for agent in new_edge.source_agents | new_edge.target_agents:
            self.agent_to_hyperedges[agent].add(new_edge_id)

        logger.debug("Message from %s created hyperedge %s", from_agent, new_edge_id)

        payload = (
            message.to_dict()
            if isinstance(message, BaseResponse)
            else getattr(message, "to_dict", lambda: str(message))()
        )

        self.message_history.append(
            {
                "edge_id": new_edge_id,
                "source_agent": from_agent,
                "target_agents": list(new_edge.target_agents),
                "message_type": message_type,
                "payload": payload,
                "created_at": new_edge.created_at,
            }
        )

        return new_edge_id

    def receive_messages(
        self,
        agent_name: str,
        message_type: str | None = None,
        clear_buffers: bool = False,
    ) -> list[dict[str, Any]]:
        """Receive messages for a specific agent.

        Args:
            agent_name: Name of the receiving agent
            message_type: Optional filter for message type; if None, all messages are returned
            clear_buffers: Whether to clear hyperedge buffers after receiving

        Returns:
            List of messages for the agent
        """
        if agent_name not in self.nodes:
            raise ValueError(f"Agent {agent_name} not found in hypergraph")

        messages: list[dict[str, Any]] = []

        edges_to_remove: list[str] = []

        ordered_edge_ids = sorted(
            self.agent_to_hyperedges[agent_name],
            key=lambda eid: getattr(self.hyperedges[eid], "created_at", 0.0),
        )

        for edge_id in ordered_edge_ids:
            hyperedge = self.hyperedges[edge_id]
            if not hyperedge.is_target(agent_name):
                continue
            if message_type is not None and hyperedge.message_type != message_type:
                continue
            if not hyperedge.has_message():
                continue
            if agent_name in hyperedge.delivered_targets:
                continue
            # Retrieve without consuming; leave buffers intact unless clear_buffers=True
            payload = hyperedge.peek_message()
            if payload is None:
                continue
            from_agent, message_obj = payload
            messages.append(
                {
                    "from_agent": from_agent,
                    "message": message_obj,
                    "message_type": hyperedge.message_type,
                    "edge_id": edge_id,
                    "created_at": hyperedge.created_at,
                }
            )
            if clear_buffers:
                hyperedge.delivered_targets.add(agent_name)
                if hyperedge.delivered_targets.issuperset(hyperedge.target_agents):
                    edges_to_remove.append(edge_id)

        for edge_id in edges_to_remove:
            self.remove_hyperedge(edge_id)

        logger.debug(f"Agent {agent_name} received {len(messages)} messages")
        return messages

    def get_agent_connections(self, agent_name: str) -> dict[str, Any]:
        """Get connection information for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Dictionary containing connection information
        """
        if agent_name not in self.nodes:
            raise ValueError(f"Agent {agent_name} not found in hypergraph")

        connections = {
            "outgoing_hyperedges": [],
            "incoming_hyperedges": [],
            "connected_agents": set(),
        }

        for edge_id in self.agent_to_hyperedges[agent_name]:
            hyperedge = self.hyperedges[edge_id]

            if hyperedge.is_source(agent_name):
                connections["outgoing_hyperedges"].append(edge_id)
                connections["connected_agents"].update(hyperedge.target_agents)

            if hyperedge.is_target(agent_name):
                connections["incoming_hyperedges"].append(edge_id)
                connections["connected_agents"].update(hyperedge.source_agents)

        # Convert set to list for JSON serialization
        connections["connected_agents"] = list(connections["connected_agents"])

        return connections

    def get_agent_message_types(self, agent_name: str) -> set[str]:
        """Return the set of message types targeting a specific agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Set of message types that can be received by the agent.
        """
        if agent_name not in self.nodes:
            raise ValueError(f"Agent {agent_name} not found in hypergraph")

        message_types: set[str] = set()

        for edge_id in self.agent_to_hyperedges[agent_name]:
            hyperedge = self.hyperedges[edge_id]
            if hyperedge.is_target(agent_name):
                message_types.add(hyperedge.message_type)

        return message_types

    @property
    def hypergraph_stats(self) -> dict[str, Any]:
        """Statistics summarising the hypergraph state."""
        total_messages = sum(
            1 for edge in self.hyperedges.values() if edge.has_message()
        )

        return {
            "node_count": len(self.nodes),
            "hyperedge_count": len(self.hyperedges),
            "total_buffered_messages": total_messages,
            "message_history_length": len(self.message_history),
            "nodes": list(self.nodes),
            "hyperedges": {
                edge_id: edge.to_dict() for edge_id, edge in self.hyperedges.items()
            },
        }

    def clear_all_buffers(self) -> None:
        """Clear all message buffers in the hypergraph."""
        dynamic_edges = [
            edge_id for edge_id, edge in self.hyperedges.items() if edge.has_message()
        ]
        for edge_id in dynamic_edges:
            self.remove_hyperedge(edge_id)
        logger.debug("Cleared all message-carrying hyperedges")

    def to_easydict(self) -> EasyDict:
        """Convert the hypergraph to EasyDict format.

        Returns:
            EasyDict representation of the hypergraph
        """
        return EasyDict(self.hypergraph_stats)

    # ------------------------------------------------------------------
    # Ledger utilities
    # ------------------------------------------------------------------

    def export_message_history(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self.message_history]

    def write_ledger(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.export_message_history(), handle, indent=2, sort_keys=True)


# Export classes
__all__ = ["OrientedHyperedge", "OrientedMessageHypergraph"]
