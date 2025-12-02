"""Logging configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class LogConfig:
    """Logging and metrics configuration.

    Controls logging levels, file output, and monitoring settings.
    """

    metrics_enabled: bool = field(
        default=True,
        metadata={"help": "Enable monitoring"},
    )
    metrics_port: int = field(
        default=9090,
        metadata={"help": "Prometheus metrics port"},
    )
    log_level: str = field(
        default="INFO",
        metadata={"help": "Logging level (DEBUG, INFO, WARNING, ERROR)"},
    )
    log_file: str | None = field(
        default=None,
        metadata={"help": "Log file path (if None, logs to console)"},
    )
