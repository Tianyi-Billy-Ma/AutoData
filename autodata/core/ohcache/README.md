# OHCache (Oriented Hypergraph Cache System)

OHCache is a comprehensive system designed for effective and cost-efficient multi-agent collaboration in open web data collection tasks. It consists of three main components:

1. **Oriented Message Hypergraph** - Models inter-agent message flow as oriented hyperedges
2. **Oriented Hyperedge Formatter** - Enforces structured communication schema and hyperedge message accumulation
3. **Local Cache System** - Stores reusable artifacts for agents to retrieve on demand

## Overview

The OHCache system enables sophisticated communication patterns between agents in the AutoData multi-agent system, allowing for:

- Complex message routing through oriented hyperedges
- Efficient caching of agent responses and artifacts
- Structured communication with type-safe response models
- Persistent storage and retrieval of cached data
- Tag-based organization and filtering of cached content

## Components

### 1. Oriented Message Hypergraph

The `OrientedMessageHypergraph` class models inter-agent communication as a hypergraph where:
- **Nodes** represent agents
- **Oriented hyperedges** represent message flows between multiple agents
- Messages can be accumulated and routed based on hyperedge orientation

#### Key Features:
- Support for complex routing patterns (one-to-many, many-to-one, many-to-many)
- Message buffering and accumulation
- Type-based message filtering
- Connection analysis and statistics

### 2. Local Cache System

The `LocalCacheSystem` class provides comprehensive caching capabilities:
- Multiple cache types (code, data, configuration, etc.)
- TTL-based expiration
- Tag-based organization and retrieval
- Persistent storage to disk
- Memory-efficient operations with configurable limits

#### Key Features:
- Automatic cleanup of expired entries
- Memory limit enforcement
- Persistent storage with automatic save/load
- Comprehensive statistics and monitoring

#### Filesystem Persistence
- Each cached artifact is written to `{cache_dir}/artifacts/{slugified_key}-{hash}.{extension}` using an extension that matches the payload (e.g., `.json`, `.html`, `.txt`).
- A companion metadata file `{cache_dir}/meta/{filename}.meta.json` records the original cache key, cache type, tags, TTL, and serializer details for offline inspection.
- Retrieval loads artifact content from disk on demand, ensuring the latest persisted data is returned even across process boundaries.
- Previous `cache.pkl` snapshots are automatically migrated to the new per-artifact layout (creating the `artifacts/` + `meta/` directories if missing) the next time the cache is initialised.

### 3. Response Formatters

Structured response models for all agent types:
- `BaseResponse` - Foundation for all agent responses
- `BlueprintAgentResponse` - Blueprint generation responses
- `BrowserAgentResponse` - Web browsing operation responses
- `EngineerAgentResponse` - Code generation responses
- `PlanAgentResponse` - Planning and strategy responses
- `SupervisorResponse` - Supervisor decision responses
- `TestAgentResponse` - Testing and debugging responses
- `ToolAgentResponse` - Tool execution responses
- `ValidationAgentResponse` - Validation and quality assessment responses

### 4. Integration Layer

The `OHCache` class provides seamless integration with existing AutoData components:
- Automatic setup for BaseAgent instances
- Graph-level integration with AutoDataGraph
- Mixin class for easy agent enhancement

## Usage Examples

### Basic Setup

```python
from autodata.core.ohcache.ohcache import OHCache
from autodata.core.ohcache import LocalCacheSystem, OrientedMessageHypergraph

# Create OHCache integration
integration = OHCache(config=...)  # Provide an OHCacheConfig

# Or create with custom components
cache_system = LocalCacheSystem(cache_dir="./cache", max_memory_entries=500)
hypergraph = OrientedMessageHypergraph()
integration = OHCache(config=...,)  # OHCache internally creates components
```

### Agent Integration

```python
from autodata.agents.base_agent import BaseAgent
from autodata.core.ohcache.ohcache import OHCache

# Create an agent
agent = BaseAgent(
    instruction="You are a helpful agent",
    description="A test agent",
    agent_name="TestAgent",
    formatter=SomeResponseModel
)

# Set up OHCache integration
integration = OHCache(config=...)
integration.setup_agent_integration(agent)

# Now the agent has caching and hypergraph capabilities
agent.cache_set("my_data", {"key": "value"})
cached_data = agent.cache_get("my_data")
```

### Hypergraph Communication

```python
from autodata.core.ohcache import OrientedMessageHypergraph
from autodata.core.ohcache.formatter import TestAgentResponse

# Create hypergraph and add agents
hypergraph = OrientedMessageHypergraph()
hypergraph.add_nodes(["agent1", "agent2", "agent3"])

# Create a hyperedge for communication
hypergraph.add_hyperedge(
    edge_id="broadcast_edge",
    source_agents={"agent1"},
    target_agents={"agent2", "agent3"},
    message_type="broadcast"
)

# Send a message
message = TestAgentResponse(execution_result="Task completed")
edge_ids = hypergraph.send_message("agent1", message, message_type="broadcast")

# Receive messages
messages = hypergraph.receive_messages("agent2", message_type="broadcast")
```

### Caching System

```python
from autodata.core.ohcache import LocalCacheSystem

# Create cache system
cache = LocalCacheSystem(cache_dir="./cache")

# Store data with metadata and tags
cache.set(
    key="web_scraping_results",
    value={"data": "scraped_content"},
    cache_type="web_data",
    ttl=3600,  # 1 hour
    tags={"scraping", "ecommerce", "prices"}
)

# Retrieve data
data = cache.get("web_scraping_results", cache_type="web_data")

# Get data by tags
ecommerce_data = cache.get_by_tags({"ecommerce", "prices"})

# Get data by type
all_web_data = cache.get_by_type("web_data")
```

### Graph Integration

```python
from autodata.core.graph import AutoDataGraph
from autodata.core.ohcache.ohcache import OHCache

# Create graph
graph = AutoDataGraph(llm_config=config)

# Set up OHCache integration
integration = OHCache(config=...)
integration.setup_graph_integration(graph)

# Access OHCache via graph
graph.ohcache.cache_system.set("project_config", {"setting": "value"})
config = graph.ohcache.cache_system.get("project_config")

# Create hyperedges for agent communication
# Create hyperedges for agent communication via hypergraph
graph.ohcache.hypergraph.add_hyperedge(
    "research_to_development",
    {"BrowserAgent", "ToolAgent"},
    {"EngineerAgent", "TestAgent"},
    "research_results"
)
```

### Response Models

```python
from autodata.core.ohcache.formatter import EngineerAgentResponse

# Create a structured response
response = EngineerAgentResponse(
    code="print('Hello, World!')",
    title="hello_world",
    summary="Prints a greeting to standard output.",
    description="A simple hello world program",
    dependencies=["requests"],
)

# Convert to different formats
easydict = response.to_easydict()
dictionary = response.to_dict()
message = response.to_message()

# Optionally cache structured responses directly via the cache system
integration.cache_system.set(
    key="EngineerAgent:latest_response",
    value=response,
    cache_type="agent_response",
    ttl=7200,
)
```

## Advanced Features

### Custom Hyperedge Patterns

```python
# Many-to-many communication
hypergraph.add_hyperedge(
    "collaborative_analysis",
    {"Agent1", "Agent2", "Agent3"},
    {"Agent4", "Agent5"},
    "analysis_results"
)

# Broadcast pattern
hypergraph.add_hyperedge(
    "status_broadcast",
    {"SupervisorAgent"},
    {"Agent1", "Agent2", "Agent3", "Agent4"},
    "status_update"
)
```

### Cache Management

```python
# Clear specific cache types
cache.clear(cache_type="temporary_data")

# Get cache statistics
stats = cache.stats
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Total entries: {stats['total_entries']}")

# Manual cleanup of hypergraph message buffers
hypergraph.clear_all_buffers()
```

### Integration Statistics

```python
# Get comprehensive statistics
stats = integration.integration_stats
print(f"Caching enabled: {stats['caching_enabled']}")
print(f"Hypergraph enabled: {stats['hypergraph_enabled']}")
print(f"Cache hit rate: {stats['cache_stats']['hit_rate']:.2%}")
print(f"Hypergraph nodes: {stats['hypergraph_stats']['node_count']}")
```

## Configuration

### Cache System Configuration

```python
cache = LocalCacheSystem(
    cache_dir="./cache",           # Persistent storage directory
    max_memory_entries=1000,       # Memory limit
    auto_cleanup=True              # Automatic cleanup of expired entries
)
```

### Integration Configuration

```python
# Configure OHCache via OHCacheConfig and initialize
from autodata.core.config import OHCacheConfig

ohcfg = OHCacheConfig(enable_ohcache=True)
integration = OHCache(config=ohcfg)
```

## Best Practices

1. **Use appropriate cache types** - Organize cached data by type (code, data, config, etc.)
2. **Set reasonable TTL values** - Balance between data freshness and performance
3. **Use tags for organization** - Tag cached items for easy retrieval and management
4. **Monitor cache statistics** - Regularly check hit rates and memory usage
5. **Design hyperedges carefully** - Consider the communication patterns between agents
6. **Use structured responses** - Leverage the type-safe response models for consistency

## Performance Considerations

- The cache system automatically manages memory usage and cleans up expired entries
- Hypergraph operations are optimized for typical multi-agent communication patterns
- Persistent storage is automatically handled with minimal performance impact
- All components provide comprehensive statistics for monitoring and optimization

## Reference

For more detailed information about the OHCache system, refer to the research paper:
- **OHCache: Oriented Hypergraph Cache System for Multi-Agent Collaboration**
- arXiv: https://arxiv.org/abs/2505.15859
