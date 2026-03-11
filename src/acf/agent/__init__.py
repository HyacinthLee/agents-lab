"""Agent management module for ACF v2.0.

This module provides agent template generation and workspace management.
"""

from acf.agent.agent_template import AgentTemplate, AgentRole, PREDEFINED_ROLES, load_agent_config
from acf.agent.workspace_manager import WorkspaceManager, WorkspaceConfig

__all__ = [
    "AgentTemplate",
    "AgentRole", 
    "PREDEFINED_ROLES",
    "load_agent_config",
    "WorkspaceManager",
    "WorkspaceConfig",
]
