"""Tool agent module for AutoData multi-agent system.

This module provides the Tool agent that manages and utilizes tools from the
autodata/tools/ directory in the multi-agent system. It binds LangChain tools
to the chat model and, after invoking the chain, executes any returned tool
calls and caches results via OHCache.
"""

import logging
from typing import Any

from easydict import EasyDict
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableBinding
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing_extensions import override

from autodata.agents.base_agent import BaseAgent
from autodata.core.exceptions import AgentStateError
from autodata.core.ohcache.formatter import ToolAgentResponse
from autodata.prompts import TOOL_AGENT_INSTRUCTION

logger = logging.getLogger("AutoData.agents")


class ToolAgent(BaseAgent):
    """Tool agent that manages and utilizes tools from the autodata/tools/ directory.

    This agent is responsible for coordinating tool usage, executing tool operations,
    and providing tool recommendations to other agents in the multi-agent system.
    """

    description: str = "manages and utilizes tools from the autodata/tools/ directory"
    agent_name: str = "ToolAgent"
    instruction: str = Field(default=TOOL_AGENT_INSTRUCTION)
    formatter: type[BaseModel] | PydanticOutputParser = Field(default=ToolAgentResponse)

    # Tool-specific public field
    worker_info: dict[str, Any] | None = None

    def forward_step(self, context: EasyDict) -> EasyDict:  # type: ignore[override]
        """Invoke the model with bound tools, execute tool calls, and cache results."""
        chain = context.get("chain")
        state = context.get("state")
        if chain is None or state is None:
            raise AgentStateError("ToolAgent requires prepared chain and state")

        ai_msg = self._invoke_chain_with_retry(chain, state)
        response = self._handle_model_response(ai_msg)
        context.result = response
        return context

    async def forward_step_async(
        self, context: EasyDict
    ) -> EasyDict:  # type: ignore[override]
        """Asynchronous forward method mirroring the synchronous workflow."""
        chain = context.get("chain")
        state = context.get("state")
        if chain is None or state is None:
            raise AgentStateError("ToolAgent requires prepared chain and state")

        ai_msg = await self._invoke_chain_with_retry_async(chain, state)
        response = await self._handle_model_response_async(ai_msg)
        context.result = response
        return context

    # ------------------------------------------------------------------
    # Helper methods reused by sync and async workflows
    # ------------------------------------------------------------------

    def _handle_model_response(self, msg: Any) -> ToolAgentResponse:
        """Handle model response and execute single tool."""
        tool_calls = getattr(msg, "tool_calls", None) or []

        # Enforce single tool execution
        if len(tool_calls) == 0:
            return ToolAgentResponse(
                tool_name="",
                tool_result={"message": "No tool calls returned by the model."},
                error_message="No tool calls received",
            )

        if len(tool_calls) > 1:
            logger.warning(
                f"Model returned {len(tool_calls)} tool calls. "
                f"ToolAgent executes ONE tool per call. Using only the first tool: {tool_calls[0].get('name')}"
            )

        # Execute single tool
        tool_call = tool_calls[0]
        return self._execute_single_tool(tool_call)

    async def _handle_model_response_async(self, msg: Any) -> ToolAgentResponse:
        """Handle model response and execute single tool asynchronously."""
        tool_calls = getattr(msg, "tool_calls", None) or []

        # Enforce single tool execution
        if len(tool_calls) == 0:
            return ToolAgentResponse(
                tool_name="",
                tool_result={"message": "No tool calls returned by the model."},
                error_message="No tool calls received",
            )

        if len(tool_calls) > 1:
            logger.warning(
                f"Model returned {len(tool_calls)} tool calls. "
                f"ToolAgent executes ONE tool per call. Using only the first tool: {tool_calls[0].get('name')}"
            )

        # Execute single tool
        tool_call = tool_calls[0]
        return await self._execute_single_tool_async(tool_call)

    def _resolve_tool(self, tool_name: str | None) -> BaseTool | None:
        if not tool_name:
            return None
        return next(
            (tool for tool in getattr(self, "tools", []) if tool.name == tool_name),
            None,
        )

    def _cache_tool_result(
        self,
        *,
        tool_name: str,
        call_id: str | None,
        output: Any,
        args: dict[str, Any],
    ) -> None:
        """Cache tool execution result."""
        summary = f"Executed {tool_name} with args {args!r}"
        cache_key = f"tool::{tool_name}::{call_id}" if call_id else f"tool::{tool_name}"
        self.cache_artifact(
            key=cache_key,
            value=output,
            cache_type="tool_result",
            summary=summary,
            tags={tool_name},
        )

    def _execute_single_tool(self, tool_call: dict[str, Any]) -> ToolAgentResponse:
        """Execute a single tool and return ToolAgentResponse directly."""
        args = tool_call.get("args", {}) or {}
        call_id = tool_call.get("id")
        tool_name = tool_call.get("name") or ""

        if not tool_name:
            return ToolAgentResponse(
                tool_name="",
                message={"error": "Tool name missing from tool call"},
                error_message="Tool name missing",
            )

        tool = self._resolve_tool(tool_name)
        if tool is None:
            return ToolAgentResponse(
                tool_name=tool_name,
                message={"error": f"Tool '{tool_name}' not found"},
                error_message=f"Tool '{tool_name}' not found",
            )

        try:
            tool_response = tool.invoke(args)

            # Cache full output
            self._cache_tool_result(
                tool_name=tool_name,
                call_id=call_id,
                output=tool_response,
                args=args,
            )

            return ToolAgentResponse(
                tool_name=tool_name,
                message=tool_response.message,
                error_message=tool_response.error_message,
            )

        except Exception as exc:
            logger.exception(f"Error executing tool {tool_name}")
            return ToolAgentResponse(
                tool_name=tool_name,
                message={"error": str(exc)},
                error_message=str(exc),
            )

    async def _execute_single_tool_async(
        self, tool_call: dict[str, Any]
    ) -> ToolAgentResponse:
        """Execute a single tool asynchronously and return ToolAgentResponse directly."""
        args = tool_call.get("args", {}) or {}
        call_id = tool_call.get("id")
        tool_name = tool_call.get("name") or ""

        if not tool_name:
            return ToolAgentResponse(
                tool_name="",
                message={"error": "Tool name missing from tool call"},
                error_message="Tool name missing from tool call",
            )

        tool = self._resolve_tool(tool_name)
        if tool is None:
            return ToolAgentResponse(
                tool_name=tool_name,
                message={"error": f"Tool '{tool_name}' not found"},
                error_message=f"Tool '{tool_name}' not found",
            )

        try:
            tool_response = await tool.ainvoke(args)

            # Cache full output
            self._cache_tool_result(
                tool_name=tool_name,
                call_id=call_id,
                output=tool_response,
                args=args,
            )

            return ToolAgentResponse(
                tool_name=tool_name,
                message=tool_response.message,
                error_message=tool_response.error_message,
            )

        except Exception as exc:
            logger.exception(f"Error executing tool {tool_name}")
            return ToolAgentResponse(
                tool_name=tool_name,
                message={"error": str(exc)},
                error_message=str(exc),
            )

    @override
    def _build_chain(self) -> None:
        self.prompt = self._build_prompt()

        if self.model is not None and isinstance(
            self.model, BaseChatModel | RunnableBinding
        ):
            # For ToolAgent we avoid an output parser to inspect tool_calls
            self.chain = self.prompt | self.model
        else:
            self.chain = None
