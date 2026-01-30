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
        from src.prompts import (
            AGENT_CLAIM_VERIFY_PROMPT,
            CORE_SYSTEM_PROMPT,
        )

        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        prompt = AGENT_CLAIM_VERIFY_PROMPT.format(paragraph=paragraph, lang_name=lang_name)
        try:
            logger.info(f"Verifying paragraph claims with model: {self.model}")

            # Call AI with search enabled and structured output
            verification: ClaimVerificationResponse = await self.ai_provider.generate(
                prompt,
                model=self.model,
                response_model=ClaimVerificationResponse,
                system_instruction=CORE_SYSTEM_PROMPT,
            )

            return verification.model_dump()

        except Exception as e:
            logger.error(f"Claim verification failed: {e}")
            return {
                "status": "error",
                "summary": "Verification failed",
                "details": "Could not verify claims due to an error.",
                "sources": [],
            }
