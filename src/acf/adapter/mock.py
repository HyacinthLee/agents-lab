"""Mock adapter for ACF v2.0.

This module provides a mock adapter for testing and development purposes.
"""

import asyncio
import random
from typing import Any, AsyncIterator, Dict, List, Optional

from acf.adapter.base import AgentAdapter, AgentResult, AgentStatus, AdapterConfig


class MockAdapter(AgentAdapter):
    """Mock adapter for testing and development.

    This adapter simulates agent responses without making external API calls.
    It's useful for testing the framework, development, and CI/CD pipelines.

    Configuration options in metadata:
        - response_delay: Delay in seconds before responding (default: 0.1)
        - fail_probability: Probability of simulating a failure (default: 0.0)
        - echo_mode: If True, echo the prompt back (default: False)
        - fixed_response: If set, always return this response
        - stream_chunks: Number of chunks for streaming (default: 5)

    Example:
        ```python
        config = AdapterConfig(
            name="mock-agent",
            metadata={
                "response_delay": 0.5,
                "echo_mode": True,
            }
        )
        adapter = MockAdapter(config)
        result = await adapter.execute("Hello")
        ```
    """

    # Predefined responses for variety
    DEFAULT_RESPONSES: List[str] = [
        "This is a mock response from the test adapter.",
        "Mock agent received your message and processed it successfully.",
        "[MOCK] Processing complete. No actual AI was used.",
        "Test adapter response: Everything is working correctly.",
        "MockAgent: Your prompt has been acknowledged.",
    ]

    def __init__(self, config: AdapterConfig) -> None:
        """Initialize the Mock adapter.

        Args:
            config: Adapter configuration.
        """
        super().__init__(config)
        self._response_delay: float = config.metadata.get("response_delay", 0.1)
        self._fail_probability: float = config.metadata.get("fail_probability", 0.0)
        self._echo_mode: bool = config.metadata.get("echo_mode", False)
        self._fixed_response: Optional[str] = config.metadata.get("fixed_response")
        self._stream_chunks: int = config.metadata.get("stream_chunks", 5)
        self._call_count: int = 0
        self._history: List[Dict[str, Any]] = []

    def _generate_response(self, prompt: str) -> str:
        """Generate a mock response.

        Args:
            prompt: The input prompt.

        Returns:
            Generated response string.
        """
        if self._fixed_response:
            return self._fixed_response

        if self._echo_mode:
            return f"[ECHO] {prompt}"

        # Select a random response
        return random.choice(self.DEFAULT_RESPONSES)

    def _should_fail(self) -> bool:
        """Determine if this call should simulate a failure.

        Returns:
            True if should fail, False otherwise.
        """
        return random.random() < self._fail_probability

    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        """Execute a mock request.

        Args:
            prompt: The input prompt.
            **kwargs: Additional parameters.

        Returns:
            AgentResult containing the mock response.
        """
        await self._set_status(AgentStatus.RUNNING)
        self._call_count += 1

        # Apply response delay
        delay = kwargs.get("delay", self._response_delay)
        if delay > 0:
            await asyncio.sleep(delay)

        # Record call in history
        call_record = {
            "call_id": self._call_count,
            "prompt": prompt,
            "timestamp": asyncio.get_event_loop().time(),
        }

        # Check for simulated failure
        if self._should_fail():
            await self._set_status(AgentStatus.ERROR)
            call_record["status"] = "error"
            self._history.append(call_record)

            return self._create_result(
                AgentStatus.ERROR,
                error="Simulated failure (mock adapter)",
                call_id=self._call_count,
            )

        # Generate response
        response = self._generate_response(prompt)

        await self._set_status(AgentStatus.COMPLETED)
        call_record["status"] = "completed"
        call_record["response"] = response
        self._history.append(call_record)

        return self._create_result(
            AgentStatus.COMPLETED,
            output=response,
            call_id=self._call_count,
            is_mock=True,
        )

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Execute a mock streaming request.

        Args:
            prompt: The input prompt.
            **kwargs: Additional parameters.

        Yields:
            Chunks of the mock response.
        """
        await self._set_status(AgentStatus.RUNNING)
        self._call_count += 1

        # Check for simulated failure
        if self._should_fail():
            await self._set_status(AgentStatus.ERROR)
            yield "Error: Simulated failure (mock adapter)"
            return

        # Generate full response
        response = self._generate_response(prompt)

        # Split into chunks
        num_chunks = kwargs.get("stream_chunks", self._stream_chunks)
        chunk_size = max(1, len(response) // num_chunks)

        delay = kwargs.get("delay", self._response_delay)
        chunk_delay = delay / num_chunks if num_chunks > 0 else 0

        for i in range(0, len(response), chunk_size):
            chunk = response[i:i + chunk_size]
            yield chunk
            if chunk_delay > 0:
                await asyncio.sleep(chunk_delay)

        await self._set_status(AgentStatus.COMPLETED)

    async def health_check(self) -> bool:
        """Check if the mock adapter is healthy.

        Returns:
            Always True for the mock adapter.
        """
        return True

    def get_call_count(self) -> int:
        """Get the number of calls made to this adapter.

        Returns:
            Number of calls.
        """
        return self._call_count

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the call history.

        Returns:
            List of call records.
        """
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear the call history."""
        self._history.clear()

    def reset(self) -> None:
        """Reset the adapter state."""
        self._call_count = 0
        self._history.clear()
        self._status = AgentStatus.IDLE
