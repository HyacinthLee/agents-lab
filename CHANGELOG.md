# Changelog

All notable changes to ACF v2.0 will be documented in this file.

## [2.0.0] - 2026-03-07

### Added
- Initial release of ACF v2.0
- **Agent Adapter Layer**
  - `AgentAdapter` abstract base class with async interface
  - `ClaudeAdapter` for Claude Code CLI integration via tmux
  - `KimiAdapter` for Moonshot AI API
  - `MockAdapter` for testing and development
  - `AdapterFactory` for unified adapter creation
- **LangGraph Integration**
  - `WorkflowBuilder` for constructing StateGraph workflows
  - `AgentNode` for wrapping adapters in workflow nodes
  - `WorkflowRunner` for executing workflows with checkpoint support
  - `AgentState` TypedDict for state management
  - Checkpoint saving and recovery mechanism
- **Features**
  - Synchronous and asynchronous workflow execution
  - Event callback system for monitoring
  - State streaming support
  - Human-in-the-loop (HITL) with checkpoint recovery
  - Conditional routing between nodes
  - Retry logic with configurable attempts
  - In-memory checkpoint and memory stores
- **Testing**
  - 129 unit tests covering all modules
  - Mock-based testing for CI/CD
  - Integration tests with LangGraph
- **Documentation**
  - Comprehensive README with quick start
  - API documentation for all public interfaces
  - 5 example workflows demonstrating features

### Design Principles
- "Don't reinvent the wheel" - Built on LangGraph
- Adapter pattern for pluggable agent backends
- Clear separation between framework and engine layers
- Demo-first approach for cost control

## Future Roadmap

### [2.1.0] - Planned
- YAML configuration file support
- CLI tool (acf init/run/status)
- Pre-built templates (software-dev, content-creation)
- Persistent checkpoint storage (SQLite/Redis)

### [2.2.0] - Planned
- OpenTelemetry tracing integration
- Web UI for workflow visualization
- Multi-LLM backend support (OpenAI, Gemini)
- Distributed workflow execution

### [3.0.0] - Planned
- Agent skill system
- Auto-scaling for agent pools
- Advanced debugging tools
- Enterprise features (RBAC, audit logs)
