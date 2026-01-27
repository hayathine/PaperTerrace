"""
Unit tests for SidebarMemoService.
"""

import os
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture
def memo_service():
    """Create a memo service with temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Set env before importing
    os.environ["DB_PATH"] = db_path
    os.environ["GEMINI_API_KEY"] = "test-key"

    # Import after setting env
    from src.providers.storage_provider import SQLiteStorage

    storage = SQLiteStorage(db_path)

    # Create the service with patched storage
    with patch("src.feature.sidebar.get_storage_provider", return_value=storage):
        from src.feature.sidebar import SidebarMemoService

        service = SidebarMemoService()
        service.storage = storage  # Ensure it uses our storage

        yield service

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_add_memo(memo_service):
    """Test adding a memo."""
    memo = memo_service.add_memo("session-1", "NLP", "自然言語処理の略称")

    assert memo["term"] == "NLP"
    assert memo["note"] == "自然言語処理の略称"
    assert "memo_id" in memo


def test_get_memos(memo_service):
    """Test retrieving memos."""
    memo_service.add_memo("session-1", "Term1", "Note1")
    memo_service.add_memo("session-1", "Term2", "Note2")
    memo_service.add_memo("session-2", "Term3", "Note3")  # Different session

    memos = memo_service.get_memos("session-1")

    assert len(memos) == 2
    assert any(m["term"] == "Term1" for m in memos)
    assert any(m["term"] == "Term2" for m in memos)


def test_delete_memo(memo_service):
    """Test deleting a memo."""
    memo = memo_service.add_memo("session-1", "ToDelete", "Will be deleted")
    memo_id = memo["memo_id"]

    result = memo_service.delete_memo(memo_id)
    assert result is True

    memos = memo_service.get_memos("session-1")
    assert not any(m["memo_id"] == memo_id for m in memos)


def test_clear_session_memos(memo_service):
    """Test clearing all memos for a session."""
    memo_service.add_memo("session-1", "Term1", "Note1")
    memo_service.add_memo("session-1", "Term2", "Note2")
    memo_service.add_memo("session-2", "Term3", "Note3")

    count = memo_service.clear_session_memos("session-1")

    assert count == 2
    assert len(memo_service.get_memos("session-1")) == 0
    assert len(memo_service.get_memos("session-2")) == 1


def test_export_memos(memo_service):
    """Test exporting memos as text."""
    memo_service.add_memo("session-1", "NLP", "Natural Language Processing")
    memo_service.add_memo("session-1", "ML", "Machine Learning")

    export = memo_service.export_memos("session-1")

    assert "# 保存したメモ" in export
    assert "NLP" in export
    assert "ML" in export
