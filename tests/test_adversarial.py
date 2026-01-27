"""
Unit tests for AdversarialReviewService.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_critique(mock_ai_provider):
    """Test adversarial critique generation."""
    mock_response = """{
        "hidden_assumptions": [{"assumption": "Test assumption", "risk": "Test risk", "severity": "medium"}],
        "unverified_conditions": [],
        "reproducibility_risks": [],
        "methodology_concerns": [],
        "overall_assessment": "The paper has some issues."
    }"""
    mock_ai_provider.generate = AsyncMock(return_value=mock_response)

    with patch(
        "src.feature.adversarial.get_ai_provider", return_value=mock_ai_provider
    ):
        from src.feature.adversarial import AdversarialReviewService

        service = AdversarialReviewService()
        critique = await service.critique("Sample paper text...")

        assert "hidden_assumptions" in critique
        assert "overall_assessment" in critique


@pytest.mark.asyncio
async def test_identify_limitations(mock_ai_provider):
    """Test limitation identification."""
    mock_response = '[{"limitation": "Sample size", "evidence": "Only 100 samples", "impact": "Limited generalization", "severity": "high"}]'
    mock_ai_provider.generate = AsyncMock(return_value=mock_response)

    with patch(
        "src.feature.adversarial.get_ai_provider", return_value=mock_ai_provider
    ):
        from src.feature.adversarial import AdversarialReviewService

        service = AdversarialReviewService()
        limitations = await service.identify_limitations("Sample paper text...")

        assert isinstance(limitations, list)


@pytest.mark.asyncio
async def test_suggest_counterarguments(mock_ai_provider):
    """Test counterargument generation."""
    mock_response = "1. First counterargument\n2. Second counterargument\n3. Third counterargument"
    mock_ai_provider.generate = AsyncMock(return_value=mock_response)

    with patch(
        "src.feature.adversarial.get_ai_provider", return_value=mock_ai_provider
    ):
        from src.feature.adversarial import AdversarialReviewService

        service = AdversarialReviewService()
        args = await service.suggest_counterarguments("The method is optimal")

        assert isinstance(args, list)
        assert len(args) >= 1
