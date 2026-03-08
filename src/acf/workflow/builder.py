"""Workflow builder for ACF v2.0.

This module provides WorkflowBuilder for constructing LangGraph StateGraph
from YAML configurations with support for conditional branches and loops.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from acf.adapter.base import AgentAdapter
from acf.adapter.factory import AdapterFactory
from acf.workflow.state import AgentState, WorkflowStatus, create_initial_state
from acf.workflow.nodes import (
    AgentNode,
    ConditionalNode,
    NodeConfig,
    NodeExecutionError,
)
from acf.adapter.base import AgentResult

logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    """Configuration for workflow construction.

    Attributes:
        name: Workflow identifier.
        description: Workflow description.
        entry_point: Starting node name.
        nodes: Node configurations.
        edges: Edge definitions.
        conditional_edges: Conditional edge definitions.
        metadata: Additional workflow metadata.
    """

    name: str
    description: str = ""
    entry_point: str = ""
    nodes: Dict[str, NodeConfig] = field(default_factory=dict)
    edges: List[tuple[str, str]] = field(default_factory=list)
    conditional_edges: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowBuilder:
    """Builder for constructing LangGraph workflows.

    This class provides a fluent API for building StateGraph workflows
    with ACF adapters and nodes.

    Example:
        ```python
        builder = WorkflowBuilder("my_workflow")

        # Add nodes
        builder.add_node("analyzer", analyzer_adapter)
        builder.add_node("writer", writer_adapter)

        # Add edges
        builder.add_edge("analyzer", "writer")
        builder.add_edge("writer", END)

        # Set entry point
        builder.set_entry_point("analyzer")

        # Build and compile
        graph = builder.compile()
        ```
    """

    def __init__(self, name: str, description: str = ""):
        """Initialize workflow builder.

        Args:
            name: Workflow name.
            description: Workflow description.
        """
        self.name = name
        self.description = description
        self._graph = StateGraph(AgentState)
        self._entry_point: Optional[str] = None
        self._nodes: Dict[str, AgentNode] = {}
        self._conditional_nodes: Dict[str, ConditionalNode] = {}
        self._compiled: bool = False

    def add_node(
        self,
        name: str,
        adapter: AgentAdapter,
        system_prompt: Optional[str] = None,
        retry_count: int = 3,
        timeout: float = 60.0,
        transform_input: Optional[Callable[[AgentState], str]] = None,
        transform_output: Optional[Callable[[AgentResult], Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> WorkflowBuilder:
        """Add an agent node to the workflow.

        Args:
            name: Node identifier.
            adapter: Agent adapter instance.
            system_prompt: Optional system prompt.
            retry_count: Number of retries on failure.
            timeout: Execution timeout.
            transform_input: Input transformation function.
            transform_output: Output transformation function.
            **kwargs: Additional node configuration.

        Returns:
            Self for method chaining.
        """
        if self._compiled:
            raise RuntimeError("Cannot modify compiled workflow")

        config = NodeConfig(
            name=name,
            adapter=adapter,
            system_prompt=system_prompt,
            retry_count=retry_count,
            timeout=timeout,
            transform_input=transform_input,
            transform_output=transform_output,
            metadata=kwargs,
        )

        node = AgentNode(config)
        self._nodes[name] = node

        # Add to graph - node.execute returns AgentState
        self._graph.add_node(name, node.execute)

        logger.debug(f"Added node '{name}' with adapter '{adapter.name}'")
        return self

    def add_edge(self, from_node: str, to_node: Union[str, Any]) -> WorkflowBuilder:
        """Add a direct edge between nodes.

        Args:
            from_node: Source node name.
            to_node: Target node name or END.

        Returns:
            Self for method chaining.
        """
        if self._compiled:
            raise RuntimeError("Cannot modify compiled workflow")

        self._graph.add_edge(from_node, to_node)
        logger.debug(f"Added edge: {from_node} -> {to_node}")
        return self

    def add_conditional_edges(
        self,
        from_node: str,
        condition: Callable[[AgentState], str],
        path_map: Dict[str, str],
        default: Optional[str] = None,
    ) -> WorkflowBuilder:
        """Add conditional edges from a node.

        Args:
            from_node: Source node name.
            condition: Function that evaluates state and returns path key.
            path_map: Mapping of path keys to target node names.
            default: Default path if condition returns unknown key.

        Returns:
            Self for method chaining.
        """
        if self._compiled:
            raise RuntimeError("Cannot modify compiled workflow")

        # Create conditional node
        cond_node = ConditionalNode(
            name=f"{from_node}_condition",
            condition=condition,
            branches=path_map,
            default_branch=default,
        )
        self._conditional_nodes[from_node] = cond_node

        # Add conditional edges to graph
        self._graph.add_conditional_edges(
            from_node,
            condition,
            path_map,
        )

        logger.debug(f"Added conditional edges from '{from_node}': {path_map}")
        return self

    def set_entry_point(self, node_name: str) -> WorkflowBuilder:
        """Set the workflow entry point.

        Args:
            node_name: Starting node name.

        Returns:
            Self for method chaining.
        """
        if self._compiled:
            raise RuntimeError("Cannot modify compiled workflow")

        self._entry_point = node_name
        self._graph.set_entry_point(node_name)
        logger.debug(f"Set entry point: {node_name}")
        return self

    def compile(self, checkpointer: Optional[Any] = None) -> CompiledStateGraph:
        """Compile the workflow graph.

        Args:
            checkpointer: Optional checkpoint saver for persistence.

        Returns:
            Compiled LangGraph.

        Raises:
            RuntimeError: If workflow configuration is invalid.
        """
        if self._compiled:
            raise RuntimeError("Workflow already compiled")

        if not self._entry_point:
            raise RuntimeError("Entry point not set")

        if not self._nodes:
            raise RuntimeError("No nodes added to workflow")

        try:
            compiled = self._graph.compile(checkpointer=checkpointer)
            self._compiled = True
            logger.info(f"Compiled workflow '{self.name}' with {len(self._nodes)} nodes")
            return compiled
        except Exception as e:
            raise RuntimeError(f"Failed to compile workflow: {e}") from e

    def get_node(self, name: str) -> Optional[AgentNode]:
        """Get a node by name.

        Args:
            name: Node name.

        Returns:
            AgentNode if found, None otherwise.
        """
        return self._nodes.get(name)

    def get_nodes(self) -> Dict[str, AgentNode]:
        """Get all nodes.

        Returns:
            Dictionary of node names to AgentNodes.
        """
        return dict(self._nodes)

    @classmethod
    def from_yaml(
        cls,
        yaml_path: Union[str, Path],
        adapter_factory: Optional[AdapterFactory] = None,
    ) -> WorkflowBuilder:
        """Build workflow from YAML configuration.

        Args:
            yaml_path: Path to YAML configuration file.
            adapter_factory: Optional factory for creating adapters.

        Returns:
            Configured WorkflowBuilder.

        Raises:
            ImportError: If PyYAML is not installed.
            FileNotFoundError: If YAML file not found.
            ValueError: If configuration is invalid.
        """
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is required for YAML configuration. "
                "Install with: pip install pyyaml"
            )

        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {yaml_path}")

        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError("YAML must contain a dictionary")

        # Create builder
        name = config.get("name", "unnamed_workflow")
        description = config.get("description", "")
        builder = cls(name, description)

        # Create adapters
        adapters: Dict[str, AgentAdapter] = {}
        adapter_configs = config.get("adapters", {})

        for adapter_name, adapter_config in adapter_configs.items():
            adapter_type = adapter_config.get("type", "mock")
            adapter_params = adapter_config.get("params", {})

            if adapter_factory:
                adapter = adapter_factory.create(adapter_type, **adapter_params)
            else:
                adapter = AdapterFactory.create(adapter_type, **adapter_params)

            adapters[adapter_name] = adapter

        # Add nodes
        nodes_config = config.get("nodes", {})
        for node_name, node_config in nodes_config.items():
            adapter_name = node_config.get("adapter")
            if adapter_name not in adapters:
                raise ValueError(f"Unknown adapter '{adapter_name}' for node '{node_name}'")

            builder.add_node(
                name=node_name,
                adapter=adapters[adapter_name],
                system_prompt=node_config.get("system_prompt"),
                retry_count=node_config.get("retry_count", 3),
                timeout=node_config.get("timeout", 60.0),
            )

        # Add edges
        edges_config = config.get("edges", [])
        for edge in edges_config:
            from_node = edge.get("from")
            to_node = edge.get("to")

            if edge.get("conditional"):
                # Conditional edge
                condition_name = edge.get("condition", "default")
                paths = edge.get("paths", {})
                default = edge.get("default")

                condition_func = _get_condition_function(condition_name)
                builder.add_conditional_edges(from_node, condition_func, paths, default)
            else:
                # Direct edge
                builder.add_edge(from_node, to_node)

        # Set entry point
        entry_point = config.get("entry_point")
        if entry_point:
            builder.set_entry_point(entry_point)

        return builder

    def to_yaml(self, yaml_path: Union[str, Path]) -> None:
        """Export workflow configuration to YAML.

        Args:
            yaml_path: Path to write YAML file.
        """
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is required for YAML export. "
                "Install with: pip install pyyaml"
            )

        config = {
            "name": self.name,
            "description": self.description,
            "entry_point": self._entry_point,
            "nodes": {},
            "edges": [],
        }

        # Export nodes
        for name, node in self._nodes.items():
            config["nodes"][name] = {
                "adapter": node.adapter.name,
                "system_prompt": node.config.system_prompt,
                "retry_count": node.config.retry_count,
                "timeout": node.config.timeout,
            }

        yaml_path = Path(yaml_path)
        with open(yaml_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)


def _get_condition_function(name: str) -> Callable[[AgentState], str]:
    """Get a predefined condition function by name.

    Args:
        name: Condition function name.

    Returns:
        Condition function.
    """
    conditions: Dict[str, Callable[[AgentState], str]] = {
        "default": lambda state: "default",
        "has_error": lambda state: "error" if state.get("error") else "continue",
        "is_complete": lambda state: "complete" if state.get("workflow_status") == WorkflowStatus.COMPLETED else "continue",
        "needs_retry": lambda state: "retry" if state.get("error") and state.get("metadata", {}).get("retry_count", 0) < 3 else "fail",
    }

    if name not in conditions:
        logger.warning(f"Unknown condition '{name}', using default")
        return conditions["default"]

    return conditions[name]


def create_simple_workflow(
    name: str,
    nodes: List[tuple[str, AgentAdapter]],
    entry_point: Optional[str] = None,
) -> WorkflowBuilder:
    """Create a simple linear workflow.

    Args:
        name: Workflow name.
        nodes: List of (node_name, adapter) tuples.
        entry_point: Optional explicit entry point.

    Returns:
        Configured WorkflowBuilder.
    """
    if not nodes:
        raise ValueError("At least one node required")

    builder = WorkflowBuilder(name)

    # Add all nodes
    for node_name, adapter in nodes:
        builder.add_node(node_name, adapter)

    # Add sequential edges
    for i in range(len(nodes) - 1):
        builder.add_edge(nodes[i][0], nodes[i + 1][0])

    # Add final edge
    builder.add_edge(nodes[-1][0], END)

    # Set entry point
    builder.set_entry_point(entry_point or nodes[0][0])

    return builder
