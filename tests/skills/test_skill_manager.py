"""Tests for skill_manager module."""

import tempfile
from pathlib import Path

import pytest

from acf.skills import Skill, SkillManager, format_skills_for_agent


class TestSkill:
    """Tests for Skill class."""

    def test_skill_creation(self):
        """Test creating a Skill."""
        skill = Skill(
            name="test-skill",
            description="A test skill",
            when_to_use="When testing",
            inputs=["input1"],
            outputs=["output1"],
            steps=["step1", "step2"],
        )

        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.when_to_use == "When testing"
        assert len(skill.inputs) == 1
        assert len(skill.outputs) == 1
        assert len(skill.steps) == 2

    def test_skill_from_file(self):
        """Test parsing skill from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "test-skill.md"
            skill_file.write_text("""---
name: test-skill
description: A test skill
---

## Description

This is a test skill.

## When to Use

Use this skill when testing.

## Input

- input1: First input
- input2: Second input

## Output

- output1: First output

## Steps

1. First step
2. Second step
3. Third step
""")

            skill = Skill.from_file(skill_file)

            assert skill.name == "test-skill"
            assert skill.description == "A test skill"
            assert "testing" in skill.when_to_use.lower()
            assert len(skill.inputs) == 2
            assert len(skill.outputs) == 1
            assert len(skill.steps) == 3

    def test_skill_from_file_without_frontmatter(self):
        """Test parsing skill from file without frontmatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "simple-skill.md"
            skill_file.write_text("""## Description

This is a simple skill.

## When to Use

Use when needed.
""")

            skill = Skill.from_file(skill_file)

            assert skill.name == "simple-skill"
            assert "simple skill" in skill.description.lower()

    def test_skill_from_file_not_found(self):
        """Test parsing skill from non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "nonexistent.md"

            with pytest.raises(FileNotFoundError):
                Skill.from_file(skill_file)

    def test_skill_format_for_prompt(self):
        """Test formatting skill for prompt."""
        skill = Skill(
            name="test-skill",
            description="A test skill",
            when_to_use="When testing",
            inputs=["input1", "input2"],
            outputs=["output1"],
            steps=["step1", "step2"],
        )

        formatted = skill.format_for_prompt()

        assert "@test-skill" in formatted
        assert "A test skill" in formatted
        assert "When testing" in formatted
        assert "input1" in formatted
        assert "output1" in formatted
        assert "step1" in formatted
        assert "step2" in formatted

    def test_skill_to_dict(self):
        """Test converting skill to dictionary."""
        skill = Skill(
            name="test-skill",
            description="A test skill",
            inputs=["input1"],
        )

        data = skill.to_dict()

        assert data["name"] == "test-skill"
        assert data["description"] == "A test skill"
        assert data["inputs"] == ["input1"]


class TestSkillManager:
    """Tests for SkillManager class."""

    def test_load_skills(self):
        """Test loading skills for an agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            skills_dir = agents_dir / "test_agent" / "skills"
            skills_dir.mkdir(parents=True)

            # Create skill files
            (skills_dir / "skill1.md").write_text("---\nname: skill1\ndescription: Skill 1\n---\n")
            (skills_dir / "skill2.md").write_text("---\nname: skill2\ndescription: Skill 2\n---\n")

            manager = SkillManager(agents_dir)
            skills = manager.load_skills("test_agent")

            assert len(skills) == 2
            assert "skill1" in skills
            assert "skill2" in skills

    def test_load_skills_empty(self):
        """Test loading skills when directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)

            manager = SkillManager(agents_dir)
            skills = manager.load_skills("nonexistent_agent")

            assert skills == {}

    def test_load_skills_with_cache(self):
        """Test that skills are cached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            skills_dir = agents_dir / "test_agent" / "skills"
            skills_dir.mkdir(parents=True)

            (skills_dir / "skill1.md").write_text("---\nname: skill1\ndescription: Skill 1\n---\n")

            manager = SkillManager(agents_dir)

            # First load
            skills1 = manager.load_skills("test_agent", use_cache=True)
            assert len(skills1) == 1

            # Add new skill
            (skills_dir / "skill2.md").write_text("---\nname: skill2\ndescription: Skill 2\n---\n")

            # Second load with cache (should not see new skill)
            skills2 = manager.load_skills("test_agent", use_cache=True)
            assert len(skills2) == 1

            # Third load without cache (should see new skill)
            skills3 = manager.load_skills("test_agent", use_cache=False)
            assert len(skills3) == 2

    def test_get_skill(self):
        """Test getting a specific skill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            skills_dir = agents_dir / "test_agent" / "skills"
            skills_dir.mkdir(parents=True)

            (skills_dir / "target.md").write_text("---\nname: target\ndescription: Target Skill\n---\n")

            manager = SkillManager(agents_dir)
            skill = manager.get_skill("test_agent", "target")

            assert skill is not None
            assert skill.name == "target"

    def test_get_skill_not_found(self):
        """Test getting a non-existent skill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)

            manager = SkillManager(agents_dir)
            skill = manager.get_skill("test_agent", "nonexistent")

            assert skill is None

    def test_format_for_prompt(self):
        """Test formatting skills for prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            skills_dir = agents_dir / "test_agent" / "skills"
            skills_dir.mkdir(parents=True)

            (skills_dir / "skill1.md").write_text("---\nname: skill1\ndescription: First skill\n---\n")
            (skills_dir / "skill2.md").write_text("---\nname: skill2\ndescription: Second skill\n---\n")

            manager = SkillManager(agents_dir)
            formatted = manager.format_for_prompt("test_agent")

            assert "Available Skills" in formatted
            assert "@skill1" in formatted
            assert "@skill2" in formatted
            assert "First skill" in formatted
            assert "Second skill" in formatted

    def test_format_for_prompt_empty(self):
        """Test formatting when no skills exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)

            manager = SkillManager(agents_dir)
            formatted = manager.format_for_prompt("test_agent")

            assert "No skills available" in formatted

    def test_create_skill(self):
        """Test creating a new skill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)

            manager = SkillManager(agents_dir)
            skill_path = manager.create_skill(
                agent_name="test_agent",
                skill_name="new-skill",
                description="A new skill",
                when_to_use="When needed",
                inputs=["input1"],
                outputs=["output1"],
                steps=["step1", "step2"],
            )

            assert skill_path.exists()
            content = skill_path.read_text()
            assert "new-skill" in content
            assert "A new skill" in content
            assert "When needed" in content
            assert "input1" in content
            assert "output1" in content
            assert "step1" in content

    def test_list_skills(self):
        """Test listing skills for an agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            skills_dir = agents_dir / "test_agent" / "skills"
            skills_dir.mkdir(parents=True)

            (skills_dir / "skill1.md").write_text("content")
            (skills_dir / "skill2.md").write_text("content")

            manager = SkillManager(agents_dir)
            skills = manager.list_skills("test_agent")

            assert "skill1" in skills
            assert "skill2" in skills

    def test_clear_cache(self):
        """Test clearing cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            skills_dir = agents_dir / "test_agent" / "skills"
            skills_dir.mkdir(parents=True)

            (skills_dir / "skill1.md").write_text("content")

            manager = SkillManager(agents_dir)
            manager.load_skills("test_agent")

            # Clear specific agent cache
            manager.clear_cache("test_agent")

            # Clear all cache
            manager.load_skills("test_agent")
            manager.clear_cache()


class TestFormatSkillsForAgent:
    """Tests for format_skills_for_agent function."""

    def test_format_without_enforced_skill(self):
        """Test formatting without enforced skill."""
        skills = {
            "skill1": Skill(name="skill1", description="First skill"),
            "skill2": Skill(name="skill2", description="Second skill"),
        }

        formatted = format_skills_for_agent(skills)

        assert "Available Skills" in formatted
        assert "@skill1" in formatted
        assert "@skill2" in formatted
        assert "First skill" in formatted

    def test_format_with_enforced_skill(self):
        """Test formatting with enforced skill."""
        skills = {
            "skill1": Skill(
                name="skill1",
                description="First skill",
                when_to_use="When needed",
                steps=["step1"],
            ),
            "skill2": Skill(name="skill2", description="Second skill"),
        }

        formatted = format_skills_for_agent(skills, enforced_skill="skill1")

        assert "ENFORCED SKILL" in formatted
        assert "@skill1" in formatted
        assert "When needed" in formatted
        assert "step1" in formatted

    def test_format_empty_skills(self):
        """Test formatting with no skills."""
        formatted = format_skills_for_agent({})

        assert formatted == ""
