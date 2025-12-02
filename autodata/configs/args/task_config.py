"""Task configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class TaskConfig:
    """Task-level flags and CLI-focused options."""

    config: str = field(
        default="configs/default.yaml",
        metadata={"help": "Path to configuration file"},
    )
    config_format: str | None = field(
        default=None,
        metadata={
            "help": "Configuration file format (yaml, json, toml). Auto-detected if not specified."
        },
    )
    task: str = field(
        default="",
        metadata={"help": "Task description to execute"},
    )
    run_name: str | None = field(
        default="default_run",
        metadata={"help": "Optional run name (populates storage directories)."},
    )
    disable_human: bool = field(
        default=False,
        metadata={"help": "Automatically approve HumanAgent prompts without user input"},
    )
    task_timeout: int = field(
        default=3600,
        metadata={"help": "Task timeout in seconds."},
    )
    execution_strategy: str = field(
        default="stream",
        metadata={
            "help": "Execution strategy: 'stream', 'run', 'astream', or 'arun'"
        },
    )
    dry_run: bool = field(
        default=False,
        metadata={"help": "Validate configuration and exit without running"},
    )
    verbose: bool = field(
        default=False,
        metadata={"help": "Enable verbose logging"},
    )
    visualize_graph: bool = field(
        default=False,
        metadata={"help": "Generate and save graph visualization"},
    )
