"""
Pytest configuration and fixtures for PaperTerrace tests.
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set test environment before importing app modules
os.environ["DB_PATH"] = ":memory:"
os.environ["GEMINI_API_KEY"] = "test-api-key"
os.environ["AI_PROVIDER"] = "gemini"


@pytest.fixture
def mock_ai_provider():
    """Create a mock AI provider for testing."""
    provider = MagicMock()
    provider.generate = AsyncMock(return_value="Mock AI response")
    provider.generate_with_image = AsyncMock(return_value="Mock image analysis")
    provider.generate_with_pdf = AsyncMock(return_value="Mock PDF OCR text")
    return provider


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    os.environ["DB_PATH"] = db_path
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def sample_paper_text():
    """Sample paper text for testing."""
    return """
    Abstract: This paper presents a novel approach to natural language processing
    using transformer-based models. We demonstrate significant improvements in
    accuracy compared to previous methods.
    
    1. Introduction
    The field of NLP has seen remarkable progress in recent years. Our work builds
    upon the foundation of attention mechanisms introduced by Vaswani et al. (2017).
    
    2. Methodology
    We employ a modified BERT architecture with additional layers for improved
    context understanding. The model is trained on a diverse corpus of academic papers.
    
    3. Results
    Our experiments show a 15% improvement in F1 score on standard benchmarks.
    
    4. Conclusion
    This research contributes to the advancement of NLP techniques for academic
    document analysis.
    """
