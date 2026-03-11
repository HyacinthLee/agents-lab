"""Workspace management for ACF v2.0 Real Agent Example.

This module provides WorkspaceManager for creating and managing
agent workspaces and shared directories.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class WorkspaceConfig:
    """Configuration for a workspace.

    Attributes:
        agent_name: Name of the agent.
        base_dir: Base directory for all agents.
        private_dirs: List of private subdirectories to create.
        shared_access: List of shared namespaces this agent can access.
    """

    agent_name: str
    base_dir: Path = field(default_factory=lambda: Path("."))
    private_dirs: List[str] = field(default_factory=lambda: ["workspace", "skills"])
    shared_access: List[str] = field(default_factory=lambda: ["deliverables", "decisions", "lessons"])


class WorkspaceManager:
    """Manager for agent workspaces and shared directories.

    This class handles the creation and management of:
    - Individual agent workspaces (agents/{name}/workspace/)
    - Agent skill directories (agents/{name}/skills/)
    - Shared directories (shared/deliverables/, shared/decisions/, shared/lessons/)

    Directory Structure:
    ```
    base_dir/
    ├── agents/
    │   ├── agent-a/
    │   │   ├── AGENT.md
    │   │   ├── skills/
    │   │   └── workspace/
    │   └── agent-b/
    │       ├── AGENT.md
    │       ├── skills/
    │       └── workspace/
    └── shared/
        ├── deliverables/
        ├── decisions/
        └── lessons/
    ```

    Example:
        ```python
        # Initialize manager
        manager = WorkspaceManager("./real_agents")

        # Ensure full structure exists
        manager.ensure_structure()

        # Create agent workspace
        manager.create_agent_workspace("product_manager")

        # Get paths
        pm_workspace = manager.get_agent_workspace("product_manager")
        shared_deliverables = manager.get_shared_workspace() / "deliverables"
        ```
    """

    def __init__(self, base_dir: Path | str):
        """Initialize workspace manager.

        Args:
            base_dir: Base directory for the workspace structure.
        """
        self.base_dir = Path(base_dir).resolve()
        self.agents_dir = self.base_dir / "agents"
        self.shared_dir = self.base_dir / "shared"

    def create_agent_workspace(
        self,
        agent_name: str,
        create_skills_dir: bool = True,
        create_workspace_dir: bool = True,
    ) -> Path:
        """Create workspace for an agent.

        Args:
            agent_name: Name of the agent.
            create_skills_dir: Whether to create the skills directory.
            create_workspace_dir: Whether to create the workspace directory.

        Returns:
            Path to the agent's base directory.
        """
        agent_dir = self.agents_dir / agent_name

        # Create base agent directory
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        if create_skills_dir:
            (agent_dir / "skills").mkdir(exist_ok=True)

        if create_workspace_dir:
            (agent_dir / "workspace").mkdir(exist_ok=True)

        return agent_dir

    def get_agent_workspace(self, agent_name: str) -> Path:
        """Get the workspace path for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Path to the agent's workspace directory.
        """
        return self.agents_dir / agent_name / "workspace"

    def get_agent_skills_dir(self, agent_name: str) -> Path:
        """Get the skills directory path for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Path to the agent's skills directory.
        """
        return self.agents_dir / agent_name / "skills"

    def get_agent_dir(self, agent_name: str) -> Path:
        """Get the base directory for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Path to the agent's base directory.
        """
        return self.agents_dir / agent_name

    def get_shared_workspace(self) -> Path:
        """Get the shared workspace path.

        Returns:
            Path to the shared directory.
        """
        return self.shared_dir

    def get_shared_subdir(self, name: str) -> Path:
        """Get a specific shared subdirectory.

        Args:
            name: Name of the subdirectory (e.g., "deliverables", "decisions", "lessons").

        Returns:
            Path to the shared subdirectory.
        """
        return self.shared_dir / name

    def ensure_structure(
        self,
        agents: Optional[List[str]] = None,
        shared_subdirs: Optional[List[str]] = None,
    ) -> Dict[str, Path]:
        """Ensure the complete workspace structure exists.

        Args:
            agents: List of agent names to create workspaces for. If None, only creates shared dirs.
            shared_subdirs: List of shared subdirectories to create. Defaults to ["deliverables", "decisions", "lessons"].

        Returns:
            Dictionary mapping directory names to paths.
        """
        paths: Dict[str, Path] = {}

        # Create shared directories
        if shared_subdirs is None:
            shared_subdirs = ["deliverables", "decisions", "lessons"]

        for subdir in shared_subdirs:
            path = self.shared_dir / subdir
            path.mkdir(parents=True, exist_ok=True)
            paths[f"shared_{subdir}"] = path

        # Create agent workspaces
        if agents:
            for agent_name in agents:
                agent_dir = self.create_agent_workspace(agent_name)
                paths[f"agent_{agent_name}"] = agent_dir
                paths[f"agent_{agent_name}_workspace"] = agent_dir / "workspace"
                paths[f"agent_{agent_name}_skills"] = agent_dir / "skills"

        return paths

    def agent_exists(self, agent_name: str) -> bool:
        """Check if an agent workspace exists.

        Args:
            agent_name: Name of the agent.

        Returns:
            True if the agent directory exists.
        """
        return (self.agents_dir / agent_name).exists()

    def list_agents(self) -> List[str]:
        """List all agent workspaces.

        Returns:
            List of agent names.
        """
        if not self.agents_dir.exists():
            return []

        return [
            d.name for d in self.agents_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def get_agent_files(self, agent_name: str, subdir: str = "workspace") -> List[Path]:
        """Get all files in an agent's subdirectory.

        Args:
            agent_name: Name of the agent.
            subdir: Subdirectory to list ("workspace" or "skills").

        Returns:
            List of file paths.
        """
        target_dir = self.agents_dir / agent_name / subdir

        if not target_dir.exists():
            return []

        return [f for f in target_dir.iterdir() if f.is_file()]

    def write_to_agent_workspace(
        self,
        agent_name: str,
        filename: str,
        content: str,
    ) -> Path:
        """Write a file to an agent's workspace.

        Args:
            agent_name: Name of the agent.
            filename: Name of the file to write.
            content: Content to write.

        Returns:
            Path to the written file.
        """
        workspace = self.get_agent_workspace(agent_name)
        workspace.mkdir(parents=True, exist_ok=True)

        file_path = workspace / filename
        file_path.write_text(content, encoding="utf-8")

        return file_path

    def write_to_shared(
        self,
        subdir: str,
        filename: str,
        content: str,
    ) -> Path:
        """Write a file to a shared subdirectory.

        Args:
            subdir: Shared subdirectory name.
            filename: Name of the file to write.
            content: Content to write.

        Returns:
            Path to the written file.
        """
        target_dir = self.shared_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / filename
        file_path.write_text(content, encoding="utf-8")

        return file_path

    def read_from_agent_workspace(
        self,
        agent_name: str,
        filename: str,
    ) -> Optional[str]:
        """Read a file from an agent's workspace.

        Args:
            agent_name: Name of the agent.
            filename: Name of the file to read.

        Returns:
            File content if exists, None otherwise.
        """
        file_path = self.get_agent_workspace(agent_name) / filename

        if not file_path.exists():
            return None

        return file_path.read_text(encoding="utf-8")

    def read_from_shared(
        self,
        subdir: str,
        filename: str,
    ) -> Optional[str]:
        """Read a file from a shared subdirectory.

        Args:
            subdir: Shared subdirectory name.
            filename: Name of the file to read.

        Returns:
            File content if exists, None otherwise.
        """
        file_path = self.shared_dir / subdir / filename

        if not file_path.exists():
            return None

        return file_path.read_text(encoding="utf-8")

    def copy_to_shared(
        self,
        agent_name: str,
        filename: str,
        subdir: str = "deliverables",
        new_filename: Optional[str] = None,
    ) -> Optional[Path]:
        """Copy a file from agent workspace to shared directory.

        Args:
            agent_name: Name of the agent.
            filename: Name of the file to copy.
            subdir: Shared subdirectory to copy to.
            new_filename: Optional new filename in shared directory.

        Returns:
            Path to the copied file if successful, None otherwise.
        """
        source = self.get_agent_workspace(agent_name) / filename

        if not source.exists():
            return None

        target_name = new_filename or filename
        target_dir = self.shared_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / target_name

        content = source.read_text(encoding="utf-8")
        target.write_text(content, encoding="utf-8")

        return target

    def get_workspace_info(self) -> Dict[str, Any]:
        """Get information about the workspace structure.

        Returns:
            Dictionary with workspace information.
        """
        info = {
            "base_dir": str(self.base_dir),
            "agents_dir": str(self.agents_dir),
            "shared_dir": str(self.shared_dir),
            "agents": {},
            "shared": {},
        }

        # Get agent info
        for agent_name in self.list_agents():
            agent_dir = self.get_agent_dir(agent_name)
            workspace_files = self.get_agent_files(agent_name, "workspace")
            skills_files = self.get_agent_files(agent_name, "skills")

            info["agents"][agent_name] = {
                "path": str(agent_dir),
                "workspace_files": [f.name for f in workspace_files],
                "skills_count": len(skills_files),
            }

        # Get shared info
        if self.shared_dir.exists():
            for subdir in ["deliverables", "decisions", "lessons"]:
                subdir_path = self.shared_dir / subdir
                if subdir_path.exists():
                    files = [f.name for f in subdir_path.iterdir() if f.is_file()]
                    info["shared"][subdir] = {
                        "path": str(subdir_path),
                        "files": files,
                    }

        return info

    def export_workspace_info(self, output_file: Optional[Path | str] = None) -> Path:
        """Export workspace information to a JSON file.

        Args:
            output_file: Path to output file. If None, uses workspace/info.json.

        Returns:
            Path to the output file.
        """
        if output_file is None:
            output_file = self.base_dir / "workspace_info.json"
        else:
            output_file = Path(output_file)

        info = self.get_workspace_info()
        output_file.write_text(json.dumps(info, indent=2), encoding="utf-8")

        return output_file

    def clean_agent_workspace(self, agent_name: str) -> bool:
        """Clean (remove all files from) an agent's workspace.

        Args:
            agent_name: Name of the agent.

        Returns:
            True if successful.
        """
        workspace = self.get_agent_workspace(agent_name)

        if not workspace.exists():
            return True

        for file_path in workspace.iterdir():
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)

        return True

    def remove_agent(self, agent_name: str) -> bool:
        """Remove an agent's entire directory.

        Args:
            agent_name: Name of the agent.

        Returns:
            True if successful.
        """
        agent_dir = self.get_agent_dir(agent_name)

        if not agent_dir.exists():
            return False

        shutil.rmtree(agent_dir)
        return True
