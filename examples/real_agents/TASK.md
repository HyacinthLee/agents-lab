# ACF v2.0 Real Agent Example 实现任务

## 目标
根据 DESIGN.md 中的设计，实现完整的 Real Agent Example，包含：

1. **AGENT.md 模板系统** - 框架生成模板，用户手动编辑
2. **Skill 系统** - Agent 自选 + 强制使用模式
3. **共享白板** - 基于 BaseStore 的 Agent 间通信
4. **Workspace 结构** - 共享根目录 + 各 Agent 子目录

## 文件结构
```
acf-v2/examples/real_agents/
├── __init__.py
├── agent_template.py       # AGENT.md 模板生成器
├── shared_board.py         # 共享白板实现
├── skill_manager.py        # Skill 加载和管理
├── workspace_manager.py    # Workspace 管理
├── real_agent_workflow.py  # 更新后的主工作流
├── agents/
│   ├── product_manager/
│   │   ├── AGENT.md        # 由模板生成，用户可编辑
│   │   ├── skills/
│   │   │   └── write-prd.md
│   │   └── workspace/      # 私有工作空间
│   ├── developer/
│   │   ├── AGENT.md
│   │   ├── skills/
│   │   │   └── write-code.md
│   │   └── workspace/
│   └── code_reviewer/
│       ├── AGENT.md
│       ├── skills/
│       │   └── review-code.md
│       └── workspace/
└── shared/                 # 共享空间
    ├── deliverables/
    ├── decisions/
    └── lessons/
```

## 详细需求

### 1. agent_template.py
- `AgentTemplate` 类
- `generate(role, workspace)` 方法 - 生成 AGENT.md 模板
- 模板包含：Identity、Demo Declaration、Responsibilities、Constraints、Skills

### 2. skill_manager.py
- `Skill` 类 - 解析 SKILL.md
- `SkillManager` 类
  - `load_skills(agent_name)` - 加载指定 agent 的 skills
  - `format_for_prompt(skills)` - 格式化为 prompt
  - `get_skill(name)` - 获取特定 skill

### 3. shared_board.py
- `SharedBoard` 类 - 封装 BaseStore
  - `put(namespace, key, value, index)` - 写入共享板
  - `get(namespace, key)` - 读取
  - `search(namespace, query)` - 语义搜索
  - `get_shared_context()` - 获取共享上下文

### 4. workspace_manager.py
- `WorkspaceManager` 类
  - `create_agent_workspace(agent_name)` - 创建 agent 工作空间
  - `get_agent_workspace(agent_name)` - 获取路径
  - `get_shared_workspace()` - 获取共享空间路径
  - `ensure_structure()` - 确保完整目录结构

### 5. real_agent_workflow.py
更新主脚本：
- 使用 WorkspaceManager 创建/管理目录
- 使用 AgentTemplate 生成 AGENT.md（如果不存在）
- 使用 SkillManager 加载 skills
- 使用 SharedBoard 进行 Agent 间通信
- 工作流：PM → Developer → Reviewer，使用 SharedBoard 传递交付物

## 技术约束
- 使用 LangGraph BaseStore 作为 SharedBoard 底层
- 与现有 acf-v2 框架兼容
- 支持 Python 3.10+
- 包含基础类型注解

## 测试要求
- 每个模块至少 3 个单元测试
- 集成测试验证完整工作流

请实现以上功能。