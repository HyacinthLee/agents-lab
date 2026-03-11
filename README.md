# ACF v2.0 - Agent Collaboration Framework

基于 LangGraph 的 Agent 协作框架，支持多 Agent 工作流编排。

## 🎯 核心特性

- **Agent 适配层**：统一接口支持 Claude、kimi、Mock 等多种 Agent
- **LangGraph 集成**：完整支持 StateGraph、条件分支、循环
- **工作流编排**：可视化构建多 Agent 协作流程
- **检查点恢复**：支持中断恢复和人机协作
- **事件系统**：实时监控工作流执行状态

## 📦 安装

```bash
# 从源码安装
cd acf-v2
pip install -e ".[dev]"

# 依赖
- Python >= 3.10
- LangGraph >= 0.3.0
- tmux (用于 Claude 适配器)
```

## 🚀 快速开始

### 1. 基础适配器使用

```python
import asyncio
from acf.adapter.factory import AdapterFactory

async def main():
    # 创建 Mock 适配器
    adapter = AdapterFactory.create("mock", name="test-agent")
    
    # 执行提示词
    result = await adapter.execute("Hello, world!")
    print(f"Status: {result.status}")
    print(f"Output: {result.output}")

asyncio.run(main())
```

### 2. 简单工作流

```python
import asyncio
from acf.adapter.factory import AdapterFactory
from acf.workflow.builder import WorkflowBuilder
from acf.workflow.runner import WorkflowRunner

async def main():
    # 创建适配器
    analyzer = AdapterFactory.create("mock", name="analyzer")
    writer = AdapterFactory.create("mock", name="writer")
    
    # 构建工作流
    builder = WorkflowBuilder("content_pipeline")
    builder.add_node("analyze", analyzer)
    builder.add_node("write", writer)
    builder.add_edge("analyze", "write")
    builder.set_entry_point("analyze")
    
    # 编译并运行
    graph = builder.compile()
    runner = WorkflowRunner(graph)
    
    result = await runner.run("Write a blog post about AI")
    print(f"Success: {result.success}")
    print(f"Output: {result.get_output()}")

asyncio.run(main())
```

### 3. 使用 Claude Code

```python
from acf.adapter.factory import AdapterFactory

# 创建 Claude 适配器（需要 tmux 和 claude CLI）
claude = AdapterFactory.create(
    "claude",
    name="claude-dev",
    metadata={
        "workspace_dir": "/path/to/project",
        "confirm_delay": 0.5,  # 确认延迟
    }
)

# 执行开发任务
result = await claude.execute("Create a Python calculator")
```

## 🚀 核心示例：dev_workflow_v2

**路径**: `examples/dev_workflow/dev_workflow_v2.py`

完整的软件研发流程多 Agent 系统，从需求到部署的 5 阶段工作流：

```
产品 Agent → 架构师 Agent → 开发 Agent → 测试 Agent → 运维 Agent
   (PRD)        (规格说明书)      (代码)      (测试用例+执行)   (部署脚本)
```

**特性**:
- ✅ 基于 LangGraph + ACF 框架
- ✅ 基于 Claude Code 真实执行
- ✅ AGENT.md + Skills 动态提示词
- ✅ 自动修复测试用例导入
- ✅ 自动清理历史交付物
- ✅ **测试首次通过**（2026-03-11）

**运行**:
```bash
cd examples/dev_workflow
python3 dev_workflow_v2.py
```

**输出示例**:
```
📋 【产品 Agent】... ✅ (38.2s, 403字符)
🏗️  【架构师 Agent】... ✅ (38.2s, 1104字符)
💻 【开发 Agent】... ✅ (38.2s, 2685字符)
🧪 【测试 Agent】... ✅ 测试通过
🚀 【运维 Agent】... ✅ (94.4s, 7089字符)
```

详见 [REFACTOR_SUMMARY.md](REFACTOR_SUMMARY.md) 了解完整重构历程。

## 📚 使用案例

### 案例 1：内容生成流水线

```python
examples/content_generation.py
```

演示多 Agent 协作生成内容：
- **研究 Agent**：收集资料
- **大纲 Agent**：生成文章结构
- **写作 Agent**：撰写内容
- **审核 Agent**：质量检查

### 案例 2：代码审查工作流

```python
examples/code_review.py
```

自动化代码审查流程：
- **静态分析 Agent**：检查代码规范
- **安全扫描 Agent**：检测漏洞
- **性能分析 Agent**：优化建议
- **汇总 Agent**：生成审查报告

### 案例 3：人机协作（HITL）

```python
examples/human_in_the_loop.py
```

演示检查点和中断恢复：
- 工作流执行到关键节点暂停
- 人工审核后继续
- 支持修改和重试

### 案例 4：条件分支工作流

```python
examples/conditional_workflow.py
```

根据状态动态选择执行路径：
- 根据输入类型选择不同处理节点
- 支持默认分支
- 错误处理和重试

### 案例 5：循环和迭代

```python
examples/iteration_workflow.py
```

实现循环处理：
- 文档分批处理
- 结果汇总
- 直到满足退出条件

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    用户层 (User Layer)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  CLI 工具    │  │  YAML 配置  │  │  Python API         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   框架层 (Framework Layer)                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Agent Adapters                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │  │
│  │  │  Claude  │  │   kimi   │  │   Mock   │          │  │
│  │  └──────────┘  └──────────┘  └──────────┘          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Workflow System                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │  │
│  │  │  Builder │  │  Runner  │  │  State   │          │  │
│  │  └──────────┘  └──────────┘  └──────────┘          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   引擎层 (Engine Layer)                      │
│                  LangGraph (StateGraph)                     │
└─────────────────────────────────────────────────────────────┘
```

## 📖 API 文档

### AgentAdapter 接口

```python
class AgentAdapter(ABC):
    @abstractmethod
    async def execute(self, prompt: str, **kwargs) -> AgentResult:
        """执行提示词并返回结果"""
        pass
    
    @abstractmethod
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """流式执行"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
```

### WorkflowBuilder

```python
builder = WorkflowBuilder("my_workflow")

# 添加节点
builder.add_node("node1", adapter1)
builder.add_node("node2", adapter2)

# 添加边
builder.add_edge("node1", "node2")
builder.add_edge("node2", END)

# 设置入口
builder.set_entry_point("node1")

# 条件分支
builder.add_conditional_edges(
    "node1",
    condition=lambda state: state["category"],
    path_map={"A": "node_a", "B": "node_b"},
    default="node_default"
)

# 编译
graph = builder.compile()
```

### WorkflowRunner

```python
runner = WorkflowRunner(graph)

# 添加回调
def on_event(event):
    print(f"Event: {event.event_type}")

runner.add_callback(on_event)

# 执行
result = await runner.run("Input prompt")

# 从检查点恢复
result = await runner.run("Input", checkpoint_id="cp_123")

# 取消
runner.cancel()
```

## 📁 项目结构

```
acf-v2/
├── src/acf/                    # 核心框架
│   ├── adapter/                # Agent 适配层
│   │   ├── base.py            # AgentAdapter 基类
│   │   ├── claude.py          # Claude Code 适配器
│   │   ├── kimi.py            # kimi API 适配器
│   │   ├── mock.py            # Mock 适配器
│   │   └── factory.py         # 适配器工厂
│   ├── agent/                  # Agent 管理
│   │   ├── agent_template.py  # AGENT.md 模板生成
│   │   └── workspace_manager.py # 工作空间管理
│   ├── skills/                 # 技能系统
│   │   └── skill_manager.py   # 技能加载与管理
│   ├── store/                  # 存储层
│   │   └── shared_board.py    # 共享白板 (BaseStore)
│   └── workflow/               # 工作流系统
│       ├── builder.py         # WorkflowBuilder
│       ├── runner.py          # WorkflowRunner
│       ├── nodes.py           # AgentNode, ConditionalNode
│       └── state.py           # AgentState, Checkpoint
├── tests/                      # 测试套件
│   ├── agent/                 # Agent 管理测试
│   ├── skills/                # 技能系统测试
│   ├── store/                 # 存储层测试
│   └── test_*.py              # 核心模块测试
├── examples/                   # 使用示例
│   ├── basic_usage.py         # 基础用法
│   ├── workflow_example.py    # 工作流示例
│   ├── real_agents/           # Real Agent 完整示例
│   └── dev_workflow/          # 软件研发流程示例
└── docs/                       # 文档
    ├── DESIGN.md              # 设计文档
    └── blog/                  # 技术博客
```

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/test_adapter_base.py -v
pytest tests/test_workflow_runner.py -v

# 运行示例
python examples/basic_usage.py
python examples/workflow_example.py
```

## 📈 性能优化建议

1. **文件轮询优化**：使用 `watchdog` 替代 `_wait_for_file_stability()` 的轮询
2. **重试策略**：使用指数退避替代固定间隔
3. **并发执行**：多个独立节点可并行执行

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 许可证

MIT License

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) - 工作流引擎
- [Claude Code](https://github.com/anthropics/anthropic-cookbook) - Claude CLI
- [Moonshot AI](https://www.moonshot.cn/) - kimi API
