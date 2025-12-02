"""
OHCache (Oriented Hypergraph Cache System) module.

This module provides the OHCache system for effective and cost-efficient
multi-agent collaboration in open web data collection tasks.

The OHCache system consists of:
1. An oriented message hypergraph that models inter-agent message flow as oriented hyperedges
2. An oriented hyperedge formatter to enforce structured communication schema
3. A local cache system to store reusable artifacts for agents to retrieve on demand

Reference: https://arxiv.org/abs/2505.15859
"""

__version__ = "0.1.0"

# Import formatter components
# Import cache components
from .cache import (
    CacheEntry,
    LocalCacheSystem,
)
from .formatter import (
    BaseResponse,
    BlueprintAgentResponse,
    BrowserAgentResponse,
    EngineerAgentOutput,
    EngineerAgentResponse,
    PlanAgentResponse,
    SupervisorResponse,
    TestAgentResponse,
    ToolAgentResponse,
    ValidationAgentResponse,
)

# Import hypergraph components
from .hypergraph import (
    OrientedHyperedge,
    OrientedMessageHypergraph,
)

# Import integration components (imported separately to avoid circular imports)
# from .integration import (
#     OHCacheIntegration,
#     OHCacheAgentMixin,
# )

__all__ = [
    "__version__",
    # Formatter exports
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
    # Hypergraph exports
    "OrientedHyperedge",
    "OrientedMessageHypergraph",
    # Cache exports
    "CacheEntry",
    "LocalCacheSystem",
    # Integration exports (commented out to avoid circular imports)
    # "OHCacheIntegration",
    # "OHCacheAgentMixin",
]
