"""Skill management system for ACF v2.0 Real Agent Example.

This module provides Skill and SkillManager for loading, parsing,
and formatting agent skills from markdown files.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Represents a skill loaded from a SKILL.md file.

    Attributes:
        name: Skill name (from filename or frontmatter).
        description: Brief description of what the skill does.
        content: Full markdown content of the skill.
        when_to_use: Conditions for using this skill.
        inputs: Expected input parameters.
        outputs: Expected output format.
        steps: List of steps to execute.
        metadata: Additional metadata from frontmatter.
    """

    name: str
    description: str = ""
    content: str = ""
    when_to_use: str = ""
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, file_path: Path | str) -> "Skill":
        """Parse a skill from a markdown file.

        Args:
            file_path: Path to the skill markdown file.

        Returns:
            Parsed Skill instance.

        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Skill file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Extract name from filename
        name = file_path.stem

        # Parse frontmatter if present
        metadata = {}
        if content.startswith("---"):
            frontmatter_match = re.match(r"---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if frontmatter_match:
                frontmatter_text = frontmatter_match.group(1)
                content = content[frontmatter_match.end():]

                # Simple YAML-like parsing
                for line in frontmatter_text.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()

        # Extract description from frontmatter or first heading
        description = metadata.get("description", "")
        if not description and "## Description" in content:
            desc_match = re.search(r"## Description\s*\n(.*?)(?=\n##|$)", content, re.DOTALL)
            if desc_match:
                description = desc_match.group(1).strip()

        # Extract when_to_use
        when_to_use = ""
        if "## When to Use" in content:
            when_match = re.search(r"## When to Use\s*\n(.*?)(?=\n##|$)", content, re.DOTALL)
            if when_match:
                when_to_use = when_match.group(1).strip()

        # Extract inputs
        inputs = []
        if "## Input" in content or "## Inputs" in content:
            input_section = re.search(r"## Inputs?\s*\n(.*?)(?=\n##|$)", content, re.DOTALL)
            if input_section:
                for line in input_section.group(1).split("\n"):
                    line = line.strip()
                    if line.startswith("-") or line.startswith("*"):
                        inputs.append(line[1:].strip())
                    elif line and ":" in line:
                        inputs.append(line)

        # Extract outputs
        outputs = []
        if "## Output" in content or "## Outputs" in content:
            output_section = re.search(r"## Outputs?\s*\n(.*?)(?=\n##|$)", content, re.DOTALL)
            if output_section:
                for line in output_section.group(1).split("\n"):
                    line = line.strip()
                    if line.startswith("-") or line.startswith("*"):
                        outputs.append(line[1:].strip())
                    elif line and ":" in line:
                        outputs.append(line)

        # Extract steps
        steps = []
        if "## Steps" in content or "## Procedure" in content:
            steps_section = re.search(r"## (Steps|Procedure)\s*\n(.*?)(?=\n##|$)", content, re.DOTALL)
            if steps_section:
                for line in steps_section.group(2).split("\n"):
                    line = line.strip()
                    # Match numbered lists (1. step) or bullet lists
                    if re.match(r"^\d+\.\s", line):
                        steps.append(re.sub(r"^\d+\.\s", "", line))
                    elif line.startswith("-") or line.startswith("*"):
                        steps.append(line[1:].strip())

        return cls(
            name=name,
            description=description,
            content=content,
            when_to_use=when_to_use,
            inputs=inputs,
            outputs=outputs,
            steps=steps,
            metadata=metadata,
        )

    def format_for_prompt(self) -> str:
        """Format skill as a prompt-friendly string.

        Returns:
            Formatted skill description.
        """
        lines = [f"### @{self.name}", ""]

        if self.description:
            lines.append(self.description)
            lines.append("")

        if self.when_to_use:
            lines.append(f"**When to use:** {self.when_to_use}")
            lines.append("")

        if self.inputs:
            lines.append("**Inputs:**")
            for inp in self.inputs:
                lines.append(f"- {inp}")
            lines.append("")

        if self.outputs:
            lines.append("**Outputs:**")
            for out in self.outputs:
                lines.append(f"- {out}")
            lines.append("")

        if self.steps:
            lines.append("**Steps:**")
            for i, step in enumerate(self.steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert skill to dictionary.

        Returns:
            Dictionary representation of the skill.
        """
        return {
            "name": self.name,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "steps": self.steps,
            "metadata": self.metadata,
        }


class SkillManager:
    """Manages loading and formatting of agent skills.

    This class provides a centralized way to load skills from the
    agents/{name}/skills/ directory and format them for use in prompts.

    Example:
        ```python
        manager = SkillManager("./agents")

        # Load all skills for an agent
        skills = manager.load_skills("product_manager")

        # Format for prompt
        prompt_section = manager.format_for_prompt(skills)

        # Get specific skill
        skill = manager.get_skill("product_manager", "write-prd")
        ```
    """

    def __init__(self, agents_dir: Path | str):
        """Initialize skill manager.

        Args:
            agents_dir: Base directory containing agent subdirectories.
        """
        self.agents_dir = Path(agents_dir)
        self._cache: Dict[str, Dict[str, Skill]] = {}

    def load_skills(self, agent_name: str, use_cache: bool = True) -> Dict[str, Skill]:
        """Load all skills for an agent.

        Args:
            agent_name: Name of the agent directory.
            use_cache: If True, return cached skills if available.

        Returns:
            Dictionary mapping skill names to Skill objects.
        """
        cache_key = agent_name

        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        skills_dir = self.agents_dir / agent_name / "skills"
        skills: Dict[str, Skill] = {}

        if not skills_dir.exists():
            return skills

        for skill_file in skills_dir.glob("*.md"):
            try:
                skill = Skill.from_file(skill_file)
                skills[skill.name] = skill
            except Exception as e:
                logger.warning(f"Failed to load skill {skill_file}: {e}")

        if use_cache:
            self._cache[cache_key] = skills

        return skills

    def get_skill(self, agent_name: str, skill_name: str) -> Optional[Skill]:
        """Get a specific skill for an agent.

        Args:
            agent_name: Name of the agent directory.
            skill_name: Name of the skill (without .md extension).

        Returns:
            Skill object if found, None otherwise.
        """
        # Check cache first
        cache_key = agent_name
        if cache_key in self._cache and skill_name in self._cache[cache_key]:
            return self._cache[cache_key][skill_name]

        # Load from file
        skill_file = self.agents_dir / agent_name / "skills" / f"{skill_name}.md"

        if not skill_file.exists():
            return None

        try:
            return Skill.from_file(skill_file)
        except Exception as e:
            logger.warning(f"Failed to load skill {skill_file}: {e}")
            return None

    def format_for_prompt(
        self,
        skills: Dict[str, Skill] | str,
        include_content: bool = False,
    ) -> str:
        """Format skills for inclusion in a prompt.

        Args:
            skills: Dictionary of skills or agent name to load from.
            include_content: If True, include full skill content.

        Returns:
            Formatted skills section for prompt.
        """
        if isinstance(skills, str):
            skills = self.load_skills(skills)

        if not skills:
            return "No skills available."

        lines = ["## Available Skills", ""]

        for skill in skills.values():
            if include_content:
                lines.append(skill.format_for_prompt())
            else:
                desc = skill.description or "No description"
                lines.append(f"- @{skill.name}: {desc}")

        lines.append("")
        lines.append("Use appropriate skills based on the task.")

        return "\n".join(lines)

    def create_skill(
        self,
        agent_name: str,
        skill_name: str,
        description: str,
        when_to_use: str = "",
        inputs: List[str] | None = None,
        outputs: List[str] | None = None,
        steps: List[str] | None = None,
    ) -> Path:
        """Create a new skill file for an agent.

        Args:
            agent_name: Name of the agent.
            skill_name: Name of the skill.
            description: Skill description.
            when_to_use: When to use this skill.
            inputs: List of input parameters.
            outputs: List of output formats.
            steps: List of execution steps.

        Returns:
            Path to the created skill file.
        """
        skills_dir = self.agents_dir / agent_name / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_file = skills_dir / f"{skill_name}.md"

        lines = [
            "---",
            f"name: {skill_name}",
            f"description: {description}",
            "---",
            "",
            f"## Description",
            "",
            description,
            "",
        ]

        if when_to_use:
            lines.extend([
                "## When to Use",
                "",
                when_to_use,
                "",
            ])

        if inputs:
            lines.extend([
                "## Input",
                "",
            ])
            for inp in inputs:
                lines.append(f"- {inp}")
            lines.append("")

        if outputs:
            lines.extend([
                "## Output",
                "",
            ])
            for out in outputs:
                lines.append(f"- {out}")
            lines.append("")

        if steps:
            lines.extend([
                "## Steps",
                "",
            ])
            for i, step in enumerate(steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        skill_file.write_text("\n".join(lines), encoding="utf-8")

        # Clear cache for this agent
        cache_key = agent_name
        if cache_key in self._cache:
            del self._cache[cache_key]

        return skill_file

    def clear_cache(self, agent_name: str | None = None):
        """Clear the skills cache.

        Args:
            agent_name: If specified, clear only this agent's cache.
                       If None, clear all cache.
        """
        if agent_name is None:
            self._cache.clear()
        elif agent_name in self._cache:
            del self._cache[agent_name]

    def list_skills(self, agent_name: str) -> List[str]:
        """List all skill names for an agent.

        Args:
            agent_name: Name of the agent directory.

        Returns:
            List of skill names.
        """
        skills_dir = self.agents_dir / agent_name / "skills"

        if not skills_dir.exists():
            return []

        return [f.stem for f in skills_dir.glob("*.md")]


def format_skills_for_agent(
    skills: Dict[str, Skill],
    enforced_skill: str | None = None,
) -> str:
    """Format skills section for agent system prompt.

    Args:
        skills: Dictionary of available skills.
        enforced_skill: If specified, enforce using this skill.

    Returns:
        Formatted skills section.
    """
    if not skills:
        return ""

    lines = ["## Available Skills", ""]

    if enforced_skill and enforced_skill in skills:
        skill = skills[enforced_skill]
        lines.append(f"**ENFORCED SKILL: @{enforced_skill}**")
        lines.append("")
        lines.append(skill.format_for_prompt())
    else:
        for skill in skills.values():
            lines.append(f"- @{skill.name}: {skill.description}")

        lines.append("")
        lines.append("Use the appropriate skill based on the task.")

    return "\n".join(lines)
