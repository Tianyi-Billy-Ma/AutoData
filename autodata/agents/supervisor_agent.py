"""Supervisor agent module for AutoData multi-agent system.

This module provides the Supervisor agent that coordinates and manages the workflow
between different worker agents in the system.
"""

import logging

from easydict import EasyDict
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing_extensions import override

from autodata.agents.base_agent import BaseAgent
from autodata.agents.types import WORKER_INFO
from autodata.configs.api_registry import API_INFO
from autodata.core.ohcache.formatter import SupervisorResponse
from autodata.prompts import SUPERVISOR_INSTRUCTION
from autodata.tools.types import TOOL_INFO

logger = logging.getLogger("AutoData.agents")


class Supervisor(BaseAgent):
    """Supervisor agent that coordinates and manages workflow between different worker agents.

    This agent is responsible for task delegation, progress monitoring, and decision routing
    with the ability to finish tasks when complete.
    """

    # ============================================================================
    # Class Fields
    # ============================================================================

    description: str = "supervises the task process"
    agent_name: str = "SupervisorAgent"
    instruction: str = Field(default=SUPERVISOR_INSTRUCTION)
    formatter: type[BaseModel] | PydanticOutputParser = Field(
        default=SupervisorResponse
    )
    enable_think_stage: bool = False

    # Private attributes for supervisor-specific functionality
    worker_info: dict[str, str] = Field(default=WORKER_INFO)
    tools_info: dict[str, str] = Field(default=TOOL_INFO)
    api_info: dict[str, str] = Field(default=API_INFO)
    options: list[str] = Field(default=["[FINISH]", *WORKER_INFO.keys()])

    # =========================================================================
    # Protected Methods - Overrides
    # =========================================================================

    @override
    def _build_prompt(self) -> ChatPromptTemplate:
        """Build the supervisor-specific prompt template."""
        if not self.worker_info:
            raise ValueError("Worker info is required for supervisor agent")

        return ChatPromptTemplate(
            [
                (
                    "system",
                    "# INSTRUCTION:\n{instruction}\n\n"
                    "# FORMAT INSTRUCTION:\n{format_instruction}\n\n",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ],
            partial_variables={
                "instruction": self.instruction.format(
                    workers=", ".join(self.worker_info.keys()),
                    worker_info="\n".join(
                        [f"- {name}: {desc}" for name, desc in self.worker_info.items()]
                    ),
                    tools_info="\n".join(
                        [f"- {name}: {desc}" for name, desc in self.tools_info.items()]
                    ),
                    api_info="\n".join(
                        [f"- {name}: {desc}" for name, desc in self.api_info.items()]
                    ),
                    options=", ".join(self.options),
                    plugin_prompt=self._get_plugin_prompt_section(),
                ),
                "format_instruction": self.format_instruction,
            },
            input_types={"messages": list[BaseMessage]},
        )

    def on_forward_end(self, context: EasyDict) -> EasyDict:
        """Customize final response metadata for supervisor routing."""

        if context.get("exception") is None:
            result: SupervisorResponse | None = context.get("result")
            if result is not None:
                next_agent = getattr(result, "next", "Supervisor")
                context["next_agent"] = next_agent
                context["message_type"] = "supervisor"
                context["target_agents"] = {next_agent, self.agent_name}

        return super().on_forward_end(context)

    async def on_forward_end_async(self, context: EasyDict) -> EasyDict:
        """Async customization mirroring the sync flow."""

        if context.get("exception") is None:
            result: SupervisorResponse | None = context.get("result")
            if result is not None:
                next_agent = getattr(result, "next", "Supervisor")
                context["next_agent"] = next_agent
                context["message_type"] = "supervisor"
                context["target_agents"] = {next_agent}

        return await super().on_forward_end_async(context)

    @override
    def _bind_tools(self, tools: BaseTool | list[BaseTool]) -> None:
        """Bind tools to the model and rebuild the chain."""
        self._build_chain()
