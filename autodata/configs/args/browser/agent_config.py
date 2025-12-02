"""Browser-Use agent configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class BrowserUseAgentConfig:
    """Settings controlling browser-use Agent execution.

    Controls agent behavior such as max steps, actions per step, and GIF generation.
    """

    max_steps: int = field(
        default=20,
        metadata={"help": "Maximum number of steps the browser-use agent may take."},
    )
    max_actions_per_step: int = field(
        default=50,
        metadata={"help": "Maximum number of actions browser-use may execute in a single step."},
    )
    llm_timeout: int | None = field(
        default=None,
        metadata={"help": "Maximum timeout (in seconds) for the LLM to complete the task."},
    )
    generate_gif: str | None = field(
        default=None,
        metadata={
            "help": "Enable GIF generation for agent actions. Provide output path or 'true'."
        },
    )
    file_system_path: str | None = field(
        default=None,
        metadata={
            "help": "Optional file system path for the browser-use agent to save the browser session."
        },
    )
