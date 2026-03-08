"""Tests for workflow runner."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from acf.workflow.runner import (
    WorkflowRunner,
    WorkflowResult,
    WorkflowEvent,
    WorkflowEventType,
)
from acf.workflow.state import AgentState, WorkflowStatus, CheckpointData


class TestWorkflowRunner:
    """Test WorkflowRunner functionality."""

    @pytest.fixture
    def mock_graph(self):
        """Create mock compiled graph."""
        from langgraph.graph.state import CompiledStateGraph
        graph = MagicMock(spec=CompiledStateGraph)
        return graph

    @pytest.fixture
    def runner(self, mock_graph):
        """Create workflow runner."""
        return WorkflowRunner(mock_graph, workflow_id="test_workflow")

    @pytest.mark.asyncio
    async def test_run_success(self, mock_graph):
        """Test successful workflow run."""
        # Create a proper async generator mock - LangGraph returns dict format
        final_state = AgentState({
            "messages": [{"role": "assistant", "content": "Result"}],
            "workflow_status": WorkflowStatus.COMPLETED,
        })

        async def mock_astream(*args, **kwargs):
            yield {"node1": {"messages": [{"role": "assistant", "content": "Result"}]}}

        mock_graph.astream = mock_astream

        runner = WorkflowRunner(mock_graph)
        result = await runner.run("Hello")

        assert isinstance(result, WorkflowResult)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.success
        assert result.get_output() == "Result"

    @pytest.mark.asyncio
    async def test_run_with_error(self, mock_graph):
        """Test workflow run with error."""
        async def mock_astream(*args, **kwargs):
            yield {"node1": {"error": {"message": "Something went wrong"}}}

        mock_graph.astream = mock_astream

        runner = WorkflowRunner(mock_graph)
        result = await runner.run("Hello")

        assert result.status == WorkflowStatus.ERROR
        assert not result.success
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_run_already_running(self, mock_graph):
        """Test running when already running fails."""
        runner = WorkflowRunner(mock_graph)
        runner._is_running = True

        with pytest.raises(RuntimeError, match="already running"):
            await runner.run("Hello")

    @pytest.mark.asyncio
    async def test_run_from_checkpoint(self, mock_graph):
        """Test resuming from checkpoint."""
        checkpoint_state = AgentState({
            "messages": [{"role": "user", "content": "Previous"}],
            "workflow_status": WorkflowStatus.PENDING,
        })

        # Create mock checkpoint saver with all async methods
        mock_saver = MagicMock()
        mock_saver.load = AsyncMock(return_value=CheckpointData(
            checkpoint_id="cp_123",
            state=dict(checkpoint_state),
        ))
        mock_saver.save = AsyncMock()

        async def mock_astream(*args, **kwargs):
            yield {"node1": {"messages": [{"role": "assistant", "content": "Result"}]}}

        mock_graph.astream = mock_astream

        runner = WorkflowRunner(mock_graph, checkpoint_saver=mock_saver)
        result = await runner.run("", checkpoint_id="cp_123")

        mock_saver.load.assert_called_once_with("cp_123")
        assert result.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_checkpoint_not_found(self, mock_graph):
        """Test error when checkpoint not found."""
        mock_saver = MagicMock()
        mock_saver.load = AsyncMock(return_value=None)
        mock_saver.save = AsyncMock()

        runner = WorkflowRunner(mock_graph, checkpoint_saver=mock_saver)

        # The checkpoint not found error is caught and wrapped in a result
        result = await runner.run("", checkpoint_id="nonexistent")
        assert result.status == WorkflowStatus.ERROR
        assert "Checkpoint not found" in result.error["message"]

    def test_run_sync(self, mock_graph):
        """Test synchronous run."""
        async def mock_astream(*args, **kwargs):
            yield {"node1": {"messages": [{"role": "assistant", "content": "Result"}]}}

        mock_graph.astream = mock_astream

        runner = WorkflowRunner(mock_graph)
        result = runner.run_sync("Hello")

        assert isinstance(result, WorkflowResult)
        assert result.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_stream(self, mock_graph):
        """Test streaming workflow execution."""
        async def mock_astream(*args, **kwargs):
            yield {"node1": {"messages": [{"role": "assistant", "content": "Result"}]}}

        mock_graph.astream = mock_astream

        runner = WorkflowRunner(mock_graph)
        events = []
        async for event in runner.stream("Hello"):
            events.append(event)

        assert len(events) > 0
        assert events[0].event_type == WorkflowEventType.STARTED
        assert events[-1].event_type == WorkflowEventType.COMPLETED

    def test_add_callback(self, runner):
        """Test adding event callback."""
        def callback(event):
            pass

        runner.add_callback(callback)
        assert callback in runner._callbacks

    def test_add_async_callback(self, runner):
        """Test adding async event callback."""
        async def callback(event):
            pass

        runner.add_async_callback(callback)
        assert callback in runner._async_callbacks

    def test_remove_callback(self, runner):
        """Test removing callback."""
        def callback(event):
            pass

        runner.add_callback(callback)
        assert runner.remove_callback(callback) is True
        assert runner.remove_callback(callback) is False

    def test_cancel(self, runner):
        """Test workflow cancellation."""
        runner._is_running = True
        runner.cancel()
        assert runner._cancelled is True

    def test_is_running(self, runner):
        """Test is_running property."""
        assert not runner.is_running
        runner._is_running = True
        assert runner.is_running

    def test_get_stats(self, runner):
        """Test getting runner statistics."""
        stats = runner.get_stats()
        assert stats["workflow_id"] == "test_workflow"
        assert stats["execution_count"] == 0
        assert stats["is_running"] is False


class TestWorkflowResult:
    """Test WorkflowResult functionality."""

    def test_success_property(self):
        """Test success property."""
        success_result = WorkflowResult(
            status=WorkflowStatus.COMPLETED,
            state=AgentState({}),
            execution_time=1.0,
            node_count=2,
        )
        assert success_result.success

        error_result = WorkflowResult(
            status=WorkflowStatus.ERROR,
            state=AgentState({"error": {"message": "Error"}}),
            execution_time=1.0,
            node_count=1,
            error={"message": "Error"},
        )
        assert not error_result.success

    def test_get_output(self):
        """Test getting output from result."""
        result = WorkflowResult(
            status=WorkflowStatus.COMPLETED,
            state=AgentState({
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "World"},
                ],
            }),
            execution_time=1.0,
            node_count=1,
        )
        assert result.get_output() == "World"

    def test_get_output_empty(self):
        """Test getting output with no messages."""
        result = WorkflowResult(
            status=WorkflowStatus.COMPLETED,
            state=AgentState({"messages": []}),
            execution_time=1.0,
            node_count=0,
        )
        assert result.get_output() == ""


class TestWorkflowEvent:
    """Test WorkflowEvent functionality."""

    def test_to_dict(self):
        """Test event serialization."""
        # Use a fixed timestamp to avoid event loop issues
        event = WorkflowEvent(
            event_type=WorkflowEventType.STARTED,
            workflow_id="wf_1",
            node_name="node1",
            data={"key": "value"},
            timestamp=1234567890.0,
        )

        data = event.to_dict()
        assert data["event_type"] == "STARTED"
        assert data["workflow_id"] == "wf_1"
        assert data["node_name"] == "node1"
        assert data["data"] == {"key": "value"}
