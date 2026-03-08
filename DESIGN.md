# ACF v2.0 Design Documentation

## Overview

Agent Collaboration Framework (ACF) v2.0 is a Python framework for building multi-agent workflows using LangGraph as the underlying execution engine.

## Design Philosophy

### 1. Don't Reinvent the Wheel
LangGraph already provides excellent primitives for state management, checkpointing, and workflow execution. ACF builds on top of LangGraph rather than replacing it.

### 2. Adapter Pattern
Different agents (Claude, kimi, etc.) have different interfaces. The adapter pattern provides a unified interface while allowing backend-specific implementations.

### 3. Separation of Concerns
- **Framework Layer**: ACF-specific code (adapters, builders)
- **Engine Layer**: LangGraph (StateGraph, checkpointing)
- **User Layer**: Application code using ACF

### 4. Demo-First
Include Demo declarations to control complexity and cost during development.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Layer                                │
│  - Application code                                          │
│  - Workflow definitions                                      │
│  - Business logic                                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Framework Layer                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Agent Adapters                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │  │
│  │  │  Claude  │  │   kimi   │  │   Mock   │          │  │
│  │  │  Adapter │  │  Adapter │  │  Adapter │          │  │
│  │  └──────────┘  └──────────┘  └──────────┘          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Workflow System                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │  │
│  │  │  Builder │  │  Runner  │  │  State   │          │  │
│  │  └──────────┘  └──────────┘  └──────────┘          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Engine Layer                               │
│                  LangGraph                                   │
│  - StateGraph                                                │
│  - CheckpointSaver                                           │
│  - BaseStore                                                 │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### AgentAdapter (Abstract Base)

```python
class AgentAdapter(ABC):
    @abstractmethod
    async def execute(self, prompt: str, **kwargs) -> AgentResult: ...
    
    @abstractmethod
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]: ...
    
    @abstractmethod
    async def health_check(self) -> bool: ...
```

**Design Decisions**:
- Async-first interface for non-blocking I/O
- Generic kwargs for backend-specific parameters
- Context manager support for resource cleanup

### WorkflowBuilder

Wraps LangGraph's StateGraph with ACF-specific features:
- Agent node wrapping
- YAML configuration support (planned)
- Validation and error handling

```python
builder = WorkflowBuilder("my_workflow")
builder.add_node("agent1", adapter1)
builder.add_node("agent2", adapter2)
builder.add_edge("agent1", "agent2")
builder.add_conditional_edges("agent1", condition_fn, path_map)
graph = builder.compile()
```

### WorkflowRunner

High-level execution interface:
- Event callbacks for monitoring
- Checkpoint save/load
- Sync/async execution modes
- Cancellation support

```python
runner = WorkflowRunner(graph)
runner.add_callback(on_event)
result = await runner.run("input", checkpoint_id="cp_123")
```

## State Management

### AgentState (TypedDict)

```python
class AgentState(TypedDict, total=False):
    messages: List[Dict[str, Any]]
    current_node: str
    workflow_status: str
    context: Dict[str, Any]
    metadata: Dict[str, Any]
    error: Optional[Dict[str, Any]]
    checkpoint_key: Optional[str]
    memory: Dict[str, Any]
```

**Rationale**:
- TypedDict provides type safety
- `total=False` allows flexible state evolution
- Standard fields support common use cases

### Checkpoint System

Checkpoints enable:
- Workflow pause/resume
- Human-in-the-loop
- Fault tolerance
- Audit trails

```python
@dataclass
class CheckpointData:
    checkpoint_id: str
    state: Dict[str, Any]
    created_at: float
    node_name: str
    metadata: Dict[str, Any]
```

## Error Handling

### Strategy

1. **Per-Node Retry**: AgentNode handles transient failures
2. **Workflow-Level Error**: Runner catches and emits events
3. **Checkpoint Recovery**: Resume from last known good state

### Error Types

```python
class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
```

## Concurrency

### Thread Safety

- AgentAdapter uses `asyncio.Lock` for status updates
- CheckpointSaver implementations are thread-safe
- WorkflowRunner tracks `_is_running` to prevent concurrent runs

### Async Patterns

- All I/O operations are async
- Event callbacks support both sync and async functions
- Streaming uses AsyncIterator

## Testing Strategy

### Unit Tests

- Mock adapters for isolated testing
- Fixture-based setup
- Async test support with pytest-asyncio

### Integration Tests

- Real LangGraph compilation
- End-to-end workflow execution
- Checkpoint save/load verification

### Coverage Areas

1. Adapter interface compliance
2. Workflow construction
3. State transitions
4. Error conditions
5. Checkpoint recovery

## Future Extensions

### Planned Features

1. **Skill System**: Reusable agent capabilities
2. **CLI Tool**: Command-line workflow management
3. **Web UI**: Visual workflow editor
4. **Persistence**: Database-backed checkpoints
5. **Observability**: OpenTelemetry integration

### Extension Points

- Custom adapters via `AdapterFactory.register()`
- Custom checkpoint savers via `CheckpointSaver` base class
- Custom memory stores via `MemoryStore` base class
- Event callbacks for custom monitoring

## Performance Considerations

### Known Limitations

1. **File Polling**: ClaudeAdapter uses polling for output detection
   - Mitigation: Consider watchdog/inotify for production
   
2. **In-Memory Storage**: Default checkpoint/memory stores
   - Mitigation: Implement persistent backends

3. **No Parallel Node Execution**: Sequential node execution
   - Mitigation: Use LangGraph's parallel mapping (future)

### Optimization Opportunities

1. Connection pooling for API adapters
2. Caching for repeated operations
3. Lazy loading for heavy dependencies
4. Streaming for large outputs

## Security

### Best Practices

1. **Secrets Management**: Never hardcode API keys
2. **Input Validation**: Sanitize agent inputs
3. **Sandboxing**: Run agents in isolated environments
4. **Audit Logging**: Track all agent actions

### Current Implementation

- API keys via environment variables
- No built-in authentication (application responsibility)
- Workspace isolation via separate directories

## Migration Guide

### From v1.0 to v2.0

ACF v2.0 is a complete rewrite with:
- New LangGraph-based architecture
- Different API (adapter-based vs. direct LLM)
- Async-first interface
- Better checkpointing

Migration requires rewriting application code.

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Claude Code CLI](https://github.com/anthropics/anthropic-cookbook)
- [Python Asyncio](https://docs.python.org/3/library/asyncio.html)
