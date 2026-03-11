import asyncio
import sys
sys.path.insert(0, "/root/.openclaw/workspace/acf-v2/src")

from acf import AdapterFactory

async def test():
    print("Testing ACF ClaudeAdapter...")
    adapter = AdapterFactory.create(
        "claude",
        name="test_agent",
        timeout=60.0,
        metadata={
            "workspace_dir": "/root/.openclaw/workspace/acf-v2/examples/dev_workflow/output",
            "confirm_delay": 0.5,
        }
    )
    
    result = await adapter.execute("Write a simple hello world Python program")
    print(f"Status: {result.status}")
    print(f"Output length: {len(result.output) if result.output else 0}")
    print(f"Output preview: {result.output[:500] if result.output else 'None'}")
    print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(test())
