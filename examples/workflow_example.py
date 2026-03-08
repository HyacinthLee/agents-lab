"""Example usage of ACF v2.0 Workflow system.

This example demonstrates how to build and execute multi-agent workflows
using the LangGraph integration layer.
"""

import asyncio
from langgraph.graph import END

from acf import AdapterFactory
from acf.workflow import WorkflowBuilder, WorkflowRunner, WorkflowEventType
from acf.workflow.state import WorkflowStatus


async def simple_workflow_example():
    """Example: Simple linear workflow."""
    print("=== Simple Linear Workflow ===")

    # Create adapters
    analyzer = AdapterFactory.create("mock", name="analyzer", metadata={"fixed_response": "Analysis complete: This is a test."})
    writer = AdapterFactory.create("mock", name="writer", metadata={"fixed_response": "Written output based on analysis."})

    # Build workflow
    builder = WorkflowBuilder("simple_pipeline", "Analyze then write")
    builder.add_node("analyzer", analyzer, system_prompt="You are an analyzer.")
    builder.add_node("writer", writer, system_prompt="You are a writer.")

    # Add edges
    builder.add_edge("analyzer", "writer")
    builder.add_edge("writer", END)

    # Set entry point
    builder.set_entry_point("analyzer")

    # Compile
    graph = builder.compile()

    # Run workflow
    runner = WorkflowRunner(graph, workflow_id="simple_001")

    # Add event callback
    def on_event(event):
        print(f"  Event: {event.event_type.name} - Node: {event.node_name}")

    runner.add_callback(on_event)

    # Execute
    result = await runner.run("Please analyze this text and write a summary.")

    print(f"Status: {result.status.value}")
    print(f"Success: {result.success}")
    print(f"Output: {result.get_output()}")
    print(f"Execution time: {result.execution_time:.2f}s")
    print(f"Nodes executed: {result.node_count}")
    print()


async def conditional_workflow_example():
    """Example: Workflow with conditional branching."""
    print("=== Conditional Workflow ===")

    # Create adapters
    classifier = AdapterFactory.create("mock", name="classifier", metadata={"fixed_response": "positive"})
    positive_handler = AdapterFactory.create("mock", name="positive_handler", metadata={"fixed_response": "Handling positive sentiment."})
    negative_handler = AdapterFactory.create("mock", name="negative_handler", metadata={"fixed_response": "Handling negative sentiment."})

    # Build workflow
    builder = WorkflowBuilder("sentiment_pipeline", "Classify and route based on sentiment")

    builder.add_node("classifier", classifier)
    builder.add_node("positive_handler", positive_handler)
    builder.add_node("negative_handler", negative_handler)

    # Add conditional edges
    def route_by_sentiment(state):
        """Route based on classifier output."""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("node") == "classifier":
                content = msg.get("content", "").lower()
                if "positive" in content:
                    return "positive"
                elif "negative" in content:
                    return "negative"
        return "unknown"

    builder.add_conditional_edges(
        "classifier",
        route_by_sentiment,
        {"positive": "positive_handler", "negative": "negative_handler", "unknown": "negative_handler"},
    )

    builder.add_edge("positive_handler", END)
    builder.add_edge("negative_handler", END)
    builder.set_entry_point("classifier")

    # Compile and run
    graph = builder.compile()
    runner = WorkflowRunner(graph, workflow_id="conditional_001")

    result = await runner.run("This product is amazing!")

    print(f"Status: {result.status.value}")
    print(f"Output: {result.get_output()}")
    print()


async def streaming_workflow_example():
    """Example: Streaming workflow execution."""
    print("=== Streaming Workflow ===")

    # Create adapters
    agent1 = AdapterFactory.create("mock", name="agent1", metadata={"fixed_response": "Step 1 complete."})
    agent2 = AdapterFactory.create("mock", name="agent2", metadata={"fixed_response": "Step 2 complete."})

    # Build workflow
    builder = WorkflowBuilder("streaming_pipeline")
    builder.add_node("agent1", agent1)
    builder.add_node("agent2", agent2)
    builder.add_edge("agent1", "agent2")
    builder.add_edge("agent2", END)
    builder.set_entry_point("agent1")

    graph = builder.compile()
    runner = WorkflowRunner(graph, workflow_id="streaming_001")

    # Stream events
    print("Streaming events:")
    async for event in runner.stream("Start the process"):
        print(f"  {event.event_type.name}: {event.node_name or 'N/A'}")

    print()


async def checkpoint_recovery_example():
    """Example: Checkpoint and recovery."""
    print("=== Checkpoint and Recovery ===")

    from acf.workflow.state import InMemoryCheckpointSaver

    # Create checkpoint saver
    checkpoint_saver = InMemoryCheckpointSaver()

    # Create adapters
    agent = AdapterFactory.create("mock", name="agent", metadata={"fixed_response": "Processed with checkpoint."})

    # Build workflow
    builder = WorkflowBuilder("checkpoint_pipeline")
    builder.add_node("agent", agent)
    builder.add_edge("agent", END)
    builder.set_entry_point("agent")

    graph = builder.compile()
    runner = WorkflowRunner(graph, checkpoint_saver=checkpoint_saver, workflow_id="checkpoint_001")

    # Run workflow
    result = await runner.run("Process this")

    print(f"First run status: {result.status.value}")

    # List checkpoints
    checkpoints = await checkpoint_saver.list_checkpoints("checkpoint_001")
    print(f"Checkpoints created: {len(checkpoints)}")

    if checkpoints:
        # Resume from checkpoint
        cp_id = checkpoints[0].checkpoint_id
        print(f"Resuming from checkpoint: {cp_id}")

        runner2 = WorkflowRunner(graph, checkpoint_saver=checkpoint_saver, workflow_id="checkpoint_001")
        result2 = await runner2.resume(cp_id)

        print(f"Resume status: {result2.status.value}")

    print()


async def error_handling_example():
    """Example: Error handling in workflows."""
    print("=== Error Handling Workflow ===")

    # Create adapter that will fail
    failing_agent = AdapterFactory.create(
        "mock",
        name="failing_agent",
        metadata={"fail_probability": 1.0}  # Always fail
    )

    # Build workflow
    builder = WorkflowBuilder("error_pipeline")
    builder.add_node("agent", failing_agent, retry_count=2)
    builder.add_edge("agent", END)
    builder.set_entry_point("agent")

    graph = builder.compile()
    runner = WorkflowRunner(graph, workflow_id="error_001")

    result = await runner.run("This will fail")

    print(f"Status: {result.status.value}")
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    print()


async def main():
    """Run all examples."""
    print("ACF v2.0 Workflow Examples\n")
    print("=" * 50)
    print()

    await simple_workflow_example()
    await conditional_workflow_example()
    await streaming_workflow_example()
    await checkpoint_recovery_example()
    await error_handling_example()

    print("=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
