"""Adapter module for ACF v2.0.

This module provides adapter implementations for different agent types.
"""

from acf.adapter.base import AgentAdapter, AdapterConfig
from acf.adapter.factory import AdapterFactory
from acf.adapter.claude import ClaudeAdapter
from acf.adapter.kimi import KimiAdapter
from acf.adapter.mock import MockAdapter

__all__ = [
    "AgentAdapter",
    "AdapterConfig",
    "AdapterFactory",
    "ClaudeAdapter",
    "KimiAdapter",
    "MockAdapter",
]
