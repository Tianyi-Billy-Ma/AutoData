"""Utilities for logging agent routing decisions."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from autodata.core.exceptions.storage import PathGovernanceError

logger = logging.getLogger("AutoData.core")


class BaseAgentProtocol(Protocol):
    """Protocol describing agent surface needed for routing logs."""

    agent_name: str
    config: Any


def _resolve_routing_log_path(agent: BaseAgentProtocol) -> Path:
    """Resolve the ROUTING.log path based on agent configuration."""

    config = getattr(agent, "config", None)
    if config is None:
        raise PathGovernanceError(
            "Routing logger requires agent config",
            hint="Ensure agent has config attribute with log_dir or run_dir",
        )

    log_dir = getattr(config, "log_dir", None)
    if log_dir is None and isinstance(config, dict):
        log_dir = config.get("log_dir")
    if log_dir:
        return Path(log_dir) / "ROUTING.log"

    run_dir = getattr(config, "run_dir", None)
    if run_dir is None and isinstance(config, dict):
        run_dir = config.get("run_dir")
    if run_dir:
        return Path(run_dir) / "logs" / "ROUTING.log"

    raise PathGovernanceError(
        "Routing logger requires log_dir or run_dir in config",
        hint="Ensure AutoDataConfig provides log_dir or run_dir",
    )


def _extract_routing_info(result: Any) -> dict | None:
    """Extract routing metadata from an agent response payload."""

    if not isinstance(result, dict):
        return None

    if "next" not in result or "sender" not in result:
        return None

    messages = result.get("messages", [])
    preview = ""
    if messages:
        first_msg = messages[0]
        if hasattr(first_msg, "content"):
            preview = str(first_msg.content)
        elif isinstance(first_msg, dict) and "content" in first_msg:
            preview = str(first_msg["content"])
        else:
            preview = str(first_msg)

    return {
        "sender": result["sender"],
        "next_agent": result["next"],
        "targets": result.get("target_agents", {result["next"]}),
        "message_type": result.get("message_type", "routing"),
        "hyperedges": result.get("hyperedges", []),
        "preview": preview,
    }


def log_routing_decision(agent: BaseAgentProtocol, payload: Any) -> None:
    """Append a routing log entry if payload contains routing metadata."""

    routing_info = _extract_routing_info(payload)
    if not routing_info:
        return

    try:
        log_path = _resolve_routing_log_path(agent)
        entry = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "sender": routing_info["sender"],
            "next_agent": routing_info["next_agent"],
            "targets": sorted(routing_info["targets"]),
            "message_type": routing_info["message_type"],
            "hyperedges": list(routing_info["hyperedges"]),
            "preview": routing_info["preview"][:280],
        }

        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry))
            handle.write("\n")
    except (PathGovernanceError, OSError) as err:  # pragma: no cover - best effort
        logger.warning(
            "Failed to write routing log for %s: %s",
            getattr(agent, "agent_name", agent.__class__.__name__),
            err,
        )


__all__ = [
    "log_routing_decision",
]
