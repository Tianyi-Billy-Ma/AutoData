"""
Oriented Hyperedge Formatter for OHCache System.

This module provides the structured communication schema and response models
for inter-agent communication in the AutoData multi-agent system.

The formatter enforces consistent message structure and hyperedge message accumulation
as part of the OHCache (Oriented Hypergraph Cache System).
"""

from typing import Any
from easydict import EasyDict
from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Base response model for all agent communications.

    This class provides the foundation for all agent response models,
    ensuring consistent structure and utility methods across the system.
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the response."""
        return getattr(self, key, default)

    def to_easydict(self) -> EasyDict:
        """Convert response to EasyDict format for easy access."""
        return EasyDict(self.model_dump())

    def to_dict(self) -> dict:
        """Convert response to standard dictionary format."""
        return self.model_dump()

    def to_message(self) -> str:
        """Convert response to string message format."""
        return str(self.to_dict())


class BlueprintAgentResponse(BaseResponse):
    """Response model for blueprint agent operations.

    This model defines the structure of responses from the blueprint agent,
    containing generated blueprints and specifications for data collection scripts.
    """

    blueprint_name: str = Field(description="Name of the generated blueprint.")
    blueprint_description: str = Field(
        description="Description of the blueprint purpose and functionality."
    )
    data_sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of data sources and their specifications.",
    )
    data_extraction_logic: dict[str, Any] = Field(
        default_factory=dict,
        description="Specification of data extraction and parsing logic.",
    )
    data_validation: dict[str, Any] = Field(
        default_factory=dict, description="Data validation and cleaning procedures."
    )
    output_specifications: dict[str, Any] = Field(
        default_factory=dict, description="Output format and storage specifications."
    )
    error_handling: dict[str, Any] = Field(
        default_factory=dict, description="Error handling and retry mechanisms."
    )
    performance_considerations: list[str] = Field(
        default_factory=list,
        description="Performance optimization and resource management considerations.",
    )
    integration_points: list[str] = Field(
        default_factory=list,
        description="Integration points with other system components.",
    )
    error_message: str | None = Field(
        default=None, description="Error message if the blueprint generation failed."
    )


class BrowserAgentResponse(BaseResponse):
    """Response model for browser agent reconnaissance outputs.

    Delivers structured knowledge gathered while browsing so downstream agents
    can reason about site structure without revisiting the page.
    """

    url: str = Field(
        description="Primary URL or entry point examined during the session."
    )
    summary: str = Field(
        default="",
        description="Brief narrative summary of the browsing session and key findings.",
    )
    content: str = Field(
        default="",
        description=(
            "Detailed knowledge gathered from browsing, including page structure, interaction patterns, "
            "API endpoints, DOM selectors, authentication requirements, and references to cached artifacts. "
            "Should integrate cache_key references to guide downstream agents "
            "(e.g., 'HTML structure cached as github_api_docs_html for DOM selector reference')."
        ),
    )
    error_message: str | None = Field(
        default=None, description="Error message if the browsing operation failed."
    )


class EngineerAgentResponse(BaseResponse):
    """Response model for engineer agent code generation.

    This model defines the structure of responses from the engineer agent,
    containing the generated code and related metadata used for downstream
    validation, caching, and persistence.
    """

    code: str = Field(
        description=(
            "Complete, standalone executable Python script that implements the required functionality. "
            "The code should be production-ready and include all necessary imports, error handling, "
            "and documentation. It should be runnable as-is in an isolated environment."
        )
    )
    title: str = Field(
        description=(
            "Short lowercase slug (max three words, use underscores) describing the script. "
            "Used when naming the persisted file."
        )
    )
    summary: str = Field(
        default="",
        max_length=240,
        description="Concise summary of the script's primary behavior (<=240 characters).",
    )
    description: str = Field(
        description="A brief description of what the code does and how it works."
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description=(
            "List of external Python packages required to run the code. "
            "Format: package names optionally with version specifiers "
            "(e.g., ['requests>=2.31.0', 'pandas', 'beautifulsoup4==4.12.0']). "
            "Do not include standard library packages."
        ),
    )
    error_message: str | None = Field(
        default=None, description="Error message if the code generation failed."
    )


class EngineerAgentOutput(BaseResponse):
    """Persisted engineer agent output shared with downstream agents."""

    message: str = Field(
        description=(
            "Status message describing where the script was saved locally and inside Docker, "
            "plus any cache metadata."
        )
    )
    description: str = Field(
        description="Brief description of what the script accomplishes."
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of pip-installable dependencies required for execution.",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if code generation reported a failure.",
    )


class StepResponse(BaseResponse):
    """Response model for step of the plan."""

    step_name: str = Field(description="Name of the step.")
    agent_name: str = Field(description="Agent for the step.")
    description: str = Field(description="Description of the step.")
    expect_output: str = Field(description="Expected output of the step.")
    depends_on: list[str] = Field(
        default_factory=list,
        description="Optional list of step names/IDs this step depends on.",
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Inputs or parameters for the step (e.g., URLs, queries, hints).",
    )
    outputs: list[str] = Field(
        default_factory=list,
        description="Artifact keys or result names produced by this step.",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Checks that define when the step is considered successful.",
    )


class PlanAgentResponse(BaseResponse):
    """Agent-oriented execution plan.

    Minimal, actionable structure focused on orchestrating agents rather than
    human-facing documentation.
    """

    goals: list[str] = Field(
        default_factory=list,
        description="High-level goals the plan aims to achieve.",
    )
    steps: list[StepResponse] = Field(
        default_factory=list,
        description="Ordered steps with agent assignments and expected outputs.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional freeform notes or caveats for the orchestrator.",
    )
    error_message: str | None = Field(
        default=None, description="Error message if plan generation failed."
    )


class SupervisorResponse(BaseResponse):
    """Response model for supervisor decisions.

    This model defines the structure of responses from the supervisor agent,
    indicating the next worker to act and the message to pass along.
    """

    next: str = Field(
        description=(
            "The next worker to act. If the task is finished, response with [FINISH]."
        ),
    )
    message: str = Field(description="The message send to the next worker.")

    def to_message(self) -> str:
        return self.message


class TestAgentResponse(BaseResponse):
    """Response model for test agent execution and debugging.

    This model defines the structure of responses from the test agent,
    containing test results, debugging information, and recommendations.
    """

    execution_result: str = Field(
        description="The output from executing the code, including any errors or exceptions."
    )
    test_results: list[str] = Field(
        default_factory=list, description="Results from running test cases on the code."
    )
    debug_info: str = Field(
        default="",
        description="Detailed debugging information including error analysis and fixes.",
    )
    performance_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Performance metrics such as execution time and memory usage.",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improving the code quality and performance.",
    )
    error_message: str | None = Field(
        default=None, description="Error message if the testing failed."
    )


class ToolAgentResponse(BaseResponse):
    """Response model for tool agent operations.

    This model defines the structure of responses from the tool agent,
    containing tool execution results and recommendations.
    """

    tool_name: str = Field(description="Name of the tool that was executed.")
    message: Any = Field(description="Result of the tool execution.")
    error_message: str | None = Field(
        default=None, description="Error message if the testing failed."
    )


class ToolCallResponse(BaseResponse):
    """Response model for tool call operations."""

    tool_name: str = Field(description="Name of the tool that was executed.")
    message: str = Field(description="Message from the tool execution.")
    additional: dict[str, Any] = Field(
        description="Additional information from the tool execution."
    )
    error_message: str | None = Field(
        description="Error message if the tool call failed."
    )


class ValidationAgentResponse(BaseResponse):
    """Response model for validation agent results.

    This model defines the structure of responses from the validation agent,
    containing execution results, validation metrics, and debugging information.
    """

    validation_status: str = Field(
        description=(
            "Overall validation status: PASS (code executed successfully), "
            "FAIL (execution failed or errors found), or PARTIAL (executed with warnings)."
        )
    )
    execution_status: str = Field(
        default="",
        description=(
            "Status of the code execution: SUCCESS, ERROR, TIMEOUT, or NOT_EXECUTED."
        ),
    )
    execution_output: str = Field(
        default="",
        description="Complete output from executing the code, including stdout and stderr.",
    )
    execution_errors: list[str] = Field(
        default_factory=list,
        description="List of errors encountered during code execution.",
    )
    environment_setup_log: str = Field(
        default="",
        description="Log output from setting up the execution environment and installing dependencies.",
    )
    dependencies_installed: list[str] = Field(
        default_factory=list,
        description="List of dependencies that were successfully installed.",
    )
    feedback: list[str] = Field(
        default_factory=list,
        description=(
            "Actionable feedback for the EngineerAgent describing validation findings, "
            "errors encountered, and required follow-up work."
        ),
    )
    attempt_count: int = Field(
        default=1,
        description="Number of execution attempts made (including retries).",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improving the code or fixing remaining issues.",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if the validation process itself failed.",
    )


class HumanAgentResponse(BaseResponse):
    """Response model for human agent feedback and approvals.

    Captures the user's decision and optional feedback to guide subsequent steps.
    """

    decision: str = Field(
        description=("Human decision tag. One of [APPROVE], [REVISE], [COMMENT].")
    )
    feedback: str = Field(
        default="", description="Optional human feedback or comments."
    )
    error_message: str | None = Field(
        default=None, description="Error message if interaction failed."
    )


class CacheNotice(BaseResponse):
    """Notification emitted when an artifact is stored in OHCache."""

    owner: str = Field(
        default="unknown",
        description="Agent that created the cached artifact.",
    )
    cache_key: str = Field(description="Fully qualified cache key for the artifact.")
    cache_type: str = Field(description="Cache category for the artifact.")
    summary: str = Field(
        description="Brief human-readable description of the artifact."
    )


class ThinkResponse(BaseResponse):
    """Structured response for the agent think-and-fetch preflight stage."""

    cache_keys: list[str] = Field(
        default_factory=list,
        description="Ordered list of cache keys to retrieve before action.",
    )
    rationale: str = Field(
        default="",
        description="Short explanation of why artifacts should or should not be fetched.",
    )


# Export all response classes
__all__ = [
    "BaseResponse",
    "BlueprintAgentResponse",
    "BrowserAgentResponse",
    "EngineerAgentOutput",
    "EngineerAgentResponse",
    "PlanAgentResponse",
    "SupervisorResponse",
    "TestAgentResponse",
    "ToolAgentResponse",
    "ValidationAgentResponse",
    "HumanAgentResponse",
    "CacheNotice",
    "ThinkResponse",
]
