"""Tests for the Mock adapter."""

import pytest
from acf.adapter.base import AgentStatus
from acf.adapter.mock import MockAdapter
from acf.adapter.factory import create_mock_adapter, AdapterFactory


class TestMockAdapter:
    """Tests for MockAdapter."""

    @pytest.fixture
    def adapter(self) -> MockAdapter:
        """Create a test mock adapter."""
        return create_mock_adapter(name="test-mock")

    @pytest.mark.asyncio
    async def test_execute_success(self, adapter: MockAdapter) -> None:
        """Test successful execution."""
        result = await adapter.execute("Hello")
        assert result.status == AgentStatus.COMPLETED
        assert result.output is not None
        assert result.metadata["is_mock"] is True
        assert result.metadata["call_id"] == 1

    @pytest.mark.asyncio
    async def test_execute_echo_mode(self) -> None:
        """Test echo mode."""
        adapter = create_mock_adapter(name="echo-mock", echo_mode=True)
        result = await adapter.execute("Test message")
        assert result.status == AgentStatus.COMPLETED
        assert "Test message" in result.output

    @pytest.mark.asyncio
    async def test_execute_fixed_response(self) -> None:
        """Test fixed response."""
        adapter = create_mock_adapter(
            name="fixed-mock",
            fixed_response="Custom response"
        )
        result = await adapter.execute("Any prompt")
        assert result.output == "Custom response"

    @pytest.mark.asyncio
    async def test_execute_simulated_failure(self) -> None:
        """Test simulated failure."""
        adapter = create_mock_adapter(
            name="failing-mock",
            fail_probability=1.0  # Always fail
        )
        result = await adapter.execute("Test")
        assert result.status == AgentStatus.ERROR
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_stream(self, adapter: MockAdapter) -> None:
        """Test streaming."""
        chunks = []
        async for chunk in adapter.stream("Hello"):
            chunks.append(chunk)
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_failure(self) -> None:
        """Test streaming with failure."""
        adapter = create_mock_adapter(fail_probability=1.0)
        chunks = []
        async for chunk in adapter.stream("Test"):
            chunks.append(chunk)
        assert any("Error" in chunk for chunk in chunks)

    @pytest.mark.asyncio
    async def test_health_check(self, adapter: MockAdapter) -> None:
        """Test health check."""
        assert await adapter.health_check() is True

    def test_call_count(self, adapter: MockAdapter) -> None:
        """Test call counting."""
        assert adapter.get_call_count() == 0

    @pytest.mark.asyncio
    async def test_call_count_increment(self, adapter: MockAdapter) -> None:
        """Test call count increments."""
        await adapter.execute("First")
        assert adapter.get_call_count() == 1
        await adapter.execute("Second")
        assert adapter.get_call_count() == 2

    @pytest.mark.asyncio
    async def test_history(self, adapter: MockAdapter) -> None:
        """Test history tracking."""
        await adapter.execute("Test 1")
        await adapter.execute("Test 2")

        history = adapter.get_history()
        assert len(history) == 2
        assert history[0]["prompt"] == "Test 1"
        assert history[1]["prompt"] == "Test 2"

    @pytest.mark.asyncio
    async def test_clear_history(self, adapter: MockAdapter) -> None:
        """Test clearing history."""
        await adapter.execute("Test")
        adapter.clear_history()
        assert adapter.get_history() == []

    @pytest.mark.asyncio
    async def test_reset(self, adapter: MockAdapter) -> None:
        """Test reset functionality."""
        await adapter.execute("Test")
        adapter.reset()
        assert adapter.get_call_count() == 0
        assert adapter.get_history() == []

    @pytest.mark.asyncio
    async def test_delay(self) -> None:
        """Test response delay."""
        import asyncio
        adapter = create_mock_adapter(response_delay=0.1)
        start = asyncio.get_event_loop().time()
        await adapter.execute("Test")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.1


class TestMockAdapterFactory:
    """Tests for Mock adapter via factory."""

    @pytest.mark.asyncio
    async def test_factory_create_mock(self) -> None:
        """Test creating mock adapter via factory."""
        adapter = AdapterFactory.create("mock", name="factory-mock")
        assert isinstance(adapter, MockAdapter)
        assert adapter.name == "factory-mock"

    @pytest.mark.asyncio
    async def test_factory_mock_execute(self) -> None:
        """Test mock execution via factory-created adapter."""
        adapter = AdapterFactory.create(
            "mock",
            name="test",
            metadata={"echo_mode": True}
        )
        result = await adapter.execute("Hello")
        assert result.status == AgentStatus.COMPLETED
