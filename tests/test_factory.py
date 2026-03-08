"""Tests for the adapter factory."""

import pytest
from acf.adapter.base import AgentAdapter, AdapterConfig
from acf.adapter.claude import ClaudeAdapter
from acf.adapter.kimi import KimiAdapter
from acf.adapter.mock import MockAdapter
from acf.adapter.factory import (
    AdapterFactory,
    create_claude_adapter,
    create_kimi_adapter,
    create_mock_adapter,
)


class TestAdapterFactory:
    """Tests for AdapterFactory."""

    def setup_method(self) -> None:
        """Reset factory before each test."""
        AdapterFactory.reset()

    def test_available_types(self) -> None:
        """Test getting available adapter types."""
        types = AdapterFactory.available_types()
        assert "claude" in types
        assert "kimi" in types
        assert "mock" in types

    def test_is_registered(self) -> None:
        """Test checking if adapter type is registered."""
        assert AdapterFactory.is_registered("claude") is True
        assert AdapterFactory.is_registered("unknown") is False

    def test_create_claude(self) -> None:
        """Test creating Claude adapter."""
        adapter = AdapterFactory.create("claude", name="test-claude")
        assert isinstance(adapter, ClaudeAdapter)
        assert adapter.name == "test-claude"

    def test_create_kimi(self) -> None:
        """Test creating Kimi adapter."""
        adapter = AdapterFactory.create("kimi", name="test-kimi")
        assert isinstance(adapter, KimiAdapter)
        assert adapter.name == "test-kimi"

    def test_create_mock(self) -> None:
        """Test creating Mock adapter."""
        adapter = AdapterFactory.create("mock", name="test-mock")
        assert isinstance(adapter, MockAdapter)
        assert adapter.name == "test-mock"

    def test_create_with_config(self) -> None:
        """Test creating adapter with explicit config."""
        config = AdapterConfig(name="custom-config", timeout=90.0)
        adapter = AdapterFactory.create("mock", config=config)
        assert adapter.name == "custom-config"
        assert adapter.config.timeout == 90.0

    def test_create_unknown_type(self) -> None:
        """Test creating unknown adapter type."""
        with pytest.raises(ValueError, match="Unknown adapter type"):
            AdapterFactory.create("unknown")

    def test_get_adapter_class(self) -> None:
        """Test getting adapter class."""
        cls = AdapterFactory.get_adapter_class("mock")
        assert cls is MockAdapter

    def test_get_adapter_class_unknown(self) -> None:
        """Test getting unknown adapter class."""
        with pytest.raises(ValueError, match="Unknown adapter type"):
            AdapterFactory.get_adapter_class("unknown")

    def test_register_custom_adapter(self) -> None:
        """Test registering custom adapter."""

        class CustomAdapter(AgentAdapter):
            async def execute(self, prompt, **kwargs):
                pass

            async def stream(self, prompt, **kwargs):
                yield ""

            async def health_check(self):
                return True

        AdapterFactory.register("custom", CustomAdapter)
        assert AdapterFactory.is_registered("custom") is True

        adapter = AdapterFactory.create("custom", name="test-custom")
        assert isinstance(adapter, CustomAdapter)

    def test_register_duplicate(self) -> None:
        """Test registering duplicate adapter type."""
        with pytest.raises(ValueError, match="already registered"):
            AdapterFactory.register("claude", ClaudeAdapter)

    def test_register_invalid_class(self) -> None:
        """Test registering invalid adapter class."""

        class NotAnAdapter:
            pass

        with pytest.raises(TypeError, match="must inherit from AgentAdapter"):
            AdapterFactory.register("invalid", NotAnAdapter)  # type: ignore

    def test_unregister(self) -> None:
        """Test unregistering adapter type."""
        AdapterFactory.unregister("mock")
        assert AdapterFactory.is_registered("mock") is False

    def test_unregister_unknown(self) -> None:
        """Test unregistering unknown adapter type."""
        with pytest.raises(KeyError, match="not registered"):
            AdapterFactory.unregister("unknown")

    def test_reset(self) -> None:
        """Test factory reset."""
        AdapterFactory.unregister("mock")
        assert AdapterFactory.is_registered("mock") is False

        AdapterFactory.reset()
        assert AdapterFactory.is_registered("mock") is True


class TestConvenienceFunctions:
    """Tests for convenience factory functions."""

    def test_create_claude_adapter(self) -> None:
        """Test create_claude_adapter convenience function."""
        adapter = create_claude_adapter(
            name="my-claude",
            workspace_dir="/tmp",
            timeout=120.0,
        )
        assert isinstance(adapter, ClaudeAdapter)
        assert adapter.name == "my-claude"
        assert adapter.config.timeout == 120.0
        assert adapter.config.metadata["workspace_dir"] == "/tmp"

    def test_create_kimi_adapter(self) -> None:
        """Test create_kimi_adapter convenience function."""
        adapter = create_kimi_adapter(
            name="my-kimi",
            api_key="test-key",
            model="kimi-pro",
            timeout=90.0,
        )
        assert isinstance(adapter, KimiAdapter)
        assert adapter.name == "my-kimi"
        assert adapter.config.timeout == 90.0
        assert adapter.config.metadata["api_key"] == "test-key"
        assert adapter.config.metadata["model"] == "kimi-pro"

    def test_create_mock_adapter(self) -> None:
        """Test create_mock_adapter convenience function."""
        adapter = create_mock_adapter(
            name="my-mock",
            echo_mode=True,
            fail_probability=0.5,
        )
        assert isinstance(adapter, MockAdapter)
        assert adapter.name == "my-mock"
        assert adapter.config.metadata["echo_mode"] is True
        assert adapter.config.metadata["fail_probability"] == 0.5

    @pytest.mark.asyncio
    async def test_mock_adapter_integration(self) -> None:
        """Test full integration with mock adapter."""
        adapter = create_mock_adapter(echo_mode=True)
        result = await adapter.execute("Hello, World!")
        assert result.status.name == "COMPLETED"
        assert "Hello, World!" in result.output
