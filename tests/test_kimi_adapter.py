"""Tests for the Kimi adapter."""

import pytest
from acf.adapter.base import AgentStatus
from acf.adapter.kimi import KimiAdapter
from acf.adapter.factory import create_kimi_adapter, AdapterFactory


class TestKimiAdapter:
    """Tests for KimiAdapter."""

    @pytest.fixture
    def adapter(self, monkeypatch: pytest.MonkeyPatch) -> KimiAdapter:
        """Create a test Kimi adapter with no API key."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        return create_kimi_adapter(name="test-kimi")

    def test_initialization(self, adapter: KimiAdapter) -> None:
        """Test adapter initialization."""
        assert adapter.name == "test-kimi"
        assert adapter.status == AgentStatus.IDLE
        assert adapter._model == "kimi-latest"
        assert adapter._base_url == "https://api.moonshot.cn/v1"

    def test_api_key_from_config(self) -> None:
        """Test API key from config metadata."""
        adapter = create_kimi_adapter(
            name="test",
            api_key="test-api-key"
        )
        assert adapter._api_key == "test-api-key"

    def test_custom_model(self) -> None:
        """Test custom model selection."""
        adapter = create_kimi_adapter(
            name="test",
            model="kimi-pro"
        )
        assert adapter._model == "kimi-pro"

    def test_custom_base_url(self) -> None:
        """Test custom base URL."""
        adapter = create_kimi_adapter(
            name="test",
            metadata={"base_url": "https://custom.api.com/v1"}
        )
        assert adapter._base_url == "https://custom.api.com/v1"

    @pytest.mark.asyncio
    async def test_health_check_no_key(self, adapter: KimiAdapter) -> None:
        """Test health check without API key."""
        # Adapter fixture has no API key
        result = await adapter.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_with_key(self) -> None:
        """Test health check with API key."""
        adapter = create_kimi_adapter(api_key="test-key")
        result = await adapter.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test execution without API key."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        adapter = create_kimi_adapter(name="test-no-key")
        result = await adapter.execute("Hello")
        assert result.status == AgentStatus.ERROR
        assert "API key not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_api_key(self) -> None:
        """Test execution with API key (simulated)."""
        adapter = create_kimi_adapter(
            name="test",
            api_key="test-key",
            model="kimi-latest"
        )
        result = await adapter.execute("Hello")
        # In demo mode, this should succeed with simulated response
        assert result.status == AgentStatus.COMPLETED
        assert "[Kimi kimi-latest Response]" in result.output

    @pytest.mark.asyncio
    async def test_stream_with_api_key(self) -> None:
        """Test streaming with API key."""
        adapter = create_kimi_adapter(api_key="test-key")
        chunks = []
        async for chunk in adapter.stream("Hello"):
            chunks.append(chunk)
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_conversation_history(self) -> None:
        """Test conversation history tracking."""
        adapter = create_kimi_adapter(api_key="test-key")

        # Initial history should be empty
        assert adapter.get_history() == []

        # Execute a prompt
        await adapter.execute("First message")

        # History should have user and assistant messages
        history = adapter.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "First message"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_clear_history(self) -> None:
        """Test clearing conversation history."""
        adapter = create_kimi_adapter(api_key="test-key")
        await adapter.execute("Test")
        assert len(adapter.get_history()) == 2

        adapter.clear_history()
        assert adapter.get_history() == []

    def test_build_messages_with_system(self) -> None:
        """Test building messages with system message."""
        adapter = create_kimi_adapter(
            name="test",
            metadata={"system_message": "You are a helpful assistant."}
        )
        messages = adapter._build_messages("Hello")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"


class TestKimiAdapterFactory:
    """Tests for Kimi adapter via factory."""

    def test_factory_create_kimi(self) -> None:
        """Test creating Kimi adapter via factory."""
        adapter = AdapterFactory.create("kimi", name="factory-kimi")
        assert isinstance(adapter, KimiAdapter)
        assert adapter.name == "factory-kimi"

    def test_factory_kimi_with_metadata(self) -> None:
        """Test creating Kimi adapter with metadata."""
        adapter = AdapterFactory.create(
            "kimi",
            name="test",
            metadata={
                "api_key": "my-key",
                "model": "kimi-pro",
                "system_message": "Be helpful",
            }
        )
        assert adapter._api_key == "my-key"
        assert adapter._model == "kimi-pro"
