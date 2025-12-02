"""Plugin configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class PluginConfig:
    """Configuration for AutoData plugins.

    Specifies which plugins to activate and their settings.
    """

    enabled_plugins: list[str] = field(
        default_factory=list,
        metadata={"help": "List of plugin identifiers to enable (e.g., ['academic'])."},
    )
