"""Tests for agent_template module."""

import tempfile
from pathlib import Path

import pytest

from acf.agent import AgentRole, AgentTemplate, load_agent_config, PREDEFINED_ROLES


class TestAgentRole:
    """Tests for AgentRole dataclass."""

    def test_agent_role_creation(self):
        """Test creating an AgentRole."""
        role = AgentRole(
            name="Test Role",
            identity="Test identity",
            responsibilities=["resp1", "resp2"],
            constraints=["constraint1"],
            default_skills=["skill1"],
        )

        assert role.name == "Test Role"
        assert role.identity == "Test identity"
        assert len(role.responsibilities) == 2
        assert len(role.constraints) == 1
        assert len(role.default_skills) == 1


class TestAgentTemplate:
    """Tests for AgentTemplate class."""

    def test_render_template(self):
        """Test rendering AGENT.md template."""
        role = AgentRole(
            name="Test Agent",
            identity="You are a test agent.",
            responsibilities=["Do testing", "Write tests"],
            constraints=["Don't break things"],
            default_skills=["test", "debug"],
        )
        template = AgentTemplate(role)

        content = template.render()

        assert "# Test Agent" in content
        assert "You are a test agent." in content
        assert "Do testing" in content
        assert "Don't break things" in content
        assert "@test" in content
        assert "@debug" in content

    def test_save_template(self):
        """Test saving template to file."""
        role = AgentRole(
            name="Test Agent",
            identity="You are a test agent.",
        )
        template = AgentTemplate(role)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = template.save(tmpdir)

            assert path.exists()
            assert path.name == "AGENT.md"
            content = path.read_text()
            assert "# Test Agent" in content

    def test_save_template_to_file_path(self):
        """Test saving template to explicit file path."""
        role = AgentRole(
            name="Test Agent",
            identity="You are a test agent.",
        )
        template = AgentTemplate(role)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "custom.md"
            path = template.save(file_path)

            assert path.exists()
            assert path.name == "custom.md"

    def test_from_predefined(self):
        """Test creating template from predefined role."""
        for role_name in PREDEFINED_ROLES.keys():
            template = AgentTemplate.from_predefined(role_name)
            assert template.role.name == PREDEFINED_ROLES[role_name].name

    def test_from_predefined_invalid(self):
        """Test creating template from invalid predefined role."""
        with pytest.raises(ValueError) as exc_info:
            AgentTemplate.from_predefined("invalid_role")

        assert "Unknown role" in str(exc_info.value)

    def test_generate_new_file(self):
        """Test generating AGENT.md in new workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "test_agent"
            path = AgentTemplate.generate("product_manager", workspace)

            assert path.exists()
            assert path.name == "AGENT.md"
            content = path.read_text()
            assert "Product Manager" in content

    def test_generate_existing_file_with_exist_ok(self):
        """Test generating AGENT.md when file exists with exist_ok=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "test_agent"
            workspace.mkdir()
            agent_md = workspace / "AGENT.md"
            agent_md.write_text("Existing content")

            path = AgentTemplate.generate("product_manager", workspace, exist_ok=True)

            assert path.exists()
            # Should overwrite
            content = path.read_text()
            assert "Product Manager" in content

    def test_generate_existing_file_without_exist_ok(self):
        """Test generating AGENT.md when file exists with exist_ok=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "test_agent"
            workspace.mkdir()
            agent_md = workspace / "AGENT.md"
            agent_md.write_text("Existing content")

            with pytest.raises(FileExistsError):
                AgentTemplate.generate("product_manager", workspace, exist_ok=False)

    def test_generate_with_custom_role(self):
        """Test generating AGENT.md with custom AgentRole."""
        custom_role = AgentRole(
            name="Custom Agent",
            identity="Custom identity",
            responsibilities=["Custom task"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "test_agent"
            path = AgentTemplate.generate(custom_role, workspace)

            content = path.read_text()
            assert "Custom Agent" in content
            assert "Custom identity" in content

    def test_get_available_roles(self):
        """Test getting available predefined roles."""
        roles = AgentTemplate.get_available_roles()

        assert isinstance(roles, list)
        assert "product_manager" in roles
        assert "developer" in roles
        assert "code_reviewer" in roles


class TestLoadAgentConfig:
    """Tests for load_agent_config function."""

    def test_load_existing_config(self):
        """Test loading existing AGENT.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "test_agent"
            workspace.mkdir()
            agent_md = workspace / "AGENT.md"
            agent_md.write_text("""
# Test Agent

## Identity
You are a test agent.

## Responsibilities
- Do testing
- Write tests

## Constraints
- Don't break things

## Skills
- @test
- @debug
""")

            config = load_agent_config(workspace)

            assert config["name"] == "test_agent"
            assert "You are a test agent." in config["identity"]
            assert "Do testing" in config["responsibilities"]
            assert "Write tests" in config["responsibilities"]
            assert "Don't break things" in config["constraints"]
            assert "test" in config["skills"]
            assert "debug" in config["skills"]

    def test_load_nonexistent_config(self):
        """Test loading non-existent AGENT.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "test_agent"
            workspace.mkdir()

            config = load_agent_config(workspace)

            assert config["name"] == "test_agent"
            assert config["identity"] == "No AGENT.md found."
            assert config["responsibilities"] == []
            assert config["constraints"] == []
            assert config["skills"] == []

    def test_load_config_from_file_path(self):
        """Test loading AGENT.md from file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_md = Path(tmpdir) / "AGENT.md"
            agent_md.write_text("""
# Test Agent

## Identity
You are a test agent.
""")

            config = load_agent_config(agent_md)

            assert "You are a test agent." in config["identity"]


class TestPredefinedRoles:
    """Tests for predefined roles."""

    def test_product_manager_role(self):
        """Test product manager predefined role."""
        role = PREDEFINED_ROLES["product_manager"]
        assert role.name == "Product Manager"
        assert "产品经理" in role.identity
        assert len(role.responsibilities) > 0
        assert len(role.constraints) > 0
        assert "write-prd" in role.default_skills

    def test_developer_role(self):
        """Test developer predefined role."""
        role = PREDEFINED_ROLES["developer"]
        assert role.name == "Developer"
        assert "开发者" in role.identity
        assert len(role.responsibilities) > 0
        assert len(role.constraints) > 0
        assert "write-code" in role.default_skills

    def test_code_reviewer_role(self):
        """Test code reviewer predefined role."""
        role = PREDEFINED_ROLES["code_reviewer"]
        assert role.name == "Code Reviewer"
        assert "代码审查者" in role.identity
        assert len(role.responsibilities) > 0
        assert len(role.constraints) > 0
        assert "review-code" in role.default_skills
