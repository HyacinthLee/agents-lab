"""Adapter factory for ACF v2.0.

This module provides a factory for creating adapter instances based on type.
"""

from typing import Any, Dict, Type

from acf.adapter.base import AgentAdapter, AdapterConfig
from acf.adapter.claude import ClaudeAdapter
from acf.adapter.kimi import KimiAdapter
from acf.adapter.mock import MockAdapter


class AdapterFactory:
    """Factory for creating agent adapters.

    This factory provides a centralized way to create adapter instances
    based on the adapter type. It supports registration of custom adapters
    and provides convenience methods for common adapter types.

    Supported adapter types:
        - "claude": Claude Code CLI adapter
        - "kimi": Kimi AI (Moonshot) adapter
        - "mock": Mock adapter for testing

    Example:
        ```python
        # Create using factory method
        adapter = AdapterFactory.create("claude", name="my-claude")

        # Or with full config
        config = AdapterConfig(name="my-agent", timeout=120.0)
        adapter = AdapterFactory.create("kimi", config=config)

        # Register custom adapter
        AdapterFactory.register("custom", MyCustomAdapter)
        ```
    """

    # Registry of adapter types to classes
    _registry: Dict[str, Type[AgentAdapter]] = {
        "claude": ClaudeAdapter,
        "kimi": KimiAdapter,
        "mock": MockAdapter,
    }

    @classmethod
    def register(cls, adapter_type: str, adapter_class: Type[AgentAdapter]) -> None:
        """Register a custom adapter type.

        Args:
            adapter_type: Unique identifier for the adapter type.
            adapter_class: Adapter class (must inherit from AgentAdapter).

        Raises:
            ValueError: If adapter_type is already registered.
            TypeError: If adapter_class is not a subclass of AgentAdapter.
        """
        if adapter_type in cls._registry:
            raise ValueError(f"Adapter type '{adapter_type}' is already registered")

        if not issubclass(adapter_class, AgentAdapter):
            raise TypeError(
                f"Adapter class must inherit from AgentAdapter, got {adapter_class}"
            )

        cls._registry[adapter_type] = adapter_class

    @classmethod
    def unregister(cls, adapter_type: str) -> None:
        """Unregister an adapter type.

        Args:
            adapter_type: The adapter type to unregister.

        Raises:
            KeyError: If adapter_type is not registered.
        """
        if adapter_type not in cls._registry:
            raise KeyError(f"Adapter type '{adapter_type}' is not registered")

        del cls._registry[adapter_type]

    @classmethod
    def create(
        cls,
        adapter_type: str,
        name: str | None = None,
        config: AdapterConfig | None = None,
        **kwargs: Any,
    ) -> AgentAdapter:
        """Create an adapter instance.

        Args:
            adapter_type: Type of adapter to create.
            name: Adapter name (used if config not provided).
            config: Full adapter configuration.
            **kwargs: Additional configuration parameters.

        Returns:
            Configured adapter instance.

        Raises:
            ValueError: If adapter_type is not registered.
        """
        if adapter_type not in cls._registry:
            raise ValueError(
                f"Unknown adapter type '{adapter_type}'. "
                f"Available types: {', '.join(cls.available_types())}"
            )

        adapter_class = cls._registry[adapter_type]

        # Build config if not provided
        if config is None:
            if name is None:
                name = f"{adapter_type}-agent"
            config = AdapterConfig(name=name, **kwargs)

        return adapter_class(config)

    @classmethod
    def available_types(cls) -> list[str]:
        """Get list of available adapter types.

        Returns:
            List of registered adapter type names.
        """
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, adapter_type: str) -> bool:
        """Check if an adapter type is registered.

        Args:
            adapter_type: Adapter type to check.

        Returns:
            True if registered, False otherwise.
        """
        return adapter_type in cls._registry

    @classmethod
    def get_adapter_class(cls, adapter_type: str) -> Type[AgentAdapter]:
        """Get the adapter class for a type.

        Args:
            adapter_type: Adapter type.

        Returns:
            Adapter class.

        Raises:
            ValueError: If adapter_type is not registered.
        """
        if adapter_type not in cls._registry:
            raise ValueError(f"Unknown adapter type '{adapter_type}'")
        return cls._registry[adapter_type]

    @classmethod
    def reset(cls) -> None:
        """Reset the factory to default state.

        This removes all custom registrations and restores defaults.
        """
        cls._registry = {
            "claude": ClaudeAdapter,
            "kimi": KimiAdapter,
            "mock": MockAdapter,
        }


# Convenience functions for common use cases

def create_claude_adapter(
    name: str = "claude-agent",
    workspace_dir: str | None = None,
    timeout: float = 120.0,
    confirm_delay: float | None = None,
    **kwargs: Any,
) -> ClaudeAdapter:
    """Create a Claude adapter with convenient defaults.

    Args:
        name: Adapter name.
        workspace_dir: Working directory for Claude.
        timeout: Execution timeout in seconds.
        confirm_delay: Delay before sending confirmation "2".
        **kwargs: Additional configuration.

    Returns:
        Configured ClaudeAdapter instance.
    """
    metadata = kwargs.pop("metadata", {})
    if workspace_dir:
        metadata["workspace_dir"] = workspace_dir
    if confirm_delay is not None:
        metadata["confirm_delay"] = confirm_delay

    config = AdapterConfig(name=name, timeout=timeout, metadata=metadata, **kwargs)
    return ClaudeAdapter(config)


def create_kimi_adapter(
    name: str = "kimi-agent",
    api_key: str | None = None,
    model: str = "kimi-latest",
    timeout: float = 60.0,
    **kwargs: Any,
) -> KimiAdapter:
    """Create a Kimi adapter with convenient defaults.

    Args:
        name: Adapter name.
        api_key: Kimi API key (or set KIMI_API_KEY env var).
        model: Model name to use.
        timeout: Execution timeout in seconds.
        **kwargs: Additional configuration.

    Returns:
        Configured KimiAdapter instance.
    """
    metadata = kwargs.pop("metadata", {})
    if api_key:
        metadata["api_key"] = api_key
    metadata["model"] = model

    config = AdapterConfig(name=name, timeout=timeout, metadata=metadata, **kwargs)
    return KimiAdapter(config)


def create_mock_adapter(
    name: str = "mock-agent",
    echo_mode: bool = False,
    fail_probability: float = 0.0,
    fixed_response: str | None = None,
    response_delay: float = 0.1,
    **kwargs: Any,
) -> MockAdapter:
    """Create a Mock adapter with convenient defaults.

    Args:
        name: Adapter name.
        echo_mode: If True, echo the prompt back.
        fail_probability: Probability of simulated failure (0.0-1.0).
        fixed_response: If set, always return this response.
        response_delay: Delay in seconds before responding.
        **kwargs: Additional configuration.

    Returns:
        Configured MockAdapter instance.
    """
    metadata = kwargs.pop("metadata", {})
    metadata["echo_mode"] = echo_mode
    metadata["fail_probability"] = fail_probability
    metadata["response_delay"] = response_delay
    if fixed_response is not None:
        metadata["fixed_response"] = fixed_response

    config = AdapterConfig(name=name, metadata=metadata, **kwargs)
    return MockAdapter(config)
