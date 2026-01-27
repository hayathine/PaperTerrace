"""
関連する論文を調査・取得する機能を提供するモジュール
"""

import json

from src.logger import logger
from src.providers import get_ai_provider


class ResearchRadarError(Exception):
    """Research Radar-specific exception."""

    pass


class ResearchRadarService:
    """Research Radar service for finding related papers."""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    async def find_related_papers(self, abstract: str) -> list[dict]:
        """
        Extract related paper suggestions based on the abstract.

        Args:
            abstract: The paper's abstract or summary

        Returns:
            List of suggested related papers with title, authors, relevance
        """
        prompt = f"""以下の論文の概要を分析し、関連する可能性のある論文を5件提案してください。

【概要】
{abstract[:3000]}

以下のJSON形式で出力してください：
[
  {{
    "title": "推定される論文タイトル",
    "authors": "推定される著者名",
    "year": "推定される発表年",
    "relevance": "この論文との関連性の説明（1-2文）",
    "search_query": "Google Scholarで検索するためのクエリ"
  }}
]

実在する可能性が高い論文を提案してください。JSONのみを出力してください。"""

        try:
            logger.debug(
                "Finding related papers",
                extra={"abstract_length": len(abstract)},
            )
            response = await self.ai_provider.generate(prompt)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            papers = json.loads(response)

            logger.info(
                "Related papers found",
                extra={"paper_count": len(papers)},
            )
            return papers
        except json.JSONDecodeError as e:
            logger.exception(
                "Failed to parse related papers JSON",
                extra={"error": str(e)},
            )
            return []
        except Exception as e:
            logger.exception(
                "Related papers search failed",
                extra={"error": str(e)},
            )
            return []

    async def generate_search_queries(self, text: str) -> list[str]:
        """
        Generate search queries for finding related work.

        Args:
            text: The paper text

        Returns:
            List of search query strings
        """
        prompt = f"""以下の論文に関連する論文を検索するためのクエリを5つ生成してください。

【論文テキスト】
{text[:5000]}

各クエリは、Google ScholarやSemantic Scholarで効果的に検索できる形式にしてください。
クエリのみを改行区切りで出力してください。"""

        try:
            response = await self.ai_provider.generate(prompt)
            queries = [q.strip() for q in response.strip().split("\n") if q.strip()]
            logger.info(f"Generated {len(queries)} search queries")
            return queries[:5]
        except Exception as e:
            logger.error(f"Search query generation failed: {e}")
            return []

    async def analyze_citations(self, text: str) -> list[dict]:
        """
        Analyze citation patterns and intent in the paper.

        Args:
            text: The paper text

        Returns:
            List of citations with their intent analysis
        """
        prompt = f"""以下の論文から引用を抽出し、その引用意図を分析してください。

【論文テキスト】
{text[:10000]}

以下のJSON形式で出力してください：
[
  {{
    "citation": "引用されている論文や著者",
    "context": "引用されている文脈（1文）",
    "intent": "Support/Use/Contrast/Criticize のいずれか",
    "explanation": "引用意図の説明"
  }}
]

最大10件まで。JSONのみを出力してください。"""

        try:
            response = await self.ai_provider.generate(prompt)
            import json

            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            citations = json.loads(response)
            logger.info(f"Analyzed {len(citations)} citations")
            return citations
        except Exception as e:
            logger.error(f"Citation analysis failed: {e}")
            return []
