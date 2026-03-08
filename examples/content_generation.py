"""Content generation pipeline example.

This example demonstrates a multi-agent content generation workflow:
1. Research Agent - gathers information
2. Outline Agent - creates article structure
3. Writing Agent - writes the content
4. Review Agent - quality check
"""

import asyncio
from acf.adapter.factory import AdapterFactory
from acf.workflow.builder import WorkflowBuilder, END
from acf.workflow.runner import WorkflowRunner, WorkflowEventType
from acf.workflow.state import WorkflowStatus


async def main():
    """Run content generation pipeline."""
    print("=" * 60)
    print("Content Generation Pipeline Example")
    print("=" * 60)
    
    # Create specialized agents
    research_agent = AdapterFactory.create(
        "mock",
        name="researcher",
        metadata={
            "fixed_response": """
Research Findings:
- AI adoption has grown 300% in the last 2 years
- Major industries: Healthcare, Finance, Manufacturing
- Key challenges: Data privacy, Integration costs, Talent shortage
- Future trends: Multimodal AI, Edge computing, Autonomous agents
"""
        }
    )
    
    outline_agent = AdapterFactory.create(
        "mock",
        name="outliner",
        metadata={
            "fixed_response": """
Article Outline:
1. Introduction - AI revolution overview
2. Current State - Adoption statistics and trends
3. Industry Applications - Healthcare, Finance, Manufacturing
4. Challenges - Privacy, Costs, Talent
5. Future Outlook - Emerging technologies
6. Conclusion - Key takeaways
"""
        }
    )
    
    writer_agent = AdapterFactory.create(
        "mock",
        name="writer",
        metadata={
            "fixed_response": """
# The AI Revolution: Transforming Industries in 2024

## Introduction
Artificial Intelligence has become one of the most transformative technologies...

## Current State
With 300% growth in adoption over the past two years...

## Industry Applications
### Healthcare
AI is revolutionizing diagnostics and drug discovery...

### Finance
Automated trading and risk assessment...

### Manufacturing
Predictive maintenance and quality control...

## Challenges
Organizations face several hurdles...

## Future Outlook
The next frontier includes multimodal AI...

## Conclusion
The AI revolution is just beginning...
"""
        }
    )
    
    review_agent = AdapterFactory.create(
        "mock",
        name="reviewer",
        metadata={
            "fixed_response": """
Review Report:
✓ Content quality: Excellent
✓ Structure: Well-organized
✓ Facts: Accurate and well-researched
✓ Tone: Professional and engaging
✓ Length: Appropriate for target audience

Recommendation: APPROVED for publication
"""
        }
    )
    
    # Build the pipeline
    builder = WorkflowBuilder(
        "content_pipeline",
        description="Multi-agent content generation"
    )
    
    # Add nodes
    builder.add_node("research", research_agent)
    builder.add_node("outline", outline_agent)
    builder.add_node("write", writer_agent)
    builder.add_node("review", review_agent)
    
    # Define the pipeline flow
    builder.add_edge("research", "outline")
    builder.add_edge("outline", "write")
    builder.add_edge("write", "review")
    builder.add_edge("review", END)
    
    # Set entry point
    builder.set_entry_point("research")
    
    # Compile workflow
    graph = builder.compile()
    
    # Create runner with event monitoring
    runner = WorkflowRunner(graph, workflow_id="content_gen_001")
    
    # Add event callbacks
    def on_event(event):
        if event.event_type == WorkflowEventType.NODE_COMPLETED:
            print(f"✓ {event.node_name} completed")
        elif event.event_type == WorkflowEventType.CHECKPOINT_SAVED:
            print(f"  Checkpoint saved: {event.data.get('checkpoint_id', 'unknown')}")
    
    runner.add_callback(on_event)
    
    # Run the pipeline
    print("\nStarting content generation...")
    print("-" * 60)
    
    result = await runner.run(
        "Write a comprehensive article about AI adoption in industries",
    )
    
    # Display results
    print("-" * 60)
    print("\nPipeline Results:")
    print(f"Status: {result.status}")
    print(f"Success: {result.success}")
    print(f"Execution Time: {result.execution_time:.2f}s")
    print(f"Nodes Executed: {result.node_count}")
    
    if result.success:
        print("\nFinal Output:")
        print(result.get_output()[:500] + "...")
    else:
        print(f"\nError: {result.error}")
    
    # Get execution stats
    stats = runner.get_stats()
    print(f"\nExecution Stats:")
    print(f"  Total Executions: {stats['execution_count']}")
    print(f"  Is Running: {stats['is_running']}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
