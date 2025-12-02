"""Base agent class for AutoData multi-agent system.

This module provides the foundation for all agent types in the system.
"""

from __future__ import annotations

import logging
from typing import Any

from easydict import EasyDict
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableBinding
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from autodata.agents.types import AgentState
from autodata.core.exceptions import AutoDataModelError
from autodata.core.mixins.checkpoint_mixin import CheckpointAgentMixin
from autodata.core.mixins.log_mixin import LogMixin
from autodata.core.mixins.ohcache_mixin import OHCacheAgentMixin
from autodata.core.mixins.think_mixin import ThinkAgentMixin
from autodata.plugins import collect_plugin_prompts, load_enabled_plugins
from autodata.tools import BASE_TOOL_CLASSES
from autodata.tools.types import merge_tool_info
from autodata.utils.type_utils import to_easydict

logger = logging.getLogger("AutoData.agents")


class BaseAgent(
    CheckpointAgentMixin,
    ThinkAgentMixin,
    OHCacheAgentMixin,
    LogMixin,
    BaseModel,
):
    """Base agent class for AutoData multi-agent system.

    This class provides the foundation for all agent types in the system,
    including chain building, model management, and response handling.
    """

    # ============================================================================
    # Class Fields
    # ============================================================================

    # Public fields - accessible to external code
    description: str
    agent_name: str

    # Private fields - internal implementation details
    instruction: str = Field()
    formatter: BaseModel | PydanticOutputParser = Field()
    model: BaseChatModel | None = Field(default=None)
    config: Any = Field(default_factory=EasyDict)
    tools: list[BaseTool] = Field(default_factory=list)

    # Internal state - computed fields
    output_parser: PydanticOutputParser = Field(init=False, default=None)
    format_instruction: str = Field(init=False, default="")
    chain: Runnable | None = Field(init=False, default=None)
    prompt: ChatPromptTemplate = Field(init=False, default=None)

    checkpoint_auto_sync: bool = True
    checkpoint_auto_async: bool = True

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "extra": "allow",
    }

    # ============================================================================
    # Magic Methods
    # ============================================================================

    def __init__(self, **data: Any) -> None:
        """Initialize the agent with Pydantic validation."""
        super().__init__(**data)
        # Normalise configuration into EasyDict form for downstream use
        self.config = to_easydict(self.config)
        self._initialise_checkpointing(self.config)

        # Load plugin specifications and cache prompt/tool metadata
        plugin_config = getattr(self.config, "plugin_config", None)
        if plugin_config is None:
            plugin_config = to_easydict({"enabled_plugins": []})
            self.config.plugin_config = plugin_config

        enabled_plugins = list(getattr(plugin_config, "enabled_plugins", []) or [])
        plugin_config.enabled_plugins = enabled_plugins

        plugin_specs = getattr(self.config, "_plugin_specs", None)
        if plugin_specs is None:
            plugin_specs = load_enabled_plugins(enabled_plugins)
            try:
                self.config._plugin_specs = plugin_specs
            except Exception:  # pragma: no cover - config may be immutable
                pass

        self._plugin_prompts = collect_plugin_prompts(plugin_specs)
        self._plugin_prompt_text = self._build_plugin_prompt_text()
        self._plugin_prompt_section = self._build_plugin_prompt_section()

        # Merge tool info metadata for agents that expose tools_info
        if hasattr(self, "tools_info"):
            extra_tool_info: dict[str, str] = {}
            for spec in plugin_specs:
                metadata = getattr(spec, "metadata", {}) or {}
                tool_info = (
                    metadata.get("tool_info") if isinstance(metadata, dict) else None
                )
                if isinstance(tool_info, dict):
                    extra_tool_info.update(tool_info)
            if extra_tool_info:
                self.tools_info = merge_tool_info(extra_tool_info)

        # Initialize computed fields
        self.output_parser = (
            PydanticOutputParser(pydantic_object=self.formatter)
            if not isinstance(self.formatter, PydanticOutputParser)
            else self.formatter
        )
        self.format_instruction = self.output_parser.get_format_instructions()
        self.chain = None

        # Build the LCEL chain
        self._build_chain()
        tool_cfg = getattr(self.config, "tool_config", EasyDict())
        resolved_tool_config = (
            to_easydict(tool_cfg) if tool_cfg is not None else EasyDict()
        )

        base_tool_classes = tuple(
            getattr(self.config, "_base_tool_classes", BASE_TOOL_CLASSES)
        )
        plugin_tool_classes = _filter_plugin_tools(base_tool_classes, plugin_specs)
        tool_classes = base_tool_classes + plugin_tool_classes

        self.tools = [
            tool_obj(config=resolved_tool_config) for tool_obj in tool_classes
        ]
        if self.tools and self.model:
            self._bind_tools(self.tools)

    def __call__(self, state: AgentState) -> dict:
        """Synchronous call method for the agent."""
        assert isinstance(self.model, BaseChatModel | RunnableBinding), (
            "Please provide valid LLM."
        )

        response = self.forward(state)
        # Return only the delta; LangGraph handles aggregation
        return response

    async def __acall__(self, state: AgentState) -> dict:
        """Async call method for the agent."""
        assert isinstance(self.model, BaseChatModel), "Please provide valid LLM."
        response = await self.aforward(state)
        # Return only the delta; LangGraph handles aggregation
        return response

    # ============================================================================
    # Public Methods
    # ============================================================================

    def forward(
        self, state: AgentState, model: BaseChatModel | None = None
    ) -> EasyDict:
        """
        Forward pass through the agent chain.

        Args:
            state: The agent state containing messages
            model: Optional model override

        Returns:
            EasyDict containing the agent response. Routing-aware callers MUST include
            the following keys for downstream logging:
            - ``messages``: list[BaseMessage] containing the outbound messages
            - ``sender``: str identifying the current agent (typically ``self.agent_name``)
            - ``next``: str name of the next agent or ``"[FINISH]"``
            - ``target_agents`` (optional): set/list of recipients; defaults to ``{next}``
            - ``message_type`` (optional): classification string (defaults to ``"routing"``)
            - ``hyperedges`` (optional): list of OHCache correlation identifiers

        Notes:
            Agents that do not participate in routing may omit ``next``/``sender``;
            the routing logger will gracefully skip logging in that case.
        """
        context = EasyDict(
            {
                "state": state,
                "model": model,
                "auto_checkpoint": getattr(self, "checkpoint_auto_sync", True),
                "result": None,
                "response": None,
                "exception": None,
            }
        )

        try:
            context = self.on_forward_start(context)
            context = self.forward_step(context)
        except Exception as exc:  # noqa: BLE001
            context.exception = exc
            try:
                context = self.on_forward_end(context)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Error finalising forward hooks for %s after failure",
                    self.agent_name,
                )
            logger.exception("Error in %s forward pass", self.agent_name)
            return self._create_error_response(
                f"Error in {self.agent_name.lower()} agent forward: {str(exc)}"
            )

        context.exception = None
        context = self.on_forward_end(context)
        return context.response

    async def aforward(
        self, state: AgentState, model: BaseChatModel | None = None
    ) -> EasyDict:
        """
        Asynchronous forward pass through the agent chain.

        Args:
            state: The agent state containing messages
            model: Optional model override

        Returns:
            EasyDict containing the agent response following the same routing contract
            outlined in ``forward()`` (``messages``, ``sender``, ``next``, optional
            ``target_agents``/``message_type``/``hyperedges``). Missing routing keys are
            treated as non-routing responses and will not emit log entries.
        """
        context = EasyDict(
            {
                "state": state,
                "model": model,
                "auto_checkpoint": getattr(self, "checkpoint_auto_async", True),
                "result": None,
                "response": None,
                "exception": None,
            }
        )

        try:
            context = await self.on_forward_start_async(context)
            context = await self.forward_step_async(context)
        except Exception as exc:  # noqa: BLE001
            context.exception = exc
            try:
                context = await self.on_forward_end_async(context)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Error finalising async forward hooks for %s after failure",
                    self.agent_name,
                )
            logger.exception("Error in %s async forward pass", self.agent_name)
            return self._create_error_response(
                f"Error in {self.agent_name.lower()} agent async forward: {str(exc)}"
            )

        context.exception = None
        context = await self.on_forward_end_async(context)
        return context.response

    # ============================================================================
    # Protected Methods - Chain Building
    # ============================================================================

    # -------------------------------------------------------------------------
    # Hook stages
    # -------------------------------------------------------------------------

    def on_forward_start(self, context: EasyDict) -> EasyDict:
        """Hook: prepare execution context before invoking the chain."""

        requested_model = context.get("model")
        current_model = self._validate_model(requested_model)
        context.model = current_model

        context = super().on_forward_start(context)

        if context.get("chain") is None:
            context.chain = self._get_chain(current_model)

        return context

    async def on_forward_start_async(self, context: EasyDict) -> EasyDict:
        """Async hook: prepare execution context."""

        requested_model = context.get("model")
        current_model = self._validate_model(requested_model)
        context.model = current_model

        context = await super().on_forward_start_async(context)

        if context.get("chain") is None:
            context.chain = self._get_chain(current_model)

        return context

    def forward_step(self, context: EasyDict) -> EasyDict:
        """Hook: invoke the model chain."""

        return super().forward_step(context)

    async def forward_step_async(self, context: EasyDict) -> EasyDict:
        """Async hook: invoke the model chain."""

        return await super().forward_step_async(context)

    def on_forward_end(self, context: EasyDict) -> EasyDict:
        """Hook: finalize the response payload."""

        return super().on_forward_end(context)

    async def on_forward_end_async(self, context: EasyDict) -> EasyDict:
        """Async hook: finalize response payload."""

        return await super().on_forward_end_async(context)

    def _build_prompt(self) -> ChatPromptTemplate:
        """Build the chat prompt template."""
        system_message = self._resolve_system_message()

        return ChatPromptTemplate(
            [
                (
                    "system",
                    "You are a helpful AI agent, collaborating with other assistants.\n"
                    "Remember to focus on your given task only, and do not do any works if not requested.\n\n"
                    "# TASK INSTRUCTION:\n{system_message}\n\n"
                    "# FORMAT INSTRUCTION:\n{format_instruction}\n\n",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ],
            partial_variables={
                "system_message": system_message,
                "format_instruction": self.format_instruction,
            },
            input_types={
                "system_message": str,
                "format_instruction": str,
                "messages": list[BaseMessage],
            },
        )

    def _build_chain(self) -> None:
        """Build the LCEL chain for the agent."""
        self.prompt = self._build_prompt()

        # Create the base chain: prompt | model | parser
        if self.model is None or not isinstance(
            self.model, BaseChatModel | RunnableBinding
        ):
            raise AutoDataModelError("Model must be initialized before building chain")

        self.chain = self.prompt | self.model | self.output_parser

        # Invalidate cached think chain when the primary chain is rebuilt.
        self.think_chain = None

    def _bind_tools(self, tools: BaseTool | list[BaseTool]) -> None:
        """Bind tools to the model and rebuild the chain."""
        if isinstance(self.model, BaseChatModel):
            self.model = self.model.bind_tools(
                tools if isinstance(tools, list) else [tools]
            )
            # Rebuild the chain with the updated model
            self._build_chain()
        else:
            raise ValueError("Model not initialized")

    def _update_model(self, model: BaseChatModel) -> None:
        """Update the model and rebuild the chain."""
        self.model = model
        self._build_chain()

    # -------------------------------------------------------------------------
    # Plugin helpers
    # -------------------------------------------------------------------------

    def _resolve_system_message(self) -> str:
        """Inject plugin prompt text into the base instruction if applicable."""

        instruction = self.instruction
        plugin_prompt_section = self._get_plugin_prompt_section()

        if "{plugin_prompt}" in instruction:
            return instruction.replace("{plugin_prompt}", plugin_prompt_section)

        if plugin_prompt_section:
            return f"{instruction}\n\n{plugin_prompt_section}".strip()

        return instruction

    def _get_plugin_prompt_section(self) -> str:
        return getattr(self, "_plugin_prompt_section", "")

    def _build_plugin_prompt_text(self) -> str:
        prompts = (
            self._plugin_prompts.get(self.agent_name, [])
            if hasattr(self, "_plugin_prompts")
            else []
        )
        return "\n\n".join(filter(None, prompts))

    def _build_plugin_prompt_section(self) -> str:
        text = self._build_plugin_prompt_text()
        if not text.strip():
            return ""
        return f"## Plugin Guidance\n{text.strip()}"

    # ============================================================================
    # Protected Methods - Model and Chain Management
    # ============================================================================

    def _create_chain_with_model(self, model: BaseChatModel) -> Runnable:
        """Create a chain with a specific model."""
        return self.prompt | model | self.output_parser

    def _validate_model(self, model: BaseChatModel | None) -> BaseChatModel:
        """Validate and return the model to use."""
        current_model = model or self.model

        if current_model is None:
            raise ValueError("Please provide a valid language model")

        if not isinstance(current_model, BaseChatModel | RunnableBinding):
            raise ValueError("Please provide a valid language model")

        return current_model

    def _get_chain(self, model: BaseChatModel) -> Runnable:
        """Get the appropriate chain for the given model."""
        if model != self.model:
            return self._create_chain_with_model(model)
        else:
            if self.chain is None:
                raise ValueError("Chain not initialized")
            return self.chain

    # ============================================================================
    # Protected Methods - Execution and Response Handling
    # ============================================================================

    def _finalize_forward_response(
        self,
        result: Any,
        *,
        next_agent: str = "Supervisor",
        message_type: str = "routing",
        target_agents: set[str] | None = None,
    ) -> EasyDict:
        """Build the routing payload for forward/aforward results."""

        message = HumanMessage(
            content=result.to_message(),
            name=self.agent_name,  # type: ignore[attr-defined]
        )
        send_metadata = self.send_message(
            message,
            target_agents=target_agents,
            message_type=message_type,
        )

        hyperedge_id = send_metadata.get("hyperedge_id")
        hyperedge_ids = list(send_metadata.get("hyperedges", []))
        if not hyperedge_ids and hyperedge_id:
            hyperedge_ids = [hyperedge_id]

        resolved_targets = set(send_metadata.get("target_agents", set()))
        recipients = (
            set(target_agents)
            if target_agents
            else (resolved_targets or {self.agent_name, next_agent})
        )

        metadata = self._forward_metadata(hyperedge_id, result, next_agent=next_agent)

        return EasyDict(
            {
                "messages": [message],
                "sender": self.agent_name,
                "next": next_agent,
                "target_agents": recipients,
                "message_type": message_type,
                "hyperedges": hyperedge_ids,
                "hyperedge_id": hyperedge_id,
                "metadata": metadata,
            }
        )

    def _forward_metadata(
        self,
        hyperedge_id: str | None,
        result: Any,
        *,
        next_agent: str,
    ) -> dict[str, Any]:
        """Construct harness metadata for the latest agent invocation."""

        metadata = {
            "agent": self.agent_name,
            "routing": {
                "sender": self.agent_name,
                "next": next_agent,
                "hyperedge_id": hyperedge_id,
            },
            "ohcache": {
                "artifacts": getattr(result, "ohcache_artifacts", []),
                "reuse_rationale": getattr(result, "reuse_minimal_diff", None),
            },
        }
        return metadata

    def _invoke_chain_with_retry(self, chain: Runnable, state: AgentState) -> any:
        """Invoke the chain with retry mechanism for malformed output."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                return chain.invoke(state)
            except Exception as parse_error:
                if attempt < max_retries:
                    continue  # Retry with a fresh invocation
                else:
                    # Final attempt failed, raise the error
                    raise Exception(
                        f"Failed to parse LLM output after {max_retries + 1} attempts: {str(parse_error)}"
                    ) from parse_error

    async def _invoke_chain_with_retry_async(
        self, chain: Runnable, state: AgentState
    ) -> Any:
        """Asynchronously invoke the chain with retry for malformed output."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                return await chain.ainvoke(state)
            except Exception as parse_error:
                if attempt < max_retries:
                    continue
                raise Exception(
                    f"Failed to parse LLM output after {max_retries + 1} attempts: {str(parse_error)}"
                ) from parse_error

    def _create_error_response(self, error_message: str) -> EasyDict:
        """Create a standardized error response as message delta."""
        content = f"[ERROR] {self.agent_name}: {error_message}"
        message = HumanMessage(content=content, name=self.agent_name)
        delta = {"messages": [message], "sender": self.agent_name}
        # If supervisor fails, gracefully finish to avoid invalid routing
        if getattr(self, "agent_name", "") == "SupervisorAgent":
            delta["next"] = "[FINISH]"
        return EasyDict(delta)


def _filter_plugin_tools(
    base_tool_classes: tuple[type[BaseTool], ...],
    plugin_specs: list,
) -> tuple[type[BaseTool], ...]:
    """Return plugin tool classes without name conflicts."""

    known_names: set[str] = {
        getattr(cls, "name", cls.__name__) for cls in base_tool_classes
    }
    filtered: list[type[BaseTool]] = []

    for spec in plugin_specs:
        for tool_cls in getattr(spec, "tool_classes", ()) or ():
            tool_name = getattr(tool_cls, "name", tool_cls.__name__)
            if tool_name in known_names:
                logger.error(
                    "Plugin '%s' tool '%s' conflicts with an existing tool name; rejecting plugin tool.",
                    getattr(spec, "name", "unknown"),
                    tool_name,
                )
                continue
            filtered.append(tool_cls)
            known_names.add(tool_name)

    return tuple(filtered)
