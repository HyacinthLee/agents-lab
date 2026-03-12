"""
软件研发流程多 Agent 系统 - ACF-v2 合并版
基于 LangGraph + ACF-v2 框架 + AGENT.md/Skills 动态提示词
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import TypedDict, Annotated, Literal, Any, Dict, Optional
import operator

# 添加 ACF 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from acf import AdapterFactory, AdapterConfig
from acf.adapter.base import AgentResult, AgentStatus
from acf.adapter.factory import create_claude_adapter
from acf.workflow.builder import WorkflowBuilder
from acf.workflow.runner import WorkflowRunner
from acf.workflow.state import AgentState, WorkflowStatus, create_initial_state
from acf.agent import AgentTemplate, WorkspaceManager, load_agent_config
from acf.skills import SkillManager, format_skills_for_agent
from acf.store import SharedBoard, SimpleSharedBoard
from langgraph.graph import StateGraph, START, END


# ==================== 配置 ====================

WORK_DIR = str(Path(__file__).parent / "output")
BASE_DIR = Path(__file__).parent  # dev_workflow 目录
AGENTS_DIR = BASE_DIR  # WorkspaceManager 内部会添加 agents/ 子目录
os.makedirs(WORK_DIR, exist_ok=True)

# 日志配置 - 使用 Tee 类同时输出到控制台和文件
class Tee:
    """将输出同时写入文件和控制台"""
    def __init__(self, filepath):
        self.filepath = filepath
        self.file = open(filepath, 'w', encoding='utf-8')
        self.stdout = sys.stdout
        
    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)
        self.file.flush()
        
    def flush(self):
        self.stdout.flush()
        self.file.flush()
        
    def close(self):
        self.file.write(f"\n=== 流程结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        self.file.close()

LOG_FILE = None
tee = None

def log_init():
    """初始化日志，返回日志文件路径"""
    global LOG_FILE, tee
    LOG_FILE = os.path.join(WORK_DIR, f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    tee = Tee(LOG_FILE)
    sys.stdout = tee
    print(f"=== 软件研发流程多 Agent 系统 (ACF-v2 合并版) ===")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"日志文件: {LOG_FILE}")
    print("="*50 + "\n")
    return LOG_FILE

def log_close():
    """关闭日志"""
    global tee
    if tee:
        tee.close()
        sys.stdout = tee.stdout


def clean_output_directory():
    """清理 output 目录中的历史文件，只保留最近的 3 次运行记录"""
    import glob
    import shutil
    
    try:
        # 获取所有文件，按修改时间排序
        files = []
        for pattern in ['*.md', '*.py', '*.sh', '*.log']:
            files.extend(glob.glob(os.path.join(WORK_DIR, pattern)))
        
        # 按修改时间排序（最新的在前）
        files.sort(key=os.path.getmtime, reverse=True)
        
        # 保留最近的 20 个文件（大约 3 次完整运行的交付物）
        files_to_keep = set(files[:20])
        files_to_remove = [f for f in files if f not in files_to_keep]
        
        removed_count = 0
        for f in files_to_remove:
            try:
                os.remove(f)
                removed_count += 1
            except Exception:
                pass
        
        if removed_count > 0:
            print(f"   🧹 已清理 {removed_count} 个历史文件")
    except Exception as e:
        print(f"   ⚠️  清理历史文件时出错: {e}")


def save_deliverable(filename: str, content: str) -> str:
    """保存交付物到文件"""
    filepath = os.path.join(WORK_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath


# ==================== Agent 超时配置 ====================

AGENT_TIMEOUTS = {
    "product_agent": 90,      # 产品 Agent：PRD 相对简单
    "architect_agent": 180,   # 架构师：设计较复杂
    "developer_agent": 300,   # 开发：写代码最耗时
    "tester_agent": 300,      # 测试：生成用例 + 执行
    "ops_agent": 180,         # 运维：部署脚本
}


# ==================== 提示词构建 ====================

def build_system_prompt(
    agent_name: str,
    skill_manager: SkillManager,
    workspace_manager: WorkspaceManager,
    shared_board: SharedBoard,
    enforced_skill: str | None = None,
) -> str:
    """从 AGENT.md 和 skills 构建系统提示词
    
    Args:
        agent_name: Agent 名称 (如 product_manager)
        skill_manager: SkillManager 实例
        workspace_manager: WorkspaceManager 实例
        shared_board: SharedBoard 实例
        enforced_skill: 强制使用的技能名称
        
    Returns:
        完整的系统提示词
    """
    # 加载 AGENT.md 配置
    agent_dir = workspace_manager.get_agent_dir(agent_name)
    agent_config = load_agent_config(agent_dir)
    
    # 加载技能
    skills = skill_manager.load_skills(agent_name)
    
    # 获取共享上下文
    shared_context = shared_board.get_shared_context()
    
    # 构建提示词
    prompt_parts = [
        "You are an AI agent with the following configuration:",
        "",
        "=" * 60,
    ]
    
    # 身份
    if agent_config.get("identity"):
        prompt_parts.extend([
            "## Identity",
            agent_config["identity"],
            "",
        ])
    
    # 职责
    if agent_config.get("responsibilities"):
        prompt_parts.append("## Responsibilities")
        for resp in agent_config["responsibilities"]:
            prompt_parts.append(f"- {resp}")
        prompt_parts.append("")
    
    # 约束
    if agent_config.get("constraints"):
        prompt_parts.append("## Constraints")
        for constraint in agent_config["constraints"]:
            prompt_parts.append(f"- {constraint}")
        prompt_parts.append("")
    
    prompt_parts.append("=" * 60)
    prompt_parts.append("")
    
    # 技能
    skills_section = format_skills_for_agent(skills, enforced_skill)
    if skills_section:
        prompt_parts.append(skills_section)
        prompt_parts.append("")
    
    # 工作空间
    workspace = workspace_manager.get_agent_workspace(agent_name)
    prompt_parts.extend([
        "## Workspace",
        f"Your workspace is: {workspace}",
        "All files you create should be saved there.",
        "",
    ])
    
    # 共享交付物
    if shared_context.get("deliverables"):
        prompt_parts.extend([
            "## Shared Deliverables",
            "The following deliverables have been shared by other agents:",
            "",
        ])
        for item in shared_context["deliverables"]:
            prompt_parts.append(f"- {item['key']} (by {item.get('author', 'unknown')})")
        prompt_parts.append("")
    
    # 指令
    prompt_parts.extend([
        "## Instructions",
        "1. Read the task carefully",
        "2. Check shared deliverables for relevant context",
        "3. Use your skills appropriately",
        "4. **IMPORTANT**: Directly output your response content below. Do NOT ask for permission to write files.",
        "5. Be concise and focused",
        "",
    ])
    
    return "\n".join(prompt_parts)


# ==================== Agent 封装（使用 ACF ClaudeAdapter）====================

# Agent 名称映射：agent_type -> directory name
AGENT_DIR_MAP = {
    "product_agent": "product_manager",
    "architect_agent": "architect",
    "developer_agent": "developer",
    "tester_agent": "tester",
    "ops_agent": "ops_engineer",
}

class ClaudeAgent:
    """基于 ACF ClaudeAdapter 的 Agent 封装"""
    
    def __init__(self, name: str, role: str, agent_type: str = "developer", system_prompt: str = ""):
        self.name = name
        self.role = role
        self.agent_type = agent_type
        self.system_prompt = system_prompt
        self.timeout = AGENT_TIMEOUTS.get(agent_type, 300)
        self.adapter = None
        
    async def execute(self, prompt: str) -> str:
        """执行 prompt 并返回结果"""
        if self.adapter is None:
            # 延迟创建 adapter
            agent_dir_name = AGENT_DIR_MAP.get(self.name, self.name.replace("_agent", ""))
            workspace = AGENTS_DIR / "agents" / agent_dir_name / "workspace"
            self.adapter = create_claude_adapter(
                name=self.name,
                workspace_dir=str(workspace),
                timeout=self.timeout,
                confirm_delay=1.0,
            )
        
        print(f"     ⏳ 调用 Claude ({self.role})...", end="", flush=True)
        start = asyncio.get_event_loop().time()
        
        # 组合系统提示词和任务提示词
        full_prompt = f"{self.system_prompt}\n\n## Task\n{prompt}"
        
        result = await self.adapter.execute(full_prompt)
        
        elapsed = asyncio.get_event_loop().time() - start
        
        if result.status == AgentStatus.COMPLETED and result.output:
            print(f" ✅ ({elapsed:.1f}s, {len(result.output)} 字符)")
            return result.output
        else:
            error_msg = result.error or "No output"
            print(f" ⚠️ 错误: {error_msg[:50]}")
            return f"[Error: {error_msg}]"


# ==================== 状态定义 ====================

class DevState(TypedDict):
    """研发流程状态"""
    # 需求输入
    requirement: str
    
    # 产品阶段交付物
    prd_file: str          # PRD 文档链接
    
    # 开发阶段交付物
    spec_file: str         # 软件规格说明书链接
    code_file: str         # 代码文件链接
    
    # 测试阶段交付物
    test_plan_file: str    # 测试计划文件链接
    test_cases_file: str   # 测试用例文件链接
    test_report_file: str  # 测试报告链接
    test_passed: bool      # 测试是否通过
    
    # 运维阶段交付物
    deploy_script_file: str    # 运维脚本链接
    deploy_report_file: str    # 发布上线报告链接
    deploy_passed: bool        # 部署是否成功
    
    # 流程控制
    iteration: int
    max_iterations: int
    rejections: Annotated[list, operator.add]


# ==================== SharedBoard 实例 ====================

shared_board = SimpleSharedBoard(team_id="dev_workflow")
workspace_manager = WorkspaceManager(BASE_DIR)
skill_manager = SkillManager(workspace_manager.agents_dir)


# ==================== Agent 节点 ====================

async def product_agent(state: DevState) -> dict:
    """产品 Agent：交付 PRD 文档"""
    print("\n" + "="*70)
    print("📋 【产品 Agent - Claude】正在编写 PRD 文档...")
    print("="*70)
    
    # 简化：不使用复杂的 system_prompt，直接传递任务提示词
    agent = ClaudeAgent("product_agent", "产品经理", agent_type="product_agent")
    
    prompt = f"""你是产品经理，正在编写产品需求文档（PRD）。请直接输出 PRD 的完整内容，不要有任何对话或解释。

需求：{state['requirement']}

PRD 必须包含以下章节：
1. 产品概述（1-2句话描述产品）
2. 功能列表（3-5个核心功能）
3. 验收标准（2-3条可测试的标准）

要求：
- 使用 Markdown 格式
- 简洁明了，控制在 500 字以内
- 直接输出 PRD 内容，不要询问澄清

请直接输出 PRD："""
    
    prd_content = await agent.execute(prompt)
    
    # 保存交付物
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"PRD_{timestamp}.md"
    filepath = save_deliverable(filename, prd_content)
    
    # 写入 SharedBoard
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"prd_{timestamp}",
        value={"filename": filename, "content": prd_content[:500], "filepath": filepath},
        author="product_agent"
    )
    
    print(f"\n   📄 交付物：{filename} ({len(prd_content)} 字符)")
    print(f"   📍 文件路径：{filepath}")
    
    return {"prd_file": filename}


async def architect_agent(state: DevState) -> dict:
    """架构师 Agent：交付软件规格说明书"""
    print("\n" + "="*70)
    print("🏗️  【架构师 Agent - Claude】正在编写规格说明书...")
    print("="*70)
    
    # 读取 PRD 内容
    prd_path = os.path.join(WORK_DIR, state['prd_file'])
    with open(prd_path, 'r', encoding='utf-8') as f:
        prd_content = f.read()
    
    # 简化：不使用复杂的 system_prompt
    agent = ClaudeAgent("architect_agent", "系统架构师", agent_type="architect_agent")
    
    prompt = f"""你是系统架构师，正在编写软件规格说明书。请直接输出规格说明书的完整内容。

PRD 内容：
{prd_content[:3000]}

规格说明书必须包含：
1. 系统架构设计（1-2句话描述整体架构）
2. 模块划分（列出主要模块及其职责）
3. 接口定义（关键函数/类的输入输出）
4. 数据结构（核心数据类型定义）

要求：
- 使用 Markdown 格式
- 简洁实用，控制在 800 字以内
- 直接输出规格说明书内容

请直接输出规格说明书："""
    
    spec_content = await agent.execute(prompt)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Spec_{timestamp}.md"
    filepath = save_deliverable(filename, spec_content)
    
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"spec_{timestamp}",
        value={"filename": filename, "content": spec_content[:500], "filepath": filepath},
        author="architect_agent"
    )
    
    print(f"\n   📄 规格说明书：{filename} ({len(spec_content)} 字符)")
    print(f"   📍 文件路径：{filepath}")
    
    return {"spec_file": filename}


async def developer_agent(state: DevState) -> dict:
    """开发 Agent：交付代码实现"""
    print("\n" + "="*70)
    print(f"💻 【开发 Agent - Claude】第 {state['iteration'] + 1} 次开发...")
    print("="*70)
    
    # 读取规格说明书
    spec_path = os.path.join(WORK_DIR, state['spec_file'])
    with open(spec_path, 'r', encoding='utf-8') as f:
        spec_content = f.read()
    
    # 如果有测试报告（打回情况），也读取
    test_report_content = ""
    if state.get('test_report_file') and os.path.exists(os.path.join(WORK_DIR, state['test_report_file'])):
        with open(os.path.join(WORK_DIR, state['test_report_file']), 'r', encoding='utf-8') as f:
            test_report_content = f.read()
        print(f"\n   📖 读取测试报告：发现 {test_report_content.count('FAIL')} 个失败测试")
    
    # 简化：不使用复杂的 system_prompt
    agent = ClaudeAgent("developer_agent", "Python 工程师", agent_type="developer_agent")
    
    if test_report_content:
        prompt = f"""你是Python工程师。请直接输出修复后的完整Python代码，不要有任何对话或解释。

规格说明书：
{spec_content[:3000]}

测试报告（需要修复的问题）：
{test_report_content[:2000]}

要求：
1. 修复测试报告中的问题
2. 代码必须可运行
3. 包含命令行交互界面
4. 完善的错误处理
5. 所有代码放在一个文件中
6. 只输出纯Python代码，不要有其他文字

请直接输出修复后的代码："""
    else:
        prompt = f"""你是Python工程师。请直接输出完整可运行的Python代码，不要有任何对话或解释。

规格说明书：
{spec_content[:3000]}

要求：
1. 严格按照规格说明书实现
2. 代码必须可运行
3. 包含命令行交互界面（main函数）
4. 完善的错误处理（try-except）
5. 所有代码放在一个文件中
6. 只输出纯Python代码，不要有其他文字

请直接输出代码："""
    
    code_content = await agent.execute(prompt)
    
    # 提取代码块
    if "```python" in code_content:
        code_blocks = code_content.split("```python")
        if len(code_blocks) > 1:
            code_content = code_blocks[1].split("```")[0].strip()
    
    iteration = state['iteration']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"code_v{iteration + 1}_{timestamp}.py"
    filepath = save_deliverable(filename, code_content)
    
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"code_{timestamp}",
        value={"filename": filename, "content": code_content[:500], "filepath": filepath},
        author="developer_agent"
    )
    
    print(f"\n   📄 代码文件：{filename} ({len(code_content)} 字符)")
    print(f"   📍 文件路径：{filepath}")
    
    return {"code_file": filename}


async def tester_agent(state: DevState) -> dict:
    """测试 Agent：交付测试计划、用例和报告"""
    print("\n" + "="*70)
    print("🧪 【测试 Agent - Claude】正在开发测试用例并执行...")
    print("="*70)
    
    # 读取 PRD 和代码
    prd_path = os.path.join(WORK_DIR, state['prd_file'])
    code_path = os.path.join(WORK_DIR, state['code_file'])
    
    with open(prd_path, 'r', encoding='utf-8') as f:
        prd_content = f.read()
    with open(code_path, 'r', encoding='utf-8') as f:
        code_content = f.read()
    
    print(f"   📖 输入：")
    print(f"      - PRD：{state['prd_file']} ({len(prd_content)} 字符)")
    print(f"      - 代码：{state['code_file']} ({len(code_content)} 字符)")
    
    # 简化：不使用复杂的 system_prompt
    agent = ClaudeAgent("tester_agent", "测试工程师", agent_type="tester_agent")
    
    # 步骤 1: 生成测试计划
    print("\n   📝 步骤 1/3：基于 PRD 生成测试计划...")
    prompt = f"""你是测试工程师。请直接输出测试计划的完整内容，不要有任何对话或解释。

PRD内容：
{prd_content[:2000]}

测试计划必须包含：
1. 测试范围（要测哪些功能）
2. 测试策略（正常场景、异常场景、边界条件）
3. 测试用例列表（编号、标题、前置条件、操作步骤、期望结果）

要求：
- 使用 Markdown 格式
- 测试用例控制在 10-15 个
- 直接输出测试计划内容

请直接输出测试计划："""
    
    test_plan_content = await agent.execute(prompt)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    test_plan_file = f"test_plan_{timestamp}.md"
    save_deliverable(test_plan_file, test_plan_content)
    
    print(f"   📄 测试计划：{test_plan_file} ({len(test_plan_content)} 字符)")
    
    # 步骤 2: 生成测试用例
    print("\n   📝 步骤 2/3：基于代码生成测试用例...")
    code_filename = state['code_file']
    prompt = f"""你是测试工程师。请直接输出 pytest 测试用例代码，不要有任何对话或解释。

待测试代码文件：{code_filename}

待测试代码内容：
```python
{code_content}
```

测试计划：
{test_plan_content[:1500]}

重要要求：
1. 使用 pytest 框架
2. 测试用例覆盖主要功能
3. 代码可执行
4. **关键**：使用以下动态导入方式加载被测代码：

```python
import importlib.util
import sys
from pathlib import Path

# 动态加载代码文件
spec = importlib.util.spec_from_file_location("calculator", Path(__file__).parent / "{code_filename}")
calc = importlib.util.module_from_spec(spec)
sys.modules["calculator"] = calc
spec.loader.exec_module(calc)

# 从模块导入需要的函数（根据实际代码中的函数名调整）
# 例如：parse_input = calc.parse_input
```

5. 只输出纯 Python 代码，不要有其他文字

请直接输出测试用例代码："""
    
    test_cases_content = await agent.execute(prompt)
    
    # 提取代码
    if "```python" in test_cases_content:
        blocks = test_cases_content.split("```python")
        if len(blocks) > 1:
            test_cases_content = blocks[1].split("```")[0].strip()
    
    test_cases_file = f"test_cases_{timestamp}.py"
    
    # 自动修复导入：将 'from xxx import' 替换为动态导入
    if "from " in test_cases_content and "import" in test_cases_content:
        print("   🔧 自动修复导入语句...")
        # 生成动态导入代码
        dynamic_import = f'''"""测试用例 - 自动修复导入"""
import importlib.util
import sys
from pathlib import Path

# 动态加载被测代码
spec = importlib.util.spec_from_file_location("calculator", Path(__file__).parent / "{code_filename}")
calc = importlib.util.module_from_spec(spec)
sys.modules["calculator"] = calc
spec.loader.exec_module(calc)

'''
        # 移除原有的 from xxx import 行
        lines = test_cases_content.split('\n')
        filtered_lines = []
        for line in lines:
            if not (line.strip().startswith('from ') and ' import ' in line):
                filtered_lines.append(line)
        test_cases_content = dynamic_import + '\n'.join(filtered_lines)
    
    save_deliverable(test_cases_file, test_cases_content)
    
    print(f"   📄 测试用例：{test_cases_file} ({len(test_cases_content)} 字符)")
    
    # 步骤 3: 执行测试并生成报告
    print("\n   🧪 步骤 3/3：执行测试并生成报告...")
    test_report_file = f"test_report_{timestamp}.md"
    
    # 尝试执行测试
    import subprocess
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", os.path.join(WORK_DIR, test_cases_file), "-v"],
            capture_output=True,
            text=True,
            timeout=30
        )
        test_output = result.stdout + "\n" + result.stderr
        passed = result.returncode == 0
    except Exception as e:
        test_output = f"Test execution error: {e}"
        passed = False
    
    # 生成测试报告
    report_content = f"""# 测试报告

## 测试执行结果

**状态**: {'✅ 通过' if passed else '❌ 失败'}

## 测试输出

```
{test_output[:2000]}
```

## 统计

- 测试用例文件: {test_cases_file}
- 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    save_deliverable(test_report_file, report_content)
    
    print(f"   📄 测试报告：{test_report_file}")
    print(f"   {'✅' if passed else '❌'} 测试{'通过' if passed else '失败'}")
    
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"test_report_{timestamp}",
        value={"filename": test_report_file, "content": report_content[:500], "filepath": os.path.join(WORK_DIR, test_report_file)},
        author="tester_agent"
    )
    
    return {
        "test_plan_file": test_plan_file,
        "test_cases_file": test_cases_file,
        "test_report_file": test_report_file,
        "test_passed": passed
    }


async def ops_agent(state: DevState) -> dict:
    """运维 Agent：交付部署脚本和上线报告"""
    print("\n" + "="*70)
    print("🚀 【运维 Agent - Claude】正在开发运维脚本并部署...")
    print("="*70)
    
    # 读取测试报告和代码
    test_report_path = os.path.join(WORK_DIR, state['test_report_file'])
    spec_path = os.path.join(WORK_DIR, state['spec_file'])
    code_path = os.path.join(WORK_DIR, state['code_file'])
    
    with open(test_report_path, 'r', encoding='utf-8') as f:
        test_report_content = f.read()
    with open(spec_path, 'r', encoding='utf-8') as f:
        spec_content = f.read()
    with open(code_path, 'r', encoding='utf-8') as f:
        code_content = f.read()
    
    print(f"   📖 输入：")
    print(f"      - 测试报告：{state['test_report_file']}")
    print(f"      - 规格说明书：{state['spec_file']}")
    print(f"      - 代码：{state['code_file']}")
    
    # 简化：不使用复杂的 system_prompt
    agent = ClaudeAgent("ops_agent", "运维工程师", agent_type="ops_agent")
    
    # 步骤 1: 开发运维脚本
    print("\n   📝 步骤 1/2：开发运维脚本...")
    prompt = f"""你是运维工程师。请直接输出部署脚本的完整内容，不要有任何对话或解释。

代码文件内容：
```python
{code_content[:1500]}
```

测试报告摘要：
{test_report_content[:1000]}

要求：
1. 输出 bash/shell 脚本
2. 包含：部署步骤、健康检查、回滚命令
3. 脚本可执行
4. 只输出纯脚本代码，不要有其他文字

请直接输出部署脚本："""
    
    deploy_script_content = await agent.execute(prompt)
    
    # 提取 shell 代码
    if "```bash" in deploy_script_content:
        blocks = deploy_script_content.split("```bash")
        if len(blocks) > 1:
            deploy_script_content = blocks[1].split("```")[0].strip()
    elif "```sh" in deploy_script_content:
        blocks = deploy_script_content.split("```sh")
        if len(blocks) > 1:
            deploy_script_content = blocks[1].split("```")[0].strip()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    deploy_script_file = f"deploy_{timestamp}.sh"
    save_deliverable(deploy_script_file, deploy_script_content)
    
    print(f"   📄 部署脚本：{deploy_script_file} ({len(deploy_script_content)} 字符)")
    
    # 步骤 2: 生成发布上线报告
    print("\n   📋 步骤 2/2：生成发布上线报告...")
    prompt = f"""你是运维工程师。请直接输出发布上线报告的完整内容，不要有任何对话或解释。

规格说明书摘要：
{spec_content[:1500]}

测试报告摘要：
{test_report_content[:1000]}

部署脚本摘要：
{deploy_script_content[:1000]}

报告必须包含：
1. 发布内容概述
2. 测试结果汇总
3. 部署方案说明
4. 上线建议（是否建议上线，风险评估）

要求：
- 使用 Markdown 格式
- 简洁明了
- 直接输出报告内容

请直接输出发布上线报告："""
    
    deploy_report_content = await agent.execute(prompt)
    deploy_report_file = f"deploy_report_{timestamp}.md"
    save_deliverable(deploy_report_file, deploy_report_content)
    
    print(f"   📄 上线报告：{deploy_report_file} ({len(deploy_report_content)} 字符)")
    
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"deploy_{timestamp}",
        value={"filename": deploy_script_file, "content": deploy_script_content[:500], "filepath": os.path.join(WORK_DIR, deploy_script_file)},
        author="ops_agent"
    )
    
    return {
        "deploy_script_file": deploy_script_file,
        "deploy_report_file": deploy_report_file,
        "deploy_passed": True
    }


# ==================== 路由函数 ====================

def route_test(state: DevState) -> Literal["ops", "dev"]:
    """测试后路由：通过进入运维，失败返回开发"""
    if state.get('test_passed'):
        print("\n⏭️  路由：测试通过 → 部署阶段")
        return "ops"
    else:
        print("\n⏭️  路由：测试失败 → 返回开发阶段")
        return "dev"


def route_dev(state: DevState) -> Literal["test", END]:
    """开发后路由：迭代次数检查"""
    if state['iteration'] < state['max_iterations']:
        return "test"
    else:
        print("\n⚠️  达到最大迭代次数，流程结束")
        return END


# ==================== 工作流构建 ====================

def build_workflow():
    """构建工作流"""
    workflow = StateGraph(DevState)
    
    # 添加节点
    workflow.add_node("product", product_agent)
    workflow.add_node("architect", architect_agent)
    workflow.add_node("dev", developer_agent)
    workflow.add_node("test", tester_agent)
    workflow.add_node("ops", ops_agent)
    
    # 定义边
    workflow.add_edge("product", "architect")
    workflow.add_edge("architect", "dev")
    workflow.add_edge("dev", "test")
    workflow.add_edge("test", "ops")
    workflow.add_edge("ops", END)
    
    # 设置入口
    workflow.set_entry_point("product")
    
    return workflow.compile()


# ==================== 主函数 ====================

async def main_async():
    """异步主函数"""
    # 初始化日志
    log_path = log_init()
    
    # 清理历史文件
    print("\n🧹 清理历史交付物...")
    clean_output_directory()
    print()
    
    print("\n" + "🚀" * 35)
    print("   软件研发流程多 Agent 系统")
    print("   基于 LangGraph + ACF-v2 框架 + AGENT.md/Skills")
    print("   采用交付物链传递的规范流程")
    print("🚀" * 35)
    
    # 需求输入
    if len(sys.argv) > 1:
        requirement = sys.argv[1]
    else:
        requirement = """开发一个命令行计算器，支持加减乘除四则运算，有错误处理（如除零检查）。"""
    
    initial_state: DevState = {
        "requirement": requirement.strip(),
        "prd_file": "",
        "spec_file": "",
        "code_file": "",
        "test_plan_file": "",
        "test_cases_file": "",
        "test_report_file": "",
        "test_passed": False,
        "deploy_script_file": "",
        "deploy_report_file": "",
        "deploy_passed": False,
        "iteration": 0,
        "max_iterations": 2,
        "rejections": []
    }
    
    print(f"\n【需求】{requirement}")
    
    print("\n" + "="*70)
    print("开始执行工作流...")
    print("="*70)
    
    try:
        app = build_workflow()
        
        async for event in app.astream(initial_state, stream_mode="values"):
            pass
    finally:
        log_close()
        print(f"\n日志已保存到: {log_path}")
    
    print("\n\n执行完成！")


def main():
    """主函数入口"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
