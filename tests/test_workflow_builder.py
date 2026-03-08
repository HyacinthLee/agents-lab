"""Tests for workflow builder."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph

from acf.adapter.base import AgentAdapter, AgentStatus
from acf.workflow.builder import WorkflowBuilder, create_simple_workflow
from acf.workflow.nodes import AgentNode
from acf.workflow.state import AgentState


class TestWorkflowBuilder:
    """Test WorkflowBuilder functionality."""

    @pytest.fixture
    def mock_adapter(self):
        """Create mock adapter."""
        adapter = MagicMock(spec=AgentAdapter)
        adapter.name = "test_adapter"
        adapter.status = AgentStatus.IDLE
        return adapter

    def test_init(self):
        """Test builder initialization."""
        builder = WorkflowBuilder("test_workflow", "Test description")
        assert builder.name == "test_workflow"
        assert builder.description == "Test description"
        assert not builder._compiled

    def test_add_node(self, mock_adapter):
        """Test adding nodes."""
        builder = WorkflowBuilder("test")
        result = builder.add_node("node1", mock_adapter)

        assert result is builder  # Method chaining
        assert "node1" in builder._nodes
        assert isinstance(builder._nodes["node1"], AgentNode)

    def test_add_node_compiled(self, mock_adapter):
        """Test adding node to compiled workflow fails."""
        builder = WorkflowBuilder("test")
        builder._compiled = True

        with pytest.raises(RuntimeError, match="Cannot modify compiled workflow"):
            builder.add_node("node1", mock_adapter)

    def test_add_edge(self, mock_adapter):
        """Test adding edges."""
        builder = WorkflowBuilder("test")
        builder.add_node("node1", mock_adapter)
        builder.add_node("node2", mock_adapter)

        result = builder.add_edge("node1", "node2")
        assert result is builder  # Method chaining

    def test_set_entry_point(self, mock_adapter):
        """Test setting entry point."""
        builder = WorkflowBuilder("test")
        builder.add_node("node1", mock_adapter)

        result = builder.set_entry_point("node1")
        assert result is builder
        assert builder._entry_point == "node1"

    def test_compile_success(self, mock_adapter):
        """Test successful compilation."""
        builder = WorkflowBuilder("test")
        builder.add_node("node1", mock_adapter)
        builder.add_edge("node1", END)
        builder.set_entry_point("node1")

        graph = builder.compile()
        assert graph is not None
        assert builder._compiled

    def test_compile_no_entry_point(self, mock_adapter):
        """Test compilation without entry point fails."""
        builder = WorkflowBuilder("test")
        builder.add_node("node1", mock_adapter)

        with pytest.raises(RuntimeError, match="Entry point not set"):
            builder.compile()

    def test_compile_no_nodes(self):
        """Test compilation without nodes fails."""
        builder = WorkflowBuilder("test")
        builder.set_entry_point("node1")

        with pytest.raises(RuntimeError, match="No nodes added"):
            builder.compile()

    def test_get_node(self, mock_adapter):
        """Test getting node by name."""
        builder = WorkflowBuilder("test")
        builder.add_node("node1", mock_adapter)

        node = builder.get_node("node1")
        assert node is not None
        assert node.name == "node1"

        missing = builder.get_node("nonexistent")
        assert missing is None

    def test_get_nodes(self, mock_adapter):
        """Test getting all nodes."""
        builder = WorkflowBuilder("test")
        builder.add_node("node1", mock_adapter)
        builder.add_node("node2", mock_adapter)

        nodes = builder.get_nodes()
        assert len(nodes) == 2
        assert "node1" in nodes
        assert "node2" in nodes

    def test_add_conditional_edges(self, mock_adapter):
        """Test adding conditional edges."""
        builder = WorkflowBuilder("test")
        builder.add_node("node1", mock_adapter)
        builder.add_node("node_a", mock_adapter)
        builder.add_node("node_b", mock_adapter)

        def condition(state):
            return "a" if state.get("go_a") else "b"

        result = builder.add_conditional_edges(
            "node1",
            condition,
            {"a": "node_a", "b": "node_b"},
        )

        assert result is builder
        assert "node1" in builder._conditional_nodes


class TestCreateSimpleWorkflow:
    """Test create_simple_workflow helper."""

    @pytest.fixture
    def mock_adapter(self):
        """Create mock adapter."""
        adapter = MagicMock(spec=AgentAdapter)
        adapter.name = "test_adapter"
        adapter.status = AgentStatus.IDLE
        return adapter

    def test_create_linear_workflow(self, mock_adapter):
        """Test creating simple linear workflow."""
        adapter1 = MagicMock(spec=AgentAdapter)
        adapter1.name = "adapter1"
        adapter1.status = AgentStatus.IDLE

        adapter2 = MagicMock(spec=AgentAdapter)
        adapter2.name = "adapter2"
        adapter2.status = AgentStatus.IDLE

        builder = create_simple_workflow(
            "linear",
            [("node1", adapter1), ("node2", adapter2)],
        )

        assert builder.name == "linear"
        assert len(builder._nodes) == 2
        assert builder._entry_point == "node1"

    def test_create_empty_workflow_fails(self):
        """Test creating workflow with no nodes fails."""
        with pytest.raises(ValueError, match="At least one node required"):
            create_simple_workflow("empty", [])

    def test_create_single_node_workflow(self, mock_adapter):
        """Test creating single node workflow."""
        builder = create_simple_workflow("single", [("node1", mock_adapter)])

        assert len(builder._nodes) == 1
        assert builder._entry_point == "node1"


class TestWorkflowBuilderFromYaml:
    """Test YAML configuration loading."""

    def test_from_yaml_not_installed(self):
        """Test error when PyYAML not installed."""
        with patch("acf.workflow.builder.YAML_AVAILABLE", False):
            with pytest.raises(ImportError, match="PyYAML is required"):
                WorkflowBuilder.from_yaml("config.yaml")

    def test_from_yaml_file_not_found(self):
        """Test error when YAML file not found."""
        with patch("acf.workflow.builder.YAML_AVAILABLE", True):
            with pytest.raises(FileNotFoundError):
                WorkflowBuilder.from_yaml("/nonexistent/config.yaml")

    @pytest.mark.skip(reason="Requires PyYAML and proper mocking")
    def test_from_yaml_success(self):
        """Test loading workflow from YAML."""
        # This would require more extensive mocking
        pass
