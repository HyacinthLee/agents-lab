# 软件研发流程多 Agent 系统 - ACF-v2 重构版

基于 LangGraph + ACF-v2 框架的软件研发流程自动化系统。

## 概述

本项目是将原有的 `langgraph-dev-workflow/dev_workflow_v3.py` 从直接使用 tmux 调用 Claude，重构为使用 ACF-v2 框架（ClaudeAdapter、WorkflowBuilder、SharedBoard）。

## 架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Product   │────▶│    Dev      │────▶│     QA      │────▶│    Ops      │
│    Agent    │     │    Agent    │     │    Agent    │     │    Agent    │
└─────────────┘     └─────────────┘     └──────┬──────┘     └──────┬──────┘
                                               │                   │
                                               ▼                   ▼
                                          ┌─────────┐         ┌─────────┐
                                          │  Reject │         │  Reject │
                                          │(to Dev) │         │(to Dev) │
                                          └─────────┘         └─────────┘
```

## 关键组件

### 1. ClaudeAdapter (`acf/adapter/claude.py`)
- 替代直接 tmux 调用
- 提供异步 `execute()` 和 `stream()` 接口
- 自动处理 Claude Code 初始化确认

```python
from acf import AdapterFactory
adapter = AdapterFactory.create("claude", name="product_agent", ...)
result = await adapter.execute(prompt)
```

### 2. WorkflowBuilder (`acf/workflow/builder.py`)
- 构建 LangGraph 工作流
- 支持条件分支和循环
- 提供 Fluent API

### 3. WorkflowRunner (`acf/workflow/runner.py`)
- 执行工作流
- 支持检查点恢复
- 提供事件回调机制

### 4. SharedBoard (`shared_board.py`)
- 基于 SimpleSharedBoard 实现
- 存储交付物链接和元数据
- 支持导出为 JSON

## 工作流阶段

1. **Product Agent** - 生成 PRD 文档
2. **Dev Agent** - 生成规格说明书 + 代码（两步）
3. **QA Agent** - 生成测试计划 + 测试用例 + 执行测试（三步）
4. **Ops Agent** - 生成部署脚本 + 上线报告（两步）

## 状态管理

- 使用 `DevState` (TypedDict) 传递状态
- 使用 `SimpleSharedBoard` 存储交付物链接
- 质量门禁：测试失败打回开发，部署失败也打回

## 安装

### 依赖

```bash
# 基础依赖
pip install langgraph

# ACF-v2 框架
# 确保 /root/.openclaw/workspace/acf-v2/src 在 PYTHONPATH 中

# Claude Code CLI
# 确保已安装 claude 命令行工具
```

### 环境要求

- Python 3.10+
- tmux
- Claude Code CLI
- LangGraph

## 使用

### 基本使用

```bash
# 使用默认需求
cd /root/.openclaw/workspace/acf-v2/examples/dev_workflow
python dev_workflow_acf.py

# 使用自定义需求
python dev_workflow_acf.py "开发一个待办事项管理工具，支持添加、删除、标记完成功能"
```

### 输出

所有交付物保存在 `output/` 目录：

- `PRD_YYYYMMDD_HHMMSS.md` - 产品需求文档
- `Spec_YYYYMMDD_HHMMSS.md` - 软件规格说明书
- `code_v{N}_YYYYMMDD_HHMMSS.py` - 代码实现
- `test_plan_YYYYMMDD_HHMMSS.md` - 测试计划
- `test_cases_YYYYMMDD_HHMMSS.py` - 测试用例
- `test_report_YYYYMMDD_HHMMSS.md` - 测试报告
- `deploy_YYYYMMDD_HHMMSS.sh` - 部署脚本
- `deploy_report_YYYYMMDD_HHMMSS.md` - 上线报告
- `shared_board_YYYYMMDD_HHMMSS.json` - SharedBoard 导出
- `workflow_YYYYMMDD_HHMMSS.log` - 执行日志

## 与原版的差异

| 特性 | 原版 (v3) | ACF-v2 版 |
|------|-----------|-----------|
| Agent 调用 | `run_claude_in_tmux()` 直接调用 | `ClaudeAdapter.execute()` 异步调用 |
| 状态管理 | 原生 TypedDict | TypedDict + AgentState |
| 交付物存储 | 仅文件系统 | 文件系统 + SharedBoard |
| 工作流构建 | 直接 StateGraph | StateGraph + WorkflowBuilder 支持 |
| 日志 | Tee 类双写 | 保留 Tee 类双写 |
| 代码风格 | 同步 | async/await 异步 |

## 代码示例

### 原版调用方式

```python
result = run_claude_in_tmux("产品经理", prompt, ...)
```

### ACF-v2 调用方式

```python
from acf import AdapterFactory

adapter = AdapterFactory.create(
    "claude",
    name="product_agent",
    timeout=300,
    metadata={"workspace_dir": WORK_DIR}
)
result = await adapter.execute(prompt)
```

### SharedBoard 使用

```python
from shared_board import SimpleSharedBoard

shared_board = SimpleSharedBoard(team_id="dev_workflow")

# 写入交付物
shared_board.put(
    namespace=("team", "deliverables"),
    key=f"prd_{timestamp}",
    value={"filename": filename, "filepath": filepath},
    author="product_agent"
)

# 导出
shared_board.export_to_file("shared_board.json")
```

## 质量门禁

### 测试打回

当 QA Agent 执行测试失败时：
1. 打回记录被添加到 `rejections` 列表
2. 流程返回到 Dev Agent
3. Dev Agent 读取测试报告内容，修复缺陷后重新开发

### 部署打回

当 Ops Agent 部署失败时：
1. 打回记录被添加到 `rejections` 列表
2. 流程返回到 Dev Agent
3. 需要重新修复并再次测试

## 配置

### 工作目录

```python
WORK_DIR = "/root/.openclaw/workspace/acf-v2/examples/dev_workflow/output"
```

### 最大迭代次数

```python
initial_state = {
    "max_iterations": 2,  # 最多打回重试 2 次
}
```

### 超时设置

| Agent | 超时时间 |
|-------|----------|
| Product | 300s |
| Dev (规格) | 300s |
| Dev (代码) | 600s |
| QA (测试计划) | 300s |
| QA (测试用例) | 600s |
| QA (报告) | 300s |
| Ops (脚本) | 300s |
| Ops (报告) | 300s |

## 日志

日志同时输出到控制台和文件：

```
output/workflow_YYYYMMDD_HHMMSS.log
```

格式：
```
=== 软件研发流程多 Agent 系统 (ACF-v2) ===
启动时间: 2026-03-09 19:20:00
日志文件: ...
==================================================

=== ... 【产品 Agent - Claude】正在编写 PRD 文档...
     ⏳ 调用 Claude (产品经理)... ✅ (45.2s)
...
```

## 故障排除

### Claude Code 未响应

- 检查 tmux 是否安装：`tmux -V`
- 检查 claude 命令是否可用：`which claude`
- 检查权限：首次运行可能需要确认 root 权限（自动发送 "2"）

### 测试执行失败

- 检查 Python 版本：`python3 --version`
- 检查 pytest 是否安装：`pip install pytest`
- 检查代码语法错误：查看生成的代码文件

### SharedBoard 导出失败

- 检查 output 目录权限
- 检查磁盘空间

## 扩展

### 添加新的 Agent

```python
async def new_agent(state: DevState) -> dict:
    agent = ClaudeAgent("new_agent", "新角色", timeout=300)
    prompt = "..."
    content = await agent.execute(prompt)
    # 保存交付物...
    return {"new_file": filename}
```

### 自定义路由逻辑

```python
def route_custom(state: DevState) -> Literal["path_a", "path_b"]:
    if state.get("condition"):
        return "path_a"
    return "path_b"
```

## 运行记录

### 2026-03-10 完整运行（命令行计算器）

```
【需求】创建一个命令行计算器

📋 产品 Agent   ✅ 45.5s  →  PRD (2463字符)
💻 开发 Agent   ✅ 291s   →  规格说明书 + 代码 (39318字符)
🧪 测试 Agent   ✅ 146s   →  测试计划 + 用例 + 报告 ✅通过
🚀 运维 Agent   ✅ 100.5s →  部署脚本 (18515字符)
📝 运维报告     ✅ 43s    →  上线报告 (16701字符) [补跑]

总耗时：约12分钟
测试通过率：100% (13/13)
结论：全流程闭环，质量达标，建议上线
```

**交付物清单：**

| 文件 | 大小 | 说明 |
|------|------|------|
| PRD_20260310_004412.md | 4.3KB | 产品需求文档 |
| Spec_20260310_004608.md | 20.6KB | 软件规格说明书 |
| code_v1_20260310_004608.py | 42KB | 源代码实现 |
| test_plan_20260310_004954.md | 4.3KB | 测试计划 |
| test_cases_20260310_004954.py | 3.6KB | 测试用例 |
| test_report_20260310_004954.md | 5.8KB | 测试报告 |
| deploy_20260310_005311.sh | 21KB | 部署脚本 |
| deploy_report_20260310_074500.md | 16.7KB | 上线报告 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `dev_workflow_acf.py` | 主工作流实现 |
| `README.md` | 使用说明 |
| `requirements.txt` | 依赖列表 |
| `output/` | 交付物和日志输出目录 |

## 参考

- [ACF-v2 框架](/root/.openclaw/workspace/acf-v2/)
- [原版工作流](/root/.openclaw/workspace/langgraph-dev-workflow/dev_workflow_v3.py)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
