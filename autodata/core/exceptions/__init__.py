"""Core exception hierarchy package for AutoData."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .agent import (
    AgentConfigurationError,
    AgentDependencyError,
    AgentError,
    AgentExecutionError,
    AgentStateError,
    AgentTimeoutError,
)
from .base import AutoDataError
from .checkpoint import (
    CheckpointError,
    CheckpointIntegrityError,
    CheckpointLoadError,
    CheckpointNotFoundError,
    CheckpointSaveError,
    CheckpointValidationError,
    CheckpointVersionError,
)
from .models import AutoDataModelError
from .runtime import (
    AutoDataInitializationError,
    CacheError,
    ConfigurationError,
    ExecutionError,
    GraphError,
    log_and_raise,
)
from .storage import (
    DirectoryCreationError,
    InvalidRunNameError,
    PathGovernanceError,
)
from .validation import (
    ValidationAssertionError,
    ValidationError,
    ValidationRuleError,
    ValidationSetupError,
    ValidationTimeoutError,
)

ToolingExceptionCategory = Literal[
    "configuration", "execution", "timeout", "validation"
]


@dataclass(slots=True)
class ToolingExceptionRecord:
    """Normalised view of exception metadata for reliability audits."""

    exception: type[AutoDataError]
    category: ToolingExceptionCategory
    default_message: str
    recommended_handlers: list[str] = field(default_factory=list)
    deprecated_replacements: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, object]:
        """Return serialisable metadata for registry exports."""

        return {
            "exception_name": self.exception.__name__,
            "category": self.category,
            "default_message": self.default_message,
            "recommended_handlers": list(self.recommended_handlers),
            "deprecated_replacements": list(self.deprecated_replacements),
        }


def _message_for(exception_type: type[AutoDataError]) -> str:
    return getattr(exception_type, "default_message", exception_type.__name__)


TOOLING_EXCEPTION_REGISTRY: dict[str, ToolingExceptionRecord] = {
    "ConfigurationError": ToolingExceptionRecord(
        exception=ConfigurationError,
        category="configuration",
        default_message=_message_for(ConfigurationError),
    ),
    "ExecutionError": ToolingExceptionRecord(
        exception=ExecutionError,
        category="execution",
        default_message=_message_for(ExecutionError),
    ),
    "CacheError": ToolingExceptionRecord(
        exception=CacheError,
        category="execution",
        default_message=_message_for(CacheError),
    ),
    "AutoDataInitializationError": ToolingExceptionRecord(
        exception=AutoDataInitializationError,
        category="configuration",
        default_message=_message_for(AutoDataInitializationError),
        recommended_handlers=["autodata.utils.sys_utils.initialize"],
    ),
    "GraphError": ToolingExceptionRecord(
        exception=GraphError,
        category="execution",
        default_message=_message_for(GraphError),
    ),
    "AgentConfigurationError": ToolingExceptionRecord(
        exception=AgentConfigurationError,
        category="configuration",
        default_message=_message_for(AgentConfigurationError),
        recommended_handlers=["autodata.agents.base_agent.BaseAgent.__init__"],
    ),
    "AgentDependencyError": ToolingExceptionRecord(
        exception=AgentDependencyError,
        category="execution",
        default_message=_message_for(AgentDependencyError),
    ),
    "AgentExecutionError": ToolingExceptionRecord(
        exception=AgentExecutionError,
        category="execution",
        default_message=_message_for(AgentExecutionError),
    ),
    "AgentTimeoutError": ToolingExceptionRecord(
        exception=AgentTimeoutError,
        category="timeout",
        default_message=_message_for(AgentTimeoutError),
    ),
    "CheckpointValidationError": ToolingExceptionRecord(
        exception=CheckpointValidationError,
        category="validation",
        default_message=_message_for(CheckpointValidationError),
        recommended_handlers=[
            "autodata.core.checkpoint.events.CheckpointEventRecorder.record"
        ],
    ),
    "CheckpointSaveError": ToolingExceptionRecord(
        exception=CheckpointSaveError,
        category="execution",
        default_message=_message_for(CheckpointSaveError),
    ),
    "CheckpointIntegrityError": ToolingExceptionRecord(
        exception=CheckpointIntegrityError,
        category="execution",
        default_message=_message_for(CheckpointIntegrityError),
    ),
    "CheckpointLoadError": ToolingExceptionRecord(
        exception=CheckpointLoadError,
        category="execution",
        default_message=_message_for(CheckpointLoadError),
    ),
    "CheckpointNotFoundError": ToolingExceptionRecord(
        exception=CheckpointNotFoundError,
        category="validation",
        default_message=_message_for(CheckpointNotFoundError),
    ),
    "CheckpointVersionError": ToolingExceptionRecord(
        exception=CheckpointVersionError,
        category="validation",
        default_message=_message_for(CheckpointVersionError),
    ),
    "ValidationTimeoutError": ToolingExceptionRecord(
        exception=ValidationTimeoutError,
        category="timeout",
        default_message=_message_for(ValidationTimeoutError),
    ),
    "ValidationAssertionError": ToolingExceptionRecord(
        exception=ValidationAssertionError,
        category="validation",
        default_message=_message_for(ValidationAssertionError),
    ),
    "ValidationRuleError": ToolingExceptionRecord(
        exception=ValidationRuleError,
        category="validation",
        default_message=_message_for(ValidationRuleError),
    ),
    "ValidationSetupError": ToolingExceptionRecord(
        exception=ValidationSetupError,
        category="configuration",
        default_message=_message_for(ValidationSetupError),
    ),
    "PathGovernanceError": ToolingExceptionRecord(
        exception=PathGovernanceError,
        category="configuration",
        default_message=_message_for(PathGovernanceError),
    ),
    "DirectoryCreationError": ToolingExceptionRecord(
        exception=DirectoryCreationError,
        category="configuration",
        default_message=_message_for(DirectoryCreationError),
        recommended_handlers=[
            "autodata.utils.sys_utils.setup_output_directory",
        ],
    ),
    "InvalidRunNameError": ToolingExceptionRecord(
        exception=InvalidRunNameError,
        category="configuration",
        default_message=_message_for(InvalidRunNameError),
        recommended_handlers=[
            "autodata.utils.cli_utils.CLIManager.validate_args",
        ],
    ),
}


def get_tooling_exception_record(
    exception_name: str,
) -> ToolingExceptionRecord | None:
    """Return registry metadata for a given exception name."""

    return TOOLING_EXCEPTION_REGISTRY.get(exception_name)


__all__ = [
    "AutoDataError",
    "AutoDataModelError",
    "AgentConfigurationError",
    "AgentDependencyError",
    "AgentStateError",
    "AgentExecutionError",
    "AgentTimeoutError",
    "CacheError",
    "ConfigurationError",
    "ExecutionError",
    "AutoDataInitializationError",
    "GraphError",
    "CheckpointIntegrityError",
    "CheckpointLoadError",
    "CheckpointNotFoundError",
    "CheckpointSaveError",
    "CheckpointValidationError",
    "CheckpointVersionError",
    "ValidationAssertionError",
    "ValidationRuleError",
    "ValidationSetupError",
    "ValidationTimeoutError",
    "PathGovernanceError",
    "DirectoryCreationError",
    "InvalidRunNameError",
    "ToolingExceptionRecord",
    "ToolingExceptionCategory",
    "TOOLING_EXCEPTION_REGISTRY",
    "get_tooling_exception_record",
]
