"""Agent-related exception definitions."""

from __future__ import annotations

from .base import AutoDataError


class AgentError(AutoDataError):
    """Base exception for agent execution failures."""

    default_code = "agent_error"


class AgentConfigurationError(AgentError):
    """Raised when agent configuration is invalid or incomplete."""

    default_code = "agent_configuration_error"
    default_message = "Agent configuration is invalid."


class AgentTimeoutError(AgentError):
    """Raised when an agent execution times out."""

    default_code = "agent_timeout_error"
    default_message = "Agent execution timed out."


class AgentExecutionError(AgentError):
    """Raised when an agent fails during execution."""

    default_code = "agent_execution_error"
    default_message = "Agent execution failed."


class AgentDependencyError(AgentError):
    """Raised when required agent dependencies are missing."""

    default_code = "agent_dependency_error"
    default_message = "Agent dependencies are unavailable."


class AgentStateError(AgentError):
    """Raised when an agent receives an invalid or missing state payload."""

    default_code = "agent_state_error"
    default_message = "Agent state is missing or malformed."


__all__ = [
    "AgentError",
    "AgentConfigurationError",
    "AgentTimeoutError",
    "AgentExecutionError",
    "AgentDependencyError",
    "AgentStateError",
]
