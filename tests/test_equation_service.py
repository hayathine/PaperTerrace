from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.features.figure_insight.equation_service import EquationAnalysisResponse, EquationService


@pytest.fixture
def equation_service():
    with patch("src.features.figure_insight.equation_service.get_ai_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_get_provider.return_value = mock_provider
        service = EquationService()
        service.ai_provider = mock_provider
        yield service


@pytest.mark.asyncio
async def test_analyze_bbox_with_ai(equation_service):
    """Test AI analysis of an equation image."""
    mock_response = EquationAnalysisResponse(
        is_equation=True, confidence=0.9, latex="E=mc^2", explanation="Mass-energy equivalence"
    )
    equation_service.ai_provider.generate_with_image.return_value = mock_response

    result = await equation_service._analyze_bbox_with_ai(b"fake_image", "ja")

    assert result is not None
    assert result.is_equation is True
    assert result.latex == "E=mc^2"
    assert result.explanation == "Mass-energy equivalence"


def test_sanitize_bboxes(equation_service):
    """Test bounding box sanitization (merging overlaps)."""
    bboxes = [
        [10.0, 10.0, 20.0, 20.0],
        [15.0, 15.0, 25.0, 25.0],  # Overlaps with pprevious
        [100.0, 100.0, 110.0, 110.0],
    ]
    sanitized = equation_service._sanitize_bboxes(bboxes)

    # Expected: First two merged into [10, 10, 25, 25], third remains separate
    assert len(sanitized) == 2
    assert sanitized[0] == [10.0, 10.0, 25.0, 25.0]
    assert sanitized[1] == [100.0, 100.0, 110.0, 110.0]


def test_sanitize_bboxes_small(equation_service):
    """Test filtering of small bounding boxes."""
    bboxes = [
        [10.0, 10.0, 12.0, 12.0],  # Very small (2x2)
        [50.0, 50.0, 80.0, 80.0],  # Normal
    ]
    sanitized = equation_service._sanitize_bboxes(bboxes)

    assert len(sanitized) == 1
    assert sanitized[0] == [50.0, 50.0, 80.0, 80.0]


@pytest.mark.asyncio
async def test_detect_and_convert_equations_no_candidates(equation_service):
    """Test detection when no candidates are found."""
    equation_service._identify_potential_equation_areas = MagicMock(return_value=[])

    results = await equation_service.detect_and_convert_equations(b"pdf_bytes", 1)
    assert results == []


@pytest.mark.asyncio
async def test_detect_and_convert_equations_with_candidates(equation_service):
    """Test full flow with mocked candidates and AI response."""
    # Mock candidates
    equation_service._identify_potential_equation_areas = MagicMock(return_value=[[10, 10, 50, 50]])

    # Mock AI response
    mock_analysis = EquationAnalysisResponse(
        is_equation=True, confidence=0.8, latex="a+b", explanation="Simple addition"
    )
    equation_service._analyze_bbox_with_ai = AsyncMock(return_value=mock_analysis)

    # Mock fitz (PyMuPDF)
    with patch("src.features.figure_insight.equation_service.fitz.open") as mock_fitz:
        mock_doc = MagicMock()
        mock_page = MagicMock()

        # Setup page width/height
        mock_page.rect.width = 1000
        mock_page.rect.height = 1000

        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.return_value = mock_doc

        # Mock getting pixmap and bytes
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"image_bytes"
        mock_page.get_pixmap.return_value = mock_pix

        results = await equation_service.detect_and_convert_equations(b"pdf_bytes", 1)

        assert len(results) == 1
        assert results[0]["latex"] == "a+b"
        assert results[0]["bbox"] == [10, 10, 50, 50]
        assert results[0]["page_num"] == 1
