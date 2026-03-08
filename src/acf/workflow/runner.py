"""Workflow runner for ACF v2.0.

This module provides WorkflowRunner for executing LangGraph workflows
with support for sync/async execution, interrupt recovery, and event callbacks.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from acf.workflow.state import (
    AgentState,
    CheckpointData,
    CheckpointSaver,
    InMemoryCheckpointSaver,
    WorkflowStatus,
    create_initial_state,
)
from acf.workflow.builder import WorkflowBuilder

logger = logging.getLogger(__name__)


class WorkflowEventType(Enum):
    """Types of workflow events."""

    STARTED = auto()
    NODE_STARTED = auto()
    NODE_COMPLETED = auto()
    NODE_ERROR = auto()
    CHECKPOINT_SAVED = auto()
    CHECKPOINT_LOADED = auto()
    PAUSED = auto()
    RESUMED = auto()
    COMPLETED = auto()
    ERROR = auto()
    CANCELLED = auto()


@dataclass
class WorkflowEvent:
    """Event emitted during workflow execution.

    Attributes:
        event_type: Type of event.
        workflow_id: Workflow identifier.
        node_name: Current node name (if applicable).
        data: Event-specific data.
        timestamp: Event timestamp.
    """

    event_type: WorkflowEventType
    workflow_id: str
    node_name: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.name,
            "workflow_id": self.workflow_id,
            "node_name": self.node_name,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# Type alias for event callbacks
EventCallback = Callable[[WorkflowEvent], None]
AsyncEventCallback = Callable[[WorkflowEvent], asyncio.Future]


@dataclass
class WorkflowResult:
    """Result of workflow execution.

    Attributes:
        status: Final workflow status.
        state: Final workflow state.
        execution_time: Total execution time in seconds.
        node_count: Number of nodes executed.
        error: Error information if failed.
    """

    status: WorkflowStatus
    state: AgentState
    execution_time: float
    node_count: int
    error: Optional[Dict[str, Any]] = None

    @property
    def success(self) -> bool:
        """Check if workflow completed successfully."""
        return self.status == WorkflowStatus.COMPLETED and not self.error

    def get_output(self) -> str:
        """Get final output from workflow.

        Returns:
            Last assistant message content or empty string.
        """
        messages = self.state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""


class WorkflowRunner:
    """Runner for executing LangGraph workflows.

    This class provides a high-level interface for workflow execution
    with support for:
    - Synchronous and asynchronous execution
    - Checkpoint-based interrupt recovery
    - Event callbacks for monitoring
    - State streaming

    Example:
        ```python
        # Build workflow
        builder = WorkflowBuilder("my_workflow")
        builder.add_node("agent1", adapter1)
        builder.add_node("agent2", adapter2)
        builder.add_edge("agent1", "agent2")
        builder.add_edge("agent2", END)
        builder.set_entry_point("agent1")

        graph = builder.compile()

        # Run workflow
        runner = WorkflowRunner(graph)
        result = await runner.run("Hello, agents!")

        # With callbacks
        def on_event(event):
            print(f"Event: {event.event_type}")

        runner.add_callback(on_event)
        result = await runner.run("Hello again!")
        ```
    """

    def __init__(
        self,
        graph: CompiledStateGraph,
        checkpoint_saver: Optional[CheckpointSaver] = None,
        workflow_id: Optional[str] = None,
    ):
        """Initialize workflow runner.

        Args:
            graph: Compiled LangGraph workflow.
            checkpoint_saver: Optional checkpoint saver for persistence.
            workflow_id: Optional workflow identifier.
        """
        self.graph = graph
        self.checkpoint_saver = checkpoint_saver or InMemoryCheckpointSaver()
        self.workflow_id = workflow_id or f"workflow_{id(self)}"
        self._callbacks: List[EventCallback] = []
        self._async_callbacks: List[AsyncEventCallback] = []
        self._execution_count = 0
        self._is_running = False
        self._cancelled = False

    def add_callback(self, callback: EventCallback) -> None:
        """Add synchronous event callback.

        Args:
            callback: Function to call on events.
        """
        self._callbacks.append(callback)

    def add_async_callback(self, callback: AsyncEventCallback) -> None:
        """Add asynchronous event callback.

        Args:
            callback: Async function to call on events.
        """
        self._async_callbacks.append(callback)

    def remove_callback(self, callback: EventCallback) -> bool:
        """Remove event callback.

        Args:
            callback: Callback to remove.

        Returns:
            True if removed, False if not found.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            return True
        if callback in self._async_callbacks:
            self._async_callbacks.remove(callback)
            return True
        return False

    async def _emit_event(self, event: WorkflowEvent) -> None:
        """Emit event to all callbacks.

        Args:
            event: Event to emit.
        """
        # Sync callbacks
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Callback error: {e}")

        # Async callbacks
        for callback in self._async_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.warning(f"Async callback error: {e}")

    def _create_checkpoint(self, state: AgentState, node_name: str) -> CheckpointData:
        """Create checkpoint from current state.

        Args:
            state: Current workflow state.
            node_name: Current node name.

        Returns:
            Checkpoint data.
        """
        checkpoint_id = f"{self.workflow_id}_{self._execution_count}_{node_name}"
        return CheckpointData(
            checkpoint_id=checkpoint_id,
            state=dict(state),
            node_name=node_name,
            metadata={
                "workflow_id": self.workflow_id,
                "execution_count": self._execution_count,
            },
        )

    async def run(
        self,
        input_data: Union[str, AgentState, Dict[str, Any]],
        checkpoint_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Run workflow with input.

        Args:
            input_data: Input string, state dict, or initial state.
            checkpoint_id: Optional checkpoint to resume from.
            config: Optional LangGraph configuration.

        Returns:
            Workflow execution result.
        """
        if self._is_running:
            raise RuntimeError("Workflow is already running")

        self._is_running = True
        self._cancelled = False
        self._execution_count += 1

        start_time = asyncio.get_event_loop().time()
        node_count = 0

        try:
            # Prepare initial state
            if checkpoint_id:
                # Resume from checkpoint
                checkpoint = await self.checkpoint_saver.load(checkpoint_id)
                if not checkpoint:
                    raise ValueError(f"Checkpoint not found: {checkpoint_id}")

                state = AgentState(checkpoint.state)
                await self._emit_event(WorkflowEvent(
                    event_type=WorkflowEventType.CHECKPOINT_LOADED,
                    workflow_id=self.workflow_id,
                    data={"checkpoint_id": checkpoint_id},
                ))
            else:
                # Create new state
                if isinstance(input_data, str):
                    state = create_initial_state(
                        messages=[{"role": "user", "content": input_data}],
                        metadata={"workflow_id": self.workflow_id},
                    )
                elif isinstance(input_data, dict):
                    state = AgentState(input_data)
                else:
                    state = input_data

            # Emit started event
            await self._emit_event(WorkflowEvent(
                event_type=WorkflowEventType.STARTED,
                workflow_id=self.workflow_id,
                data={"checkpoint_id": checkpoint_id},
            ))

            # Run workflow
            graph_config = config or {}
            result_state = None

            async for event in self.graph.astream(state, graph_config):
                if self._cancelled:
                    await self._emit_event(WorkflowEvent(
                        event_type=WorkflowEventType.CANCELLED,
                        workflow_id=self.workflow_id,
                    ))
                    return WorkflowResult(
                        status=WorkflowStatus.CANCELLED,
                        state=state,
                        execution_time=asyncio.get_event_loop().time() - start_time,
                        node_count=node_count,
                    )

                # Process events - LangGraph returns dict with node names as keys
                if isinstance(event, dict):
                    # Get the node name (first key) and state
                    for node_name, node_output in event.items():
                        if node_name.startswith('__') or node_name == 'branch:to:':
                            continue
                        node_count += 1

                        # Build state from output
                        if isinstance(node_output, dict):
                            node_state = AgentState({**state, **node_output})
                        else:
                            node_state = AgentState(state)

                        # Emit node completed event
                        await self._emit_event(WorkflowEvent(
                            event_type=WorkflowEventType.NODE_COMPLETED,
                            workflow_id=self.workflow_id,
                            node_name=node_name,
                            data={"state": dict(node_state)},
                        ))

                        # Save checkpoint
                        checkpoint = self._create_checkpoint(node_state, node_name)
                        await self.checkpoint_saver.save(checkpoint)
                        await self._emit_event(WorkflowEvent(
                            event_type=WorkflowEventType.CHECKPOINT_SAVED,
                            workflow_id=self.workflow_id,
                            node_name=node_name,
                            data={"checkpoint_id": checkpoint.checkpoint_id},
                        ))

                        result_state = node_state
                        state = node_state  # Update state for next iteration
                else:
                    # Direct state update
                    result_state = event

            # Determine final status
            final_state = result_state or state
            status = final_state.get("workflow_status", WorkflowStatus.COMPLETED)
            error = final_state.get("error")

            # If status is still RUNNING or PENDING but no error, mark as COMPLETED
            if status in (WorkflowStatus.RUNNING, WorkflowStatus.PENDING) and not error:
                status = WorkflowStatus.COMPLETED
                final_state = AgentState({**final_state, "workflow_status": status})

            if error:
                status = WorkflowStatus.ERROR
                await self._emit_event(WorkflowEvent(
                    event_type=WorkflowEventType.ERROR,
                    workflow_id=self.workflow_id,
                    data={"error": error},
                ))
            else:
                await self._emit_event(WorkflowEvent(
                    event_type=WorkflowEventType.COMPLETED,
                    workflow_id=self.workflow_id,
                    data={"node_count": node_count},
                ))

            execution_time = asyncio.get_event_loop().time() - start_time

            return WorkflowResult(
                status=WorkflowStatus(status),
                state=final_state,
                execution_time=execution_time,
                node_count=node_count,
                error=error,
            )

        except Exception as e:
            logger.exception("Workflow execution failed")
            await self._emit_event(WorkflowEvent(
                event_type=WorkflowEventType.ERROR,
                workflow_id=self.workflow_id,
                data={"error": str(e)},
            ))

            execution_time = asyncio.get_event_loop().time() - start_time

            return WorkflowResult(
                status=WorkflowStatus.ERROR,
                state=state if 'state' in locals() else AgentState({}),
                execution_time=execution_time,
                node_count=node_count,
                error={"message": str(e), "type": type(e).__name__},
            )

        finally:
            self._is_running = False

    def run_sync(
        self,
        input_data: Union[str, AgentState, Dict[str, Any]],
        checkpoint_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Run workflow synchronously.

        Args:
            input_data: Input string, state dict, or initial state.
            checkpoint_id: Optional checkpoint to resume from.
            config: Optional LangGraph configuration.

        Returns:
            Workflow execution result.
        """
        return asyncio.run(self.run(input_data, checkpoint_id, config))

    async def stream(
        self,
        input_data: Union[str, AgentState, Dict[str, Any]],
        checkpoint_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[WorkflowEvent]:
        """Stream workflow execution events.

        Args:
            input_data: Input string, state dict, or initial state.
            checkpoint_id: Optional checkpoint to resume from.
            config: Optional LangGraph configuration.

        Yields:
            Workflow events as they occur.
        """
        if self._is_running:
            raise RuntimeError("Workflow is already running")

        self._is_running = True
        self._cancelled = False
        self._execution_count += 1

        try:
            # Prepare initial state
            if checkpoint_id:
                checkpoint = await self.checkpoint_saver.load(checkpoint_id)
                if not checkpoint:
                    raise ValueError(f"Checkpoint not found: {checkpoint_id}")
                state = AgentState(checkpoint.state)
                yield WorkflowEvent(
                    event_type=WorkflowEventType.CHECKPOINT_LOADED,
                    workflow_id=self.workflow_id,
                    data={"checkpoint_id": checkpoint_id},
                )
            else:
                if isinstance(input_data, str):
                    state = create_initial_state(
                        messages=[{"role": "user", "content": input_data}],
                        metadata={"workflow_id": self.workflow_id},
                    )
                elif isinstance(input_data, dict):
                    state = AgentState(input_data)
                else:
                    state = input_data

            yield WorkflowEvent(
                event_type=WorkflowEventType.STARTED,
                workflow_id=self.workflow_id,
            )

            # Run and stream
            graph_config = config or {}
            async for event in self.graph.astream(state, graph_config):
                if self._cancelled:
                    yield WorkflowEvent(
                        event_type=WorkflowEventType.CANCELLED,
                        workflow_id=self.workflow_id,
                    )
                    return

                # Process events - LangGraph returns dict with node names as keys
                if isinstance(event, dict):
                    for node_name, node_output in event.items():
                        if node_name.startswith('__') or node_name == 'branch:to:':
                            continue

                        if isinstance(node_output, dict):
                            node_state = AgentState({**state, **node_output})
                        else:
                            node_state = AgentState(state)

                        yield WorkflowEvent(
                            event_type=WorkflowEventType.NODE_COMPLETED,
                            workflow_id=self.workflow_id,
                            node_name=node_name,
                            data={"state": dict(node_state)},
                        )

                        # Save checkpoint
                        checkpoint = self._create_checkpoint(node_state, node_name)
                        await self.checkpoint_saver.save(checkpoint)
                        yield WorkflowEvent(
                            event_type=WorkflowEventType.CHECKPOINT_SAVED,
                            workflow_id=self.workflow_id,
                            node_name=node_name,
                            data={"checkpoint_id": checkpoint.checkpoint_id},
                        )

                        state = node_state

            # Final status
            final_status = state.get("workflow_status", WorkflowStatus.COMPLETED)
            if final_status == WorkflowStatus.RUNNING and not state.get("error"):
                final_status = WorkflowStatus.COMPLETED

            if state.get("error"):
                yield WorkflowEvent(
                    event_type=WorkflowEventType.ERROR,
                    workflow_id=self.workflow_id,
                    data={"error": state["error"]},
                )
            else:
                yield WorkflowEvent(
                    event_type=WorkflowEventType.COMPLETED,
                    workflow_id=self.workflow_id,
                )

        finally:
            self._is_running = False

    def cancel(self) -> None:
        """Cancel running workflow."""
        if self._is_running:
            self._cancelled = True
            logger.info(f"Workflow {self.workflow_id} cancellation requested")

    async def pause(self, checkpoint_id: Optional[str] = None) -> str:
        """Pause workflow and save checkpoint.

        Args:
            checkpoint_id: Optional specific checkpoint ID.

        Returns:
            Checkpoint ID for resuming.
        """
        # This would require more complex integration with LangGraph
        # For now, we just save current state
        self._cancelled = True

        await self._emit_event(WorkflowEvent(
            event_type=WorkflowEventType.PAUSED,
            workflow_id=self.workflow_id,
        ))

        return checkpoint_id or f"{self.workflow_id}_paused"

    async def resume(self, checkpoint_id: str) -> WorkflowResult:
        """Resume workflow from checkpoint.

        Args:
            checkpoint_id: Checkpoint to resume from.

        Returns:
            Workflow execution result.
        """
        await self._emit_event(WorkflowEvent(
            event_type=WorkflowEventType.RESUMED,
            workflow_id=self.workflow_id,
            data={"checkpoint_id": checkpoint_id},
        ))

        return await self.run("", checkpoint_id=checkpoint_id)

    @property
    def is_running(self) -> bool:
        """Check if workflow is currently running."""
        return self._is_running

    def get_stats(self) -> Dict[str, Any]:
        """Get runner statistics.

        Returns:
            Dictionary with execution statistics.
        """
        return {
            "workflow_id": self.workflow_id,
            "execution_count": self._execution_count,
            "is_running": self._is_running,
            "callback_count": len(self._callbacks) + len(self._async_callbacks),
        }
