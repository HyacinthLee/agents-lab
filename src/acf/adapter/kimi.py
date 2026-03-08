"""Kimi adapter for ACF v2.0.

This module provides an adapter for Kimi AI (Moonshot AI) integration.
"""

import asyncio
import os
from typing import Any, AsyncIterator, Dict, Optional

from acf.adapter.base import AgentAdapter, AgentResult, AgentStatus, AdapterConfig


class KimiAdapter(AgentAdapter):
    """Adapter for Kimi AI (Moonshot AI).

    This adapter integrates with Kimi's API for agent execution.
    It supports both synchronous execution and streaming responses.

    Note: This is a demo implementation. In production, you would use
    the official Moonshot AI SDK or REST API.

    Example:
        ```python
        config = AdapterConfig(
            name="kimi-agent",
            timeout=60.0,
            metadata={"api_key": "your-api-key", "model": "kimi-latest"}
        )
        adapter = KimiAdapter(config)
        result = await adapter.execute("Explain quantum computing")
        ```
    """

    # Default API endpoint for Moonshot AI
    DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"
    DEFAULT_MODEL = "kimi-latest"

    def __init__(self, config: AdapterConfig) -> None:
        """Initialize the Kimi adapter.

        Args:
            config: Adapter configuration. Should include 'api_key' in metadata.
        """
        super().__init__(config)
        self._api_key: Optional[str] = config.metadata.get("api_key") or os.getenv("KIMI_API_KEY")
        self._base_url: str = config.metadata.get("base_url", self.DEFAULT_BASE_URL)
        self._model: str = config.metadata.get("model", self.DEFAULT_MODEL)
        self._conversation_history: list[Dict[str, str]] = []

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests.

        Returns:
            Dictionary of headers.
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_messages(self, prompt: str) -> list[Dict[str, str]]:
        """Build the messages list for the API request.

        Args:
            prompt: The user prompt.

        Returns:
            List of message dictionaries.
        """
        messages = []

        # Add system message if present in metadata
        system_message = self.config.metadata.get("system_message")
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add conversation history
        messages.extend(self._conversation_history)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        return messages

    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        """Execute a prompt using Kimi AI.

        Args:
            prompt: The input prompt for Kimi.
            **kwargs: Additional parameters (temperature, max_tokens, etc.).

        Returns:
            AgentResult containing Kimi's response.
        """
        if not self._api_key:
            return self._create_result(
                AgentStatus.ERROR,
                error="Kimi API key not found. Set KIMI_API_KEY environment variable or pass in config metadata.",
            )

        await self._set_status(AgentStatus.RUNNING)

        try:
            # Build request payload
            # Note: In production, use the actual Moonshot AI API
            messages = self._build_messages(prompt)

            payload = {
                "model": kwargs.get("model", self._model),
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 4096),
            }

            # For demo purposes, simulate API call
            # In production, use aiohttp or httpx to make actual API call
            # import aiohttp
            # async with aiohttp.ClientSession() as session:
            #     async with session.post(
            #         f"{self._base_url}/chat/completions",
            #         headers=self._get_headers(),
            #         json=payload,
            #         timeout=self.config.timeout,
            #     ) as response:
            #         data = await response.json()

            # Simulated response for demo
            await asyncio.sleep(0.5)  # Simulate network delay

            # Update conversation history
            self._conversation_history.append({"role": "user", "content": prompt})

            # Simulated response content
            simulated_response = (
                f"[Kimi {self._model} Response]\n\n"
                f"This is a simulated response to: '{prompt[:50]}...'\n\n"
                "In production, this would be the actual response from Kimi AI API.\n"
                "To use real API, implement the HTTP call to Moonshot AI endpoint."
            )

            self._conversation_history.append(
                {"role": "assistant", "content": simulated_response}
            )

            await self._set_status(AgentStatus.COMPLETED)
            return self._create_result(
                AgentStatus.COMPLETED,
                output=simulated_response,
                model=self._model,
                tokens_used=len(prompt) + len(simulated_response),  # Simulated
            )

        except asyncio.TimeoutError:
            await self._set_status(AgentStatus.TIMEOUT)
            return self._create_result(
                AgentStatus.TIMEOUT,
                error=f"Request timed out after {self.config.timeout}s",
            )

        except Exception as e:
            await self._set_status(AgentStatus.ERROR)
            return self._create_result(
                AgentStatus.ERROR,
                error=f"API error: {str(e)}",
            )

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Execute a prompt and stream the output.

        Args:
            prompt: The input prompt for Kimi.
            **kwargs: Additional parameters.

        Yields:
            Chunks of Kimi's response.
        """
        if not self._api_key:
            yield "Error: Kimi API key not found"
            return

        await self._set_status(AgentStatus.RUNNING)

        try:
            # Simulated streaming response
            simulated_chunks = [
                "[Kimi Streaming] ",
                "This ",
                "is ",
                "a ",
                "simulated ",
                "streaming ",
                "response. ",
                "In ",
                "production, ",
                "this ",
                "would ",
                "be ",
                "actual ",
                "chunks ",
                "from ",
                "the ",
                "Kimi ",
                "API.",
            ]

            full_response = ""
            for chunk in simulated_chunks:
                yield chunk
                full_response += chunk
                await asyncio.sleep(0.05)  # Simulate streaming delay

            # Update conversation history
            self._conversation_history.append({"role": "user", "content": prompt})
            self._conversation_history.append(
                {"role": "assistant", "content": full_response}
            )

            await self._set_status(AgentStatus.COMPLETED)

        except Exception as e:
            await self._set_status(AgentStatus.ERROR)
            yield f"Error: {str(e)}"

    async def health_check(self) -> bool:
        """Check if Kimi API is accessible.

        Returns:
            True if API key is configured, False otherwise.
        """
        return self._api_key is not None and len(self._api_key) > 0

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._conversation_history.clear()

    def get_history(self) -> list[Dict[str, str]]:
        """Get the conversation history.

        Returns:
            List of message dictionaries.
        """
        return self._conversation_history.copy()
