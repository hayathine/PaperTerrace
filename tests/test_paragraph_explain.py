"""
Unit tests for ParagraphExplainService.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.paragraph_analysis import ParagraphExplanationResponse


@pytest.mark.asyncio
async def test_explain(mock_ai_provider):
    """Test paragraph explanation."""
    mock_response = ParagraphExplanationResponse(
        main_claim="Claim",
        background_knowledge="Background",
        logic_flow="Flow",
        key_points=["Point 1"],
    )
    mock_ai_provider.generate = AsyncMock(return_value=mock_response)

    with patch(
        "src.features.paragraph_explain.paragraph_explain.get_ai_provider",
        return_value=mock_ai_provider,
    ):
        from src.features.paragraph_explain import ParagraphExplainService

        service = ParagraphExplainService()
        result = await service.explain("Sample paragraph", full_context="context")

        assert "Claim" in result
        assert "Point 1" in result
        mock_ai_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_translate_paragraph(mock_ai_provider):
    """Test paragraph translation."""
    mock_ai_provider.generate = AsyncMock(return_value="Translation")

    with patch(
        "src.features.paragraph_explain.paragraph_explain.get_ai_provider",
        return_value=mock_ai_provider,
    ):
        from src.features.paragraph_explain import ParagraphExplainService

        service = ParagraphExplainService()
        result = await service.translate_paragraph("Sample paragraph", full_context="context")

        assert result == "Translation"
        mock_ai_provider.generate.assert_called_once()
