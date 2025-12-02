"""Browser-Use browser configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class BrowserUseBrowserConfig:
    """Settings applied to the underlying browser-use Browser instance.

    Controls browser behavior such as headless mode, security settings, and recording.
    """

    headless: bool = field(
        default=True,
        metadata={"help": "Run the embedded browser in headless mode."},
    )
    disable_security: bool = field(
        default=False,
        metadata={"help": "Disable browser security features (use with caution)."},
    )
    user_agent: str | None = field(
        default=None,
        metadata={"help": "Optional custom user agent string."},
    )
    args: str | None = field(
        default=None,
        metadata={"help": "Additional Chromium command-line arguments (comma-separated)."},
    )
    record_video_dir: str | None = field(
        default=None,
        metadata={
            "help": "Optional directory path where browser-use should record session videos."
        },
    )
