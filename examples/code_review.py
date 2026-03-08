"""Code review workflow example.

This example demonstrates an automated code review pipeline:
1. Static Analysis - Check code style and patterns
2. Security Scan - Detect vulnerabilities
3. Performance Analysis - Optimization suggestions
4. Summary - Generate review report
"""

import asyncio
from acf.adapter.factory import AdapterFactory
from acf.workflow.builder import WorkflowBuilder, END
from acf.workflow.runner import WorkflowRunner, WorkflowEventType


async def main():
    """Run code review workflow."""
    print("=" * 60)
    print("Automated Code Review Workflow")
    print("=" * 60)
    
    # Static analysis agent
    static_analyzer = AdapterFactory.create(
        "mock",
        name="static_analyzer",
        metadata={
            "fixed_response": """
Static Analysis Results:
✓ PEP 8 compliance: 98%
✓ Type hints: 85% coverage
⚠ Line too long: 3 occurrences (lines 45, 78, 120)
⚠ Missing docstrings: 2 functions
✓ Import organization: Good
✓ Naming conventions: Followed

Score: 8.5/10
"""
        }
    )
    
    # Security scan agent
    security_scanner = AdapterFactory.create(
        "mock",
        name="security_scanner",
        metadata={
            "fixed_response": """
Security Scan Results:
✓ No SQL injection vulnerabilities detected
✓ No XSS vulnerabilities detected
⚠ Hardcoded secret found: config.py line 23
⚠ Weak password validation: auth.py line 45
✓ Dependencies are up to date
✓ No known CVEs in dependencies

Score: 7.5/10
Issues to fix: 2
"""
        }
    )
    
    # Performance analysis agent
    performance_analyzer = AdapterFactory.create(
        "mock",
        name="performance_analyzer",
        metadata={
            "fixed_response": """
Performance Analysis:
⚠ O(n²) loop detected: data_processor.py line 56
  Suggestion: Use dictionary for O(1) lookup
✓ Database queries are optimized
⚠ Memory leak risk: cache not cleared
  Suggestion: Implement TTL for cache entries
✓ Async/await usage: Correct
⚠ Large file loading: Consider streaming

Score: 7/10
Optimization suggestions: 4
"""
        }
    )
    
    # Summary/report agent
    report_generator = AdapterFactory.create(
        "mock",
        name="report_generator",
        metadata={
            "fixed_response": """
# Code Review Report

## Executive Summary
Overall Score: 7.7/10
Status: APPROVED with minor changes

## Detailed Findings

### Static Analysis (8.5/10)
- Code style is generally good
- Minor formatting issues to address
- Documentation needs improvement

### Security (7.5/10)
- No critical vulnerabilities
- 2 medium-severity issues found
- Remove hardcoded secrets

### Performance (7/10)
- Algorithm efficiency can be improved
- Memory management needs attention
- Consider caching strategies

## Action Items
1. Fix line length violations
2. Add missing docstrings
3. Remove hardcoded secrets
4. Implement cache TTL
5. Optimize data_processor.py

## Approval Status
✓ APPROVED - Address minor issues before merge
"""
        }
    )
    
    # Build workflow with parallel analysis
    builder = WorkflowBuilder(
        "code_review",
        description="Automated code review pipeline"
    )
    
    # Add nodes
    builder.add_node("static_analysis", static_analyzer)
    builder.add_node("security_scan", security_scanner)
    builder.add_node("performance_analysis", performance_analyzer)
    builder.add_node("generate_report", report_generator)
    
    # Parallel analysis (all three can run simultaneously)
    # In real implementation, these would be independent nodes
    # For this example, we run them sequentially
    builder.add_edge("static_analysis", "security_scan")
    builder.add_edge("security_scan", "performance_analysis")
    builder.add_edge("performance_analysis", "generate_report")
    builder.add_edge("generate_report", END)
    
    builder.set_entry_point("static_analysis")
    
    # Compile and run
    graph = builder.compile()
    runner = WorkflowRunner(graph, workflow_id="code_review_001")
    
    # Event monitoring
    def on_event(event):
        if event.event_type == WorkflowEventType.NODE_COMPLETED:
            emoji = {
                "static_analysis": "📐",
                "security_scan": "🔒",
                "performance_analysis": "⚡",
                "generate_report": "📊"
            }.get(event.node_name, "✓")
            print(f"{emoji} {event.node_name} completed")
    
    runner.add_callback(on_event)
    
    # Run review
    print("\nStarting code review...")
    print("-" * 60)
    
    code_to_review = """
# Example Python code for review
def process_data(data):
    result = []
    for item in data:  # O(n²) potential
        for other in data:
            if item['id'] == other['ref_id']:
                result.append(combine(item, other))
    return result
"""
    
    result = await runner.run(code_to_review)
    
    # Results
    print("-" * 60)
    print(f"\nReview Complete!")
    print(f"Status: {result.status}")
    print(f"Success: {result.success}")
    print(f"Time: {result.execution_time:.2f}s")
    
    print("\n" + "=" * 60)
    print("Final Report:")
    print("=" * 60)
    print(result.get_output())


if __name__ == "__main__":
    asyncio.run(main())
