"""Agent Collaboration Framework v2.0.

ACF v2.0 is a multi-agent collaboration framework built on top of LangGraph.
It provides adapter-based agent integration with support for Claude, Kimi, and Mock agents,
plus agent management, skills system, and shared storage.
"""

# Adapter layer
from acf.adapter.base import AgentAdapter, AdapterConfig, AgentResult, AgentStatus
from acf.adapter.factory import AdapterFactory

# Workflow layer
from acf.workflow.state import AgentState, WorkflowStatus
from acf.workflow.nodes import AgentNode, NodeConfig
from acf.workflow.builder import WorkflowBuilder, create_simple_workflow
from acf.workflow.runner import WorkflowRunner, WorkflowResult, WorkflowEvent

# Agent management
from acf.agent import AgentTemplate, AgentRole, WorkspaceManager, WorkspaceConfig
from acf.skills import Skill, SkillManager
from acf.store import SharedBoard, SimpleSharedBoard, BoardEntry

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
    # Agent Management
    "AgentTemplate",
    "AgentRole",
    "WorkspaceManager",
    "WorkspaceConfig",
    # Skills
    "Skill",
    "SkillManager",
    # Storage
    "SharedBoard",
    "SimpleSharedBoard",
    "BoardEntry",
]
