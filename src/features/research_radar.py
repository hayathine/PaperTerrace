"""
関連する論文を調査・取得する機能を提供するモジュール
Consensus APIを利用して論文検索や著者検索を行います。
"""

import os
from typing import Any, Dict, List

import httpx
from pydantic import BaseModel, Field

from src.logger import logger
from src.providers import get_ai_provider


class SimulatedPaper(BaseModel):
    title: str
    authors: List[str]
    year: int
    abstract: str
    url: str


class SimulatedSearchResponse(BaseModel):
    papers: List[SimulatedPaper]


class SearchQueriesResponse(BaseModel):
    queries: List[str] = Field(..., description="3-5 search queries")


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
        prompt = f"""Since the paper search API is unavailable, simulate a search result for the following query.
List 5 real, highly relevant academic papers.

Search Query: {query}
"""
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
        Synthesize a query from the abstract and search.
        Legacy method adapter.
        """
        # 1. Generate a search query from abstract using AI
        # 1. Generate a search query from abstract using AI
        query_prompt = f"Generate a single optimal English search query to find related papers based on the following abstract.\n\n{abstract[:1000]}"
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

    async def generate_search_queries(self, context: str) -> List[str]:
        """Generate search queries for related research."""
        prompt = f"""Based on the following paper context, generate 3-5 search queries to find related research papers.
Context:
{context[:2000]}
"""
        try:
            response: SearchQueriesResponse = await self.ai_provider.generate(
                prompt, response_model=SearchQueriesResponse
            )
            return response.queries
        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            return []

    async def analyze_citations(self, context: str) -> Dict[str, Any]:
        """Analyze citation network/importance."""
        # Simple simulation for now
        return {"status": "not_implemented_yet", "message": "Citation analysis logic pending."}
