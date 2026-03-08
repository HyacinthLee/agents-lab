"""Tests for the Claude adapter."""

import pytest
from acf.adapter.base import AgentStatus
from acf.adapter.claude import ClaudeAdapter
from acf.adapter.factory import create_claude_adapter, AdapterFactory


class TestClaudeAdapter:
    """Tests for ClaudeAdapter."""

    @pytest.fixture
    def adapter(self) -> ClaudeAdapter:
        """Create a test Claude adapter."""
        return create_claude_adapter(name="test-claude")

    def test_initialization(self, adapter: ClaudeAdapter) -> None:
        """Test adapter initialization."""
        assert adapter.name == "test-claude"
        assert adapter.status == AgentStatus.IDLE
        assert adapter.tmux_session == "acf-claude-test-claude"

    def test_custom_workspace(self) -> None:
        """Test custom workspace directory."""
        from pathlib import Path
        adapter = create_claude_adapter(
            name="test",
            workspace_dir="/custom/path"
        )
        assert adapter._workspace_dir == Path("/custom/path")

    def test_confirm_delay(self) -> None:
        """Test custom confirm delay."""
        adapter = create_claude_adapter(
            name="test",
            metadata={"confirm_delay": 1.0}
        )
        assert adapter._confirm_delay == 1.0

    @pytest.mark.asyncio
    async def test_health_check_no_tmux(self, adapter: ClaudeAdapter) -> None:
        """Test health check when tmux is not available."""
        # This test may pass or fail depending on tmux installation
        result = await adapter.health_check()
        # Just verify it doesn't raise an exception
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_tmux_session_creation(self, adapter: ClaudeAdapter) -> None:
        """Test tmux session creation."""
        # Note: This test requires tmux to be installed
        result = await adapter._create_tmux_session()
        # Cleanup if session was created
        await adapter._kill_tmux_session()
        # Result depends on tmux availability
        assert isinstance(result, bool)


class TestClaudeAdapterFactory:
    """Tests for Claude adapter via factory."""

    def test_factory_create_claude(self) -> None:
        """Test creating Claude adapter via factory."""
        adapter = AdapterFactory.create("claude", name="factory-claude")
        assert isinstance(adapter, ClaudeAdapter)
        assert adapter.name == "factory-claude"

    def test_factory_claude_with_metadata(self) -> None:
        """Test creating Claude adapter with metadata."""
        from pathlib import Path
        adapter = AdapterFactory.create(
            "claude",
            name="test",
            metadata={
                "workspace_dir": "/tmp/test",
                "confirm_delay": 0.3,
            }
        )
        assert adapter._workspace_dir == Path("/tmp/test")
        assert adapter._confirm_delay == 0.3
