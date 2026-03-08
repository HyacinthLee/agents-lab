"""Human-in-the-loop (HITL) workflow example.

This example demonstrates:
- Workflow pausing at critical checkpoints
- Human review and approval
- Resuming from checkpoint
- Modifying state before resume
"""

import asyncio
from acf.adapter.factory import AdapterFactory
from acf.workflow.builder import WorkflowBuilder, END
from acf.workflow.runner import WorkflowRunner, WorkflowEvent, WorkflowEventType
from acf.workflow.state import (
    AgentState,
    WorkflowStatus,
    create_initial_state,
    InMemoryCheckpointSaver,
)


async def main():
    """Run HITL workflow demonstration."""
    print("=" * 60)
    print("Human-in-the-Loop Workflow Example")
    print("=" * 60)
    
    # Create agents
    draft_agent = AdapterFactory.create(
        "mock",
        name="draft_writer",
        metadata={
            "fixed_response": """
# Draft Proposal: Project Phoenix

## Executive Summary
This proposal outlines the implementation of Project Phoenix,
a new initiative to modernize our infrastructure.

## Budget
Estimated cost: $500,000
Timeline: 6 months

## Risks
- Integration challenges
- Staff training required

[DRAFT - AWAITING APPROVAL]
"""
        }
    )
    
    revision_agent = AdapterFactory.create(
        "mock",
        name="revision_writer",
        metadata={
            "fixed_response": """
# Revised Proposal: Project Phoenix

## Executive Summary
This proposal outlines the implementation of Project Phoenix,
a comprehensive initiative to modernize our infrastructure and
improve operational efficiency by 40%.

## Budget (REVISED)
Estimated cost: $450,000 (reduced from $500,000)
Timeline: 6 months
ROI: 200% over 3 years

## Risk Mitigation
- Phased rollout approach
- Comprehensive training program
- 24/7 support during transition

[APPROVED VERSION]
"""
        }
    )
    
    final_agent = AdapterFactory.create(
        "mock",
        name="final_formatter",
        metadata={
            "fixed_response": """
# FINAL PROPOSAL: Project Phoenix

Status: ✓ APPROVED
Date: 2024-03-07

[Formatted for presentation]

---
Document ready for executive presentation.
"""
        }
    )
    
    # Build workflow
    builder = WorkflowBuilder(
        "hitl_proposal",
        description="Proposal workflow with human approval"
    )
    
    builder.add_node("draft", draft_agent)
    builder.add_node("revise", revision_agent)
    builder.add_node("finalize", final_agent)
    
    builder.add_edge("draft", "revise")
    builder.add_edge("revise", "finalize")
    builder.add_edge("finalize", END)
    
    builder.set_entry_point("draft")
    
    # Create checkpoint saver
    checkpoint_saver = InMemoryCheckpointSaver()
    
    # Compile and run
    graph = builder.compile()
    runner = WorkflowRunner(
        graph,
        checkpoint_saver=checkpoint_saver,
        workflow_id="proposal_001"
    )
    
    # Track checkpoints
    checkpoints = []
    
    def on_event(event: WorkflowEvent):
        if event.event_type == WorkflowEventType.NODE_COMPLETED:
            print(f"✓ Node '{event.node_name}' completed")
        elif event.event_type == WorkflowEventType.CHECKPOINT_SAVED:
            cp_id = event.data.get('checkpoint_id', 'unknown')
            checkpoints.append(cp_id)
            print(f"  💾 Checkpoint saved: {cp_id}")
    
    runner.add_callback(on_event)
    
    # === SCENARIO 1: Normal execution ===
    print("\n--- Scenario 1: Full Execution ---")
    print("Running complete workflow...\n")
    
    result = await runner.run("Create proposal for Project Phoenix")
    
    print(f"\nResult: {result.status}")
    print(f"Checkpoints created: {len(checkpoints)}")
    
    # === SCENARIO 2: Resume from checkpoint ===
    print("\n--- Scenario 2: Resume from Checkpoint ---")
    print("Simulating: Draft was rejected, need revision...")
    
    # Create new runner
    runner2 = WorkflowRunner(
        graph,
        checkpoint_saver=checkpoint_saver,
        workflow_id="proposal_002"
    )
    
    runner2.add_callback(on_event)
    
    # Resume from after draft
    if checkpoints:
        draft_checkpoint = checkpoints[0]
        print(f"\nResuming from checkpoint: {draft_checkpoint}")
        
        result2 = await runner2.run(
            "Revise with budget reduced to $450k",
            checkpoint_id=draft_checkpoint
        )
        
        print(f"\nResumed execution result: {result2.status}")
    
    # === SCENARIO 3: Simulate human approval ===
    print("\n--- Scenario 3: Simulated Approval Process ---")
    
    checkpoint_saver3 = InMemoryCheckpointSaver()
    runner3 = WorkflowRunner(
        graph,
        checkpoint_saver=checkpoint_saver3,
        workflow_id="proposal_003"
    )
    
    checkpoint_after_draft = None
    
    def capture_draft_checkpoint(event: WorkflowEvent):
        nonlocal checkpoint_after_draft
        if event.event_type == WorkflowEventType.CHECKPOINT_SAVED:
            if not checkpoint_after_draft:
                checkpoint_after_draft = event.data.get('checkpoint_id')
    
    runner3.add_callback(capture_draft_checkpoint)
    
    # Start workflow
    print("\nStarting workflow (will pause after draft)...")
    result3 = await runner3.run("Create proposal")
    
    if checkpoint_after_draft:
        print(f"\n🛑 Workflow paused at checkpoint: {checkpoint_after_draft}")
        print("📋 Human Review:")
        print("  - Budget too high? Yes")
        print("  - Missing risk mitigation? Yes")
        print("  - Action: Request revision")
        
        print("\n▶️  Resuming with revision instructions...")
        
        # Resume with modified context
        result3_final = await runner3.run(
            "Revise: reduce budget, add risk mitigation",
            checkpoint_id=checkpoint_after_draft
        )
        
        print(f"\nFinal result: {result3_final.status}")
    
    # Summary
    print("\n" + "=" * 60)
    print("HITL Workflow Demonstration Complete")
    print("=" * 60)
    print("\nKey Features Demonstrated:")
    print("  ✓ Automatic checkpoint creation")
    print("  ✓ Workflow pause and resume")
    print("  ✓ State persistence across sessions")
    print("  ✓ Human review integration point")
    print("\nBenefits:")
    print("  - Human oversight at critical points")
    print("  - Ability to modify and retry")
    print("  - Audit trail via checkpoints")
    

if __name__ == "__main__":
    asyncio.run(main())
