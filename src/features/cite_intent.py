"""
引用理由の可視化 (Citation Intent Visualization)
論文中の引用がどのような意図（支持、利用、比較、批判など）で行われているかを分析します。
"""

import json
import os
from typing import Any, Dict, List

from src.logger import logger
from src.providers import get_ai_provider


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
    ) -> List[Dict[str, Any]]:
        """
        段落内の引用を特定し、その意図を分類して詳細情報を付与する。

        Args:
            paragraph: 分析対象の段落テキスト
            lang: 出力言語 (デフォルト: 日本語)

        Returns:
            各引用の分析結果リスト
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        prompt = f"""Identify and analyze all "citations" (references to other works) in the following academic text, and classify the intent of each citation.

[Text]
{paragraph}

[Classification Criteria]
- Support: The author supports the findings of the previous research or uses it as evidence for their own claims (e.g., "consistent with", "provides evidence for").
- Use: The author uses/adopts a method, data, software, theory, or tool from the previous research (e.g., "following X", "based on data from Y").
- Contrast: The author compares or contrasts their findings/methods with the previous research (e.g., "in contrast to", "unlike previous work").
- Criticize: The author points out flaws, limitations, or errors in the previous research, or argues against it (e.g., "however, X failed to", "a limitation of").
- Neutral: The author mentions the research as background or context without explicit evaluation or dynamic usage.

[Instructions]
1. Identify the citation strings (e.g., [1], Author et al. (2020), etc.) from the text.
2. Select the most appropriate category from the 5 categories above.
3. Write a brief reason for the classification in {lang_name}.

[Output Format]
Output ONLY a JSON list of objects with the following structure:
[
  {{
    "citation": "the citation string as it appears in the text",
    "intent": "Support | Use | Contrast | Criticize | Neutral",
    "reason": "1-sentence reason for classification in {lang_name}"
  }}
]
"""
        try:
            logger.info(f"Analyzing citation intent for paragraph with model: {self.model}")
            response = await self.ai_provider.generate(prompt, model=self.model)

            # Markdownコードブロックの除去
            clean_res = response.strip()
            if clean_res.startswith("```"):
                clean_res = clean_res.split("```")[1]
                if clean_res.startswith("json"):
                    clean_res = clean_res[4:]

            results = json.loads(clean_res)

            # メタデータのマージ
            enriched_results = []
            for item in results:
                intent = item.get("intent", "Neutral")
                # 不適切なインテント名が返ってきた場合のガード
                if intent not in self.INTENT_MAP:
                    intent = "Neutral"

                meta = self.INTENT_MAP[intent]
                enriched_results.append(
                    {
                        "citation": item.get("citation"),
                        "intent": intent,
                        "label": meta["label"],
                        "icon": meta["icon"],
                        "color": meta["color"],
                        "bg": meta["bg"],
                        "border": meta["border"],
                        "reason": item.get("reason"),
                    }
                )

            logger.info(f"Successfully analyzed {len(enriched_results)} citations.")
            return enriched_results

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse citation intent JSON: {e}")
            return []
        except Exception as e:
            logger.exception(f"Unexpected error in citation intent analysis: {e}")
            return []
