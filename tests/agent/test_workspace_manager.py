"""Tests for workspace_manager module."""

import json
import tempfile
from pathlib import Path

import pytest

from acf.agent import WorkspaceConfig, WorkspaceManager


class TestWorkspaceConfig:
    """Tests for WorkspaceConfig dataclass."""

    def test_workspace_config_creation(self):
        """Test creating a WorkspaceConfig."""
        config = WorkspaceConfig(
            agent_name="test_agent",
            base_dir=Path("/tmp"),
            private_dirs=["workspace", "skills", "logs"],
            shared_access=["deliverables"],
        )

        assert config.agent_name == "test_agent"
        assert config.base_dir == Path("/tmp")
        assert len(config.private_dirs) == 3
        assert len(config.shared_access) == 1


class TestWorkspaceManager:
    """Tests for WorkspaceManager class."""

    def test_initialization(self):
        """Test initializing WorkspaceManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            assert manager.base_dir == Path(tmpdir).resolve()
            assert manager.agents_dir == manager.base_dir / "agents"
            assert manager.shared_dir == manager.base_dir / "shared"

    def test_create_agent_workspace(self):
        """Test creating agent workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            agent_dir = manager.create_agent_workspace("test_agent")

            assert agent_dir.exists()
            assert (agent_dir / "workspace").exists()
            assert (agent_dir / "skills").exists()

    def test_create_agent_workspace_custom_dirs(self):
        """Test creating agent workspace with custom directory flags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            agent_dir = manager.create_agent_workspace(
                "test_agent",
                create_skills_dir=False,
                create_workspace_dir=False,
            )

            assert agent_dir.exists()
            assert not (agent_dir / "workspace").exists()
            assert not (agent_dir / "skills").exists()

    def test_get_agent_workspace(self):
        """Test getting agent workspace path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            path = manager.get_agent_workspace("test_agent")

            assert path == manager.base_dir / "agents" / "test_agent" / "workspace"

    def test_get_agent_skills_dir(self):
        """Test getting agent skills directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            path = manager.get_agent_skills_dir("test_agent")

            assert path == manager.base_dir / "agents" / "test_agent" / "skills"

    def test_get_agent_dir(self):
        """Test getting agent base directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            path = manager.get_agent_dir("test_agent")

            assert path == manager.base_dir / "agents" / "test_agent"

    def test_get_shared_workspace(self):
        """Test getting shared workspace path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            path = manager.get_shared_workspace()

            assert path == manager.base_dir / "shared"

    def test_get_shared_subdir(self):
        """Test getting shared subdirectory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            path = manager.get_shared_subdir("deliverables")

            assert path == manager.base_dir / "shared" / "deliverables"

    def test_ensure_structure(self):
        """Test ensuring complete directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            paths = manager.ensure_structure(
                agents=["agent1", "agent2"],
                shared_subdirs=["deliverables", "decisions"],
            )

            # Check shared directories
            assert (manager.base_dir / "shared" / "deliverables").exists()
            assert (manager.base_dir / "shared" / "decisions").exists()

            # Check agent directories
            assert (manager.base_dir / "agents" / "agent1" / "workspace").exists()
            assert (manager.base_dir / "agents" / "agent2" / "workspace").exists()

            # Check paths returned
            assert "shared_deliverables" in paths
            assert "agent_agent1" in paths

    def test_ensure_structure_no_agents(self):
        """Test ensuring structure without agents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            paths = manager.ensure_structure()

            # Should create default shared subdirs
            assert (manager.base_dir / "shared" / "deliverables").exists()
            assert (manager.base_dir / "shared" / "decisions").exists()
            assert (manager.base_dir / "shared" / "lessons").exists()

            # Should not create any agents
            assert len(list(manager.base_dir.glob("agents/*"))) == 0

    def test_agent_exists(self):
        """Test checking if agent exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            assert not manager.agent_exists("test_agent")

            manager.create_agent_workspace("test_agent")

            assert manager.agent_exists("test_agent")

    def test_list_agents(self):
        """Test listing agents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            assert manager.list_agents() == []

            manager.create_agent_workspace("agent1")
            manager.create_agent_workspace("agent2")

            agents = manager.list_agents()
            assert "agent1" in agents
            assert "agent2" in agents

    def test_list_agents_empty(self):
        """Test listing agents when none exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            assert manager.list_agents() == []

    def test_get_agent_files(self):
        """Test getting agent files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.create_agent_workspace("test_agent")

            # Create a file
            workspace = manager.get_agent_workspace("test_agent")
            (workspace / "test.txt").write_text("test content")

            files = manager.get_agent_files("test_agent", "workspace")

            assert len(files) == 1
            assert files[0].name == "test.txt"

    def test_get_agent_files_nonexistent(self):
        """Test getting files from non-existent agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            files = manager.get_agent_files("nonexistent", "workspace")
            assert files == []

    def test_write_to_agent_workspace(self):
        """Test writing to agent workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            path = manager.write_to_agent_workspace(
                "test_agent",
                "test.txt",
                "test content",
            )

            assert path.exists()
            assert path.read_text() == "test content"

    def test_write_to_shared(self):
        """Test writing to shared directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            path = manager.write_to_shared(
                "deliverables",
                "prd.md",
                "PRD content",
            )

            assert path.exists()
            assert path.read_text() == "PRD content"

    def test_read_from_agent_workspace(self):
        """Test reading from agent workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.write_to_agent_workspace("test_agent", "test.txt", "content")

            content = manager.read_from_agent_workspace("test_agent", "test.txt")

            assert content == "content"

    def test_read_from_agent_workspace_not_found(self):
        """Test reading non-existent file from agent workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            content = manager.read_from_agent_workspace("test_agent", "nonexistent.txt")

            assert content is None

    def test_read_from_shared(self):
        """Test reading from shared directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.write_to_shared("deliverables", "prd.md", "PRD content")

            content = manager.read_from_shared("deliverables", "prd.md")

            assert content == "PRD content"

    def test_read_from_shared_not_found(self):
        """Test reading non-existent file from shared directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            content = manager.read_from_shared("deliverables", "nonexistent.md")

            assert content is None

    def test_copy_to_shared(self):
        """Test copying from agent workspace to shared."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.write_to_agent_workspace("test_agent", "output.txt", "output content")

            path = manager.copy_to_shared("test_agent", "output.txt", "deliverables")

            assert path is not None
            assert path.exists()
            assert path.read_text() == "output content"

    def test_copy_to_shared_with_new_name(self):
        """Test copying with new filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.write_to_agent_workspace("test_agent", "output.txt", "content")

            path = manager.copy_to_shared(
                "test_agent",
                "output.txt",
                "deliverables",
                new_filename="final.txt",
            )

            assert path.name == "final.txt"

    def test_copy_to_shared_not_found(self):
        """Test copying non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            path = manager.copy_to_shared("test_agent", "nonexistent.txt", "deliverables")

            assert path is None

    def test_get_workspace_info(self):
        """Test getting workspace info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.create_agent_workspace("agent1")
            manager.write_to_agent_workspace("agent1", "file.txt", "content")
            manager.write_to_shared("deliverables", "shared.txt", "shared content")

            info = manager.get_workspace_info()

            assert info["base_dir"] == str(manager.base_dir)
            assert "agent1" in info["agents"]
            assert "deliverables" in info["shared"]

    def test_export_workspace_info(self):
        """Test exporting workspace info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.create_agent_workspace("agent1")

            path = manager.export_workspace_info()

            assert path.exists()
            data = json.loads(path.read_text())
            assert "agents" in data
            assert "agent1" in data["agents"]

    def test_export_workspace_info_custom_path(self):
        """Test exporting workspace info to custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            custom_path = Path(tmpdir) / "custom_info.json"

            path = manager.export_workspace_info(custom_path)

            assert path == custom_path
            assert path.exists()

    def test_clean_agent_workspace(self):
        """Test cleaning agent workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.create_agent_workspace("test_agent")
            manager.write_to_agent_workspace("test_agent", "file.txt", "content")

            assert len(manager.get_agent_files("test_agent")) == 1

            result = manager.clean_agent_workspace("test_agent")

            assert result is True
            assert len(manager.get_agent_files("test_agent")) == 0

    def test_clean_nonexistent_workspace(self):
        """Test cleaning non-existent workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            result = manager.clean_agent_workspace("nonexistent")

            assert result is True

    def test_remove_agent(self):
        """Test removing an agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            manager.create_agent_workspace("test_agent")

            assert manager.agent_exists("test_agent")

            result = manager.remove_agent("test_agent")

            assert result is True
            assert not manager.agent_exists("test_agent")

    def test_remove_nonexistent_agent(self):
        """Test removing non-existent agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            result = manager.remove_agent("nonexistent")

            assert result is False
