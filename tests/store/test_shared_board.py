"""Tests for shared_board module."""

import tempfile
from pathlib import Path

import pytest

from acf.store import BoardEntry, SimpleSharedBoard


class TestBoardEntry:
    """Tests for BoardEntry dataclass."""

    def test_board_entry_creation(self):
        """Test creating a BoardEntry."""
        entry = BoardEntry(
            key="test-key",
            value={"data": "test"},
            namespace=("team", "deliverables"),
            author="test_agent",
        )

        assert entry.key == "test-key"
        assert entry.value == {"data": "test"}
        assert entry.namespace == ("team", "deliverables")
        assert entry.author == "test_agent"
        assert entry.created_at is not None

    def test_board_entry_to_dict(self):
        """Test converting BoardEntry to dictionary."""
        entry = BoardEntry(
            key="test-key",
            value={"data": "test"},
            namespace=("team", "deliverables"),
            author="test_agent",
        )

        data = entry.to_dict()

        assert data["key"] == "test-key"
        assert data["value"] == {"data": "test"}
        assert data["namespace"] == ("team", "deliverables")
        assert data["author"] == "test_agent"

    def test_board_entry_from_dict(self):
        """Test creating BoardEntry from dictionary."""
        data = {
            "key": "test-key",
            "value": {"data": "test"},
            "namespace": ("team", "deliverables"),
            "author": "test_agent",
            "created_at": "2024-01-01T00:00:00",
        }

        entry = BoardEntry.from_dict(data)

        assert entry.key == "test-key"
        assert entry.value == {"data": "test"}
        assert entry.namespace == ("team", "deliverables")
        assert entry.author == "test_agent"
        assert entry.created_at == "2024-01-01T00:00:00"


class TestSimpleSharedBoard:
    """Tests for SimpleSharedBoard class."""

    def test_put_and_get(self):
        """Test putting and getting entries."""
        board = SimpleSharedBoard()

        entry = board.put(
            namespace=("team", "deliverables"),
            key="prd",
            value={"content": "Test PRD"},
            author="pm",
        )

        assert entry.key == "prd"
        assert entry.value == {"content": "Test PRD"}
        assert entry.author == "pm"

        retrieved = board.get(("team", "deliverables"), "prd")
        assert retrieved is not None
        assert retrieved.value == {"content": "Test PRD"}

    def test_get_not_found(self):
        """Test getting non-existent entry."""
        board = SimpleSharedBoard()

        result = board.get(("team", "deliverables"), "nonexistent")
        assert result is None

    def test_put_with_string_namespace(self):
        """Test putting with string namespace."""
        board = SimpleSharedBoard()

        entry = board.put(
            namespace="custom",
            key="test",
            value="data",
        )

        assert entry.namespace == ("custom",)

        retrieved = board.get("custom", "test")
        assert retrieved is not None

    def test_search(self):
        """Test searching entries."""
        board = SimpleSharedBoard()

        board.put(
            namespace=("team", "deliverables"),
            key="prd1",
            value={"content": "Authentication feature PRD"},
        )
        board.put(
            namespace=("team", "deliverables"),
            key="prd2",
            value={"content": "User profile feature PRD"},
        )
        board.put(
            namespace=("team", "deliverables"),
            key="code",
            value={"content": "Implementation code"},
        )

        results = board.search(("team", "deliverables"), "authentication")

        assert len(results) >= 1
        # Check that at least one result contains "authentication"
        found = any("authentication" in str(r.value).lower() for r in results)
        assert found

    def test_search_empty_query(self):
        """Test searching with empty query returns all entries."""
        board = SimpleSharedBoard()

        board.put(
            namespace=("team", "deliverables"),
            key="item1",
            value={"data": "value1"},
        )
        board.put(
            namespace=("team", "deliverables"),
            key="item2",
            value={"data": "value2"},
        )

        results = board.search(("team", "deliverables"), "")

        assert len(results) == 2

    def test_search_limit(self):
        """Test search respects limit."""
        board = SimpleSharedBoard()

        for i in range(10):
            board.put(
                namespace=("team", "deliverables"),
                key=f"item{i}",
                value={"data": f"value{i}"},
            )

        results = board.search(("team", "deliverables"), "", limit=5)

        assert len(results) <= 5

    def test_get_shared_context(self):
        """Test getting shared context."""
        board = SimpleSharedBoard(team_id="test_team")

        board.put(
            namespace=("team", "deliverables"),
            key="prd",
            value={"content": "PRD content"},
            author="pm",
        )
        board.put(
            namespace=("team", "decisions"),
            key="decision1",
            value={"content": "Decision content"},
            author="pm",
        )

        context = board.get_shared_context()

        assert context["team_id"] == "test_team"
        assert len(context["deliverables"]) == 1
        assert len(context["decisions"]) == 1

    def test_get_shared_context_custom_namespaces(self):
        """Test getting shared context with custom namespaces."""
        board = SimpleSharedBoard()

        board.put(
            namespace=("custom", "ns1"),
            key="item1",
            value={"data": "value1"},
        )

        context = board.get_shared_context(namespaces=[("custom", "ns1")])

        # Should not include default namespaces
        assert len(context["deliverables"]) == 0

    def test_delete(self):
        """Test deleting entries."""
        board = SimpleSharedBoard()

        board.put(
            namespace=("team", "deliverables"),
            key="to-delete",
            value={"data": "value"},
        )

        assert board.get(("team", "deliverables"), "to-delete") is not None

        result = board.delete(("team", "deliverables"), "to-delete")
        assert result is True

        assert board.get(("team", "deliverables"), "to-delete") is None

    def test_delete_not_found(self):
        """Test deleting non-existent entry."""
        board = SimpleSharedBoard()

        result = board.delete(("team", "deliverables"), "nonexistent")
        assert result is False

    def test_delete_with_string_namespace(self):
        """Test deleting with string namespace."""
        board = SimpleSharedBoard()

        board.put(
            namespace="custom",
            key="test",
            value="data",
        )

        result = board.delete("custom", "test")
        assert result is True

    def test_clear(self):
        """Test clearing all data."""
        board = SimpleSharedBoard()

        board.put(
            namespace=("team", "deliverables"),
            key="item1",
            value={"data": "value1"},
        )

        board.clear()

        assert board.get(("team", "deliverables"), "item1") is None

    def test_list_namespace(self):
        """Test listing namespace entries."""
        board = SimpleSharedBoard()

        board.put(
            namespace=("team", "deliverables"),
            key="item1",
            value={"data": "value1"},
        )
        board.put(
            namespace=("team", "deliverables"),
            key="item2",
            value={"data": "value2"},
        )

        entries = board._list_namespace(("team", "deliverables"))

        assert len(entries) == 2

    def test_multiple_namespaces_isolation(self):
        """Test that namespaces are isolated."""
        board = SimpleSharedBoard()

        board.put(
            namespace=("team", "deliverables"),
            key="item",
            value={"data": "deliverable"},
        )
        board.put(
            namespace=("team", "decisions"),
            key="item",
            value={"data": "decision"},
        )

        deliverable = board.get(("team", "deliverables"), "item")
        decision = board.get(("team", "decisions"), "item")

        assert deliverable.value == {"data": "deliverable"}
        assert decision.value == {"data": "decision"}


class TestSimpleSharedBoardPersistence:
    """Tests for persistence features."""

    def test_export_and_import(self):
        """Test exporting and importing board data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            board1 = SimpleSharedBoard(team_id="test_team")

            board1.put(
                namespace=("team", "deliverables"),
                key="prd",
                value={"content": "PRD content"},
                author="pm",
            )

            export_file = Path(tmpdir) / "export.json"
            board1.export_to_file(export_file)

            assert export_file.exists()

            board2 = SimpleSharedBoard(team_id="new_team")
            count = board2.import_from_file(export_file)

            assert count == 1
            retrieved = board2.get(("team", "deliverables"), "prd")
            assert retrieved is not None
            assert retrieved.value == {"content": "PRD content"}

    def test_import_nonexistent_file(self):
        """Test importing from non-existent file."""
        board = SimpleSharedBoard()

        count = board.import_from_file(Path("/nonexistent/file.json"))

        assert count == 0
