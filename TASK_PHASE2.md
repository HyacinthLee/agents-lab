# ACF v2.0 第二阶段任务：LangGraph 集成

## 目标
实现 ACF 与 LangGraph 的集成层，包括：

1. **状态图构建** (workflow/builder.py)
   - WorkflowBuilder 类
   - 从 YAML 配置构建 StateGraph
   - 支持条件分支和循环

2. **节点定义** (workflow/nodes.py)
   - AgentNode 包装器
   - 状态传递和转换
   - 错误处理和重试

3. **状态管理** (workflow/state.py)
   - AgentState 定义
   - 检查点集成
   - 长期记忆访问

4. **工作流运行器** (workflow/runner.py)
   - 同步/异步执行
   - 中断恢复支持
   - 事件回调

## Demo 声明
- ✅ 完整 StateGraph 集成
- ✅ YAML 配置支持
- ✅ 基础条件分支
- ❌ 不需要：复杂可视化、分布式执行

## 技术要点
- 使用 LangGraph 的 StateGraph
- 集成 CheckpointSaver 支持中断恢复
- BaseStore 用于长期记忆
- 保持 ACF 的 Adapter 接口兼容

请开始实现。