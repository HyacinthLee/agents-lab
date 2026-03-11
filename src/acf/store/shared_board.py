"""Shared whiteboard for agent communication in ACF v2.0 Real Agent Example.

This module provides SharedBoard, a wrapper around LangGraph BaseStore
for agent-to-agent communication and shared state management.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from langgraph.store.base import BaseStore
    from langgraph.store.memory import InMemoryStore
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    BaseStore = Any
    InMemoryStore = Any


@dataclass
class BoardEntry:
    """Single entry in the shared board.

    Attributes:
        key: Unique key within the namespace.
        value: Stored value (must be JSON-serializable).
        namespace: Namespace tuple for organization.
        created_at: Timestamp when entry was created.
        author: Name of the agent that created this entry.
        metadata: Additional metadata.
    """

    key: str
    value: Any
    namespace: Tuple[str, ...] = ("default",)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    author: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "namespace": self.namespace,
            "created_at": self.created_at,
            "author": self.author,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoardEntry":
        """Create entry from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            namespace=tuple(data.get("namespace", ("default",))),
            created_at=data.get("created_at", datetime.now().isoformat()),
            author=data.get("author", ""),
            metadata=data.get("metadata", {}),
        )


class SharedBoard:
    """Shared whiteboard for agent communication.

    This class wraps LangGraph BaseStore to provide a simple interface
    for agents to share information, search previous work, and maintain
    shared context across workflows.

    Namespaces:
    - ("team", "deliverables"): Cross-agent deliverables (PRDs, code, reports)
    - ("team", "decisions"): Key decisions made during workflow
    - ("team", "lessons"): Learned experiences and best practices
    - ("agent", "{name}"): Agent-specific shared data

    Example:
        ```python
        # Initialize board
        board = SharedBoard()

        # Write to shared board
        board.put(
            namespace=("team", "deliverables"),
            key="prd-v1",
            value={"content": "...", "status": "approved"},
            author="product_manager"
        )

        # Read from shared board
        prd = board.get(("team", "deliverables"), "prd-v1")

        # Search shared board
        results = board.search(("team", "deliverables"), "authentication")

        # Get shared context for agent
        context = board.get_shared_context()
        ```
    """

    def __init__(
        self,
        store: Optional[BaseStore] = None,
        team_id: str = "default_team",
    ):
        """Initialize shared board.

        Args:
            store: LangGraph BaseStore instance. If None, creates InMemoryStore.
            team_id: Identifier for the team/workspace.
        """
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph is required for SharedBoard. "
                "Install with: pip install langgraph"
            )

        self.store = store or InMemoryStore()
        self.team_id = team_id
        self._local_cache: Dict[str, Any] = {}

    def put(
        self,
        namespace: Tuple[str, ...] | str,
        key: str,
        value: Any,
        index: Optional[List[str]] = None,
        author: str = "",
    ) -> BoardEntry:
        """Write an entry to the shared board.

        Args:
            namespace: Namespace tuple or string for organization.
            key: Unique key within the namespace.
            value: Value to store (must be JSON-serializable).
            index: Optional list of fields to index for semantic search.
            author: Name of the agent creating this entry.

        Returns:
            The created BoardEntry.
        """
        # Convert string namespace to tuple
        if isinstance(namespace, str):
            namespace = (namespace,)

        # Create entry
        entry = BoardEntry(
            key=key,
            value=value,
            namespace=namespace,
            author=author,
            metadata={
                "team_id": self.team_id,
                "indexed_fields": index or [],
            },
        )

        # Store in BaseStore
        # Note: BaseStore.put expects (namespace, key, value)
        self.store.put(namespace, key, entry.to_dict())

        # Update local cache
        cache_key = self._cache_key(namespace, key)
        self._local_cache[cache_key] = entry

        return entry

    def get(
        self,
        namespace: Tuple[str, ...] | str,
        key: str,
    ) -> Optional[BoardEntry]:
        """Read an entry from the shared board.

        Args:
            namespace: Namespace tuple or string.
            key: Key to retrieve.

        Returns:
            BoardEntry if found, None otherwise.
        """
        # Convert string namespace to tuple
        if isinstance(namespace, str):
            namespace = (namespace,)

        # Check cache first
        cache_key = self._cache_key(namespace, key)
        if cache_key in self._local_cache:
            return self._local_cache[cache_key]

        # Get from store
        try:
            data = self.store.get(namespace, key)
            if data:
                entry = BoardEntry.from_dict(data)
                self._local_cache[cache_key] = entry
                return entry
        except Exception:
            pass

        return None

    def search(
        self,
        namespace: Tuple[str, ...] | str,
        query: str,
        limit: int = 5,
    ) -> List[BoardEntry]:
        """Search the shared board using semantic search.

        Args:
            namespace: Namespace tuple or string to search within.
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            List of matching BoardEntry objects.
        """
        # Convert string namespace to tuple
        if isinstance(namespace, str):
            namespace = (namespace,)

        try:
            # BaseStore.search returns list of (key, value, score) tuples
            results = self.store.search(namespace, query, limit=limit)

            entries = []
            for item in results:
                # Handle different result formats
                if isinstance(item, tuple):
                    if len(item) >= 2:
                        data = item[1]  # (key, value, score...)
                    else:
                        continue
                elif isinstance(item, dict):
                    data = item
                else:
                    continue

                try:
                    entry = BoardEntry.from_dict(data)
                    entries.append(entry)
                except Exception:
                    # If can't parse, create simple entry
                    entries.append(BoardEntry(
                        key=str(item[0]) if isinstance(item, tuple) else "unknown",
                        value=data,
                        namespace=namespace,
                    ))

            return entries
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def get_shared_context(
        self,
        namespaces: Optional[List[Tuple[str, ...]]] = None,
    ) -> Dict[str, Any]:
        """Get shared context for agent consumption.

        This method aggregates data from multiple namespaces to provide
        a comprehensive context for agents.

        Args:
            namespaces: List of namespaces to include. If None, uses defaults.

        Returns:
            Dictionary with shared context data.
        """
        if namespaces is None:
            namespaces = [
                ("team", "deliverables"),
                ("team", "decisions"),
                ("team", "lessons"),
            ]

        context = {
            "team_id": self.team_id,
            "deliverables": [],
            "decisions": [],
            "lessons": [],
        }

        for namespace in namespaces:
            try:
                # Try to get all items in namespace
                # Note: This is store-dependent; some stores may not support listing
                items = self._list_namespace(namespace)

                for entry in items:
                    if "deliverables" in namespace:
                        context["deliverables"].append(entry.to_dict())
                    elif "decisions" in namespace:
                        context["decisions"].append(entry.to_dict())
                    elif "lessons" in namespace:
                        context["lessons"].append(entry.to_dict())
            except Exception:
                pass

        return context

    def _list_namespace(
        self,
        namespace: Tuple[str, ...],
    ) -> List[BoardEntry]:
        """List all entries in a namespace.

        Note: This is a best-effort implementation. Not all BaseStore
        implementations support listing all items.

        Args:
            namespace: Namespace tuple.

        Returns:
            List of BoardEntry objects.
        """
        entries = []

        # Try to use store's list method if available
        if hasattr(self.store, 'list'):
            try:
                items = self.store.list(namespace)
                for item in items:
                    if isinstance(item, dict):
                        entries.append(BoardEntry.from_dict(item))
                    elif isinstance(item, tuple) and len(item) >= 2:
                        entries.append(BoardEntry.from_dict(item[1]))
            except Exception:
                pass

        # Fallback: search with empty query to get all items
        if not entries:
            try:
                results = self.search(namespace, "", limit=100)
                entries.extend(results)
            except Exception:
                pass

        return entries

    def _cache_key(self, namespace: Tuple[str, ...], key: str) -> str:
        """Generate cache key for namespace + key."""
        return f"{'/'.join(namespace)}/{key}"

    def clear_cache(self) -> None:
        """Clear the local cache."""
        self._local_cache.clear()

    def delete(
        self,
        namespace: Tuple[str, ...] | str,
        key: str,
    ) -> bool:
        """Delete an entry from the shared board.

        Args:
            namespace: Namespace tuple or string.
            key: Key to delete.

        Returns:
            True if deleted, False if not found.
        """
        if isinstance(namespace, str):
            namespace = (namespace,)

        try:
            # Try to use store's delete method
            if hasattr(self.store, 'delete'):
                self.store.delete(namespace, key)

            # Clear from cache
            cache_key = self._cache_key(namespace, key)
            if cache_key in self._local_cache:
                del self._local_cache[cache_key]

            return True
        except Exception:
            return False

    def export_to_file(self, file_path: Path | str) -> None:
        """Export all shared board data to a JSON file.

        Args:
            file_path: Path to export file.
        """
        file_path = Path(file_path)

        data = {
            "team_id": self.team_id,
            "exported_at": datetime.now().isoformat(),
            "entries": [],
        }

        # Try to export all namespaces
        for namespace_type in ["deliverables", "decisions", "lessons"]:
            namespace = ("team", namespace_type)
            entries = self._list_namespace(namespace)
            for entry in entries:
                data["entries"].append(entry.to_dict())

        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def import_from_file(self, file_path: Path | str) -> int:
        """Import shared board data from a JSON file.

        Args:
            file_path: Path to import file.

        Returns:
            Number of entries imported.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return 0

        data = json.loads(file_path.read_text(encoding="utf-8"))
        count = 0

        for entry_data in data.get("entries", []):
            try:
                entry = BoardEntry.from_dict(entry_data)
                self.put(
                    namespace=entry.namespace,
                    key=entry.key,
                    value=entry.value,
                    author=entry.author,
                )
                count += 1
            except Exception:
                pass

        return count


class SimpleSharedBoard:
    """Simple in-memory shared board for testing and simple use cases.

    This implementation doesn't require LangGraph and stores everything
    in memory. Data is lost when the process exits.
    """

    def __init__(self, team_id: str = "default_team"):
        """Initialize simple shared board.

        Args:
            team_id: Identifier for the team/workspace.
        """
        self.team_id = team_id
        self._data: Dict[str, Dict[str, BoardEntry]] = {}

    def put(
        self,
        namespace: Tuple[str, ...] | str,
        key: str,
        value: Any,
        index: Optional[List[str]] = None,
        author: str = "",
    ) -> BoardEntry:
        """Write an entry to the shared board."""
        if isinstance(namespace, str):
            namespace = (namespace,)

        ns_key = "/".join(namespace)

        if ns_key not in self._data:
            self._data[ns_key] = {}

        entry = BoardEntry(
            key=key,
            value=value,
            namespace=namespace,
            author=author,
            metadata={
                "team_id": self.team_id,
                "indexed_fields": index or [],
            },
        )

        self._data[ns_key][key] = entry
        return entry

    def get(
        self,
        namespace: Tuple[str, ...] | str,
        key: str,
    ) -> Optional[BoardEntry]:
        """Read an entry from the shared board."""
        if isinstance(namespace, str):
            namespace = (namespace,)

        ns_key = "/".join(namespace)
        return self._data.get(ns_key, {}).get(key)

    def search(
        self,
        namespace: Tuple[str, ...] | str,
        query: str,
        limit: int = 5,
    ) -> List[BoardEntry]:
        """Simple keyword search (not semantic)."""
        if isinstance(namespace, str):
            namespace = (namespace,)

        ns_key = "/".join(namespace)
        entries = list(self._data.get(ns_key, {}).values())

        if not query:
            return entries[:limit]

        # Simple keyword matching
        query_lower = query.lower()
        results = []

        for entry in entries:
            value_str = json.dumps(entry.value).lower()
            if query_lower in value_str or query_lower in entry.key.lower():
                results.append(entry)

        return results[:limit]

    def get_shared_context(
        self,
        namespaces: Optional[List[Tuple[str, ...]]] = None,
    ) -> Dict[str, Any]:
        """Get shared context for agent consumption."""
        if namespaces is None:
            namespaces = [
                ("team", "deliverables"),
                ("team", "decisions"),
                ("team", "lessons"),
            ]

        context = {
            "team_id": self.team_id,
            "deliverables": [],
            "decisions": [],
            "lessons": [],
        }

        for namespace in namespaces:
            entries = self._list_namespace(namespace)
            for entry in entries:
                if "deliverables" in namespace:
                    context["deliverables"].append(entry.to_dict())
                elif "decisions" in namespace:
                    context["decisions"].append(entry.to_dict())
                elif "lessons" in namespace:
                    context["lessons"].append(entry.to_dict())

        return context

    def _list_namespace(
        self,
        namespace: Tuple[str, ...],
    ) -> List[BoardEntry]:
        """List all entries in a namespace."""
        ns_key = "/".join(namespace)
        return list(self._data.get(ns_key, {}).values())

    def delete(
        self,
        namespace: Tuple[str, ...] | str,
        key: str,
    ) -> bool:
        """Delete an entry from the shared board."""
        if isinstance(namespace, str):
            namespace = (namespace,)

        ns_key = "/".join(namespace)

        if ns_key in self._data and key in self._data[ns_key]:
            del self._data[ns_key][key]
            return True

        return False

    def clear(self) -> None:
        """Clear all data."""
        self._data.clear()

    def export_to_file(self, file_path: Path | str) -> None:
        """Export all shared board data to a JSON file.

        Args:
            file_path: Path to export file.
        """
        file_path = Path(file_path)

        data = {
            "team_id": self.team_id,
            "exported_at": datetime.now().isoformat(),
            "entries": [],
        }

        # Export all namespaces
        for ns_key, entries_dict in self._data.items():
            for entry in entries_dict.values():
                data["entries"].append(entry.to_dict())

        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def import_from_file(self, file_path: Path | str) -> int:
        """Import shared board data from a JSON file.

        Args:
            file_path: Path to import file.

        Returns:
            Number of entries imported.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return 0

        data = json.loads(file_path.read_text(encoding="utf-8"))
        count = 0

        for entry_data in data.get("entries", []):
            try:
                entry = BoardEntry.from_dict(entry_data)
                self.put(
                    namespace=entry.namespace,
                    key=entry.key,
                    value=entry.value,
                    author=entry.author,
                )
                count += 1
            except Exception:
                pass

        return count
