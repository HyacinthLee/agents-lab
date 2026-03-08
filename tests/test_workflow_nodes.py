"""Tests for workflow nodes."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from acf.adapter.base import AgentResult, AgentStatus
from acf.workflow.nodes import (
    AgentNode,
    ConditionalNode,
    NodeConfig,
    NodeExecutionError,
)
from acf.workflow.state import AgentState, WorkflowStatus


class TestAgentNode:
    """Test AgentNode functionality."""

    @pytest.fixture
    def mock_adapter(self):
        """Create mock adapter."""
        adapter = MagicMock()
        adapter.name = "test_adapter"
        adapter.status = AgentStatus.IDLE
        adapter.execute = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_adapter):
        """Test successful node execution."""
        mock_adapter.execute.return_value = AgentResult(
            status=AgentStatus.COMPLETED,
            output="Hello, world!",
            metadata={},
        )

        config = NodeConfig(name="test_node", adapter=mock_adapter)
        node = AgentNode(config)

        state = AgentState({
            "messages": [{"role": "user", "content": "Say hello"}],
            "context": {},
            "workflow_status": WorkflowStatus.PENDING,
        })

        result = await node.execute(state)

        assert result["current_node"] == "test_node"
        assert result["workflow_status"] == WorkflowStatus.RUNNING
        assert len(result["messages"]) == 2
        assert result["messages"][1]["role"] == "assistant"
        assert result["messages"][1]["content"] == "Hello, world!"
        assert result["context"]["test_node_output"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_execute_with_system_prompt(self, mock_adapter):
        """Test execution with system prompt."""
        mock_adapter.execute.return_value = AgentResult(
            status=AgentStatus.COMPLETED,
            output="Result",
        )

        config = NodeConfig(
            name="test_node",
            adapter=mock_adapter,
            system_prompt="You are a helpful assistant.",
        )
        node = AgentNode(config)

        state = AgentState({
            "messages": [{"role": "user", "content": "Hello"}],
            "context": {},
            "workflow_status": WorkflowStatus.PENDING,
        })

        await node.execute(state)

        # Check that system prompt was prepended
        call_args = mock_adapter.execute.call_args
        prompt = call_args[0][0]
        assert "You are a helpful assistant." in prompt
        assert "Hello" in prompt

    @pytest.mark.asyncio
    async def test_execute_error(self, mock_adapter):
        """Test node execution with error."""
        mock_adapter.execute.return_value = AgentResult(
            status=AgentStatus.ERROR,
            output="",
            error="Something went wrong",
        )

        config = NodeConfig(name="test_node", adapter=mock_adapter, retry_count=1)
        node = AgentNode(config)

        state = AgentState({
            "messages": [{"role": "user", "content": "Hello"}],
            "context": {},
            "workflow_status": WorkflowStatus.PENDING,
        })

        result = await node.execute(state)

        assert result["workflow_status"] == WorkflowStatus.ERROR
        assert result["error"]["node"] == "test_node"
        # After all retries exhausted, the error message is about retry exhaustion
        assert "failed after" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_execute_empty_prompt(self, mock_adapter):
        """Test execution with empty prompt."""
        config = NodeConfig(name="test_node", adapter=mock_adapter)
        node = AgentNode(config)

        state = AgentState({
            "messages": [],
            "context": {},
            "workflow_status": WorkflowStatus.PENDING,
        })

        result = await node.execute(state)

        assert result["workflow_status"] == WorkflowStatus.ERROR
        assert "Empty prompt" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_execute_with_retry(self, mock_adapter):
        """Test retry logic on failure."""
        mock_adapter.execute.side_effect = [
            AgentResult(status=AgentStatus.ERROR, error="Error 1"),
            AgentResult(status=AgentStatus.ERROR, error="Error 2"),
            AgentResult(status=AgentStatus.COMPLETED, output="Success"),
        ]

        config = NodeConfig(
            name="test_node",
            adapter=mock_adapter,
            retry_count=3,
            retry_delay=0.01,  # Fast retry for testing
        )
        node = AgentNode(config)

        state = AgentState({
            "messages": [{"role": "user", "content": "Hello"}],
            "context": {},
            "workflow_status": WorkflowStatus.PENDING,
        })

        result = await node.execute(state)

        assert result["workflow_status"] == WorkflowStatus.RUNNING
        assert mock_adapter.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_timeout(self, mock_adapter):
        """Test timeout handling."""
        import asyncio

        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(10)
            return AgentResult(status=AgentStatus.COMPLETED, output="Done")

        mock_adapter.execute.side_effect = slow_execute

        config = NodeConfig(
            name="test_node",
            adapter=mock_adapter,
            timeout=0.01,  # Very short timeout
            retry_count=1,
        )
        node = AgentNode(config)

        state = AgentState({
            "messages": [{"role": "user", "content": "Hello"}],
            "context": {},
            "workflow_status": WorkflowStatus.PENDING,
        })

        result = await node.execute(state)

        assert result["workflow_status"] == WorkflowStatus.ERROR
        # After retry exhaustion, the error is about failing after retries
        assert "failed after" in result["error"]["message"].lower()

    def test_get_stats(self, mock_adapter):
        """Test getting node statistics."""
        config = NodeConfig(name="test_node", adapter=mock_adapter)
        node = AgentNode(config)

        stats = node.get_stats()

        assert stats["name"] == "test_node"
        assert stats["execution_count"] == 0
        assert stats["error_count"] == 0
        assert stats["adapter_name"] == "test_adapter"

    def test_reset_stats(self, mock_adapter):
        """Test resetting statistics."""
        config = NodeConfig(name="test_node", adapter=mock_adapter)
        node = AgentNode(config)

        # Manually increment counters
        node._execution_count = 5
        node._error_count = 2

        node.reset_stats()

        assert node._execution_count == 0
        assert node._error_count == 0


class TestConditionalNode:
    """Test ConditionalNode functionality."""

    def test_execute_valid_branch(self):
        """Test conditional with valid branch."""
        def condition(state):
            return "success" if state.get("success") else "failure"

        node = ConditionalNode(
            name="branch",
            condition=condition,
            branches={"success": "node_a", "failure": "node_b"},
        )

        state_success = AgentState({"success": True})
        state_failure = AgentState({"success": False})

        assert node.execute(state_success) == "node_a"
        assert node.execute(state_failure) == "node_b"

    def test_execute_default_branch(self):
        """Test conditional with default branch."""
        def condition(state):
            return "unknown"

        node = ConditionalNode(
            name="branch",
            condition=condition,
            branches={"a": "node_a"},
            default_branch="node_default",
        )

        state = AgentState({})
        assert node.execute(state) == "node_default"

    def test_execute_unknown_no_default(self):
        """Test conditional with unknown branch and no default."""
        def condition(state):
            return "unknown"

        node = ConditionalNode(
            name="branch",
            condition=condition,
            branches={"a": "node_a"},
        )

        state = AgentState({})
        with pytest.raises(NodeExecutionError):
            node.execute(state)
