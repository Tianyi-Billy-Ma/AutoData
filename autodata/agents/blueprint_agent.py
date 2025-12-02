"""Blueprint agent module for AutoData multi-agent system.

This module provides the Blueprint agent that generates comprehensive blueprints
for data collection Python scripts based on information from Tool and Browser agents.
"""

import logging

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from autodata.agents.base_agent import BaseAgent
from autodata.core.ohcache.formatter import BlueprintAgentResponse
from autodata.prompts import BLUEPRINT_AGENT_INSTRUCTION

logger = logging.getLogger("AutoData.agents")


class BlueprintAgent(BaseAgent):
    """Blueprint agent that generates comprehensive blueprints for data collection Python scripts.

    This agent analyzes information from Tool and Browser agents to create detailed
    blueprints for data collection workflows and scripts.
    """

    description: str = Field(
        default="BlueprintAgent generates blueprints for data collection python scripts using information from tool and browser agents"
    )
    agent_name: str = Field(default="BlueprintAgent")

    instruction: str = Field(default=BLUEPRINT_AGENT_INSTRUCTION)
    formatter: type[BaseModel] | PydanticOutputParser = Field(
        default=BlueprintAgentResponse
    )
