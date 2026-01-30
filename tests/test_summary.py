"""
Unit tests for SummaryService.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.summary import FullSummaryResponse, SectionSummary, SectionSummaryList


@pytest.fixture
def mock_storage():
    return MagicMock()


@pytest.mark.asyncio
async def test_summarize_full(mock_ai_provider, mock_storage):
    """Test full paper summarization."""
    mock_response = FullSummaryResponse(
        overview="This is an overview.",
        key_contributions=["Contrib 1", "Contrib 2"],
        methodology="Used a method.",
        conclusion="It works.",
    )
    mock_ai_provider.generate = AsyncMock(return_value=mock_response)

    with patch("src.features.summary.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.features.summary.summary import SummaryService

        service = SummaryService(storage=mock_storage)
        summary = await service.summarize_full("Sample paper text...")

        assert "Overview" in summary
        assert "This is an overview" in summary
        assert "Contrib 1" in summary
        mock_ai_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_sections(mock_ai_provider, mock_storage):
    """Test section-by-section summarization."""
    mock_response = SectionSummaryList(
        sections=[
            SectionSummary(section="Introduction", summary="Intro summary"),
            SectionSummary(section="Methods", summary="Methods summary"),
        ]
    )
    mock_ai_provider.generate = AsyncMock(return_value=mock_response)

    with patch("src.features.summary.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.features.summary.summary import SummaryService

        service = SummaryService(storage=mock_storage)
        sections = await service.summarize_sections("Sample paper text...")

        assert isinstance(sections, list)
        assert len(sections) == 2
        assert sections[0]["section"] == "Introduction"
        mock_ai_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_abstract(mock_ai_provider, mock_storage):
    """Test abstract extraction (Regex based)."""
    # Does NOT call AI

    with patch("src.features.summary.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.features.summary.summary import SummaryService

        service = SummaryService(storage=mock_storage)
        text = """
        Title: Something
        Authors: Someone
        
        Abstract:
        This is the abstract text found by regex.
        
        1. Introduction
        ...
        """
        abstract = await service.summarize_abstract(text)

        assert "This is the abstract text" in abstract
        assert mock_ai_provider.generate.call_count == 0


@pytest.mark.asyncio
async def test_summarize_full_with_pdf_bytes(mock_ai_provider, mock_storage):
    """Test full paper summarization with PDF bytes input."""
    mock_ai_provider.generate_with_pdf = AsyncMock(
        return_value="## Overview\nTest overview from PDF.\n\n## Key Contributions\n- Contrib from PDF"
    )

    with patch("src.features.summary.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.features.summary.summary import SummaryService

        service = SummaryService(storage=mock_storage)
        # Create a minimal fake PDF bytes (just for testing)
        fake_pdf_bytes = b"%PDF-1.4 fake pdf content"
        summary = await service.summarize_full(pdf_bytes=fake_pdf_bytes)

        assert "Overview" in summary
        assert "Test overview from PDF" in summary
        mock_ai_provider.generate_with_pdf.assert_called_once()
        # Verify generate (text-based) was NOT called
        assert mock_ai_provider.generate.call_count == 0


@pytest.mark.asyncio
async def test_summarize_full_fallback_to_text(mock_ai_provider, mock_storage):
    """Test that summarization falls back to text when pdf_bytes is not provided."""
    mock_response = FullSummaryResponse(
        overview="Fallback overview.",
        key_contributions=["Fallback contrib"],
        methodology="Fallback method.",
        conclusion="Fallback conclusion.",
    )
    mock_ai_provider.generate = AsyncMock(return_value=mock_response)
    mock_ai_provider.generate_with_pdf = AsyncMock()  # Should not be called

    with patch("src.features.summary.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.features.summary.summary import SummaryService

        # storage is optional if we pass it
        service = SummaryService(storage=mock_storage)
        summary = await service.summarize_full(text="Sample text for fallback")

        assert "Fallback overview" in summary
        mock_ai_provider.generate.assert_called_once()
        # Verify generate_with_pdf was NOT called
        assert mock_ai_provider.generate_with_pdf.call_count == 0
