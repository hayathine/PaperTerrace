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
    os.environ["DB_PATH"] = db_path
    os.environ["GEMINI_API_KEY"] = "test-key"

    from src.main import app

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


def test_memo_endpoints(client):
    """Test memo CRUD operations."""
    # Create memo
    response = client.post(
        "/memo",
        json={"session_id": "test-session", "term": "API", "note": "Application Programming Interface"},
    )
    assert response.status_code == 200
    memo = response.json()
    assert memo["term"] == "API"
    memo_id = memo["memo_id"]

    # Get memos
    response = client.get("/memo/test-session")
    assert response.status_code == 200
    data = response.json()
    assert len(data["memos"]) == 1

    # Delete memo
    response = client.delete(f"/memo/{memo_id}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_export_memos_endpoint(client):
    """Test memo export."""
    # Create some memos first
    client.post(
        "/memo",
        json={"session_id": "export-test", "term": "Test", "note": "Test note"},
    )

    response = client.post("/memo/export", data={"session_id": "export-test"})
    assert response.status_code == 200
    data = response.json()
    assert "export" in data
    assert "Test" in data["export"]
