# ACF v2.0 重构与整合工作总结

## 一、代码库结构

```
acf-v2/
├── src/acf/                    # 核心框架代码
│   ├── adapter/                # Agent 适配器
│   │   ├── base.py            # AgentAdapter 基类
│   │   ├── claude.py          # Claude Code CLI 适配器
│   │   ├── kimi.py            # Moonshot API 适配器
│   │   ├── mock.py            # Mock 测试适配器
│   │   └── factory.py         # 适配器工厂
│   ├── agent/                  # Agent 管理
│   │   ├── agent_template.py  # AGENT.md 模板生成
│   │   └── workspace_manager.py # 独立 workspace 管理
│   ├── skills/                 # 技能系统
│   │   └── skill_manager.py   # 技能加载与格式化
│   ├── store/                  # 存储层
│   │   └── shared_board.py    # 共享白板
│   ├── workflow/               # 工作流系统
│   │   ├── builder.py         # WorkflowBuilder
│   │   ├── runner.py          # WorkflowRunner
│   │   ├── state.py           # AgentState 状态管理
│   │   └── nodes.py           # AgentNode 节点包装
│   └── __init__.py
├── examples/                   # 使用示例
│   ├── dev_workflow/          # ⭐ 软件研发流程多 Agent 系统
│   │   ├── dev_workflow_v2.py # 当前主版本
│   │   ├── dev_workflow_acf.py # 原版 ACF 实现
│   │   ├── agents/            # Agent 配置目录
│   │   │   ├── product_manager/
│   │   │   ├── architect/
│   │   │   ├── developer/
│   │   │   ├── tester/
│   │   │   └── ops_engineer/
│   │   └── output/            # 交付物输出目录
│   ├── real_agents/           # Real Agent 示例
│   ├── basic_usage.py
│   ├── workflow_example.py
│   └── ...
├── tests/                      # 单元测试
├── docs/                       # 文档
│   └── blog/                   # 技术博客
├── README.md
├── DESIGN.md
└── CHANGELOG.md
```

## 二、重构历程

### 阶段一：基础框架构建（3月7日）

**目标**：创建 ACF v2.0 核心框架

**完成内容**：
- ✅ AgentAdapter 抽象基类
- ✅ ClaudeAdapter（tmux + `--print` 模式）
- ✅ KimiAdapter（Moonshot API）
- ✅ MockAdapter（测试用）
- ✅ AdapterFactory 工厂模式
- ✅ WorkflowBuilder + WorkflowRunner
- ✅ AgentState 状态管理
- ✅ 129个单元测试全部通过

### 阶段二：Real Agent 示例（3月8-9日）

**目标**：实现带 AGENT.md + Skills 的真实 Agent 示例

**完成内容**：
- ✅ AgentTemplate（AGENT.md 模板生成）
- ✅ WorkspaceManager（独立 workspace）
- ✅ SkillManager（技能系统）
- ✅ SharedBoard（共享白板）
- ✅ 3个真实 Agent：Product Manager、Developer、Code Reviewer

### 阶段三：dev_workflow 整合与修复（3月10-11日）

**目标**：整合 dev_workflow_acf + real_agents → dev_workflow_v2

**核心问题与解决**：

#### 问题1："No output" 错误

**现象**：架构师/开发 Agent 频繁返回 "No output"

**根因**：
- 提示词过于复杂（AGENT.md + Skills 系统）
- ClaudeAdapter 输出检测逻辑过严
  - `min_wait = 8` 秒太短
  - 稳定检测只需 2 次，容易误判
  - 超时后未强制读取文件

**解决**：
```python
# 1. 简化提示词
prompt = f"""你是XXX。请直接输出XXX的完整内容。
需求：{...}
要求：...
请直接输出："""

# 2. 修复 ClaudeAdapter 输出检测（claude.py）
min_wait = 25          # 8 → 25
initial_delay = 8      # 3 → 5 → 8
stable_count = 4       # 2 → 3 → 4
# 超时后强制读取文件
```

**效果**：所有 Agent 成功执行，无 "No output" 错误

#### 问题2：测试用例导入失败

**现象**：测试用例执行失败，`ModuleNotFoundError: No module named 'calculator'`

**根因**：
- 测试 Agent 假设模块名（`calc`/`calculator`）
- 实际代码文件是 `code_v1_20260311_XXXXXX.py`

**解决**：
```python
# 测试用例生成后，自动修复导入
def clean_output_directory():
    """清理 output 目录中的历史文件，只保留最近的 3 次运行记录"""
    # 自动清理旧文件，保持目录整洁

# 在 tester_agent 中添加自动修复
if "from " in test_cases_content and "import" in test_cases_content:
    # 替换为动态导入
    dynamic_import = '''
import importlib.util
spec = importlib.util.spec_from_file_location("calculator", 
    Path(__file__).parent / "{code_filename}")
calc = importlib.util.module_from_spec(spec)
sys.modules["calculator"] = calc
spec.loader.exec_module(calc)
'''
```

**效果**：测试用例导入成功，**测试首次通过**

#### 问题3：output 目录历史文件堆积

**现象**：多次运行后 output 目录有大量历史文件

**解决**：
```python
def clean_output_directory():
    """清理 output 目录中的历史文件，只保留最近的 20 个文件"""
    # 按修改时间排序，保留最新的，清理其余的
```

**效果**：工作流启动时自动清理，保持目录整洁

## 三、当前状态

### 运行结果（2026-03-11 13:19）

| Agent | 状态 | 耗时 | 输出 |
|-------|------|------|------|
| 产品 | ✅ | 38.2s | 403字符 |
| 架构师 | ✅ | 38.2s | 1104字符 |
| 开发 | ✅ | 38.2s | 2685字符 |
| 测试 | ✅ | 38.2s+140.2s | 1332+6811字符，**测试通过** |
| 运维 | ✅ | 56.2s+38.2s | 5531+1558字符 |

**总耗时**：约 6 分钟  
**关键成果**：
- 🎉 **测试首次通过**
- 🎉 **零 "No output" 错误**
- 🎉 **output 目录自动清理**

### 交付物清单

| 文件 | 大小 | 说明 |
|------|------|------|
| PRD_20260311_132000.md | 403字符 | 产品需求文档 |
| Spec_20260311_132038.md | 1104字符 | 软件规格说明书 |
| code_v1_20260311_132116.py | 2670字符 | Python 代码实现 |
| test_plan_20260311_132154.md | 1332字符 | 测试计划 |
| test_cases_20260311_132154.py | 6940字符 | pytest 测试用例（自动修复导入） |
| test_report_20260311_132154.md | - | 测试报告（**通过**） |
| deploy_20260311_132511.sh | 5518字符 | 部署脚本 |
| deploy_report_20260311_132511.md | 1558字符 | 发布上线报告 |

## 四、架构演进

### 演进路线

```
langgraph-dev-workflow/          (早期原型)
    └── dev_workflow_v3.py
    
        ↓ 重构为 ACF 框架
        
acf-v2/examples/dev_workflow/    (ACF 框架版)
    ├── dev_workflow_acf.py      (原版，直接使用 tmux)
    
        ↓ 引入 AGENT.md + Skills
        
    ├── real_agents/             (Real Agent 示例)
    
        ↓ 整合两者
        
    └── dev_workflow_v2.py       (当前版本)
        - 5阶段工作流（产品→架构→开发→测试→运维）
        - AGENT.md + Skills 动态提示词
        - 自动导入修复
        - 历史文件自动清理
```

## 五、技术债务与未来工作

### 已解决
- [x] "No output" 错误
- [x] 测试用例导入失败
- [x] output 目录文件堆积
- [x] 提示词过长问题

### 待优化
- [ ] 架构师 Agent 提示词进一步简化（仍偶现慢）
- [ ] 测试用例导入修复的健壮性（正则表达式匹配）
- [ ] 工作流整体超时时间动态调整
- [ ] CLI 工具实现
- [ ] YAML 配置支持
- [ ] Web UI（长期）

## 六、关键设计决策

### 1. 提示词简化原则
**决策**：放弃复杂的 AGENT.md + Skills 系统，改用简单直接的任务提示词

**理由**：
- AGENT.md 系统导致提示词过长，Claude 被干扰
- 简单提示词 (`你是XXX。请直接输出...`) 效果更好
- 更容易调试和维护

### 2. 输出检测策略
**决策**：加长检测时长，增加稳定检测次数

**理由**：
- Claude Code 在隔离环境中启动较慢
- 过短的等待时间导致误判 "No output"
- 宁可慢一点，也要确保正确捕获输出

### 3. 导入修复策略
**决策**：后处理修复，而非依赖 Agent 正确生成

**理由**：
- Agent 无法准确知道文件路径
- 后处理更可靠，不受 Agent 输出波动影响
- 对现有代码零侵入

---

**文档更新时间**：2026-03-11  
**版本**：dev_workflow_v2 稳定版
