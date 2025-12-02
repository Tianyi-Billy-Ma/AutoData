"""Agent package for AutoData.

This package contains the multi-agent system components for web crawling.
"""

import sys

from .base_agent import BaseAgent
from .blueprint_agent import BlueprintAgent
from .browser_agent import BrowserAgent
from .engineer_agent import EngineerAgent
from .human_agent import HumanAgent
from .plan_agent import PlanAgent
from .supervisor_agent import Supervisor
from .test_agent import TestAgent
from .tool_agent import ToolAgent
from .types import WORKER_INFO, AgentState
from .validation_agent import ValidationAgent

sys.modules[f"{__name__}._types"] = sys.modules[f"{__name__}.types"]

ResearchSquadAgents = [
    "PlanAgent",
    "HumanAgent",
    "ToolAgent",
    "BrowserAgent",
    "BlueprintAgent",
]
DevelopSquadAgents = [
    "EngineerAgent",
    "TestAgent",
    "ValidationAgent",
]

AllWorkerAgents = ResearchSquadAgents + DevelopSquadAgents


# Worker info and AgentState definitions live in types.py

__all__ = [
    "ResearchSquadAgents",
    "DevelopSquadAgents",
    "AllWorkerAgents",
    "WORKER_INFO",
    "AgentState",
    "BaseAgent",
    "BlueprintAgent",
    "BrowserAgent",
    "EngineerAgent",
    "PlanAgent",
    "Supervisor",
    "TestAgent",
    "ToolAgent",
    "ValidationAgent",
    "HumanAgent",
]
