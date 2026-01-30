"""
Unit tests for SidebarNoteService.
"""

import os
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture
def note_service():
    """Create a note service with temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Set env before importing
    os.environ["DB_PATH"] = db_path
    os.environ["GEMINI_API_KEY"] = "test-key"

    # Import after setting env
    from src.providers.storage_provider import SQLiteStorage

    storage = SQLiteStorage(db_path)

    # Create the service with patched storage
    with patch("src.features.sidebar.get_storage_provider", return_value=storage):
        from src.features.sidebar import SidebarNoteService

        service = SidebarNoteService()
        service.storage = storage  # Ensure it uses our storage

        yield service

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_add_note(note_service):
    """Test adding a note."""
    note = note_service.add_note("session-1", "NLP", "自然言語処理の略称")

    assert note["term"] == "NLP"
    assert note["note"] == "自然言語処理の略称"
    assert "note_id" in note


def test_get_notes(note_service):
    """Test retrieving notes."""
    note_service.add_note("session-1", "Term1", "Note1")
    note_service.add_note("session-1", "Term2", "Note2")
    note_service.add_note("session-2", "Term3", "Note3")  # Different session

    notes = note_service.get_notes("session-1")

    assert len(notes) == 2
    assert any(m["term"] == "Term1" for m in notes)
    assert any(m["term"] == "Term2" for m in notes)


def test_delete_note(note_service):
    """Test deleting a note."""
    note = note_service.add_note("session-1", "ToDelete", "Will be deleted")
    note_id = note["note_id"]

    result = note_service.delete_note(note_id)
    assert result is True

    notes = note_service.get_notes("session-1")
    assert not any(m["note_id"] == note_id for m in notes)


def test_clear_session_notes(note_service):
    """Test clearing all notes for a session."""
    note_service.add_note("session-1", "Term1", "Note1")
    note_service.add_note("session-1", "Term2", "Note2")
    note_service.add_note("session-2", "Term3", "Note3")

    count = note_service.clear_session_notes("session-1")

    assert count == 2
    assert len(note_service.get_notes("session-1")) == 0
    assert len(note_service.get_notes("session-2")) == 1


def test_export_notes(note_service):
    """Test exporting notes as text."""
    note_service.add_note("session-1", "NLP", "Natural Language Processing")
    note_service.add_note("session-1", "ML", "Machine Learning")

    export = note_service.export_notes("session-1")

    assert "# 保存したノート" in export
    assert "NLP" in export
    assert "ML" in export
