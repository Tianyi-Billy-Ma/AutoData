import logging
from collections.abc import Awaitable, Callable, Hashable
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables.graph import MermaidDrawMethod
from langgraph.graph import END, START, StateGraph

from autodata.agents import (
    AllWorkerAgents,
    BaseAgent,
    DevelopSquadAgents,
    ResearchSquadAgents,
    Supervisor,
)
from autodata.agents.types import AgentState
from autodata.core.config import AutoDataConfig, LLMConfig
from autodata.core.ohcache.ohcache import OHCache

logger = logging.getLogger("AutoData.core")


class AutoDataGraph:
    """AutoData multi-agent graph system for coordinating data collection workflows.

    This class manages a single StateGraph with supervisor and squad agents
    for research and development workflows.
    """

    # ============================================================================
    # Magic Methods
    # ============================================================================

    def __init__(
        self,
        config: AutoDataConfig,
    ) -> None:
        """Initialize the AutoDataGraph.

        Args:
            config: Configuration for the language model
        """
        self.config = config
        self.graph: StateGraph = StateGraph(AgentState)
        self.llm: BaseChatModel | None = None
        self._setup_llm()
        self.supervisor_name: str | None = None
        self.ohcache = OHCache(config.ohcache_config)
        self.agents: dict[str, BaseAgent] = {}

    # ============================================================================
    # Properties
    # ============================================================================

    @property
    def nodes(self) -> dict[str, BaseAgent]:
        """Get all added nodes from the graph.

        Returns:
            dict[str, BaseAgent]: Dictionary of node names to agent instances
        """
        return self.graph.nodes

    @property
    def edges(self) -> list[tuple[str, str]]:
        """Get all edges from the graph.

        Returns:
            list[tuple[str, str]]: A list of all edges as tuples of (start_node, end_node)
        """
        return list(self.graph.edges)

    @property
    def node_names(self) -> list[str]:
        """Get all added node names from the graph.

        Returns:
            list[str]: A list of all node names that have been added to the graph
        """
        return list(self.nodes.keys())

    @property
    def llm_config(self) -> LLMConfig:
        """Get the LLM configuration.

        Returns:
            LLMConfig: The LLM configuration
        """
        return self.config.llm_config

    # ============================================================================
    # Public Methods - Graph Building
    # ============================================================================

    def build(self) -> None:
        """Build the complete graph with supervisor and squad agents."""
        logger.info("Building AutoData graph...")

        # Create supervisor
        supervisor = Supervisor(model=self.llm, config=self.config)
        supervisor_name = supervisor.agent_name
        self.supervisor_name = supervisor_name
        self.add_node(supervisor)

        # Add research squad agents
        for agent_name in ResearchSquadAgents:
            try:
                agent: BaseAgent = self._get_agent_class(agent_name)(
                    model=self.llm,
                    config=self.config,
                )
                self.add_node(agent)
            except Exception as e:
                logger.error(f"Failed to initialize agent {agent_name}: {e}")
                raise

        for agent_name in DevelopSquadAgents:
            try:
                agent: BaseAgent = self._get_agent_class(agent_name)(
                    model=self.llm,
                    config=self.config,
                )
                self.add_node(agent)
            except Exception as e:
                logger.error(f"Failed to initialize agent {agent_name}: {e}")
                raise

        # Connect START to supervisor
        self.add_edge(START, supervisor_name)

        # Define conditional routing from supervisor
        def path(x):
            return x["next"]

        # Build path map dynamically based on available agents
        path_map = {
            "[FINISH]": END,
            "FINISH": END, # alias for [FINISH]
            **{agent_name: agent_name for agent_name in AllWorkerAgents},
        }

        self.add_conditional_edges(supervisor_name, path, path_map)

        for agent_name in AllWorkerAgents:
            self.add_edge(agent_name, supervisor_name)

        # Configure OHCache after all nodes are in place
        self._setup_ohcache_integration()

        logger.info("AutoData graph built successfully")

    # ============================================================================
    # Public Methods - Graph Operations
    # ============================================================================

    def add_node(self, node: BaseAgent, name: str | None = None) -> None:
        """Add a node to the graph.

        Args:
            node: The agent node to add
            name: Optional name override for the node
        """
        agent_name = name or node.agent_name
        self.graph.add_node(agent_name, node)
        self.agents[agent_name] = node

    def add_nodes(self, nodes: list[BaseAgent]) -> None:
        """Add multiple nodes to the graph.

        Args:
            nodes: List of agent nodes to add
        """
        for node in nodes:
            self.add_node(node)

    def add_edge(self, start_agent: str, end_agent: str) -> None:
        """Add an edge to the graph.

        Args:
            start_agent: Name of the starting node
            end_agent: Name of the ending node
        """
        self.graph.add_edge(start_agent, end_agent)

    def add_conditional_edges(
        self,
        source: str,
        path: (
            Callable[..., Hashable | list[Hashable]]
            | Callable[..., Awaitable[Hashable | list[Hashable]]]
        ),
        path_map: dict[Hashable, str] | list[str],
    ) -> None:
        """Add conditional edges to the graph.

        Args:
            source: Source node name
            path: Path function or callable
            path_map: Mapping of path results to target nodes
        """
        self.graph.add_conditional_edges(source, path, path_map)

    # ============================================================================
    # Helper Methods - Output Formatting
    # ============================================================================

    def _print_chunk(self, chunk: dict[str, Any]) -> None:
        """Print a streaming chunk in a readable format.

        Args:
            chunk: The chunk dictionary from the graph stream
        """
        # Extract the agent name (key in the chunk dict)
        agent_names = list(chunk.keys())
        if not agent_names:
            return

        agent_name = agent_names[0]
        agent_data = chunk[agent_name]

        # Extract relevant information
        sender = agent_data.get("sender", agent_name)
        next_agent = agent_data.get("next", "")
        messages = agent_data.get("messages", [])

        # Format the output
        print(f"\n{'=' * 80}")
        print(f"🤖 Agent: {sender}")

        if next_agent:
            if next_agent == "[FINISH]":
                print("✅ Status: COMPLETE")
            else:
                print(f"➡️  Next: {next_agent}")

        # Print message content if available
        if messages:
            last_message = messages[-1] if isinstance(messages, list) else messages
            if hasattr(last_message, "content"):
                content = last_message.content
                if isinstance(content, str):
                    print(f"💬 Output: {content}")
            elif isinstance(last_message, str):
                print(f"💬 Output: {last_message}")

        print(f"{'=' * 80}\n")

    # ============================================================================
    # Helper Methods - State Management
    # ============================================================================

    # ============================================================================
    # Public Methods - Execution
    # ============================================================================

    def run(
        self, task: str, state: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict:
        """Run the graph synchronously with a given task."""

        return self._execute_sync(task, state, stream=False, **kwargs)

    async def arun(
        self, task: str, state: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict:
        """Run the graph asynchronously with a given task."""

        return await self._execute_async(task, state, stream=False, **kwargs)

    def stream(
        self, task: str, state: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict:
        """Run the graph synchronously with streaming output."""

        return self._execute_sync(task, state, stream=True, **kwargs)

    async def astream(
        self, task: str, state: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict:
        """Run the graph asynchronously with streaming output."""

        return await self._execute_async(task, state, stream=True, **kwargs)

    def _build_initial_state(self, task: str, supervisor_name: str) -> dict[str, Any]:
        """Construct the initial state enriched with run context metadata."""

        state: dict[str, Any] = {
            "messages": [HumanMessage(content=task)],
            "sender": "START",
            "next": supervisor_name,
            "user_task": task,
        }

        return state

    def _prepare_execution_state(
        self, task: str, state: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Prepare and return the execution state for the provided task."""

        self._ensure_compiled_graph()
        return self._initial_state_for_task(task, state)

    def _initial_state_for_task(
        self, task: str, state: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Return the user-provided state or construct the default graph payload."""

        if state is not None:
            return state

        supervisor_name = self.supervisor_name or "SupervisorAgent"
        return self._build_initial_state(task, supervisor_name)

    def _execute_sync(
        self,
        task: str,
        state: dict[str, Any] | None,
        *,
        stream: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute the compiled graph synchronously."""

        execution_state = self._prepare_execution_state(task, state)

        if stream:
            return self._stream_sync(execution_state, **kwargs)

        result = self.compiled_graph.invoke(execution_state, **kwargs)
        return self._attach_run_metadata(result)

    async def _execute_async(
        self,
        task: str,
        state: dict[str, Any] | None,
        *,
        stream: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute the compiled graph asynchronously."""

        execution_state = self._prepare_execution_state(task, state)

        if stream:
            return await self._stream_async(execution_state, **kwargs)

        result = await self.compiled_graph.ainvoke(execution_state, **kwargs)
        return self._attach_run_metadata(result)

    def _stream_sync(
        self,
        execution_state: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Stream graph execution synchronously and print chunk output."""

        final_chunk: dict[str, Any] | None = None

        for chunk in self.compiled_graph.stream(execution_state, **kwargs):
            if not chunk:
                continue
            self._handle_stream_chunk(chunk)
            final_chunk = chunk

        return self._attach_run_metadata(final_chunk or {})

    async def _stream_async(
        self,
        execution_state: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Stream graph execution asynchronously and print chunk output."""

        final_chunk: dict[str, Any] | None = None

        async for chunk in self.compiled_graph.astream(execution_state, **kwargs):
            if not chunk:
                continue
            self._handle_stream_chunk(chunk)
            final_chunk = chunk

        return self._attach_run_metadata(final_chunk or {})

    def _handle_stream_chunk(self, chunk: dict[str, Any]) -> None:
        """Print streaming chunk output for the current run."""

        self._print_chunk(chunk)

    def _ensure_compiled_graph(self) -> None:
        """Compile the graph if it hasn't been compiled yet."""

        if not hasattr(self, "compiled_graph"):
            self.compiled_graph = self.graph.compile()

    def _attach_run_metadata(self, result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(result, dict):
            return result

        if self.ohcache.enable_ohcache:
            result.setdefault("reuse_summary", self.ohcache.get_reuse_summary())
            result.setdefault(
                "hyperedge_ledger", self.ohcache.export_hyperedge_ledger()
            )

        return result

    # ============================================================================
    # Public Methods - Visualization
    # ============================================================================

    def visualize(self, output_path: str) -> bytes:
        """Generate a visual representation of the graph and save it.

        Args:
            output_path: Path to save the PNG image.

        Returns:
            bytes: The PNG image data

        Raises:
            RuntimeError: If the graph hasn't been compiled yet
        """
        if not hasattr(self, "compiled_graph"):
            self.compiled_graph = self.graph.compile()

        try:
            # Method 1: Try API method first
            print("🌐 Attempting PNG generation via Mermaid.ink API...")
            png_data = self.compiled_graph.get_graph().draw_mermaid_png(
                draw_method=MermaidDrawMethod.API, max_retries=3, retry_delay=1.0
            )
            print("📊 PNG graph visualization generated using Mermaid.ink API")

            # Save PNG file
            with open(output_path, "wb") as f:
                f.write(png_data)
            print(f"📊 PNG graph visualization saved to: {output_path}")
            return png_data

        except Exception as api_error:
            print(f"ℹ️  API method failed: {api_error}")

            # Method 2: Fallback to ASCII -> PNG conversion
            try:
                print("🔄 Falling back to ASCII -> PNG conversion...")
                ascii_graph = self.compiled_graph.get_graph().draw_ascii()
                png_data = self._convert_ascii_to_png(ascii_graph, output_path)
                print("📊 PNG graph visualization generated from ASCII fallback")
                return png_data

            except Exception as ascii_error:
                error_msg = f"Both API and ASCII->PNG methods failed. API: {api_error}, ASCII: {ascii_error}"
                print(f"❌ {error_msg}")
                raise RuntimeError(error_msg) from ascii_error

    # ============================================================================
    # Private Methods - Agent Registry
    # ============================================================================

    # Agent registry: maps agent names to their module paths
    _AGENT_REGISTRY = {
        "PlanAgent": "autodata.agents.plan_agent",
        "ToolAgent": "autodata.agents.tool_agent",
        "BrowserAgent": "autodata.agents.browser_agent",
        "BlueprintAgent": "autodata.agents.blueprint_agent",
        "EngineerAgent": "autodata.agents.engineer_agent",
        "TestAgent": "autodata.agents.test_agent",
        "ValidationAgent": "autodata.agents.validation_agent",
        "HumanAgent": "autodata.agents.human_agent",
    }

    def _get_agent_class(self, agent_name: str) -> type[BaseAgent]:
        """Get agent class by name using lazy import from registry.

        Args:
            agent_name: Name of the agent class

        Returns:
            Agent class

        Raises:
            ValueError: If agent class is not found in registry
        """
        if agent_name not in self._AGENT_REGISTRY:
            raise ValueError(
                f"Unknown agent: {agent_name}. "
                f"Available agents: {list(self._AGENT_REGISTRY.keys())}"
            )

        module_path = self._AGENT_REGISTRY[agent_name]

        try:
            # Lazy import the agent class
            import importlib

            module = importlib.import_module(module_path)
            agent_class = getattr(module, agent_name)
            return agent_class
        except (ImportError, AttributeError) as e:
            raise ValueError(
                f"Failed to import agent '{agent_name}' from '{module_path}': {e}"
            ) from e

    # ============================================================================
    # Private Methods - LLM Setup
    # ============================================================================

    def _setup_llm(self) -> None:
        """Initialize the language model from configuration using init_chat_model."""
        llm_config = self.llm_config

        # Build kwargs for init_chat_model
        init_kwargs: dict[str, Any] = {
            "model": llm_config.model,
            "temperature": llm_config.temperature,
        }

        # Add optional parameters if provided
        if llm_config.model_provider:
            init_kwargs["model_provider"] = llm_config.model_provider

        if llm_config.configurable_fields:
            init_kwargs["configurable_fields"] = llm_config.configurable_fields

        # Handle base_url and api_key for third-party providers
        # These are passed as additional kwargs to the underlying model class
        if llm_config.base_url:
            init_kwargs["base_url"] = llm_config.base_url

        if llm_config.api_key:
            init_kwargs["api_key"] = llm_config.api_key

        try:
            self.llm = init_chat_model(**init_kwargs)
            logger.info(
                f"Initialized LLM: model={llm_config.model}, "
                f"provider={llm_config.model_provider or 'inferred'}"
            )
        except ValueError as error:
            logger.error(
                "Failed to initialize model '%s' with provider '%s': %s",
                llm_config.model,
                llm_config.model_provider,
                error,
            )
            raise
        except Exception as e:
            logger.error(f"Failed to initialize model '{llm_config.model}': {e}")
            raise

    def _setup_ohcache_integration(self) -> None:
        """Initialize OHCache integration for the graph and its agents."""
        if not self.ohcache:
            return

        self.ohcache.setup_graph_integration(self)

    # ============================================================================
    # Private Methods - Visualization Helpers
    # ============================================================================

    def _convert_ascii_to_png(self, ascii_text: str, output_path: str) -> bytes:
        """Convert ASCII text to PNG image.

        Args:
            ascii_text: ASCII art representation of the graph
            output_path: Path where PNG should be saved

        Returns:
            PNG image data as bytes

        Raises:
            ImportError: If PIL (Pillow) is not available
            Exception: If PNG conversion fails
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as e:
            raise ImportError(
                "PIL (Pillow) is required for ASCII->PNG conversion. Install with: uv add pillow"
            ) from e

        # Configuration for the image
        font_size = 12
        line_height = font_size + 2
        char_width = 7  # Approximate width of monospace character
        padding = 20
        bg_color = "white"
        text_color = "black"

        # Split ASCII text into lines
        lines = ascii_text.split("\n")

        # Calculate image dimensions
        max_line_length = max(len(line) for line in lines) if lines else 0
        image_width = max_line_length * char_width + (padding * 2)
        image_height = len(lines) * line_height + (padding * 2)

        # Create image
        image = Image.new("RGB", (image_width, image_height), bg_color)
        draw = ImageDraw.Draw(image)

        # Try to use a monospace font, fallback to default
        try:
            # Try common monospace fonts
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                "/System/Library/Fonts/Monaco.ttf",  # macOS
                "C:/Windows/Fonts/consola.ttf",  # Windows
            ]
            font = None
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except OSError:
                    continue

            if font is None:
                font = ImageFont.load_default()

        except Exception:
            font = ImageFont.load_default()

        # Draw each line of text
        y_position = padding
        for line in lines:
            if line.strip():  # Only draw non-empty lines
                draw.text((padding, y_position), line, fill=text_color, font=font)
            y_position += line_height

        # Save to file
        image.save(output_path, "PNG")

        # Return PNG data as bytes
        import io

        img_bytes = io.BytesIO()
        image.save(img_bytes, format="PNG")
        png_data = img_bytes.getvalue()

        print(
            f"📊 ASCII converted to PNG: {len(lines)} lines, {image_width}x{image_height} pixels"
        )
        return png_data
