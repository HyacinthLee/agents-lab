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
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Agent Management                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │  │
│  │  │ Template │  │ Workspace│  │  Config  │          │  │
│  │  └──────────┘  └──────────┘  └──────────┘          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Skills System                           │  │
│  │  ┌──────────┐  ┌──────────┐                          │  │
│  │  │  Skill   │  │  Manager │                          │  │
│  │  └──────────┘  └──────────┘                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Storage Layer                           │  │
│  │  ┌──────────┐  ┌──────────┐                          │  │
│  │  │  Shared  │  │  Board   │                          │  │
│  │  │  Board   │  │  Entry   │                          │  │
│  │  └──────────┘  └──────────┘                          │  │
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

### 1. AGENT.md - Agent Configuration

**Framework generates template → User manually customizes**

```python
from acf.agent import AgentTemplate

# Framework generates template
AgentTemplate.generate(
    role="Product Manager", 
    workspace="./agents/pm"
)
# Creates:
# ./agents/pm/AGENT.md  (template)
# ./agents/pm/skills/   (empty directory)
# ./agents/pm/workspace/ (empty directory)
```

**Generated AGENT.md Template**:
```markdown
# Product Manager

## Identity
你是产品经理，负责将用户需求转化为产品需求文档。

## ⚠️ Demo Declaration
- ✅ 简单设计，核心功能即可
- ✅ PRD 控制在 500 字以内
- ❌ 不需要市场分析、竞品调研

## Responsibilities
- 分析用户需求
- 编写 PRD 文档
- 定义验收标准

## Constraints
- 不写代码实现细节
- 不指定技术栈

## Skills
- @write-prd
- @analyze-requirements
```

**User Customization**: Edit the generated AGENT.md to refine behavior.

---

### 2. Skill System - Agent-Decided Usage

**Location**: `agents/{name}/skills/*.md`

**Skill Format**:
```markdown
---
name: write-prd
description: 编写产品需求文档
---

## When to Use
当需要为新功能编写 PRD 时使用

## Input
- feature_name: 功能名称
- target_users: 目标用户

## Output
- PRD 文档 (Markdown)

## Steps
1. 理解功能背景
2. 编写产品概述
3. 列出功能列表
4. 定义验收标准
```

**Usage Modes**:

| Mode | How | When |
|------|-----|------|
| **Autonomous** (Default) | Agent decides which skill to use | `builder.add_node("pm", adapter)` |
| **Enforced** | Workflow forces specific skill | `builder.add_node("pm", adapter, skill="write-prd")` |
| **Prompt** | AGENT.md mentions skill trigger | "When user says 'analyze', use @analyze" |

**Implementation**:
```python
# Agent loads skills and formats for prompt
skills = adapter.load_skills()  # From skills/ directory
system_prompt = f"""
{agent_config}  # AGENT.md content

## Available Skills
{format_skills(skills)}  # @skill_name: description

Use appropriate skills based on the task.
"""
```

---

### 3. Shared Whiteboard - Agent Communication

**Pattern**: Pull-based shared state using LangGraph BaseStore

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Agent A │     │ Agent B │     │ Agent C │
└────┬────┘     └────┬────┘     └────┬────┘
     │               │               │
     └───────────────┼───────────────┘
                     ▼ Pull mode
            ┌─────────────────┐
            │  Shared Board   │
            │  (BaseStore)    │
            │                 │
            │ - Deliverables  │  # PRD, Code, Reports
            │ - Decisions     │  # Key decisions
            │ - Lessons       │  # Learned experiences
            └─────────────────┘
```

**Data Flow - Dual Write Pattern**:
```
Workflow State (LangGraph)          Shared Whiteboard (BaseStore)
        │                                   │
        ▼                                   ▼
┌───────────────┐                 ┌─────────────────────┐
│ State Passing │  (immediate)    │ Long-term Storage   │  (async)
│ - prd_file    │ ───────────────▶│ namespace=("team",) │
│ - code_file   │                 │ - semantic search   │
│ - test_report │                 │ - cross-workflow    │
└───────────────┘                 └─────────────────────┘
```

**Implementation**:
```python
class AgentNode:
    def execute(self, state: AgentState) -> AgentState:
        # 1. Read from shared board (pull)
        shared = self.store.search(
            namespace=("team", "deliverables"),
            query=state["requirement"]
        )
        
        # 2. Execute with shared context
        result = self.adapter.execute(task, context=shared)
        
        # 3. Write to workflow state (next agent)
        state["output"] = result.output
        
        # 4. Write to shared board (long-term)
        self.store.put(
            namespace=("team", "deliverables"),
            key=f"{self.name}-{workflow_id}",
            value={"content": result.output, "author": self.name},
            index=["content"]  # Enable semantic search
        )
        
        return state
```

---

### 4. Workspace Structure

```
project/
├── agents/
│   ├── agent-a/
│   │   ├── AGENT.md          # Role definition (user edited)
│   │   ├── skills/           # Private skills
│   │   │   └── skill1.md
│   │   └── workspace/        # Private workspace (rw)
│   │       └── outputs...
│   └── agent-b/
│       ├── AGENT.md
│       ├── skills/
│       └── workspace/
└── shared/                   # Shared space (rw for all)
    ├── deliverables/         # Cross-agent deliverables
    ├── decisions/            # Key decisions
    └── lessons/              # Learned lessons
```

**Access Rules**:
| Location | Read | Write | Purpose |
|----------|------|-------|---------|
| `agents/{name}/workspace/` | Self | Self | Private outputs |
| `agents/{name}/skills/` | Self | Self | Private skills |
| `shared/` | All | All | Cross-agent sharing |
| `shared/deliverables/` | All | All | Deliverables |

---

### 5. AgentAdapter Interface

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

---

### 6. WorkflowBuilder

```python
builder = WorkflowBuilder("my_workflow")

# Agent with autonomous skill selection
builder.add_node("agent1", adapter1)

# Agent with enforced skill
builder.add_node("agent2", adapter2, skill="write-prd")

# Edges
builder.add_edge("agent1", "agent2")
builder.add_conditional_edges("agent1", condition_fn, path_map)

graph = builder.compile()
```

---

### 7. WorkflowRunner

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

### Checkpoint System

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

```python
class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
```

## Future Extensions

### Planned Features

1. **CLI Tool**: `acf init`, `acf run`, `acf resume`
2. **Web UI**: Visual workflow editor
3. **Persistent Storage**: Postgres/SQLite backends
4. **Observability**: OpenTelemetry integration

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Claude Code CLI](https://github.com/anthropics/anthropic-cookbook)
- [Python Asyncio](https://docs.python.org/3/library/asyncio.html)
