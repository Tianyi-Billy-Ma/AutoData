"""Plan agent module for AutoData multi-agent system.

This module provides the Plan agent that creates comprehensive data collection strategies
and coordinates the overall workflow for web data collection tasks.
"""

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph.state import logging
from pydantic import BaseModel, Field
from typing_extensions import override

from autodata.agents.base_agent import BaseAgent
from autodata.agents.types import WORKER_INFO
from autodata.configs.api_registry import API_INFO
from autodata.core.ohcache.formatter import PlanAgentResponse
from autodata.prompts import PLAN_AGENT_INSTRUCTION
from autodata.tools.types import TOOL_INFO

logger = logging.getLogger("AutoData.agents")


class PlanAgent(BaseAgent):
    """Plan agent that creates comprehensive data collection strategies and coordinates workflows.

    This agent analyzes requirements and creates detailed plans for data collection projects,
    coordinating between Research Squad and Development Squad agents.
    """

    description: str = "creates comprehensive data collection strategies and coordinates the overall workflow for web data collection tasks"
    agent_name: str = "PlanAgent"
    instruction: str = Field(default=PLAN_AGENT_INSTRUCTION)
    formatter: type[BaseModel] | PydanticOutputParser = Field(default=PlanAgentResponse)

    worker_info: dict[str, str] = Field(default=WORKER_INFO)
    tools_info: dict[str, str] = Field(default=TOOL_INFO)
    api_info: dict[str, str] = Field(default=API_INFO)

    @override
    def _build_prompt(self) -> ChatPromptTemplate:
        plugin_prompt = self._get_plugin_prompt_section()
        return ChatPromptTemplate(
            [
                (
                    "system",
                    "# Instruction:\n{instruction}\n\n"
                    "# Format Instruction:\n{format_instruction}\n\n",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ],
            partial_variables={
                "instruction": self.instruction.format(
                    worker_info="\n".join(
                        [f"- {name}: {desc}" for name, desc in self.worker_info.items()]
                    ),
                    tools_info="\n".join(
                        [f"- {name}: {desc}" for name, desc in self.tools_info.items()]
                    ),
                    api_info="\n".join(
                        [f"- {name}: {desc}" for name, desc in self.api_info.items()]
                    ),
                    plugin_prompt=plugin_prompt,
                ),
                "format_instruction": self.format_instruction,
            },
            input_types={
                "messages": list,
            },
        )

    checkpoint_auto_sync: bool = False
    checkpoint_auto_async: bool = False
