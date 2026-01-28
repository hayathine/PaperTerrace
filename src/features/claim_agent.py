import os
from typing import List

from pydantic import BaseModel, Field

from src.logger import logger
from src.providers import get_ai_provider


class ClaimVerificationResponse(BaseModel):
    """結果報告のための構造化データモデル"""

    status: str = Field(..., description="warning | verified | neutral")
    summary: str = Field(
        ..., description="Short summary of the verification result (max 100 chars)."
    )
    details: str = Field(
        ...,
        description="Detailed report citing sources found during search. Mention if reproducible or accepted, or highlight doubts.",
    )
    sources: List[str] = Field(
        default_factory=list, description="List of URL or source names found"
    )


class ClaimVerificationService:
    """Service for autonomous claim verification."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = os.getenv("MODEL_CLAIM", "gemini-2.0-flash")

    async def verify_paragraph(self, paragraph: str, lang: str = "ja") -> dict:
        """
        Verify claims in a paragraph using Web Search.
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        prompt = f"""You are an autonomous "Evidence Checker".
Your task is to critically verify the claims made in the following text by cross-referencing with external information (Web Search).

[Target Text]
{paragraph}

[Instructions]
1. Identify the core claims (e.g., "Outperforms SOTA by 10%", "New architecture X").
2. AUTONOMOUSLY SEARCH for these claims online. Look for:
   - Reproducibility reports (GitHub issues, Twitter discussions, Reddit threads).
   - Contradictory papers (Google Scholar).
   - Consensus in the community.
3. Report your findings in {lang_name}.
"""
        try:
            logger.info(f"Verifying paragraph claims with model: {self.model}")

            # Call AI with search enabled and structured output
            data: ClaimVerificationResponse = await self.ai_provider.generate(
                prompt,
                model=self.model,
                enable_search=True,
                response_model=ClaimVerificationResponse,
            )

            return data.model_dump()

        except Exception as e:
            logger.error(f"Claim verification failed: {e}")
            return {
                "status": "error",
                "summary": "Verification failed",
                "details": "Could not verify claims due to an error.",
                "sources": [],
            }
