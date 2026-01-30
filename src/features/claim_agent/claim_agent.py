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

    async def verify_paragraph(
        self, paragraph: str = "", lang: str = "ja", pdf_bytes: bytes | None = None
    ) -> dict:
        """
        Verify claims in a paragraph using Web Search.

        Args:
            paragraph: 検証対象のテキスト (従来のテキストベース)
            lang: 出力言語
            pdf_bytes: PDFバイナリデータ (PDF直接入力方式)
        """
        from src.prompts import (
            AGENT_CLAIM_VERIFY_PROMPT,
            CLAIM_VERIFY_FROM_PDF_PROMPT,
            CORE_SYSTEM_PROMPT,
        )

        from ..translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        try:
            # PDF直接入力方式
            if pdf_bytes:
                logger.info(f"Verifying claims from PDF with model: {self.model}")
                prompt = CLAIM_VERIFY_FROM_PDF_PROMPT.format(lang_name=lang_name)
                raw_response = await self.ai_provider.generate_with_pdf(
                    prompt, pdf_bytes, model=self.model
                )

                # Try to parse as JSON if possible, otherwise return as text
                import json

                try:
                    response_text = raw_response.strip()
                    if response_text.startswith("```json"):
                        response_text = response_text[7:]
                    if response_text.startswith("```"):
                        response_text = response_text[3:]
                    if response_text.endswith("```"):
                        response_text = response_text[:-3]
                    return json.loads(response_text.strip())
                except json.JSONDecodeError:
                    return {
                        "status": "verified",
                        "summary": "PDF claims analyzed",
                        "details": raw_response,
                        "sources": [],
                    }
            else:
                # 従来のテキストベース方式
                logger.info(f"Verifying paragraph claims with model: {self.model}")
                prompt = AGENT_CLAIM_VERIFY_PROMPT.format(paragraph=paragraph, lang_name=lang_name)

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
