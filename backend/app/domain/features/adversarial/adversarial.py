"""
著者に不利な解釈を与える意見を生成する機能を提供するモジュール
出力例：
    隠れた前提
    未検証条件
    再現性リスク
"""

from app.providers import get_ai_provider
from common.dspy.config import setup_dspy
from common.dspy.modules import AdversarialModule
from common.logger import logger
from common.prompts import ADVERSARIAL_CRITIQUE_FROM_PDF_PROMPT


class AdversarialError(Exception):
    """Adversarial review-specific exception."""

    pass


class AdversarialReviewService:
    """Adversarial review service for critical thinking support."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        setup_dspy()
        self.adversarial_mod = AdversarialModule()

    async def critique(
        self, text: str = "", target_lang: str = "ja", pdf_bytes: bytes | None = None
    ) -> dict:
        """
        Analyze the paper from a critical perspective.

        Args:
            text: The paper text (従来のテキストベース)
            target_lang: Output language
            pdf_bytes: PDFバイナリデータ (PDF直接入力方式)

        Returns:
            Dictionary with critical analysis categories
        """
        from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        try:
            # PDF直接入力方式
            if pdf_bytes:
                logger.debug(
                    "Generating adversarial critique from PDF",
                    extra={"pdf_size": len(pdf_bytes)},
                )
                prompt = ADVERSARIAL_CRITIQUE_FROM_PDF_PROMPT.format(
                    lang_name=lang_name
                )
                raw_response = await self.ai_provider.generate_with_pdf(
                    prompt, pdf_bytes
                )

                # JSON解析を試みる
                import json

                try:
                    # マークダウンで囲まれている可能性があるので除去
                    response_text = raw_response.strip()
                    if response_text.startswith("```json"):
                        response_text = response_text[7:]
                    if response_text.startswith("```"):
                        response_text = response_text[3:]
                    if response_text.endswith("```"):
                        response_text = response_text[:-3]

                    critique = json.loads(response_text.strip())
                    logger.info(
                        "Adversarial review generated from PDF",
                        extra={"pdf_size": len(pdf_bytes)},
                    )
                    return critique
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse JSON from PDF critique, returning raw text"
                    )
                    return {
                        "hidden_assumptions": [],
                        "unverified_conditions": [],
                        "reproducibility_risks": [],
                        "methodology_concerns": [],
                        "overall_assessment": raw_response,
                    }
            else:
                # 従来のテキストベース方式
                logger.debug(
                    "Generating adversarial critique from text",
                    extra={"text_length": len(text)},
                )
                # DSPy version
                res = self.adversarial_mod(paper_text=text[:12000], lang_name=lang_name)

                critique_dict = {
                    "hidden_assumptions": res.hidden_assumptions,
                    "unverified_conditions": res.unverified_conditions,
                    "reproducibility_risks": res.reproducibility_risks,
                    "methodology_concerns": res.methodology_concerns,
                    "overall_assessment": res.overall_assessment,
                }

                issue_count = (
                    len(res.hidden_assumptions)
                    + len(res.unverified_conditions)
                    + len(res.reproducibility_risks)
                    + len(res.methodology_concerns)
                )

                logger.info(
                    "Adversarial review generated from text",
                    extra={"issue_count": issue_count},
                )
                return critique_dict
        except Exception as e:
            logger.exception(
                "Adversarial review failed",
                extra={"error": str(e)},
            )
            return {
                "error": str(e),
                "hidden_assumptions": [],
                "unverified_conditions": [],
                "reproducibility_risks": [],
                "methodology_concerns": [],
                "overall_assessment": "分析に失敗しました",
            }
