from typing import Any, Dict, Optional

import requests


class PaperAcquisitionService:
    def __init__(self):
        self.semantic_scholar_base_url = (
            "https://api.semanticscholar.org/graph/v1/paper"
        )
        self.arxiv_base_url = "http://export.arxiv.org/api/query"

    def fetch_metadata(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Semantic Scholar APIを使って論文メタデータを取得
        """
        url = f"{self.semantic_scholar_base_url}/search/match"
        params = {
            "query": query,
            "fields": "title,authors,year,abstract,openAccessPdf,citationCount,url",
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    return data["data"][0]
        except Exception as e:
            print(f"Error fetching from Semantic Scholar: {e}")

        # Fallback to arxiv
        try:
            params = {"search_query": f"all:{query}", "start": 0, "max_results": 1}
            response = requests.get(self.arxiv_base_url, params=params, timeout=10)
            if response.status_code == 200:
                # Basic parsing or feedparser usage normally goes here
                import xml.etree.ElementTree as ET

                root = ET.fromstring(response.content)
                prefix = "{http://www.w3.org/2005/Atom}"
                entry = root.find(f"{prefix}entry")
                if entry is not None:
                    title = entry.find(f"{prefix}title").text
                    abstract = entry.find(f"{prefix}summary").text
                    pdf_link = ""
                    for link in entry.findall(f"{prefix}link"):
                        if link.attrib.get("title") == "pdf":
                            pdf_link = link.attrib.get("href")

                    return {
                        "title": title,
                        "abstract": abstract,
                        "openAccessPdf": {"url": pdf_link} if pdf_link else None,
                        "url": entry.find(f"{prefix}id").text,
                    }
        except Exception as e:
            print(f"Error fetching from ArXiv: {e}")

        return None

    def search_papers(self, query: str, limit: int = 3) -> list[Dict[str, Any]]:
        """
        Semantic Scholar APIを使って複数件の論文を検索
        """
        url = f"{self.semantic_scholar_base_url}/search"
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,year,abstract,openAccessPdf,citationCount,url",
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    return data["data"]
        except Exception as e:
            print(f"Error searching from Semantic Scholar: {e}")

        return []

    def acquire_paper(self, paper_title: str) -> Dict[str, Any]:
        """
        タイトルの検索からPDF URLを含んだメタデータを返すラッパーメソッド
        """
        metadata = self.fetch_metadata(paper_title)
        if not metadata:
            return {"status": "not_found", "message": "Could not find metadata"}

        pdf_url = None
        if "openAccessPdf" in metadata and metadata["openAccessPdf"]:
            pdf_url = metadata["openAccessPdf"].get("url")

        status = "success" if pdf_url else "abstract_only"

        return {"status": status, "metadata": metadata, "pdf_url": pdf_url}
