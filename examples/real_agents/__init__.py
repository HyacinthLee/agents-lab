"""ACF v2.0 Real Agent Example.

This package provides a complete example of using ACF v2.0 with:
- AGENT.md template system
- Skill management
- Shared whiteboard for agent communication
- Workspace management

All core components are now part of the ACF framework.
"""

# Import from core framework
from acf.agent import AgentTemplate, AgentRole, load_agent_config, WorkspaceManager, WorkspaceConfig
from acf.skills import Skill, SkillManager, format_skills_for_agent
from acf.store import SharedBoard, SimpleSharedBoard, BoardEntry

__all__ = [
    "AgentTemplate",
    "AgentRole",
    "load_agent_config",
    "Skill",
    "SkillManager",
    "format_skills_for_agent",
    "SharedBoard",
    "SimpleSharedBoard",
    "BoardEntry",
    "WorkspaceManager",
    "WorkspaceConfig",
]
