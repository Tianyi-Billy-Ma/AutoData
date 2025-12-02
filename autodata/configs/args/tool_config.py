"""Tool configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class ToolConfig:
    """Tools configuration for ToolAgent and built-in tools.

    - ``work_dir``: Optional override for tool working directory. If ``None``,
      the system uses ``AutoDataConfig.work_dir``.
    - ``tools``: Tool-specific options. Currently supports:
        - ``PerplexitySearchToolModel``: Model name for Perplexity API.
    """

    run_dir: str | None = field(
        default=None,
        metadata={"help": "Optional override for tool run directory"},
    )
    work_dir: str | None = field(
        default=None,
        metadata={"help": "Optional override for tools working directory"},
    )
    tools_cache_dir: str | None = field(
        default=None,
        metadata={"help": "Optional override for tool cache directory"},
    )
    PerplexitySearchToolModel: str = field(
        default="sonar",
        metadata={"help": "Model name for Perplexity API"},
    )
