"""Conditional workflow example.

This example demonstrates:
- Dynamic routing based on state
- Multiple branches
- Default fallback
- Error handling per branch
"""

import asyncio
from acf.adapter.factory import AdapterFactory
from acf.workflow.builder import WorkflowBuilder, END
from acf.workflow.runner import WorkflowRunner
from acf.workflow.state import AgentState


async def main():
    """Run conditional workflow demonstration."""
    print("=" * 60)
    print("Conditional Workflow Example")
    print("=" * 60)
    
    # Create specialized agents for different request types
    classifier_agent = AdapterFactory.create(
        "mock",
        name="classifier",
        metadata={
            "echo_mode": True  # Will echo back input
        }
    )
    
    code_agent = AdapterFactory.create(
        "mock",
        name="code_helper",
        metadata={
            "fixed_response": """
💻 Code Assistant Response:

Here's the Python solution:

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Usage
print(fibonacci(10))  # 55
```

Need help with anything else?
"""
        }
    )
    
    writing_agent = AdapterFactory.create(
        "mock",
        name="writing_helper",
        metadata={
            "fixed_response": """
✍️ Writing Assistant Response:

Here's a professional email template:

---
Subject: Meeting Follow-up

Dear Team,

Thank you for your participation in today's meeting.
I wanted to follow up on the key points discussed...

Best regards,
[Your Name]
---

Would you like me to customize this further?
"""
        }
    )
    
    analysis_agent = AdapterFactory.create(
        "mock",
        name="analysis_helper",
        metadata={
            "fixed_response": """
📊 Analysis Response:

Data Analysis Summary:
- Total records: 1,234
- Average value: 456.78
- Trend: Increasing (+12%)
- Outliers detected: 3

Key Insights:
1. Strong growth in Q4
2. Seasonal pattern identified
3. Recommend increasing inventory

Full report attached.
"""
        }
    )
    
    general_agent = AdapterFactory.create(
        "mock",
        name="general_helper",
        metadata={
            "fixed_response": """
🤖 General Assistant Response:

I understand your request. Here's what I found:

Based on your query, I recommend:
1. Review the documentation
2. Check the FAQ section
3. Contact support if needed

Is there something specific you'd like help with?
"""
        }
    )
    
    # Build conditional workflow
    builder = WorkflowBuilder(
        "smart_router",
        description="Routes requests to appropriate agent"
    )
    
    # Add all nodes
    builder.add_node("classify", classifier_agent)
    builder.add_node("code", code_agent)
    builder.add_node("writing", writing_agent)
    builder.add_node("analysis", analysis_agent)
    builder.add_node("general", general_agent)
    
    # Define routing function
    def route_by_type(state: AgentState) -> str:
        """Determine which agent to use based on request content."""
        messages = state.get("messages", [])
        if not messages:
            return "general"
        
        last_message = messages[-1].get("content", "").lower()
        
        # Simple keyword-based routing
        if any(word in last_message for word in ["code", "python", "function", "bug"]):
            return "code"
        elif any(word in last_message for word in ["write", "email", "letter", "essay"]):
            return "writing"
        elif any(word in last_message for word in ["analyze", "data", "report", "statistics"]):
            return "analysis"
        else:
            return "general"
    
    # Add conditional edges from classifier
    builder.add_conditional_edges(
        "classify",
        condition=route_by_type,
        path_map={
            "code": "code",
            "writing": "writing",
            "analysis": "analysis",
            "general": "general"
        },
        default="general"
    )
    
    # All handlers lead to END
    builder.add_edge("code", END)
    builder.add_edge("writing", END)
    builder.add_edge("analysis", END)
    builder.add_edge("general", END)
    
    builder.set_entry_point("classify")
    
    # Compile
    graph = builder.compile()
    runner = WorkflowRunner(graph, workflow_id="router_001")
    
    # Test different request types
    test_cases = [
        ("Write a Python function to calculate factorial", "code"),
        ("Help me write a professional email to my boss", "writing"),
        ("Analyze the sales data for Q4", "analysis"),
        ("What is the weather like today?", "general"),
    ]
    
    print("\nTesting Smart Router with different request types:")
    print("-" * 60)
    
    for i, (request, expected_type) in enumerate(test_cases, 1):
        print(f"\nTest {i}: {request[:50]}...")
        print(f"Expected route: {expected_type}")
        
        result = await runner.run(request)
        
        if result.success:
            output = result.get_output()
            # Determine actual route from output
            if "Code Assistant" in output:
                actual_route = "code"
            elif "Writing Assistant" in output:
                actual_route = "writing"
            elif "Analysis" in output:
                actual_route = "analysis"
            else:
                actual_route = "general"
            
            match = "✓" if actual_route == expected_type else "✗"
            print(f"Actual route: {actual_route} {match}")
        else:
            print(f"✗ Error: {result.error}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Conditional Workflow Benefits:")
    print("=" * 60)
    print("""
1. Dynamic Routing
   - Automatically selects appropriate agent
   - Reduces manual intervention
   
2. Specialized Handling
   - Code requests → Code agent
   - Writing requests → Writing agent
   - Data requests → Analysis agent
   
3. Extensibility
   - Easy to add new agent types
   - Simple routing logic modification
   
4. Fallback
   - Default handler for unknown types
   - Graceful degradation
""")


if __name__ == "__main__":
    asyncio.run(main())
