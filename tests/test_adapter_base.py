"""Tests for the base adapter interface."""

import pytest
from acf.adapter.base import (
    AgentAdapter,
    AgentMessage,
    AgentResult,
    AgentStatus,
    AdapterConfig,
)


class TestAdapterConfig:
    """Tests for AdapterConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = AdapterConfig(name="test-agent")
        assert config.name == "test-agent"
        assert config.timeout == 60.0
        assert config.max_retries == 3
        assert config.metadata == {}

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = AdapterConfig(
            name="custom-agent",
            timeout=120.0,
            max_retries=5,
            metadata={"key": "value"},
        )
        assert config.name == "custom-agent"
        assert config.timeout == 120.0
        assert config.max_retries == 5
        assert config.metadata == {"key": "value"}


class TestAgentMessage:
    """Tests for AgentMessage dataclass."""

    def test_message_creation(self) -> None:
        """Test creating an agent message."""
        msg = AgentMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.metadata == {}

    def test_message_with_metadata(self) -> None:
        """Test message with metadata."""
        msg = AgentMessage(
            role="assistant",
            content="Hi",
            metadata={"timestamp": 123456},
        )
        assert msg.metadata["timestamp"] == 123456


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful result creation."""
        result = AgentResult(
            status=AgentStatus.COMPLETED,
            output="Success output",
        )
        assert result.status == AgentStatus.COMPLETED
        assert result.output == "Success output"
        assert result.error is None

    def test_error_result(self) -> None:
        """Test error result creation."""
        result = AgentResult(
            status=AgentStatus.ERROR,
            error="Something went wrong",
        )
        assert result.status == AgentStatus.ERROR
        assert result.error == "Something went wrong"


class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert AgentStatus.IDLE == "idle"
        assert AgentStatus.RUNNING == "running"
        assert AgentStatus.COMPLETED == "completed"
        assert AgentStatus.ERROR == "error"
        assert AgentStatus.TIMEOUT == "timeout"

    def test_status_is_string(self) -> None:
        """Test that status is a string enum."""
        assert isinstance(AgentStatus.IDLE, str)
        assert AgentStatus.IDLE.value == "idle"


class ConcreteAdapter(AgentAdapter):
    """Concrete implementation for testing abstract base class."""

    async def execute(self, prompt: str, **kwargs) -> AgentResult:
        return self._create_result(AgentStatus.COMPLETED, output=prompt)

    async def stream(self, prompt: str, **kwargs):
        yield prompt

    async def health_check(self) -> bool:
        return True


class TestAgentAdapter:
    """Tests for AgentAdapter base class."""

    @pytest.fixture
    def adapter(self) -> ConcreteAdapter:
        """Create a test adapter."""
        config = AdapterConfig(name="test-adapter")
        return ConcreteAdapter(config)

    @pytest.mark.asyncio
    async def test_initial_status(self, adapter: ConcreteAdapter) -> None:
        """Test initial adapter status."""
        assert adapter.status == AgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_adapter_name(self, adapter: ConcreteAdapter) -> None:
        """Test adapter name property."""
        assert adapter.name == "test-adapter"

    @pytest.mark.asyncio
    async def test_execute(self, adapter: ConcreteAdapter) -> None:
        """Test execute method."""
        result = await adapter.execute("test prompt")
        assert result.status == AgentStatus.COMPLETED
        assert result.output == "test prompt"

    @pytest.mark.asyncio
    async def test_stream(self, adapter: ConcreteAdapter) -> None:
        """Test stream method."""
        chunks = []
        async for chunk in adapter.stream("test"):
            chunks.append(chunk)
        assert chunks == ["test"]

    @pytest.mark.asyncio
    async def test_health_check(self, adapter: ConcreteAdapter) -> None:
        """Test health check method."""
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager."""
        config = AdapterConfig(name="test")
        async with ConcreteAdapter(config) as adapter:
            assert adapter.status == AgentStatus.IDLE
            result = await adapter.execute("test")
            assert result.status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_create_result(self, adapter: ConcreteAdapter) -> None:
        """Test _create_result helper method."""
        result = adapter._create_result(
            AgentStatus.COMPLETED,
            output="test",
            custom_key="custom_value",
        )
        assert result.status == AgentStatus.COMPLETED
        assert result.output == "test"
        assert result.metadata["adapter_name"] == "test-adapter"
        assert result.metadata["custom_key"] == "custom_value"

    @pytest.mark.asyncio
    async def test_status_update(self, adapter: ConcreteAdapter) -> None:
        """Test status update functionality."""
        await adapter._set_status(AgentStatus.RUNNING)
        assert adapter.status == AgentStatus.RUNNING

        await adapter._set_status(AgentStatus.COMPLETED)
        assert adapter.status == AgentStatus.COMPLETED
