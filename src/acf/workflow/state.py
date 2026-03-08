"""State management for ACF v2.0 workflows.

This module defines the AgentState structure and provides checkpointing
and long-term memory integration for LangGraph workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict
import json
import time


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class AgentState(TypedDict, total=False):
    """State structure for LangGraph workflows.

    This TypedDict defines the standard state structure used across
    ACF workflows. It includes messages, metadata, and execution context.

    Attributes:
        messages: List of conversation messages.
        current_node: Currently executing node name.
        workflow_status: Current workflow execution status.
        context: Shared context data between nodes.
        metadata: Additional workflow metadata.
        error: Error information if workflow failed.
        checkpoint_id: Unique identifier for checkpoint recovery.
        memory: Long-term memory access data.
    """

    messages: List[Dict[str, Any]]
    current_node: str
    workflow_status: str
    context: Dict[str, Any]
    metadata: Dict[str, Any]
    error: Optional[Dict[str, Any]]
    checkpoint_key: Optional[str]
    memory: Dict[str, Any]


@dataclass
class CheckpointData:
    """Data structure for workflow checkpoints.

    Checkpoints allow workflows to be paused and resumed, enabling
    fault tolerance and human-in-the-loop interactions.

    Attributes:
        checkpoint_id: Unique identifier for this checkpoint.
        state: Serialized state at checkpoint time.
        created_at: Timestamp when checkpoint was created.
        node_name: Name of the node that created this checkpoint.
        metadata: Additional checkpoint metadata.
    """

    checkpoint_id: str
    state: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    node_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "state": self.state,
            "created_at": self.created_at,
            "node_name": self.node_name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CheckpointData:
        """Create checkpoint from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            state=data["state"],
            created_at=data.get("created_at", time.time()),
            node_name=data.get("node_name", ""),
            metadata=data.get("metadata", {}),
        )


class CheckpointSaver:
    """Base class for checkpoint persistence.

    This class defines the interface for checkpoint storage backends.
    Implementations can provide file-based, database, or remote storage.
    """

    async def save(self, checkpoint: CheckpointData) -> None:
        """Save a checkpoint.

        Args:
            checkpoint: Checkpoint data to save.
        """
        raise NotImplementedError

    async def load(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Load a checkpoint by ID.

        Args:
            checkpoint_id: Unique checkpoint identifier.

        Returns:
            Checkpoint data if found, None otherwise.
        """
        raise NotImplementedError

    async def list_checkpoints(self, workflow_id: Optional[str] = None) -> List[CheckpointData]:
        """List available checkpoints.

        Args:
            workflow_id: Optional workflow filter.

        Returns:
            List of checkpoint data.
        """
        raise NotImplementedError

    async def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint to delete.

        Returns:
            True if deleted, False if not found.
        """
        raise NotImplementedError


class MemoryStore:
    """Base class for long-term memory storage.

    Memory stores provide persistent storage for workflow data that
    needs to survive across executions.
    """

    async def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """Retrieve a value from memory.

        Args:
            key: Memory key.
            namespace: Optional namespace for isolation.

        Returns:
            Stored value or None if not found.
        """
        raise NotImplementedError

    async def set(
        self,
        key: str,
        value: Any,
        namespace: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Store a value in memory.

        Args:
            key: Memory key.
            value: Value to store.
            namespace: Optional namespace for isolation.
            ttl: Optional time-to-live in seconds.
        """
        raise NotImplementedError

    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete a value from memory.

        Args:
            key: Memory key.
            namespace: Optional namespace.

        Returns:
            True if deleted, False if not found.
        """
        raise NotImplementedError

    async def list_keys(self, namespace: Optional[str] = None) -> List[str]:
        """List all keys in a namespace.

        Args:
            namespace: Optional namespace filter.

        Returns:
            List of keys.
        """
        raise NotImplementedError


class InMemoryCheckpointSaver(CheckpointSaver):
    """In-memory checkpoint storage for testing and development."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._checkpoints: Dict[str, CheckpointData] = {}

    async def save(self, checkpoint: CheckpointData) -> None:
        """Save checkpoint to memory."""
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint

    async def load(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Load checkpoint from memory."""
        return self._checkpoints.get(checkpoint_id)

    async def list_checkpoints(self, workflow_id: Optional[str] = None) -> List[CheckpointData]:
        """List all checkpoints in memory."""
        checkpoints = list(self._checkpoints.values())
        if workflow_id:
            checkpoints = [
                cp for cp in checkpoints
                if cp.metadata.get("workflow_id") == workflow_id
            ]
        return checkpoints

    async def delete(self, checkpoint_id: str) -> bool:
        """Delete checkpoint from memory."""
        if checkpoint_id in self._checkpoints:
            del self._checkpoints[checkpoint_id]
            return True
        return False


class InMemoryMemoryStore(MemoryStore):
    """In-memory memory store for testing and development."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._store: Dict[str, Dict[str, Any]] = {}
        self._ttl: Dict[str, float] = {}

    def _make_key(self, key: str, namespace: Optional[str]) -> str:
        """Create namespaced key."""
        if namespace:
            return f"{namespace}:{key}"
        return key

    async def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """Retrieve value from memory."""
        full_key = self._make_key(key, namespace)

        # Check TTL
        if full_key in self._ttl:
            if time.time() > self._ttl[full_key]:
                self._store.pop(full_key, None)
                self._ttl.pop(full_key, None)
                return None

        return self._store.get(full_key)

    async def set(
        self,
        key: str,
        value: Any,
        namespace: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Store value in memory."""
        full_key = self._make_key(key, namespace)
        self._store[full_key] = value

        if ttl:
            self._ttl[full_key] = time.time() + ttl

    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete value from memory."""
        full_key = self._make_key(key, namespace)
        if full_key in self._store:
            del self._store[full_key]
            self._ttl.pop(full_key, None)
            return True
        return False

    async def list_keys(self, namespace: Optional[str] = None) -> List[str]:
        """List all keys in namespace."""
        keys = []
        prefix = f"{namespace}:" if namespace else ""
        for key in self._store.keys():
            if key.startswith(prefix):
                keys.append(key[len(prefix):] if prefix else key)
        return keys


def create_initial_state(
    messages: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentState:
    """Create initial workflow state.

    Args:
        messages: Initial conversation messages.
        context: Initial context data.
        metadata: Workflow metadata.

    Returns:
        Initialized AgentState.
    """
    return AgentState(
        messages=messages or [],
        current_node="",
        workflow_status=WorkflowStatus.PENDING,
        context=context or {},
        metadata=metadata or {},
        error=None,
        checkpoint_key=None,
        memory={},
    )


def update_state(
    state: AgentState,
    updates: Dict[str, Any],
) -> AgentState:
    """Update state with new values.

    Args:
        state: Current state.
        updates: Dictionary of updates to apply.

    Returns:
        Updated state.
    """
    new_state = dict(state)
    new_state.update(updates)
    return AgentState(**new_state)
