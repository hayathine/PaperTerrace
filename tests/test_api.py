"""
Integration tests for FastAPI endpoints.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    # Reset storage provider singleton to assume new DB path
    import src.providers.storage_provider

    src.providers.storage_provider._storage_provider_instance = None

    import src.routers.papers
    from src.main import app
    from src.routers.note import sidebar_note_service

    # Create new storage connected to temp DB
    new_storage = src.providers.storage_provider.SQLiteStorage(db_path)

    # Patch services
    sidebar_note_service.storage = new_storage
    src.routers.papers.storage = new_storage

    with TestClient(app) as client:
        yield client

    if os.path.exists(db_path):
        os.remove(db_path)


def test_root_endpoint(client):
    """Test that the root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "PaperTerrace" in response.text


def test_languages_endpoint(client):
    """Test the languages endpoint."""
    response = client.get("/languages")
    assert response.status_code == 200
    data = response.json()
    assert "ja" in data
    assert "en" in data


def test_papers_list_endpoint(client):
    """Test listing papers."""
    response = client.get("/papers")
    assert response.status_code == 200
    data = response.json()
    assert "papers" in data
    assert isinstance(data["papers"], list)


def test_note_endpoints(client):
    """Test note CRUD operations."""
    # Create note
    response = client.post(
        "/note",
        json={
            "session_id": "test-session",
            "term": "API",
            "note": "Application Programming Interface",
        },
    )
    assert response.status_code == 200
    note = response.json()
    assert note["term"] == "API"
    note_id = note["note_id"]

    # Get notes
    response = client.get("/note/test-session")
    assert response.status_code == 200
    data = response.json()
    assert len(data["notes"]) == 1

    # Delete note
    response = client.delete(f"/note/{note_id}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_export_notes_endpoint(client):
    """Test note export."""
    # Create some notes first
    client.post(
        "/note",
        json={"session_id": "export-test", "term": "Test", "note": "Test note"},
    )

    response = client.post("/note/export", data={"session_id": "export-test"})
    assert response.status_code == 200
    data = response.json()
    assert "export" in data
    assert "Test" in data["export"]
