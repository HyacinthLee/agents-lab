"""Tests for workflow state management."""

import pytest
from acf.workflow.state import (
    AgentState,
    CheckpointData,
    InMemoryCheckpointSaver,
    InMemoryMemoryStore,
    WorkflowStatus,
    create_initial_state,
    update_state,
)


class TestAgentState:
    """Test AgentState structure."""

    def test_create_initial_state(self):
        """Test creating initial state."""
        state = create_initial_state(
            messages=[{"role": "user", "content": "Hello"}],
            context={"key": "value"},
            metadata={"workflow": "test"},
        )

        assert state["messages"] == [{"role": "user", "content": "Hello"}]
        assert state["context"] == {"key": "value"}
        assert state["metadata"] == {"workflow": "test"}
        assert state["workflow_status"] == WorkflowStatus.PENDING
        assert state["current_node"] == ""
        assert state["error"] is None

    def test_update_state(self):
        """Test updating state."""
        state = create_initial_state()
        updated = update_state(state, {"current_node": "node1", "workflow_status": WorkflowStatus.RUNNING})

        assert updated["current_node"] == "node1"
        assert updated["workflow_status"] == WorkflowStatus.RUNNING
        # Original state unchanged
        assert state["current_node"] == ""


class TestCheckpointData:
    """Test CheckpointData structure."""

    def test_to_dict(self):
        """Test checkpoint serialization."""
        checkpoint = CheckpointData(
            checkpoint_id="cp_123",
            state={"key": "value"},
            node_name="node1",
            metadata={"workflow_id": "wf_1"},
        )

        data = checkpoint.to_dict()
        assert data["checkpoint_id"] == "cp_123"
        assert data["state"] == {"key": "value"}
        assert data["node_name"] == "node1"

    def test_from_dict(self):
        """Test checkpoint deserialization."""
        data = {
            "checkpoint_id": "cp_123",
            "state": {"key": "value"},
            "created_at": 1234567890.0,
            "node_name": "node1",
            "metadata": {},
        }

        checkpoint = CheckpointData.from_dict(data)
        assert checkpoint.checkpoint_id == "cp_123"
        assert checkpoint.state == {"key": "value"}
        assert checkpoint.node_name == "node1"


class TestInMemoryCheckpointSaver:
    """Test in-memory checkpoint saver."""

    @pytest.mark.asyncio
    async def test_save_and_load(self):
        """Test saving and loading checkpoints."""
        saver = InMemoryCheckpointSaver()
        checkpoint = CheckpointData(
            checkpoint_id="cp_123",
            state={"messages": []},
            node_name="node1",
        )

        await saver.save(checkpoint)
        loaded = await saver.load("cp_123")

        assert loaded is not None
        assert loaded.checkpoint_id == "cp_123"
        assert loaded.node_name == "node1"

    @pytest.mark.asyncio
    async def test_load_not_found(self):
        """Test loading non-existent checkpoint."""
        saver = InMemoryCheckpointSaver()
        loaded = await saver.load("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting checkpoint."""
        saver = InMemoryCheckpointSaver()
        checkpoint = CheckpointData(checkpoint_id="cp_123", state={})

        await saver.save(checkpoint)
        assert await saver.delete("cp_123") is True
        assert await saver.load("cp_123") is None
        assert await saver.delete("cp_123") is False

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        """Test listing checkpoints."""
        saver = InMemoryCheckpointSaver()

        await saver.save(CheckpointData(checkpoint_id="cp_1", state={}, metadata={"workflow_id": "wf_1"}))
        await saver.save(CheckpointData(checkpoint_id="cp_2", state={}, metadata={"workflow_id": "wf_1"}))
        await saver.save(CheckpointData(checkpoint_id="cp_3", state={}, metadata={"workflow_id": "wf_2"}))

        all_cps = await saver.list_checkpoints()
        assert len(all_cps) == 3

        wf1_cps = await saver.list_checkpoints("wf_1")
        assert len(wf1_cps) == 2


class TestInMemoryMemoryStore:
    """Test in-memory memory store."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test setting and getting values."""
        store = InMemoryMemoryStore()

        await store.set("key1", "value1")
        assert await store.get("key1") == "value1"

    @pytest.mark.asyncio
    async def test_get_not_found(self):
        """Test getting non-existent key."""
        store = InMemoryMemoryStore()
        assert await store.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_namespace_isolation(self):
        """Test namespace isolation."""
        store = InMemoryMemoryStore()

        await store.set("key", "value1", namespace="ns1")
        await store.set("key", "value2", namespace="ns2")

        assert await store.get("key", "ns1") == "value1"
        assert await store.get("key", "ns2") == "value2"

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting values."""
        store = InMemoryMemoryStore()

        await store.set("key", "value")
        assert await store.delete("key") is True
        assert await store.get("key") is None
        assert await store.delete("key") is False

    @pytest.mark.asyncio
    async def test_list_keys(self):
        """Test listing keys."""
        store = InMemoryMemoryStore()

        await store.set("key1", "v1", namespace="ns")
        await store.set("key2", "v2", namespace="ns")
        await store.set("key3", "v3")  # No namespace

        ns_keys = await store.list_keys("ns")
        assert sorted(ns_keys) == ["key1", "key2"]

        all_keys = await store.list_keys()
        assert "key3" in all_keys

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test TTL expiration."""
        import time
        store = InMemoryMemoryStore()

        await store.set("key", "value", ttl=0.01)  # Very short TTL
        assert await store.get("key") == "value"  # Should still exist

        time.sleep(0.02)  # Wait for expiration
        assert await store.get("key") is None  # Should be expired now
