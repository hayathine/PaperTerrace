"""
Tests for the storage provider.
"""

import os
import tempfile

import pytest


@pytest.fixture
def storage():
    """Create SQLiteStorage with temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    os.environ["DB_PATH"] = db_path

    from src.providers.storage_provider import SQLiteStorage

    storage = SQLiteStorage(db_path)

    yield storage

    if os.path.exists(db_path):
        os.remove(db_path)


def test_save_and_get_paper(storage):
    """Test saving and retrieving a paper."""
    paper_id = storage.save_paper(
        paper_id="test-paper-1",
        file_hash="abc123",
        filename="test.pdf",
        ocr_text="Sample OCR text",
        html_content="<p>Sample HTML</p>",
        target_language="ja",
    )

    assert paper_id == "test-paper-1"

    paper = storage.get_paper("test-paper-1")
    assert paper is not None
    assert paper["filename"] == "test.pdf"
    assert paper["ocr_text"] == "Sample OCR text"


def test_get_paper_by_hash(storage):
    """Test retrieving a paper by file hash."""
    storage.save_paper(
        paper_id="test-paper-2",
        file_hash="unique-hash",
        filename="paper.pdf",
        ocr_text="Text",
        html_content="HTML",
        target_language="en",
    )

    paper = storage.get_paper_by_hash("unique-hash")
    assert paper is not None
    assert paper["paper_id"] == "test-paper-2"

    # Non-existent hash
    paper = storage.get_paper_by_hash("nonexistent")
    assert paper is None


def test_list_papers(storage):
    """Test listing papers."""
    storage.save_paper("p1", "h1", "file1.pdf", "t1", "html1", "ja")
    storage.save_paper("p2", "h2", "file2.pdf", "t2", "html2", "en")
    storage.save_paper("p3", "h3", "file3.pdf", "t3", "html3", "zh")

    papers = storage.list_papers(limit=10)
    assert len(papers) == 3

    papers = storage.list_papers(limit=2)
    assert len(papers) == 2


def test_delete_paper(storage):
    """Test deleting a paper."""
    storage.save_paper("to-delete", "hash", "file.pdf", "text", "html", "ja")

    result = storage.delete_paper("to-delete")
    assert result is True

    paper = storage.get_paper("to-delete")
    assert paper is None

    # Delete non-existent
    result = storage.delete_paper("nonexistent")
    assert result is False
