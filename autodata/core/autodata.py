"""AutoData main class for coordinating data collection workflows."""

import json
import logging
from pathlib import Path
from typing import Any

from autodata.agents import BaseAgent
from autodata.core.checkpoint import CheckpointManager
from autodata.core.config import (
    AutoDataConfig,
    load_environment_variables_from_file,
)
from autodata.core.exceptions import AutoDataError
from autodata.core.graph import AutoDataGraph
from autodata.utils.path_utils import resolve_run_name

logger = logging.getLogger("AutoData.core")


class AutoData:
    """Main AutoData class for coordinating data collection workflows.

    This class provides a simple interface to the AutoData multi-agent system,
    handling configuration, initialization, and execution of data collection tasks.
    """

    # ============================================================================
    # Magic Methods
    # ============================================================================

    def __init__(
        self,
        config: AutoDataConfig | None = None,
        env_file: Path | None = None,
    ) -> None:
        """Initialize AutoData with configuration.

        Args:
            config: General AutoData configuration (includes LLM config)
            env_file: Path to environment file (optional)
        """
        # Load environment variables first
        load_environment_variables_from_file(env_file)

        # Set up configuration
        self.config = config or AutoDataConfig()

        if not self.config.run_name:
            self.config.run_name = resolve_run_name()

        self.config.run_dir.mkdir(parents=True, exist_ok=True)

        # Initialize the graph
        self.graph = AutoDataGraph(config=self.config)
        self.built = False
        self.checkpoint_manager: CheckpointManager | None = None

    # ============================================================================
    # Properties
    # ============================================================================

    @property
    def is_built(self) -> bool:
        """Check if the graph has been built.

        Returns:
            bool: True if the graph is built, False otherwise
        """
        return self.graph is not None and self.built

    @property
    def available_agents(self) -> list[str]:
        """List of available agent names once the graph is built."""
        if not self.built or self.graph is None:
            raise RuntimeError("Graph not built. Call build() first.")
        return self.graph.node_names

    # ============================================================================
    # Public Methods - Core Operations
    # ============================================================================

    def build(self) -> None:
        """Build the AutoData graph with all agents and connections."""
        if self.built:
            logger.warning("Graph already built. Rebuilding...")
            # Recreate the graph cleanly without external tool injection
            self.graph = AutoDataGraph(config=self.config)

        logger.info("Building AutoData system...")
        self.checkpoint_manager = CheckpointManager(self.config)
        # Expose the shared manager to agent configuration so mixins can access it.
        try:
            self.config._checkpoint_manager = self.checkpoint_manager  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive fallback
            self.config._checkpoint_manager = self.checkpoint_manager

        self.graph.build()
        self.built = True
        logger.info("AutoData system built successfully")

        resume_from = self.config.checkpoint_config.resume_from
        if resume_from:
            try:
                self.checkpoint_manager.resume(self, resume_from)
                logger.info("Resumed AutoData state from checkpoint: %s", resume_from)
            except AutoDataError as exc:
                logger.error(
                    "Failed to resume from checkpoint %s: %s", resume_from, exc
                )
                raise

    def get_agent(self, agent_name: str) -> BaseAgent:
        """Retrieve a built agent instance by name.

        Args:
            agent_name: Agent identifier, e.g., "PlanAgent"

        Returns:
            BaseAgent instance ready for direct invocation.

        Raises:
            RuntimeError: If build() has not been called yet.
            ValueError: If the requested agent is not present in the graph.
        """
        if not self.is_built:
            raise RuntimeError("Graph not built. Call build() first.")

        try:
            return self.graph.agents[agent_name]
        except KeyError as exc:
            available = ", ".join(sorted(self.graph.agents))
            raise ValueError(
                f"Agent '{agent_name}' not found. Available agents: {available}"
            ) from exc

    def execute_task(self, task: str) -> dict[str, Any]:
        """Execute a task using the configured execution strategy.

        Args:
            task: The task description to execute

        Returns:
            Dict containing the execution results

        Raises:
            RuntimeError: If the graph hasn't been built yet
        """
        if not self.is_built:
            raise RuntimeError("Graph not built. Call build() first.")

        execution_strategy = self.config.execution_strategy
        logger.info(f"Using execution strategy: {execution_strategy}")

        # Validate and fallback to 'stream' if invalid
        if execution_strategy not in ["stream", "run", "astream", "arun"]:
            logger.warning(
                f"Unknown execution strategy '{execution_strategy}', falling back to stream"
            )
            execution_strategy = "stream"

        execute_func = getattr(self, execution_strategy)

        if execution_strategy in ["stream", "run"]:
            result = execute_func(task)
        else:  # astream, arun
            import asyncio

            result = asyncio.run(execute_func(task))

        logger.info("Task completed successfully")
        return result

    # ------------------------------------------------------------------
    # Checkpoint helpers
    # ------------------------------------------------------------------

    def save_checkpoint(
        self,
        *,
        name: str | None = None,
        pipeline_stage: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Convenience wrapper to save a checkpoint using the active manager."""

        if not self.checkpoint_manager:
            raise RuntimeError("Checkpoint manager is not initialized.")
        return self.checkpoint_manager.save(
            self,
            name=name,
            pipeline_stage=pipeline_stage,
            metadata=metadata,
        )

    def resume_from_checkpoint(self, checkpoint_name: str | Path) -> None:
        """Resume AutoData state from a checkpoint."""

        if not self.checkpoint_manager:
            self.checkpoint_manager = CheckpointManager(
                self.config,
            )
        self.checkpoint_manager.resume(self, checkpoint_name)

    # ============================================================================
    # Public Methods - Execution Strategies
    # ============================================================================

    def run(
        self,
        task: str,
        initial_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a data collection task through the AutoData system.

        Args:
            task: The task description to execute
            initial_state: Optional initial state for the graph
            **kwargs: Additional arguments passed to the graph execution

        Returns:
            Dict containing the execution results

        Raises:
            RuntimeError: If the graph hasn't been built yet
        """
        if not self.is_built:
            raise RuntimeError("Graph not built. Call build() first.")

        logger.info(f"Running task: {task}")

        # Execute the graph (it will handle its own state initialization)
        result: dict[str, Any] | None = None
        try:
            result = self.graph.run(task, initial_state, **kwargs)
            logger.info("Task completed successfully")
            self._write_run_summary(result)
            return result
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            raise

    async def arun(
        self,
        task: str,
        initial_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Asynchronously run a data collection task through the AutoData system.

        Args:
            task: The task description to execute
            initial_state: Optional initial state for the graph
            **kwargs: Additional arguments passed to the graph execution

        Returns:
            Dict containing the execution results

        Raises:
            RuntimeError: If the graph hasn't been built yet
        """
        if not self.is_built:
            raise RuntimeError("Graph not built. Call build() first.")

        logger.info(f"Running task asynchronously: {task}")

        # Execute the graph asynchronously (it will handle its own state initialization)
        try:
            result = await self.graph.arun(task, initial_state, **kwargs)
            logger.info("Task completed successfully")
            if result:
                self._write_run_summary(result)
            return result
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            raise

    def stream(
        self,
        task: str,
        state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a data collection task with streaming output.

        Args:
            task: The task description to execute
            initial_state: Optional initial state for the graph
            **kwargs: Additional arguments passed to the graph execution

        Returns:
            Dict containing the execution results

        Raises:
            RuntimeError: If the graph hasn't been built yet
        """
        if not self.is_built:
            raise RuntimeError("Graph not built. Call build() first.")

        logger.info("\n%s\n🚀 Starting task: %s\n%s", "=" * 80, task, "=" * 80)

        # Execute the graph with streaming
        try:
            result = self.graph.stream(task, state, **kwargs)
            logger.info("\n%s\n✅ Task completed successfully\n%s", "=" * 80, "=" * 80)
            if result:
                self._write_run_summary(result)
            return result
        except Exception as e:
            logger.info("\n%s\n❌ Task execution failed: %s\n%s", "=" * 80, e, "=" * 80)
            logger.error(f"Task execution failed: {e}")
            raise

    async def astream(
        self,
        task: str,
        initial_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Asynchronously run a data collection task with streaming output.

        Args:
            task: The task description to execute
            initial_state: Optional initial state for the graph
            **kwargs: Additional arguments passed to the graph execution

        Returns:
            Dict containing the execution results

        Raises:
            RuntimeError: If the graph hasn't been built yet
        """
        if not self.is_built:
            raise RuntimeError("Graph not built. Call build() first.")

        logger.info("\n%s", "=" * 80)
        logger.info("🚀 Starting async streaming task: %s", task)
        logger.info("%s", "=" * 80)

        # Execute the graph with async streaming
        try:
            result = await self.graph.astream(task, initial_state, **kwargs)
            logger.info("\n%s", "=" * 80)
            logger.info("✅ Task completed successfully")
            logger.info("%s", "=" * 80)
            if result:
                self._write_run_summary(result)
            return result
        except Exception as e:
            logger.info("\n%s", "=" * 80)
            logger.info("❌ Task execution failed: %s", e)
            logger.info("%s", "=" * 80)
            logger.error(f"Task execution failed: {e}")
            raise

    # ============================================================================
    # Internal helpers
    # ============================================================================

    def _write_run_summary(self, final_state: dict[str, Any]) -> None:
        """Persist run metadata and reuse summary to run output directory summary.json."""

        if not isinstance(final_state, dict):
            return

        run_name = self.config.run_name or "default_run"

        output_dir = Path(self.config.storage_config.output_dir) / run_name
        output_dir.mkdir(parents=True, exist_ok=True)

        summary_path = output_dir / "summary.json"

        reuse_summary = final_state.get("reuse_summary")
        hyperedge_log_path = final_state.get("hyperedge_log_path")
        hyperedge_entry_count = 0

        ohcache = getattr(self.graph, "ohcache", None)
        if ohcache and getattr(ohcache, "enable_ohcache", False):
            if not reuse_summary:
                reuse_summary = ohcache.get_reuse_summary()
                final_state["reuse_summary"] = reuse_summary

            ledger_path = output_dir / "hyperedges.json"
            try:
                ohcache.write_hyperedge_ledger(ledger_path)
                hyperedge_log_path = str(ledger_path)
                final_state["hyperedge_log_path"] = hyperedge_log_path
                try:
                    hyperedge_entry_count = len(ohcache.export_hyperedge_ledger())
                except Exception:
                    hyperedge_entry_count = 0
            except Exception as exc:  # pragma: no cover - ledger export best-effort
                logger.exception("Failed to write hyperedge ledger: %s", exc)

        summary_payload = {
            "run_name": run_name,
            "task": final_state.get("user_task") or self.config.task,
            "status": final_state.get("status", "completed"),
            "dataset": final_state.get("dataset", {}),
            "reuse_summary": reuse_summary or {},
            "hyperedge_log_path": hyperedge_log_path,
            "hyperedge_entry_count": hyperedge_entry_count,
            "notes": final_state.get("human_feedback") or final_state.get("human_note"),
        }

        try:
            with summary_path.open("w", encoding="utf-8") as handle:
                json.dump(summary_payload, handle, indent=2, sort_keys=True)
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to write run summary: %s", exc)

    # ============================================================================
    # Public Methods - Visualization and Information
    # ============================================================================

    def visualize_graph(
        self,
        output_path: str | None = None,
        run_name: str | None = None,
        raise_on_error: bool = False,
    ) -> bytes | None:
        """Generate a visual representation of the graph and optionally save it.

        Args:
            output_path: Optional path to save the PNG image. If None, defaults to output_dir/graph.png.
            run_name: Optional run name to determine output directory. If None, uses "default_run".
            raise_on_error: If True, raises exceptions on visualization failure. If False, logs warning and continues.

        Returns:
            bytes: The PNG image data, or None if visualization failed and raise_on_error is False

        Raises:
            RuntimeError: If the graph hasn't been built yet, or if visualization fails and raise_on_error is True
        """
        if not self.is_built:
            raise RuntimeError("Graph not built. Call build() first.")

        # Default to run output directory if no path provided
        if output_path is None:
            if run_name is not None:
                # Temporarily set run_name if provided
                original_run_name = self.config.storage.run_name
                self.config.storage.run_name = run_name
                output_dir = self.config.run_dir
                self.config.storage.run_name = original_run_name
            else:
                # Use current run_name from config
                output_dir = self.config.run_dir
            output_path = str(output_dir / "graph.png")

        logger.info("Generating graph visualization...")

        try:
            png_data = self.graph.visualize(output_path)
            logger.info("Graph visualization generated successfully")
            return png_data
        except Exception as e:
            if raise_on_error:
                logger.error(f"Graph visualization failed: {e}")
                raise
            else:
                logger.warning(f"Failed to generate graph visualization: {e}")
                # Continue execution even if visualization fails
                return None
