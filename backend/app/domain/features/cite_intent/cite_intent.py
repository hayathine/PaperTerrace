import os
from typing import Any

from app.domain.prompts import AGENT_CITE_INTENT_PROMPT, CORE_SYSTEM_PROMPT
from app.logger import logger
from app.providers import get_ai_provider
from app.schemas.gemini_schema import CitationAnalysisResponse


class CiteIntentService:
    """引用意図の分析と可視化を行うサービス"""

    # 引用意図の定義と対応するメタデータ
    INTENT_MAP = {
        "Support": {
            "icon": "✅",
            "label": "支持・裏付け",
            "color": "text-emerald-600",
            "bg": "bg-emerald-50",
            "border": "border-emerald-100",
        },
        "Use": {
            "icon": "🛠️",
            "label": "手法・データの利用",
            "color": "text-blue-600",
            "bg": "bg-blue-50",
            "border": "border-blue-100",
        },
        "Contrast": {
            "icon": "⚖️",
            "label": "比較・対照",
            "color": "text-amber-600",
            "bg": "bg-amber-50",
            "border": "border-amber-100",
        },
        "Criticize": {
            "icon": "⚠️",
            "label": "批判・課題指摘",
            "color": "text-rose-600",
            "bg": "bg-rose-50",
            "border": "border-rose-100",
        },
        "Neutral": {
            "icon": "📝",
            "label": "言及・背景",
            "color": "text-slate-600",
            "bg": "bg-slate-50",
            "border": "border-slate-100",
        },
    }

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = os.getenv("MODEL_CITE_INTENT", "gemini-2.0-flash")

    async def analyze_paragraph_citations(
        self, paragraph: str, lang: str = "ja"
    ) -> list[dict[str, Any]]:
        """
        段落内の引用を特定し、その意図を分類して詳細情報を付与する。
        """
        from ..translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        prompt = AGENT_CITE_INTENT_PROMPT.format(paragraph=paragraph, lang_name=lang_name)
        try:
            logger.info(f"Analyzing citation intent for paragraph with model: {self.model}")

            # 使用するモデルを指定して構造化出力を依頼
            analysis: CitationAnalysisResponse = await self.ai_provider.generate(
                prompt,
                model=self.model,
                response_model=CitationAnalysisResponse,
                system_instruction=CORE_SYSTEM_PROMPT,
            )

            # メタデータのマージ
            enriched_results = []
            for item in analysis.citations:
                intent = item.intent
                # 不適切なインテント名が返ってきた場合のガード
                if intent not in self.INTENT_MAP:
                    intent = "Neutral"

                meta = self.INTENT_MAP[intent]
                enriched_results.append(
                    {
                        "citation": item.citation,
                        "intent": intent,
                        "label": meta["label"],
                        "icon": meta["icon"],
                        "color": meta["color"],
                        "bg": meta["bg"],
                        "border": meta["border"],
                        "reason": item.reason,
                    }
                )

            logger.info(f"Successfully analyzed {len(enriched_results)} citations.")
            return enriched_results

        except Exception as e:
            logger.exception(f"Unexpected error in citation intent analysis: {e}")
            return []
