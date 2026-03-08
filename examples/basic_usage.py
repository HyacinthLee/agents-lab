"""Basic usage examples for ACF v2.0."""

import asyncio

from acf.adapter.base import AgentStatus
from acf.adapter.factory import (
    AdapterFactory,
    create_claude_adapter,
    create_kimi_adapter,
    create_mock_adapter,
)


async def mock_adapter_example() -> None:
    """Example: Using the Mock adapter."""
    print("=" * 50)
    print("Mock Adapter Example")
    print("=" * 50)

    # Create a mock adapter with echo mode
    adapter = create_mock_adapter(
        name="mock-demo",
        echo_mode=True,
        response_delay=0.1,
    )

    # Check health
    healthy = await adapter.health_check()
    print(f"Health check: {healthy}")

    # Execute a prompt
    result = await adapter.execute("Hello, ACF v2.0!")
    print(f"Status: {result.status}")
    print(f"Output: {result.output}")
    print()

    # Stream response
    print("Streaming response:")
    async for chunk in adapter.stream("Stream this message"):
        print(chunk, end="", flush=True)
    print("\n")


async def kimi_adapter_example() -> None:
    """Example: Using the Kimi adapter."""
    print("=" * 50)
    print("Kimi Adapter Example (Simulated)")
    print("=" * 50)

    # Create a Kimi adapter (simulated mode without API key)
    adapter = create_kimi_adapter(
        name="kimi-demo",
        model="kimi-latest",
    )

    # Health check without API key
    healthy = await adapter.health_check()
    print(f"Health check (no API key): {healthy}")

    # Try to execute without API key
    result = await adapter.execute("Explain quantum computing")
    print(f"Status: {result.status}")
    if result.error:
        print(f"Error: {result.error}")
    print()

    # Now with API key (simulated)
    adapter_with_key = create_kimi_adapter(
        name="kimi-demo-2",
        api_key="demo-key",
        model="kimi-latest",
    )

    healthy = await adapter_with_key.health_check()
    print(f"Health check (with API key): {healthy}")

    result = await adapter_with_key.execute("Explain quantum computing")
    print(f"Status: {result.status}")
    print(f"Output preview: {result.output[:100]}...")
    print()


async def claude_adapter_example() -> None:
    """Example: Using the Claude adapter."""
    print("=" * 50)
    print("Claude Adapter Example")
    print("=" * 50)

    # Create a Claude adapter
    adapter = create_claude_adapter(
        name="claude-demo",
        workspace_dir="/tmp",
        timeout=60.0,
    )

    # Check health (requires tmux)
    healthy = await adapter.health_check()
    print(f"Health check (tmux available): {healthy}")
    print(f"Tmux session name: {adapter.tmux_session}")
    print()


async def factory_example() -> None:
    """Example: Using the AdapterFactory."""
    print("=" * 50)
    print("Adapter Factory Example")
    print("=" * 50)

    # List available types
    types = AdapterFactory.available_types()
    print(f"Available adapter types: {types}")

    # Create adapters using factory
    for adapter_type in types:
        adapter = AdapterFactory.create(
            adapter_type,
            name=f"factory-{adapter_type}"
        )
        print(f"Created {adapter_type} adapter: {adapter.name}")

    print()

    # Register a custom adapter
    from acf.adapter.base import AgentAdapter, AgentResult, AdapterConfig

    class CustomAdapter(AgentAdapter):
        async def execute(self, prompt: str, **kwargs) -> AgentResult:
            return self._create_result(
                AgentStatus.COMPLETED,
                output=f"Custom: {prompt}"
            )

        async def stream(self, prompt: str, **kwargs):
            yield f"Custom stream: {prompt}"

        async def health_check(self) -> bool:
            return True

    AdapterFactory.register("custom", CustomAdapter)
    print("Registered custom adapter type")

    custom = AdapterFactory.create("custom", name="my-custom")
    result = await custom.execute("test")
    print(f"Custom adapter result: {result.output}")
    print()


async def context_manager_example() -> None:
    """Example: Using adapters as async context managers."""
    print("=" * 50)
    print("Context Manager Example")
    print("=" * 50)

    adapter = create_mock_adapter(name="context-demo")

    async with adapter as ctx:
        print(f"Adapter status: {ctx.status}")
        result = await ctx.execute("Hello from context")
        print(f"Result status: {result.status}")

    print(f"Final status: {adapter.status}")
    print()


async def main() -> None:
    """Run all examples."""
    print("\nACF v2.0 - Basic Usage Examples\n")

    await mock_adapter_example()
    await kimi_adapter_example()
    await claude_adapter_example()
    await factory_example()
    await context_manager_example()

    print("=" * 50)
    print("All examples completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
