"""
软件研发流程多 Agent 系统 - ACF-v2 重构版
基于 LangGraph + ACF-v2 框架，采用交付物链接传递的规范流程
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import TypedDict, Annotated, Literal, Any, Dict, Optional
import operator

# 添加 ACF 到路径
sys.path.insert(0, "/root/.openclaw/workspace/acf-v2/src")

from acf import AdapterFactory, AdapterConfig
from acf.adapter.base import AgentResult, AgentStatus
from acf.workflow.builder import WorkflowBuilder
from acf.workflow.runner import WorkflowRunner
from acf.workflow.state import AgentState, WorkflowStatus, create_initial_state
from langgraph.graph import StateGraph, START, END

# SharedBoard
sys.path.insert(0, "/root/.openclaw/workspace/acf-v2/examples/real_agents")
from shared_board import SimpleSharedBoard, BoardEntry


# ==================== 配置 ====================

WORK_DIR = "/root/.openclaw/workspace/acf-v2/examples/dev_workflow/output"
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
    print(f"=== 软件研发流程多 Agent 系统 (ACF-v2) ===")
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

# ==================== Agent 封装（使用直接 tmux 调用）====================

import subprocess
import time
import shlex

def run_claude_in_tmux(session_name: str, prompt: str, workdir: str, timeout: int = 300) -> str:
    """
    在 tmux 会话中运行 Claude Code（使用 claude --print 非交互模式）
    适配 root 环境：使用 tmux + 自动发送确认字符
    """
    TMUX_SOCKET = "/tmp/acf_dev_workflow_socket"
    
    # 清理旧会话
    try:
        subprocess.run(["tmux", "-S", TMUX_SOCKET, "kill-session", "-t", session_name],
                      capture_output=True, timeout=3)
    except:
        pass
    time.sleep(0.2)
    
    # 创建输出文件
    output_file = f"/tmp/claude_output_{session_name}.txt"
    
    # 核心：使用 claude --print 非交互模式，直接输出到文件
    prompt_quoted = shlex.quote(prompt)
    cmd_str = f"cd {shlex.quote(workdir)} && claude --print {prompt_quoted} 2>&1 | tee {shlex.quote(output_file)}"
    
    # 创建 tmux 会话直接运行命令
    cmd = [
        "tmux", "-S", TMUX_SOCKET,
        "new-session", "-d", "-s", session_name,
        "-c", workdir,
        cmd_str
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception as e:
        return f"[tmux 错误] {str(e)[:100]}"
    
    # 等待启动并出现权限提示
    time.sleep(5)
    
    # 自动发送 "2" 允许本次会话的所有编辑（Claude Code root 权限确认）
    try:
        subprocess.run(["tmux", "-S", TMUX_SOCKET, "send-keys", "-t", f"{session_name}:0.0", "-l", "--", "2"],
                      capture_output=True, timeout=5)
        time.sleep(0.3)  # 关键延迟！
        subprocess.run(["tmux", "-S", TMUX_SOCKET, "send-keys", "-t", f"{session_name}:0.0", "Enter"],
                      capture_output=True, timeout=5)
    except Exception as e:
        print(f"    [发送确认键失败] {e}")
    
    # 等待执行完成
    start_time = time.time()
    last_size = -1
    stable_seconds = 0
    
    while time.time() - start_time < timeout:
        time.sleep(5)
        
        # 检查输出文件
        try:
            if os.path.exists(output_file):
                current_size = os.path.getsize(output_file)
                if current_size == last_size and current_size > 200:
                    stable_seconds += 5
                    # 连续20秒大小不变且大于200字节，认为已完成
                    if stable_seconds >= 20:
                        break
                else:
                    stable_seconds = 0
                    last_size = current_size
        except:
            pass
    
    # 读取输出文件
    result = "[无输出]"
    try:
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                result = f.read()
            
            # 清理临时文件
            try:
                os.unlink(output_file)
            except:
                pass
    except Exception as e:
        result = f"[读取错误] {str(e)[:100]}"
    
    # 清理会话
    try:
        subprocess.run(["tmux", "-S", TMUX_SOCKET, "kill-session", "-t", session_name],
                      capture_output=True, timeout=3)
    except:
        pass
    
    return result


class ClaudeAgent:
    """基于直接 tmux 调用的 Agent 封装"""
    
    def __init__(self, name: str, role: str, agent_type: str = "developer"):
        self.name = name
        self.role = role
        self.agent_type = agent_type
        # 从配置获取超时时间，默认 300 秒
        self.timeout = AGENT_TIMEOUTS.get(agent_type, 300)
        self.session_name = f"acf_{name}_{uuid.uuid4().hex[:8]}"
    
    async def execute(self, prompt: str) -> str:
        """执行 prompt 并返回结果（使用 asyncio.to_thread）"""
        print(f"     ⏳ 调用 Claude ({self.role})...", end="", flush=True)
        start = time.time()
        
        # 使用 asyncio.to_thread 在线程中执行同步代码
        result = await asyncio.to_thread(
            run_claude_in_tmux, 
            self.session_name, 
            prompt, 
            WORK_DIR, 
            self.timeout
        )
        
        elapsed = time.time() - start
        
        if result and len(result) > 50:
            print(f" ✅ ({elapsed:.1f}s, {len(result)} 字符)")
            return result
        else:
            print(f" ⚠️ 输出较短 ({len(result) if result else 0} 字符)")
            return result or "[无输出]"


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


# ==================== Agent 节点 ====================

async def product_agent(state: DevState) -> dict:
    """
    产品 Agent：交付 PRD 文档
    输入：用户需求
    输出：PRD 文档链接
    """
    print("\n" + "="*70)
    print("📋 【产品 Agent - Claude】正在编写 PRD 文档...")
    print("="*70)
    
    agent = ClaudeAgent("product_agent", "产品经理", agent_type="product_agent")
    
    prompt = f"""你是产品经理，正在编写产品需求文档（PRD）。请直接输出 PRD 的完整内容，不要有任何对话或解释。

需求：{state['requirement']}

PRD 必须包含以下章节：

# 产品需求文档（PRD）

## 1. 产品概述
- 背景：为什么需要这个产品
- 目标：产品要实现什么
- 目标用户：谁会用这个产品

## 2. 功能列表
| 功能编号 | 功能名称 | 功能描述 | 优先级 |
|---------|---------|---------|--------|
| F001 | ... | ... | P0 |

## 3. 验收标准
| 场景 | 操作 | 期望结果 |
|------|------|---------|
| ... | ... | ... |

## 4. 使用方式
描述用户如何使用这个产品

## 5. 非功能需求
- 性能要求
- 兼容性要求
- 安全要求

重要：直接输出 PRD 文档内容，不要有任何对话、问候或解释性文字。不要提到"我会为你编写"或"文档已保存"之类的话。只需要纯 PRD 内容。"""
    
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


async def dev_agent(state: DevState) -> dict:
    """
    开发 Agent：交付软件规格说明书 + 代码
    输入：PRD 文档链接
    输出：软件规格说明书链接 + 代码文件链接
    """
    print("\n" + "="*70)
    print(f"💻 【开发 Agent - Claude】第 {state['iteration'] + 1} 次开发...")
    print("="*70)
    
    # 获取测试报告信息（如果有打回记录）
    test_report_content = ""
    test_report_file = ""
    if state["rejections"]:
        last_rejection = state["rejections"][-1]
        print(f"   🔄 上次打回原因：{last_rejection['reason']}")
        test_report_file = last_rejection.get("test_report_file", "")
        if test_report_file:
            try:
                with open(os.path.join(WORK_DIR, test_report_file), 'r', encoding='utf-8') as f:
                    test_report_content = f.read()
                print(f"   📄 已读取测试报告：{test_report_file}")
            except Exception as e:
                print(f"   ⚠️ 读取测试报告失败：{e}")
    
    prd_file = state.get('prd_file', '')
    
    # 第一步：编写软件规格说明书
    print("\n   📝 步骤 1/2：编写软件规格说明书...")
    
    spec_agent = ClaudeAgent("architect_agent", "系统架构师", agent_type="architect_agent")
    
    spec_prompt_base = f"""你是系统架构师/技术负责人。请直接输出软件规格说明书的完整内容。

请读取 PRD 文档：{prd_file}

软件规格说明书必须包含以下章节：

# 软件规格说明书

## 1. 系统架构设计
- 模块划分
- 模块间接口定义
- 调用关系图（用文字描述）

## 2. 数据结构定义
- 核心数据类/结构体定义
- 字段说明

## 3. 核心算法说明
- 关键算法逻辑
- 伪代码或流程说明

## 4. 错误处理策略
- 可能出现的错误类型
- 处理方式

## 5. 接口契约
- 每个函数的输入参数
- 返回值定义
- 异常抛出说明

## 6. 代码目录结构
```
建议的目录结构
```"""

    # 如果有测试报告，添加修复要求
    if test_report_content:
        spec_prompt = spec_prompt_base + f"""

## 7. 测试缺陷修复要求
根据以下测试报告中的缺陷，调整架构设计以修复问题：

```
{test_report_content[:3000]}
```

**修复要求**：
- 分析测试报告中的失败原因
- 在架构设计中明确如何修复这些缺陷
- 确保新的架构能支持修复后的实现
"""
    else:
        spec_prompt = spec_prompt_base

    spec_prompt += """

重要：直接输出规格说明书内容，不要有任何对话或解释。"""
    
    spec_content = await spec_agent.execute(spec_prompt)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    spec_filename = f"Spec_{timestamp}.md"
    spec_filepath = save_deliverable(spec_filename, spec_content)
    
    # 写入 SharedBoard
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"spec_{timestamp}",
        value={"filename": spec_filename, "content": spec_content[:500], "filepath": spec_filepath},
        author="dev_agent"
    )
    
    print(f"   📄 规格说明书：{spec_filename} ({len(spec_content)} 字符)")
    
    # 第二步：根据规格说明书编写代码
    print("\n   💻 步骤 2/2：根据规格说明书编写代码...")
    
    code_agent = ClaudeAgent("code_agent", "Python 工程师", agent_type="developer_agent")
    
    code_prompt_base = f"""你是 Python 工程师。请直接输出完整可运行的 Python 代码。

请读取以下文档：
- PRD 文档：{prd_file}
- 软件规格说明书：{spec_filename}

代码要求：
1. 严格按照规格说明书实现
2. 包含完整的类和方法
3. 包含命令行交互界面（main函数）
4. 完善的错误处理（try-except）
5. 使用中文注释说明关键逻辑
6. 所有代码放在一个文件中

**输出格式要求（严格遵守）**：
- 只输出纯 Python 代码
- **绝对不要**使用 Markdown 代码块标记（如 ```python 或 ```）
- **绝对不要**在开头添加任何说明文字
- 文件必须以正确的 import 语句开头
- 包含必要的 shebang（#!/usr/bin/env python3）

正确示例：
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 功能描述：命令行计算器

import sys

def main():
    pass

if __name__ == "__main__":
    main()"""

    # 如果有测试报告，添加修复要求
    if test_report_content:
        code_prompt = code_prompt_base + f"""

## 缺陷修复要求（必须修复）
根据以下测试报告中的失败用例和缺陷，修复代码问题：

```
{test_report_content[:3000]}
```

**修复要求**：
1. 仔细阅读测试报告，找出所有失败的测试用例
2. 分析失败原因（如边界条件、异常处理、精度问题等）
3. 修改代码以修复这些缺陷
4. 确保修复后的代码能通过所有测试用例
5. 在代码注释中说明修复的内容

**特别注意**：
- 不要忽略任何失败的测试
- 确保边界条件和异常场景都被正确处理
- 如果涉及数值精度问题，考虑使用合适的数据类型（如 int、Decimal 等）
"""
    else:
        code_prompt = code_prompt_base

    code_prompt += """

重要：直接输出纯 Python 代码，不要使用 Markdown 格式，不要有任何对话或解释。代码必须可以直接保存为 .py 文件并运行。"""
    
    code_content = await code_agent.execute(code_prompt)
    
    code_filename = f"code_v{state['iteration'] + 1}_{timestamp}.py"
    code_filepath = save_deliverable(code_filename, code_content)
    
    # 写入 SharedBoard
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"code_{timestamp}",
        value={"filename": code_filename, "content": code_content[:500], "filepath": code_filepath},
        author="dev_agent"
    )
    
    print(f"   📄 代码文件：{code_filename} ({len(code_content)} 字符)")
    
    return {
        "spec_file": spec_filename,
        "code_file": code_filename,
        "iteration": state["iteration"] + 1
    }


async def qa_agent(state: DevState) -> dict:
    """
    测试 Agent：交付测试用例 + 测试报告
    分三步执行：
    1. 基于 PRD 生成测试计划
    2. 基于代码生成具体测试用例
    3. 执行测试并生成报告
    """
    print("\n" + "="*70)
    print("🧪 【测试 Agent - Claude】正在开发测试用例并执行...")
    print("="*70)
    
    prd_file = state.get('prd_file', '')
    code_file = state.get('code_file', '')
    
    print(f"   📖 输入：")
    print(f"      - PRD：{prd_file}")
    print(f"      - 代码：{code_file}")
    
    # 第一步：基于 PRD 生成测试计划
    print("\n   📝 步骤 1/3：基于 PRD 生成测试计划...")
    
    test_plan_agent = ClaudeAgent("test_plan_agent", "测试工程师", agent_type="tester_agent")
    
    test_plan_prompt = f"""你是测试工程师。请直接输出测试计划的完整内容。

请读取 PRD 文档：{prd_file}

测试计划必须包含以下章节：

# 测试计划

## 1. 测试范围
- 功能测试（核心功能，不超过 5 个测试点）
- 异常测试（主要错误场景，不超过 5 个）
- 边界测试（关键边界条件，不超过 5 个）

## 2. 测试策略
- 测试方法（黑盒/白盒）
- 测试优先级（P0/P1/P2）
- **总测试用例数：10-15 个**

## 3. 测试用例设计思路
- 正常场景：标准输入下的预期行为（3-5 个）
- 异常场景：错误输入的处理（3-5 个）
- 边界条件：极限值测试（2-5 个）

## 4. 测试通过标准
- 测试覆盖率要求（核心功能覆盖）
- 通过率要求（100%）
- 性能要求（如有）

**重要约束**：
- 测试用例总数控制在 10-15 个
- 避免过度设计，重点覆盖 PRD 中的核心功能
- 不要追求全覆盖，优先保证主要业务流程正确

重要：直接输出测试计划内容，不要有任何对话或解释。"""
    
    test_plan_content = await test_plan_agent.execute(test_plan_prompt)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    test_plan_filename = f"test_plan_{timestamp}.md"
    test_plan_filepath = save_deliverable(test_plan_filename, test_plan_content)
    
    # 写入 SharedBoard
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"test_plan_{timestamp}",
        value={"filename": test_plan_filename, "content": test_plan_content[:500], "filepath": test_plan_filepath},
        author="qa_agent"
    )
    
    print(f"   📄 测试计划：{test_plan_filename} ({len(test_plan_content)} 字符)")
    
    # 第二步：基于代码和测试计划生成测试用例
    print("\n   📝 步骤 2/3：基于代码生成测试用例...")
    
    test_cases_agent = ClaudeAgent("test_cases_agent", "测试工程师", agent_type="tester_agent")
    
    test_cases_prompt = f"""你是测试工程师。请直接输出完整可运行的 Python 测试代码。

请读取以下文档：
- 测试计划：{test_plan_filename}
- 代码文件：{code_file}

测试代码要求：
1. 使用 Python unittest 框架
2. 测试类和方法名称与被测代码对应
3. **测试用例数量控制在 10-15 个以内**，覆盖核心功能即可：
   - 正常场景：3-5 个（主要功能路径）
   - 异常场景：3-5 个（错误处理、边界条件）
   - 边界条件：2-5 个（极限值、特殊输入）
4. 每个测试方法包含中文注释说明测试目的
5. 测试代码可直接运行（python3 test_xxx.py）

**重要约束**：
- 测试用例总数不超过 15 个
- 避免过度测试，重点覆盖 PRD 中的核心功能
- 不要为每个函数都写测试，优先测试主要业务流程

**输出格式要求（严格遵守）**：
- 只输出纯 Python 代码
- **绝对不要**使用 Markdown 代码块标记（如 ```python 或 ```）
- **绝对不要**在开头添加任何说明文字
- 文件必须以 import 语句开头
- 文件必须以 if __name__ 结尾（如有）

正确示例：
import unittest
from calculator import Calculator

class TestCalculator(unittest.TestCase):
    def test_add(self):
        \"\"\"测试加法功能\"\"\"
        calc = Calculator()
        self.assertEqual(calc.add(1, 2), 3)

if __name__ == '__main__':
    unittest.main()

重要：直接输出纯 Python 代码，不要使用 Markdown 格式，不要有任何对话或解释。代码必须可以直接保存为 .py 文件并运行。"""
    
    test_cases_content = await test_cases_agent.execute(test_cases_prompt)
    
    test_cases_filename = f"test_cases_{timestamp}.py"
    test_cases_filepath = save_deliverable(test_cases_filename, test_cases_content)
    
    # 写入 SharedBoard
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"test_cases_{timestamp}",
        value={"filename": test_cases_filename, "content": test_cases_content[:500], "filepath": test_cases_filepath},
        author="qa_agent"
    )
    
    print(f"   📄 测试用例：{test_cases_filename} ({len(test_cases_content)} 字符)")
    
    # 第三步：本地执行测试并生成报告
    print("\n   🧪 步骤 3/3：执行测试并生成报告...")
    
    # 本地执行测试
    import subprocess
    test_result = ""
    test_passed = False
    try:
        # 先尝试运行测试
        result = subprocess.run(
            ["python3", "-m", "pytest", test_cases_filepath, "-v"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=WORK_DIR
        )
        test_result = result.stdout + "\n" + result.stderr
        test_passed = result.returncode == 0
    except Exception as e:
        test_result = f"pytest 执行出错：{str(e)}\n\n尝试使用 unittest..."
        try:
            result = subprocess.run(
                ["python3", test_cases_filepath],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=WORK_DIR
            )
            test_result += "\n" + result.stdout + "\n" + result.stderr
            test_passed = "OK" in result.stdout or "PASSED" in result.stdout
        except Exception as e2:
            test_result += f"\nunittest 也失败：{str(e2)}"
    
    # 生成测试报告
    report_agent = ClaudeAgent("report_agent", "测试工程师", agent_type="tester_agent")
    
    report_prompt = f"""你是测试工程师。

基于以下信息，生成正式的测试报告：

测试计划：{test_plan_filename}
测试用例文件：{test_cases_filename}
代码文件：{code_file}

测试执行结果：
```
{test_result[:2000]}
```

请生成测试报告，包含：
1. 测试概述（测试范围、测试环境）
2. 测试用例执行统计（通过/失败数量）
3. 详细测试结果
4. 缺陷列表（如有）
5. 测试结论：TEST_PASSED 或 TEST_FAILED

请以 Markdown 格式输出测试报告。"""
    
    report_content = await report_agent.execute(report_prompt)
    
    report_filename = f"test_report_{timestamp}.md"
    report_filepath = save_deliverable(report_filename, report_content)
    
    # 写入 SharedBoard
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"test_report_{timestamp}",
        value={
            "filename": report_filename, 
            "content": report_content[:500], 
            "filepath": report_filepath,
            "test_passed": test_passed
        },
        author="qa_agent"
    )
    
    print(f"   📄 测试报告：{report_filename} ({len(report_content)} 字符)")
    print(f"   {'✅ 测试通过' if test_passed else '❌ 测试不通过'}")
    
    return {
        "test_plan_file": test_plan_filename,
        "test_cases_file": test_cases_filename,
        "test_report_file": report_filename,
        "test_passed": test_passed
    }


async def ops_agent(state: DevState) -> dict:
    """
    运维 Agent：交付运维脚本 + 上线报告
    输入：测试报告链接 + 软件规格说明书链接 + 代码链接
    输出：运维脚本链接 + 发布上线报告链接
    """
    print("\n" + "="*70)
    print("🚀 【运维 Agent - Claude】正在开发运维脚本并部署...")
    print("="*70)
    
    if not state["test_passed"]:
        print("   ❌ 测试未通过，禁止部署")
        return {
            "deploy_script_file": "",
            "deploy_report_file": "",
            "deploy_passed": False
        }
    
    test_report_file = state.get('test_report_file', '')
    spec_file = state.get('spec_file', '')
    code_file = state.get('code_file', '')
    
    print(f"   📖 输入：")
    print(f"      - 测试报告：{test_report_file}")
    print(f"      - 规格说明书：{spec_file}")
    print(f"      - 代码：{code_file}")
    
    # 第一步：开发运维脚本
    print("\n   📝 步骤 1/2：开发运维脚本...")
    
    deploy_agent = ClaudeAgent("deploy_agent", "运维工程师", agent_type="ops_agent")
    
    deploy_prompt = f"""你是运维工程师。请直接输出完整的 Shell 部署脚本。

请读取以下文档：
- 测试报告：{test_report_file}
- 软件规格说明书：{spec_file}
- 代码文件：{code_file}

部署脚本必须包含：
1. 环境检查（Python 版本、依赖检查）
2. 备份策略
3. 部署步骤（代码部署、配置部署）
4. 健康检查
5. 回滚策略
6. 日志记录

脚本要求：
- 以 #!/bin/bash 开头
- 包含错误处理（set -e 或手动检查）
- 包含使用说明（-h 参数）
- 可直接执行

输出格式：
```bash
#!/bin/bash
# 部署脚本说明
...
```

重要：直接输出 Shell 脚本代码，不要有任何对话、解释或说明。脚本必须可以直接运行。"""
    
    deploy_script_content = await deploy_agent.execute(deploy_prompt)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    deploy_script_filename = f"deploy_{timestamp}.sh"
    deploy_script_filepath = save_deliverable(deploy_script_filename, deploy_script_content)
    
    # 添加可执行权限
    try:
        os.chmod(deploy_script_filepath, 0o755)
    except:
        pass
    
    # 写入 SharedBoard
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"deploy_script_{timestamp}",
        value={"filename": deploy_script_filename, "content": deploy_script_content[:500], "filepath": deploy_script_filepath},
        author="ops_agent"
    )
    
    print(f"   📄 部署脚本：{deploy_script_filename} ({len(deploy_script_content)} 字符)")
    
    # 第二步：生成发布上线报告
    print("\n   📋 步骤 2/2：生成发布上线报告...")
    
    report_agent = ClaudeAgent("release_agent", "运维工程师", agent_type="ops_agent")
    
    deploy_report_prompt = f"""你是运维工程师/发布经理。请直接输出发布上线报告的完整内容。

基于以下信息生成报告：
- 代码文件：{code_file}
- 测试报告：{test_report_file}
- 部署脚本：{deploy_script_filename}

报告必须包含以下章节：

# 功能发布上线报告

## 1. 发布概述
- 版本号
- 发布时间
- 发布内容摘要

## 2. 发布清单
- 交付物列表及路径
- 每个交付物的说明

## 3. 测试结果摘要
- 测试通过率
- 关键测试场景结果

## 4. 部署步骤摘要
- 部署命令
- 关键步骤说明

## 5. 回滚方案
- 回滚命令
- 回滚触发条件

## 6. 验证结果
- 验证命令
- 预期输出
- 实际结果

## 7. 发布结论
在报告最后一行明确标注：
**发布结论：DEPLOY_SUCCESS** 或 **发布结论：DEPLOY_FAILED**

重要：直接输出报告内容，不要有任何对话或解释。"""
    
    deploy_report_content = await report_agent.execute(deploy_report_prompt)
    
    deploy_report_filename = f"deploy_report_{timestamp}.md"
    deploy_report_filepath = save_deliverable(deploy_report_filename, deploy_report_content)
    
    deploy_passed = "DEPLOY_SUCCESS" in deploy_report_content.upper() or "成功" in deploy_report_content
    
    # 写入 SharedBoard
    shared_board.put(
        namespace=("team", "deliverables"),
        key=f"deploy_report_{timestamp}",
        value={
            "filename": deploy_report_filename, 
            "content": deploy_report_content[:500], 
            "filepath": deploy_report_filepath,
            "deploy_passed": deploy_passed
        },
        author="ops_agent"
    )
    
    print(f"   📄 上线报告：{deploy_report_filename} ({len(deploy_report_content)} 字符)")
    print(f"   {'✅ 部署成功' if deploy_passed else '❌ 部署失败'}")
    
    return {
        "deploy_script_file": deploy_script_filename,
        "deploy_report_file": deploy_report_filename,
        "deploy_passed": deploy_passed
    }


async def end_node(state: DevState) -> dict:
    """结束节点：汇总所有交付物"""
    print("\n" + "="*70)
    print("🎉 【流程完成】软件研发流程已全部完成！")
    print("="*70)
    
    print(f"\n📊 流程统计：")
    print(f"   总迭代次数：{state['iteration']}")
    print(f"   打回次数：{len(state['rejections'])}")
    
    if state["rejections"]:
        print(f"\n🔄 打回记录：")
        for i, rej in enumerate(state["rejections"], 1):
            print(f"   {i}. {rej['from']} → {rej['to']}: {rej['reason']}")
    
    print(f"\n📦 交付物清单：")
    print(f"   📄 PRD 文档：{state.get('prd_file', 'N/A')}")
    print(f"   📄 软件规格说明书：{state.get('spec_file', 'N/A')}")
    print(f"   📄 代码实现：{state.get('code_file', 'N/A')}")
    print(f"   📄 测试用例：{state.get('test_cases_file', 'N/A')}")
    print(f"   📄 测试报告：{state.get('test_report_file', 'N/A')} ({'通过' if state.get('test_passed') else '不通过'})")
    print(f"   📄 部署脚本：{state.get('deploy_script_file', 'N/A')}")
    print(f"   📄 上线报告：{state.get('deploy_report_file', 'N/A')}")
    
    print(f"\n📁 所有交付物保存在：{WORK_DIR}")
    
    # 导出 SharedBoard
    board_export_path = os.path.join(WORK_DIR, f"shared_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    shared_board.export_to_file(board_export_path)
    print(f"\n📋 SharedBoard 已导出：{board_export_path}")
    
    return {}


async def handle_qa_rejection(state: DevState) -> dict:
    """处理测试打回"""
    print("\n" + "⏮️" * 35)
    print("   【质量门禁】测试不通过，打回开发阶段")
    print("⏮️" * 35)
    
    return {
        "rejections": [{
            "from": "qa",
            "to": "dev",
            "reason": "测试失败",
            "timestamp": datetime.now().isoformat(),
            "iteration": state["iteration"],
            "test_report_file": state.get("test_report_file", "")
        }]
    }


async def handle_deploy_rejection(state: DevState) -> dict:
    """处理部署打回"""
    print("\n" + "⏮️" * 35)
    print("   【发布门禁】部署失败，打回开发阶段")
    print("⏮️" * 35)
    
    return {
        "rejections": [{
            "from": "ops",
            "to": "dev",
            "reason": "部署失败",
            "timestamp": datetime.now().isoformat(),
            "iteration": state["iteration"]
        }]
    }


# ==================== 条件路由 ====================

def route_after_qa(state: DevState) -> Literal["ops", "qa_reject"]:
    """测试后的路由决策"""
    if state.get("test_passed"):
        print(f"\n⏭️  路由：测试通过 → 部署阶段")
        return "ops"
    else:
        print(f"\n⏮️  路由：测试不通过 → 打回开发")
        return "qa_reject"


def route_after_deploy(state: DevState) -> Literal["end", "deploy_reject"]:
    """部署后的路由决策"""
    if state.get("deploy_passed"):
        print(f"\n⏭️  路由：部署成功 → 完成")
        return "end"
    else:
        print(f"\n⏮️  路由：部署失败 → 打回开发")
        return "deploy_reject"


# ==================== 构建工作流 ====================

def build_workflow():
    """构建 LangGraph 工作流"""
    
    workflow = StateGraph(DevState)
    
    # 添加节点 - 使用同步包装器包装异步函数
    def run_async(async_func):
        def wrapper(state):
            # 创建新的事件循环来运行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_func(state))
            finally:
                loop.close()
        return wrapper
    
    workflow.add_node("product", run_async(product_agent))
    workflow.add_node("dev", run_async(dev_agent))
    workflow.add_node("qa", run_async(qa_agent))
    workflow.add_node("ops", run_async(ops_agent))
    workflow.add_node("qa_reject", run_async(handle_qa_rejection))
    workflow.add_node("deploy_reject", run_async(handle_deploy_rejection))
    workflow.add_node("end", run_async(end_node))
    
    # 正常流程边
    workflow.add_edge(START, "product")
    workflow.add_edge("product", "dev")
    workflow.add_edge("dev", "qa")
    
    # QA 条件边
    workflow.add_conditional_edges("qa", route_after_qa, {"ops": "ops", "qa_reject": "qa_reject"})
    
    # 部署条件边
    workflow.add_conditional_edges("ops", route_after_deploy, {"end": "end", "deploy_reject": "deploy_reject"})
    
    # 打回后返回开发
    workflow.add_edge("qa_reject", "dev")
    workflow.add_edge("deploy_reject", "dev")
    
    # 结束
    workflow.add_edge("end", END)
    
    return workflow.compile()


# ==================== ACF WorkflowBuilder 版本 ====================

async def run_with_acf_workflow(initial_state: dict):
    """使用 ACF WorkflowBuilder 和 WorkflowRunner 运行工作流"""
    
    from acf.workflow.builder import WorkflowBuilder
    from acf.workflow.runner import WorkflowRunner
    from acf.adapter.base import AgentAdapter, AdapterConfig
    
    # 创建适配器
    product_adapter = AdapterFactory.create(
        "claude", name="product_agent", timeout=300,
        metadata={"workspace_dir": WORK_DIR}
    )
    dev_adapter = AdapterFactory.create(
        "claude", name="dev_agent", timeout=600,
        metadata={"workspace_dir": WORK_DIR}
    )
    qa_adapter = AdapterFactory.create(
        "claude", name="qa_agent", timeout=600,
        metadata={"workspace_dir": WORK_DIR}
    )
    ops_adapter = AdapterFactory.create(
        "claude", name="ops_agent", timeout=300,
        metadata={"workspace_dir": WORK_DIR}
    )
    
    # 使用传统 StateGraph 方式（因为 WorkflowBuilder 更适用于简单线性流）
    # 这里展示如何集成 ACF 组件
    print("\n[ACF-v2 工作流模式]")
    
    app = build_workflow()
    
    for event in app.stream(initial_state, stream_mode="values"):
        pass
    
    return event


# ==================== 主函数 ====================

async def main_async():
    """异步主函数"""
    # 初始化日志
    log_path = log_init()
    
    print("\n" + "🚀" * 35)
    print("   软件研发流程多 Agent 系统")
    print("   基于 LangGraph + ACF-v2 框架")
    print("   采用交付物链传递的规范流程")
    print("🚀" * 35)
    
    # 需求输入 - 支持命令行参数
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
