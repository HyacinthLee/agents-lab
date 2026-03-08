# ACF v2.0 实现任务

## 项目信息
- 路径：/root/.openclaw/workspace/acf-v2/
- 目标：完整实现 Agent Collaboration Framework v2.0
- 原则：基于 LangGraph 扩展，不重复造轮子

## 第一阶段任务：核心接口与项目骨架

1. 创建 Python 项目结构（pyproject.toml, src/acf/ 等）
2. 实现 AgentAdapter 抽象基类（adapter/base.py）
3. 实现 ClaudeAdapter（adapter/claude.py）- 使用 tmux + "2" 确认
4. 实现 KimiAdapter（adapter/kimi.py）
5. 实现 MockAdapter（adapter/mock.py）
6. 创建适配器工厂（adapter/factory.py）
7. 编写第一阶段测试

## Demo 声明（控制复杂度）
这是一个演示 Demo：
- ✅ 核心接口完整实现
- ✅ 适配器覆盖 Claude/kimi/Mock
- ✅ 基础错误处理
- ❌ 不需要：复杂配置系统、完整 skill 系统、生产级日志

## 技术要点
- ClaudeAdapter 使用 tmux 启动 claude code
- 自动发送 "2" 确认（0.5s 延迟）
- 使用 tee 捕获输出到文件
- 检测文件大小稳定判断完成

请开始实现。