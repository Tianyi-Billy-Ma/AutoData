"""Prompt package exposing per-agent prompt modules and legacy constants."""

from __future__ import annotations

from . import (
    blueprint_agent,
    browser_agent,
    engineer_agent,
    human_agent,
    plan_agent,
    supervisor_agent,
    test_agent,
    tool_agent,
    validation_agent,
)

PROMPT_MODULES = {
    "blueprint_agent": blueprint_agent,
    "browser_agent": browser_agent,
    "engineer_agent": engineer_agent,
    "human_agent": human_agent,
    "plan_agent": plan_agent,
    "supervisor_agent": supervisor_agent,
    "test_agent": test_agent,
    "tool_agent": tool_agent,
    "validation_agent": validation_agent,
}

PROMPT_BY_AGENT = {name: module.PROMPT for name, module in PROMPT_MODULES.items()}

BLUEPRINT_AGENT_INSTRUCTION = blueprint_agent.PROMPT
BROWSER_AGENT_INSTRUCTION = browser_agent.PROMPT
ENGINEER_AGENT_INSTRUCTION = engineer_agent.PROMPT
HUMAN_AGENT_INSTRUCTION = human_agent.PROMPT
PLAN_AGENT_INSTRUCTION = plan_agent.PROMPT
SUPERVISOR_INSTRUCTION = supervisor_agent.PROMPT
TEST_AGENT_INSTRUCTION = test_agent.PROMPT
TOOL_AGENT_INSTRUCTION = tool_agent.PROMPT
VALIDATION_AGENT_INSTRUCTION = validation_agent.PROMPT

__all__ = [
    "blueprint_agent",
    "browser_agent",
    "engineer_agent",
    "human_agent",
    "plan_agent",
    "supervisor_agent",
    "test_agent",
    "tool_agent",
    "validation_agent",
    "PROMPT_MODULES",
    "PROMPT_BY_AGENT",
    "BLUEPRINT_AGENT_INSTRUCTION",
    "BROWSER_AGENT_INSTRUCTION",
    "ENGINEER_AGENT_INSTRUCTION",
    "HUMAN_AGENT_INSTRUCTION",
    "PLAN_AGENT_INSTRUCTION",
    "SUPERVISOR_INSTRUCTION",
    "TEST_AGENT_INSTRUCTION",
    "TOOL_AGENT_INSTRUCTION",
    "VALIDATION_AGENT_INSTRUCTION",
]
