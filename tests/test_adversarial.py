"""
Unit tests for AdversarialReviewService.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.adversarial import (
    AdversarialCritiqueResponse,
    HiddenAssumption,
)


@pytest.mark.asyncio
async def test_critique(mock_ai_provider):
    """Test adversarial critique generation."""
    mock_response = AdversarialCritiqueResponse(
        hidden_assumptions=[
            HiddenAssumption(assumption="Test assumption", risk="Test risk", severity="medium")
        ],
        unverified_conditions=[],
        reproducibility_risks=[],
        methodology_concerns=[],
        overall_assessment="The paper has some issues.",
    )
    mock_ai_provider.generate = AsyncMock(return_value=mock_response)

    with patch(
        "src.features.adversarial.adversarial.get_ai_provider", return_value=mock_ai_provider
    ):
        from src.features.adversarial import AdversarialReviewService

        service = AdversarialReviewService()
        critique = await service.critique("Sample paper text...")

        assert "hidden_assumptions" in critique
        assert len(critique["hidden_assumptions"]) == 1
        assert critique["hidden_assumptions"][0]["risk"] == "Test risk"
        assert "overall_assessment" in critique

        # Verify AI call
        mock_ai_provider.generate.assert_called_once()
