"""
Unit tests for SummaryService.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_summarize_full(mock_ai_provider):
    """Test full paper summarization."""
    mock_ai_provider.generate = AsyncMock(
        return_value="## 概要\nThis is a summary."
    )

    with patch("src.feature.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.feature.summary import SummaryService

        service = SummaryService()
        summary = await service.summarize_full("Sample paper text...")

        assert "概要" in summary or "summary" in summary.lower()
        mock_ai_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_sections(mock_ai_provider):
    """Test section-by-section summarization."""
    mock_ai_provider.generate = AsyncMock(
        return_value='[{"section": "Introduction", "summary": "Overview of the paper"}]'
    )

    with patch("src.feature.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.feature.summary import SummaryService

        service = SummaryService()
        sections = await service.summarize_sections("Sample paper text...")

        assert isinstance(sections, list)
        assert len(sections) > 0


@pytest.mark.asyncio
async def test_summarize_abstract(mock_ai_provider):
    """Test abstract-style summary generation."""
    mock_ai_provider.generate = AsyncMock(
        return_value="本研究は自然言語処理の新手法を提案する。"
    )

    with patch("src.feature.summary.get_ai_provider", return_value=mock_ai_provider):
        from src.feature.summary import SummaryService

        service = SummaryService()
        abstract = await service.summarize_abstract("Sample paper text...")

        assert len(abstract) > 0
        mock_ai_provider.generate.assert_called_once()
