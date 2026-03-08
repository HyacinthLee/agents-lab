"""Base adapter interface for ACF v2.0.

This module defines the abstract base class and configuration for agent adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union
import asyncio


class AgentStatus(str, Enum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class AdapterConfig:
    """Configuration for agent adapters.

    Attributes:
        name: Unique name for the adapter instance.
        timeout: Default timeout in seconds for agent execution.
        max_retries: Maximum number of retries on failure.
        metadata: Additional metadata for the adapter.
    """

    name: str
    timeout: float = 60.0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessage:
    """Message structure for agent communication.

    Attributes:
        role: Message role (system, user, assistant, tool).
        content: Message content.
        metadata: Additional message metadata.
    """

    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result of agent execution.

    Attributes:
        status: Execution status.
        output: Output content from the agent.
        error: Error message if status is ERROR.
        metadata: Additional result metadata.
    """

    status: AgentStatus
    output: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentAdapter(ABC):
    """Abstract base class for agent adapters.

    This class defines the interface that all agent adapters must implement.
    Adapters are responsible for communicating with specific agent implementations
    (e.g., Claude, Kimi) and providing a unified interface for the framework.

    Example:
        ```python
        config = AdapterConfig(name="my-agent", timeout=120.0)
        adapter = MyAdapter(config)
        result = await adapter.execute("Hello, agent!")
        ```
    """

    def __init__(self, config: AdapterConfig) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Adapter configuration.
        """
        self.config = config
        self._status = AgentStatus.IDLE
        self._lock = asyncio.Lock()

    @property
    def status(self) -> AgentStatus:
        """Current status of the adapter."""
        return self._status

    @property
    def name(self) -> str:
        """Adapter name."""
        return self.config.name

    @abstractmethod
    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        """Execute a prompt and return the result.

        Args:
            prompt: The input prompt for the agent.
            **kwargs: Additional execution parameters.

        Returns:
            AgentResult containing the execution result.
        """
        raise NotImplementedError

    @abstractmethod
    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Execute a prompt and stream the output.

        Args:
            prompt: The input prompt for the agent.
            **kwargs: Additional execution parameters.

        Yields:
            Chunks of the agent's output.
        """
        raise NotImplementedError
        yield ""  # Make this a generator

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the adapter is healthy and ready.

        Returns:
            True if healthy, False otherwise.
        """
        raise NotImplementedError

    async def _set_status(self, status: AgentStatus) -> None:
        """Thread-safe status update.

        Args:
            status: New status to set.
        """
        async with self._lock:
            self._status = status

    def _create_result(
        self,
        status: AgentStatus,
        output: str = "",
        error: Optional[str] = None,
        **metadata: Any,
    ) -> AgentResult:
        """Create a standardized result object.

        Args:
            status: Execution status.
            output: Output content.
            error: Error message.
            **metadata: Additional metadata.

        Returns:
            AgentResult instance.
        """
        return AgentResult(
            status=status,
            output=output,
            error=error,
            metadata={
                "adapter_name": self.name,
                **metadata,
            },
        )

    async def __aenter__(self) -> "AgentAdapter":
        """Async context manager entry."""
        await self._set_status(AgentStatus.IDLE)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._set_status(AgentStatus.IDLE)
