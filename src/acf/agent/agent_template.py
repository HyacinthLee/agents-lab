"""Agent template generator for ACF v2.0 Real Agent Example.

This module provides AgentTemplate for generating AGENT.md templates
that users can customize for each agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AgentRole:
    """Definition of an agent role.

    Attributes:
        name: Role name (e.g., "Product Manager").
        identity: Description of who this agent is.
        responsibilities: List of responsibilities.
        constraints: List of constraints (what not to do).
        default_skills: List of default skill names.
    """

    name: str
    identity: str
    responsibilities: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    default_skills: List[str] = field(default_factory=list)


# Predefined roles for common agent types
PREDEFINED_ROLES: Dict[str, AgentRole] = {
    "product_manager": AgentRole(
        name="Product Manager",
        identity="你是产品经理，负责将用户需求转化为产品需求文档。",
        responsibilities=[
            "分析用户需求",
            "编写 PRD 文档",
            "定义验收标准",
            "协调开发资源",
        ],
        constraints=[
            "不写代码实现细节",
            "不指定技术栈",
            "不做技术可行性评估",
        ],
        default_skills=["write-prd", "analyze-requirements"],
    ),
    "developer": AgentRole(
        name="Developer",
        identity="你是软件开发者，负责根据 PRD 实现功能代码。",
        responsibilities=[
            "阅读 PRD 文档",
            "编写高质量代码",
            "实现单元测试",
            "修复代码问题",
        ],
        constraints=[
            "不修改 PRD 需求",
            "不跳过测试编写",
            "不引入未指定的依赖",
        ],
        default_skills=["write-code", "write-tests", "debug-code"],
    ),
    "code_reviewer": AgentRole(
        name="Code Reviewer",
        identity="你是代码审查者，负责检查代码质量和规范。",
        responsibilities=[
            "审查代码质量",
            "检查代码规范",
            "识别潜在问题",
            "提供改进建议",
        ],
        constraints=[
            "不直接修改代码",
            "不引入新功能",
            "保持客观公正",
        ],
        default_skills=["review-code", "check-style"],
    ),
}


class AgentTemplate:
    """Template generator for AGENT.md files.

    This class generates AGENT.md templates based on predefined roles
    or custom configurations. Users can then manually edit the generated
    templates to customize agent behavior.

    Example:
        ```python
        # Generate from predefined role
        AgentTemplate.generate(
            role="product_manager",
            workspace="./agents/pm"
        )

        # Generate custom template
        template = AgentTemplate(
            role=AgentRole(
                name="Custom Agent",
                identity="...",
                responsibilities=["..."],
            )
        )
        template.save("./agents/custom/AGENT.md")
        ```
    """

    def __init__(self, role: AgentRole):
        """Initialize template with a role definition.

        Args:
            role: Agent role definition.
        """
        self.role = role

    def render(self) -> str:
        """Render the AGENT.md template content.

        Returns:
            Markdown content for AGENT.md.
        """
        lines = [
            f"# {self.role.name}",
            "",
            "## Identity",
            self.role.identity,
            "",
            "## Demo Declaration",
            "- 简单设计，核心功能即可",
            "- 输出控制在合理范围内",
            "- 避免过度工程化",
            "",
            "## Responsibilities",
        ]

        for responsibility in self.role.responsibilities:
            lines.append(f"- {responsibility}")

        lines.extend(["", "## Constraints"])

        for constraint in self.role.constraints:
            lines.append(f"- {constraint}")

        lines.extend(["", "## Skills"])

        for skill in self.role.default_skills:
            lines.append(f"- @{skill}")

        lines.extend([
            "",
            "## Custom Instructions",
            "<!-- Add any custom instructions below -->",
            "",
        ])

        return "\n".join(lines)

    def save(self, path: Path | str) -> Path:
        """Save the template to a file.

        Args:
            path: Path to save the template (file or directory).

        Returns:
            Path to the saved file.
        """
        path = Path(path)

        # If path is a directory, create AGENT.md inside it
        if path.suffix != ".md":
            path = path / "AGENT.md"

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write template content
        path.write_text(self.render(), encoding="utf-8")

        return path

    @classmethod
    def from_predefined(cls, role_name: str) -> "AgentTemplate":
        """Create template from predefined role.

        Args:
            role_name: Name of predefined role (e.g., "product_manager").

        Returns:
            AgentTemplate instance.

        Raises:
            ValueError: If role_name is not a predefined role.
        """
        if role_name not in PREDEFINED_ROLES:
            available = ", ".join(PREDEFINED_ROLES.keys())
            raise ValueError(f"Unknown role '{role_name}'. Available: {available}")

        return cls(PREDEFINED_ROLES[role_name])

    @classmethod
    def generate(
        cls,
        role: str | AgentRole,
        workspace: Path | str,
        exist_ok: bool = True,
    ) -> Path:
        """Generate AGENT.md template in workspace.

        This is the main entry point for generating agent templates.
        It creates the AGENT.md file and returns the path.

        Args:
            role: Role name (str) or custom AgentRole.
            workspace: Path to agent workspace directory.
            exist_ok: If False, raise error if AGENT.md already exists.

        Returns:
            Path to generated AGENT.md file.

        Raises:
            FileExistsError: If AGENT.md exists and exist_ok=False.
        """
        workspace = Path(workspace)
        agent_md_path = workspace / "AGENT.md"

        if agent_md_path.exists() and not exist_ok:
            raise FileExistsError(f"AGENT.md already exists: {agent_md_path}")

        # Create template from role
        if isinstance(role, str):
            template = cls.from_predefined(role)
        else:
            template = cls(role)

        # Save template
        return template.save(workspace)

    @classmethod
    def get_available_roles(cls) -> List[str]:
        """Get list of available predefined role names.

        Returns:
            List of role names.
        """
        return list(PREDEFINED_ROLES.keys())


def load_agent_config(agent_path: Path | str) -> Dict[str, Any]:
    """Load agent configuration from AGENT.md.

    Args:
        agent_path: Path to agent directory or AGENT.md file.

    Returns:
        Dictionary with parsed configuration.
    """
    agent_path = Path(agent_path)

    # If directory, look for AGENT.md inside
    if agent_path.is_dir():
        agent_md = agent_path / "AGENT.md"
    else:
        agent_md = agent_path

    if not agent_md.exists():
        return {
            "name": agent_path.name,
            "identity": "No AGENT.md found.",
            "responsibilities": [],
            "constraints": [],
            "skills": [],
        }

    content = agent_md.read_text(encoding="utf-8")

    # Parse with regex for robustness
    config = {
        "name": agent_md.parent.name,
        "raw_content": content,
        "responsibilities": [],
        "constraints": [],
        "skills": [],
    }

    # Extract identity
    identity_match = re.search(r'##\s*Identity\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if identity_match:
        config["identity"] = identity_match.group(1).strip()
    else:
        config["identity"] = "No identity defined."

    # Extract responsibilities
    resp_match = re.search(r'##\s*Responsibilities\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if resp_match:
        for line in resp_match.group(1).split("\n"):
            line = line.strip()
            if line.startswith("-"):
                config["responsibilities"].append(line[1:].strip())

    # Extract constraints
    cons_match = re.search(r'##\s*Constraints\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if cons_match:
        for line in cons_match.group(1).split("\n"):
            line = line.strip()
            if line.startswith("-"):
                config["constraints"].append(line[1:].strip())

    # Extract skills
    skills_match = re.search(r'##\s*Skills\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if skills_match:
        for line in skills_match.group(1).split("\n"):
            line = line.strip()
            if line.startswith("- @"):
                config["skills"].append(line[3:].strip())
            elif line.startswith("-"):
                config["skills"].append(line[1:].strip())

    return config
