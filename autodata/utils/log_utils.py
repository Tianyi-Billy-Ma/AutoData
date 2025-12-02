"""Logging utilities for AutoData.

This module provides centralized logging configuration and setup functions
for consistent logging across the AutoData system.
"""

import atexit
import logging
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodata.configs.args import LogConfig

from .type_utils import handle_browser_use_record

LOG_FORMAT = "[%(asctime)s][%(levelname)s] %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Global list to track file handlers for cleanup
_file_handlers: list[logging.FileHandler] = []


def setup_logging(log_config: "LogConfig", log_dir: Path | None = None) -> None:
    """Set up logging configuration based on log config.

    Args:
        log_config: Log configuration containing log settings
        log_dir: Optional log directory for per-level log files
    """
    # Get log level
    log_level = getattr(logging, log_config.log_level.upper(), logging.INFO)

    # Configure basic logging
    handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Set format to colored formatter for better readability
    formatter = ColoredFormatter(LOG_FORMAT, DATE_FORMAT)

    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # File handler if log_file is specified
    if log_config.log_file:
        log_file_path = Path(log_config.log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        handlers.append(file_handler)
        _file_handlers.append(file_handler)

    # Create per-level log files if a log directory is provided
    if log_dir:
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)

        # Create handlers for each log level
        log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        for level_name, level_value in log_levels.items():
            level_log_file = log_dir_path / f"{level_name}.log"
            level_handler = logging.FileHandler(level_log_file)
            level_handler.setLevel(level_value)
            level_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

            # Only log messages at this specific level or higher
            handlers.append(level_handler)
            _file_handlers.append(level_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Suppress verbose third-party loggers
    # httpx logs every HTTP request at INFO level, which is too verbose
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Also suppress OpenAI client internal logs
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    # Configure browser-use loggers to use our logging system
    # These loggers will use the root logger's handlers but with INFO level
    # This allows browser-use logs to display correctly with our ColoredFormatter
    for logger_name in ["browser_use", "bubus"]:
        browser_logger = logging.getLogger(logger_name)
        browser_logger.setLevel(logging.INFO)
        browser_logger.propagate = True  # Use root logger's handlers

    # Register cleanup handlers for graceful shutdown
    _register_cleanup_handlers()


def _register_cleanup_handlers() -> None:
    """Register cleanup handlers for graceful logging shutdown.

    This ensures logs are flushed even when the program is interrupted (Ctrl+C).
    """

    def cleanup_logging() -> None:
        """Flush and close all file handlers."""
        for handler in _file_handlers:
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass  # Ignore errors during cleanup

    def signal_handler(_signum: int, _frame: object) -> None:
        """Handle interrupt signals by cleaning up and exiting."""
        cleanup_logging()
        sys.exit(0)

    # Register cleanup on normal exit
    atexit.register(cleanup_logging)

    # Register cleanup on interrupt signals (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


class ColoredFormatter(logging.Formatter):
    """ANSI-colored formatter for enhanced log readability."""

    RESET = "\033[0m"
    TIMESTAMP_COLOR = "\033[90m"  # bright black / dim gray
    LEVEL_COLORS = {
        "DEBUG": "\033[34m",  # blue
        "INFO": "\033[32m",  # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    LOGGER_COLOR = "\033[36m"  # cyan
    MESSAGE_COLORS = {
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[1;31m",
    }

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        enable_color: bool | None = None,
    ) -> None:
        """Initialize the colored formatter."""
        super().__init__(fmt, datefmt)
        # Auto-detect terminal support unless explicitly configured
        self.enable_color = (
            sys.stdout.isatty() if enable_color is None else enable_color
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with ANSI colors when supported.

        This formatter handles both AutoData's standard format and third-party
        library formats (like browser-use) that don't use the ' - ' separator.

        Args:
            record: The log record to format

        Returns:
            Formatted log message with ANSI color codes (if enabled)
        """
        record = handle_browser_use_record(record)
        message = super().format(record)

        if not self.enable_color:
            return message

        # Expect format "[timestamp][LEVEL] logger - message"
        timestamp_segment, sep, remainder = message.partition("]")
        if not sep:
            return message
        timestamp_segment += sep

        level_segment, sep, remainder = remainder.partition("]")
        if not sep:
            return message
        level_segment += sep
        remainder = remainder.lstrip()

        logger_segment, sep, msg_segment = remainder.partition(" - ")
        if not sep:
            # No " - " separator found - likely a third-party library (e.g., browser-use)
            # Apply basic coloring (timestamp + level) but preserve the rest as-is
            # to avoid breaking unicode characters, emojis, or custom formatting
            level_name = record.levelname.upper()
            timestamp_colored = f"{self.TIMESTAMP_COLOR}{timestamp_segment}{self.RESET}"
            level_color = self.LEVEL_COLORS.get(level_name, "")
            level_colored = (
                f"{level_color}{level_segment}{self.RESET}"
                if level_color
                else level_segment
            )

            # Return with basic coloring only - preserve remainder as-is
            return f"{timestamp_colored}{level_colored} {remainder}"

        # Standard AutoData format with " - " separator - apply full coloring
        level_name = record.levelname.upper()

        timestamp_colored = f"{self.TIMESTAMP_COLOR}{timestamp_segment}{self.RESET}"
        level_color = self.LEVEL_COLORS.get(level_name, "")
        if level_color:
            level_colored = f"{level_color}{level_segment}{self.RESET}"
        else:
            level_colored = level_segment

        logger_colored = (
            f"{self.LOGGER_COLOR}{logger_segment}{self.RESET}"
            if logger_segment
            else logger_segment
        )

        message_color = self.MESSAGE_COLORS.get(level_name, "")
        if message_color and msg_segment:
            msg_colored = f"{message_color}{msg_segment}{self.RESET}"
        else:
            msg_colored = msg_segment

        if msg_segment:
            return (
                f"{timestamp_colored}{level_colored} {logger_colored} - {msg_colored}"
            )

        return f"{timestamp_colored}{level_colored} {logger_colored}"


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

