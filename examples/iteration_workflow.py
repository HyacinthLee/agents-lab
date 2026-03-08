"""Iteration workflow example.

This example demonstrates:
- Processing items in batches
- Loop until completion
- Accumulating results
- Conditional exit
"""

import asyncio
from acf.adapter.factory import AdapterFactory
from acf.workflow.builder import WorkflowBuilder, END
from acf.workflow.runner import WorkflowRunner
from acf.workflow.state import AgentState, WorkflowStatus


async def main():
    """Run iteration workflow demonstration."""
    print("=" * 60)
    print("Iteration Workflow Example")
    print("=" * 60)
    
    # Document processor agent
    processor_agent = AdapterFactory.create(
        "mock",
        name="doc_processor",
        metadata={
            "fixed_response": """
Processed batch:
- Items: 10
- Success: 10
- Failed: 0
- Time: 0.5s

Results stored in accumulator.
"""
        }
    )
    
    # Validator agent (checks if more processing needed)
    validator_agent = AdapterFactory.create(
        "mock",
        name="validator",
        metadata={
            "fixed_response": """
Validation complete.
Remaining items: 0
Status: COMPLETE
"""
        }
    )
    
    # Summary agent
    summary_agent = AdapterFactory.create(
        "mock",
        name="summarizer",
        metadata={
            "fixed_response": """
📊 Processing Summary:

Total Batches: 5
Total Items: 50
Success Rate: 100%
Total Time: 2.5s

All documents processed successfully!
"""
        }
    )
    
    # Build workflow
    builder = WorkflowBuilder(
        "batch_processor",
        description="Process documents in batches with iteration"
    )
    
    builder.add_node("process", processor_agent)
    builder.add_node("validate", validator_agent)
    builder.add_node("summarize", summary_agent)
    
    # Simple linear flow for this example
    # In real implementation, would use conditional edges for loop
    builder.add_edge("process", "validate")
    builder.add_edge("validate", "summarize")
    builder.add_edge("summarize", END)
    
    builder.set_entry_point("process")
    
    # Compile and run
    graph = builder.compile()
    runner = WorkflowRunner(graph, workflow_id="batch_001")
    
    # Simulate batch processing
    print("\nBatch Processing Simulation")
    print("-" * 60)
    
    batches = [
        {"batch_id": 1, "items": 10, "status": "pending"},
        {"batch_id": 2, "items": 10, "status": "pending"},
        {"batch_id": 3, "items": 10, "status": "pending"},
        {"batch_id": 4, "items": 10, "status": "pending"},
        {"batch_id": 5, "items": 10, "status": "pending"},
    ]
    
    print(f"Total batches to process: {len(batches)}")
    print(f"Items per batch: 10")
    print(f"Total items: {len(batches) * 10}\n")
    
    # Process each batch
    for i, batch in enumerate(batches, 1):
        print(f"Processing batch {i}/{len(batches)}...")
        
        result = await runner.run(
            f"Process batch {batch['batch_id']} with {batch['items']} items"
        )
        
        if result.success:
            batch["status"] = "completed"
            print(f"  ✓ Batch {i} completed")
        else:
            batch["status"] = "failed"
            print(f"  ✗ Batch {i} failed: {result.error}")
    
    # Final summary
    print("\n" + "-" * 60)
    completed = sum(1 for b in batches if b["status"] == "completed")
    print(f"Processing complete: {completed}/{len(batches)} batches")
    
    # Demonstrate concept
    print("\n" + "=" * 60)
    print("Iteration Pattern Explanation")
    print("=" * 60)
    print("""
Real Implementation with LangGraph:

1. Loop Setup
   ┌─────────────┐
   │   Start     │
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │  Process    │ ◄──────┐
   │   Batch     │        │
   └──────┬──────┘        │
          ▼               │
   ┌─────────────┐        │
   │  Validate   │        │
   └──────┬──────┘        │
          │               │
      More? │ Yes         │
          └───────────────┘
          │ No
          ▼
   ┌─────────────┐
   │   Summary   │
   └──────┬──────┘
          ▼
   ┌─────────────┐
      End

2. Key Features
   - Conditional edges for loop control
   - State accumulator for results
   - Checkpoint after each batch
   - Error handling per iteration

3. Benefits
   - Memory efficient (process in batches)
   - Fault tolerant (checkpoint each iteration)
   - Observable (track progress)
   - Configurable (batch size, max iterations)
""")


if __name__ == "__main__":
    asyncio.run(main())
