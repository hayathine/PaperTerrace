import os
from typing import Any, Dict, List

import httpx

from app.domain.prompts import (
    RADAR_GENERATE_QUERY_ABSTRACT_PROMPT,
    RADAR_GENERATE_QUERY_CONTEXT_PROMPT,
    RADAR_SIMULATE_SEARCH_PROMPT,
)
from app.logger import logger
from app.providers import get_ai_provider
from app.schemas.gemini_schema import (
    SearchQueriesResponse,
    SimulatedSearchResponse,
)


class ResearchRadarError(Exception):
    """Research Radarに関する例外"""

    pass


class ResearchRadarService:
    """Consensus APIを利用した関連論文検索サービス"""

    BASE_URL = "https://consensus.app/api"

    def __init__(self):
        self.api_key = os.getenv("CONSENSUS_API_KEY")
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self.ai_provider = get_ai_provider()

    async def close(self):
        await self.client.aclose()

    async def paper_search(
        self,
        query: str,
        year_min: int = 2020,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Consensus APIを使用して論文を検索する。

        Args:
            query: 検索クエリ
            year_min: 最低発行年
            limit: 取得件数

        Returns:
            論文情報のリスト
        """
        if not self.api_key:
            logger.warning("CONSENSUS_API_KEY not found. Using AI simulation fallback.")
            return await self._simulate_paper_search(query)

        try:
            logger.info(f"Consensus paper search: query='{query}'")
            # NOTE: APIエンドポイントは仮定（正式ドキュメントに基づく調整が必要）
            response = await self.client.get(
                "/paper_search",
                params={
                    "query": query,
                    "year_min": year_min,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("papers", [])
        except httpx.HTTPError as e:
            logger.error(f"Consensus API error: {e}")
            return []
        except Exception as e:
            logger.exception(f"Unexpected error in paper_search: {e}")
            return []

    async def author_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """著者検索を実行する。"""
        if not self.api_key:
            return []

        try:
            logger.info(f"Consensus author search: query='{query}'")
            response = await self.client.get(
                "/author_search", params={"query": query, "limit": limit}
            )
            response.raise_for_status()
            return response.json().get("authors", [])
        except Exception as e:
            logger.error(f"Author search failed: {e}")
            return []

    async def _simulate_paper_search(self, query: str) -> List[Dict[str, Any]]:
        """API利用不可時にAIによる検索結果シミュレーションを行う。"""
        prompt = RADAR_SIMULATE_SEARCH_PROMPT.format(query=query)
        try:
            response: SimulatedSearchResponse = await self.ai_provider.generate(
                prompt, response_model=SimulatedSearchResponse
            )
            return [p.model_dump() for p in response.papers]
        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            return []

    async def find_related_papers(self, abstract: str) -> List[Dict[str, Any]]:
        """
        アブストラクトからクエリを生成して関連論文を検索する。
        """
        # 1. AIを使用して検索クエリを生成
        prompt = RADAR_GENERATE_QUERY_ABSTRACT_PROMPT.format(abstract=abstract[:4000])
        search_query = await self.ai_provider.generate(prompt)
        search_query = search_query.strip().strip('"')

        # 2. 検索実行
        return await self.paper_search(search_query)

    async def get_author_profile_and_papers(self, author_name: str) -> Dict[str, Any]:
        """
        ペルソナ生成のために著者プロフィールと主要論文を取得する。
        """
        # 1. 著者検索
        authors = await self.author_search(author_name, limit=1)
        if not authors:
            return {}

        author_id = authors[0].get("id")

        # 2. 論文取得（APIキーがある場合）
        if self.api_key and author_id:
            try:
                response = await self.client.get(
                    f"/authors/{author_id}/papers", params={"limit": 10}
                )
                papers = response.json().get("papers", [])
                return {"profile": authors[0], "papers": papers}
            except Exception:
                return {"profile": authors[0], "papers": []}

        return {"profile": authors[0], "papers": []}

    async def generate_search_queries(self, context: str) -> List[str]:
        """関連研究探索用の検索クエリを生成する。"""
        prompt = RADAR_GENERATE_QUERY_CONTEXT_PROMPT.format(context=context[:6000])
        try:
            response: SearchQueriesResponse = await self.ai_provider.generate(
                prompt, response_model=SearchQueriesResponse
            )
            return response.queries
        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            return []

    async def analyze_citations(self, context: str) -> Dict[str, Any]:
        """引用ネットワークの分析（未実装）"""
        return {"status": "not_implemented_yet", "message": "Citation analysis logic pending."}
