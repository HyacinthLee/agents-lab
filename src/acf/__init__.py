"""Agent Collaboration Framework v2.0.

ACF v2.0 is a multi-agent collaboration framework built on top of LangGraph.
It provides adapter-based agent integration with support for Claude, Kimi, and Mock agents.
"""

from acf.adapter.base import AgentAdapter, AdapterConfig, AgentResult, AgentStatus
from acf.adapter.factory import AdapterFactory
from acf.workflow.state import AgentState, WorkflowStatus
from acf.workflow.nodes import AgentNode, NodeConfig
from acf.workflow.builder import WorkflowBuilder, create_simple_workflow
from acf.workflow.runner import WorkflowRunner, WorkflowResult, WorkflowEvent

__version__ = "0.2.0"
__all__ = [
    # Adapter
    "AgentAdapter",
    "AdapterConfig",
    "AgentResult",
    "AgentStatus",
    "AdapterFactory",
    # Workflow
    "AgentState",
    "WorkflowStatus",
    "AgentNode",
    "NodeConfig",
    "WorkflowBuilder",
    "create_simple_workflow",
    "WorkflowRunner",
    "WorkflowResult",
    "WorkflowEvent",
]