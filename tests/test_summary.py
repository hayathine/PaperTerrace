"""
Unit tests for SummaryService.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.summary import FullSummaryResponse, SectionSummary, SectionSummaryList


@pytest.mark.asyncio
async def test_summarize_full(mock_ai_provider):
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

        service = SummaryService()
        summary = await service.summarize_full("Sample paper text...")

        assert "Overview" in summary
        assert "This is an overview" in summary
        assert "Contrib 1" in summary
        mock_ai_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_sections(mock_ai_provider):
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

        service = SummaryService()
        sections = await service.summarize_sections("Sample paper text...")

        assert isinstance(sections, list)
        assert len(sections) == 2
        assert sections[0]["section"] == "Introduction"
        mock_ai_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_abstract(mock_ai_provider):
    """Test abstract extraction (Regex based)."""
    # Does NOT call AI

    with patch("src.features.summary.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.features.summary.summary import SummaryService

        service = SummaryService()
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
