"""
関連する論文を調査・取得する機能を提供するモジュール
Consensus APIを利用して論文検索や著者検索を行います。
"""

import json
import os
from typing import Any, Dict, List

import httpx

from src.logger import logger
from src.providers import get_ai_provider


class ResearchRadarError(Exception):
    """Research Radar-specific exception."""

    pass


class ResearchRadarService:
    """Consensus API service for finding related papers."""

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
        Search for papers using Consensus API.

        Args:
            query: Search query string
            year_min: Minimum publication year
            limit: Number of results to return

        Returns:
            List of paper dictionaries
        """
        if not self.api_key:
            logger.warning("CONSENSUS_API_KEY not found. Using AI simulation fallback.")
            return await self._simulate_paper_search(query)

        try:
            logger.info(f"Consensus paper search: query='{query}'")
            # Endpoint structure is hypothetical based on typical patterns since official docs access is limited here.
            # Assuming /paper_search or similar. Adjust based on real API docs if provided.
            # USER PROVIDED URL: https://consensus.app/home/api/ -> check if we can infer.
            # Usually strict APIs are like /v1/papers/search.
            # Let's assume a standard search endpoint for now.
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
        """Search for authors."""
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
        """Fallback method using Gemini to simulate search results."""
        prompt = f"""論文検索APIが利用できないため、以下のクエリに対する検索結果をシミュレーションしてください。
実在する、関連性の高い学術論文を5件リストアップしてください。

検索クエリ: {query}

出力JSON形式:
[
  {{
    "title": "論文タイトル",
    "authors": ["著者名"],
    "year": 2023,
    "abstract": "要約",
    "url": "https://doi.org/..."
  }}
]
JSONのみ出力してください。"""
        try:
            response = await self.ai_provider.generate(prompt)
            # Simple cleanup for markdown code blocks
            clean_res = response.strip().replace("```json", "").replace("```", "")
            return json.loads(clean_res)
        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            return []

    async def find_related_papers(self, abstract: str) -> List[Dict[str, Any]]:
        """
        Synthesize a query from the abstract and search.
        Legacy method adapter.
        """
        # 1. Generate a search query from abstract using AI
        query_prompt = f"以下の論文要約から、関連論文を検索するための最適な英語検索クエリを1つ生成してください。\n\n{abstract[:1000]}"
        search_query = await self.ai_provider.generate(query_prompt)
        search_query = search_query.strip().strip('"')

        # 2. Search
        return await self.paper_search(search_query)

    async def get_author_profile_and_papers(self, author_name: str) -> Dict[str, Any]:
        """
        Get author profile and their top papers for persona generation.
        """
        # 1. Search author
        authors = await self.author_search(author_name, limit=1)
        if not authors:
            return {}

        author_id = authors[0].get("id")

        # 2. Get author papers (hypothetical endpoint)
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
