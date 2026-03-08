"""Node definitions for ACF v2.0 workflows.

This module provides AgentNode wrapper for LangGraph nodes with
state management, error handling, and retry logic.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from acf.adapter.base import AgentAdapter, AgentResult, AgentStatus
from acf.workflow.state import AgentState, WorkflowStatus

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class NodeConfig:
    """Configuration for agent nodes.

    Attributes:
        name: Unique node identifier.
        adapter: Agent adapter instance.
        system_prompt: Optional system prompt for the agent.
        retry_count: Number of retries on failure.
        retry_delay: Delay between retries in seconds.
        timeout: Node execution timeout.
        transform_input: Optional function to transform input state.
        transform_output: Optional function to transform output result.
        metadata: Additional node metadata.
    """

    name: str
    adapter: AgentAdapter
    system_prompt: Optional[str] = None
    retry_count: int = 3
    retry_delay: float = 1.0
    timeout: float = 60.0
    transform_input: Optional[Callable[[AgentState], str]] = None
    transform_output: Optional[Callable[[AgentResult, AgentState], Dict[str, Any]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class NodeExecutionError(Exception):
    """Error raised during node execution."""

    def __init__(
        self,
        message: str,
        node_name: str,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.node_name = node_name
        self.original_error = original_error


class AgentNode:
    """Wrapper for agent execution in LangGraph workflows.

    This class wraps an AgentAdapter to provide:
    - State management integration
    - Error handling and retry logic
    - Input/output transformation
    - Execution tracking

    Example:
        ```python
        config = NodeConfig(
            name="analyzer",
            adapter=my_adapter,
            retry_count=3,
        )
        node = AgentNode(config)

        # Use in LangGraph
        graph.add_node("analyzer", node.execute)
        ```
    """

    def __init__(self, config: NodeConfig):
        """Initialize agent node.

        Args:
            config: Node configuration.
        """
        self.config = config
        self._execution_count = 0
        self._error_count = 0

    @property
    def name(self) -> str:
        """Node name."""
        return self.config.name

    @property
    def adapter(self) -> AgentAdapter:
        """Agent adapter."""
        return self.config.adapter

    def _prepare_input(self, state: AgentState) -> str:
        """Prepare input prompt from state.

        Args:
            state: Current workflow state.

        Returns:
            Prepared prompt string.
        """
        # Use custom transform if provided
        if self.config.transform_input:
            return self.config.transform_input(state)

        # Default: extract from messages
        messages = state.get("messages", [])
        if not messages:
            return ""

        # Get last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")

        # Fallback to last message
        return messages[-1].get("content", "")

    def _process_output(
        self,
        result: AgentResult,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Process agent output.

        Args:
            result: Agent execution result.
            state: Current workflow state.

        Returns:
            State updates dictionary.
        """
        # Use custom transform if provided
        if self.config.transform_output:
            return self.config.transform_output(result, state)

        # Default: add to messages and update context
        updates: Dict[str, Any] = {}

        if result.status == AgentStatus.COMPLETED:
            # Add assistant message
            messages = list(state.get("messages", []))
            messages.append({
                "role": "assistant",
                "content": result.output,
                "node": self.name,
                "metadata": result.metadata,
            })
            updates["messages"] = messages

            # Update context with output
            context = dict(state.get("context", {}))
            context[f"{self.name}_output"] = result.output
            updates["context"] = context

        elif result.status == AgentStatus.ERROR:
            updates["error"] = {
                "node": self.name,
                "message": result.error or "Unknown error",
                "status": result.status.value,
            }
            updates["workflow_status"] = WorkflowStatus.ERROR

        return updates

    async def _execute_with_retry(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AgentResult:
        """Execute adapter with retry logic.

        Args:
            prompt: Input prompt.
            **kwargs: Additional execution parameters.

        Returns:
            Agent execution result.

        Raises:
            NodeExecutionError: If all retries exhausted.
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.config.retry_count):
            try:
                result = await asyncio.wait_for(
                    self.adapter.execute(prompt, **kwargs),
                    timeout=self.config.timeout,
                )

                if result.status != AgentStatus.ERROR:
                    return result

                # Agent returned error status, retry
                last_error = Exception(result.error or "Agent error")
                logger.warning(
                    f"Node {self.name} attempt {attempt + 1} failed: {result.error}"
                )

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"Node {self.name} timed out after {self.config.timeout}s"
                )
                logger.warning(f"Node {self.name} attempt {attempt + 1} timed out")

            except Exception as e:
                last_error = e
                logger.warning(f"Node {self.name} attempt {attempt + 1} error: {e}")

            # Wait before retry (except on last attempt)
            if attempt < self.config.retry_count - 1:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        # All retries exhausted
        raise NodeExecutionError(
            f"Node {self.name} failed after {self.config.retry_count} attempts",
            self.name,
            last_error,
        )

    async def execute(self, state: AgentState) -> AgentState:
        """Execute the agent node.

        This is the main entry point for LangGraph node execution.

        Args:
            state: Current workflow state.

        Returns:
            Updated state.
        """
        self._execution_count += 1

        # Update state to show current node
        updates: Dict[str, Any] = {
            "current_node": self.name,
            "workflow_status": WorkflowStatus.RUNNING,
        }

        try:
            # Prepare input
            prompt = self._prepare_input(state)

            if not prompt:
                logger.warning(f"Node {self.name} received empty prompt")
                updates["error"] = {
                    "node": self.name,
                    "message": "Empty prompt",
                }
                updates["workflow_status"] = WorkflowStatus.ERROR
                return AgentState({**state, **updates})

            # Add system prompt if configured
            if self.config.system_prompt:
                prompt = f"{self.config.system_prompt}\n\n{prompt}"

            # Execute with retry
            result = await self._execute_with_retry(prompt)

            # Process output
            output_updates = self._process_output(result, state)
            updates.update(output_updates)

        except NodeExecutionError as e:
            self._error_count += 1
            logger.error(f"Node {self.name} execution failed: {e}")
            updates["error"] = {
                "node": self.name,
                "message": str(e),
                "original_error": str(e.original_error) if e.original_error else None,
            }
            updates["workflow_status"] = WorkflowStatus.ERROR

        except Exception as e:
            self._error_count += 1
            logger.exception(f"Unexpected error in node {self.name}")
            updates["error"] = {
                "node": self.name,
                "message": str(e),
            }
            updates["workflow_status"] = WorkflowStatus.ERROR

        # Merge updates into state
        return AgentState({**state, **updates})

    def get_stats(self) -> Dict[str, Any]:
        """Get node execution statistics.

        Returns:
            Dictionary with execution statistics.
        """
        return {
            "name": self.name,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "adapter_name": self.adapter.name,
            "adapter_status": self.adapter.status.value,
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._error_count = 0


class ConditionalNode:
    """Node for conditional branching in workflows.

    This node evaluates a condition function and returns different
    state updates based on the result.
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[AgentState], str],
        branches: Dict[str, str],
        default_branch: Optional[str] = None,
    ):
        """Initialize conditional node.

        Args:
            name: Node name.
            condition: Function that evaluates state and returns branch key.
            branches: Mapping of branch keys to next node names.
            default_branch: Default branch if condition returns unknown key.
        """
        self.name = name
        self.condition = condition
        self.branches = branches
        self.default_branch = default_branch

    def execute(self, state: AgentState) -> str:
        """Execute conditional branch selection.

        Args:
            state: Current workflow state.

        Returns:
            Name of next node to execute.
        """
        branch_key = self.condition(state)

        if branch_key in self.branches:
            return self.branches[branch_key]

        if self.default_branch:
            return self.default_branch

        raise NodeExecutionError(
            f"Unknown branch '{branch_key}' and no default set",
            self.name,
        )


class RouterNode:
    """Node for routing to different agents based on content.

    This node analyzes the input and routes to the appropriate
    agent based on predefined rules or an LLM decision.
    """

    def __init__(
        self,
        name: str,
        routes: Dict[str, AgentNode],
        router_adapter: Optional[AgentAdapter] = None,
        default_route: Optional[str] = None,
    ):
        """Initialize router node.

        Args:
            name: Node name.
            routes: Mapping of route keys to agent nodes.
            router_adapter: Optional adapter for LLM-based routing.
            default_route: Default route if no match found.
        """
        self.name = name
        self.routes = routes
        self.router_adapter = router_adapter
        self.default_route = default_route

    async def route(self, state: AgentState) -> str:
        """Determine route for current state.

        Args:
            state: Current workflow state.

        Returns:
            Route key for next node.
        """
        if self.router_adapter:
            # LLM-based routing
            prompt = self._build_routing_prompt(state)
            result = await self.router_adapter.execute(prompt)

            if result.status == AgentStatus.COMPLETED:
                route_key = result.output.strip().lower()
                if route_key in self.routes:
                    return route_key

        # Fallback to default
        if self.default_route:
            return self.default_route

        raise NodeExecutionError(
            "Could not determine route",
            self.name,
        )

    def _build_routing_prompt(self, state: AgentState) -> str:
        """Build prompt for LLM-based routing.

        Args:
            state: Current workflow state.

        Returns:
            Routing prompt.
        """
        available_routes = ", ".join(self.routes.keys())
        last_message = ""

        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1].get("content", "")

        return f"""Based on the following request, select the most appropriate route.
Available routes: {available_routes}

Request: {last_message}

Respond with only the route name."""
