"""OHCache configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class HyperedgeConfig:
    """Configuration for a template hyperedge in the OHCache hypergraph."""

    source: list[str] = field(
        default_factory=list,
        metadata={"help": "List of source agent names for this template hyperedge."},
    )
    target: list[str] = field(
        default_factory=list,
        metadata={"help": "List of target agent names for this template hyperedge."},
    )
    id: str | None = field(
        default=None,
        metadata={
            "help": "Stable template ID (optional). If omitted, a deterministic ID is generated."
        },
    )
    message_type: str | None = field(
        default="default",
        metadata={"help": "Message type routed by this hyperedge (default: 'default')."},
    )
    metadata: dict[str, any] | None = field(
        default=None,
        metadata={"help": "Optional metadata attached to the template hyperedge."},
    )


@dataclass
class OHCacheConfig:
    """OHCache configuration.

    Controls caching and hypergraph routing for inter-agent communication.
    """

    enable_ohcache: bool = field(
        default=False,
        metadata={"help": "Enable OHCache integration (caching + hypergraph)"},
    )
    cache_dir: str | None = field(
        default=None,
        metadata={"help": "Cache directory"},
    )
    auto_cleanup: bool = field(
        default=False,
        metadata={"help": "Auto cleanup"},
    )
    hyperedges: list[HyperedgeConfig] = field(
        default_factory=list,
        metadata={
            "help": "List of template hyperedges to install at build time. "
            "Each item defines source agents, target agents, and optional message_type/metadata."
        },
    )
