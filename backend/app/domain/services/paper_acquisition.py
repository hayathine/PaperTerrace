import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional

import requests

from common import settings
from common.logger import ServiceLogger

log = ServiceLogger("PaperAcquisition")


def _reconstruct_abstract(inverted_index: Optional[Dict[str, list]]) -> Optional[str]:
    """OpenAlex の転置インデックス形式からアブストラクト文字列を復元する。"""
    if not inverted_index:
        return None
    word_positions: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort(key=lambda x: x[0])
    return " ".join(word for _, word in word_positions)


class PaperAcquisitionService:
    def __init__(self):
        self.semantic_scholar_base_url = (
            "https://api.semanticscholar.org/graph/v1/paper"
        )
        self.arxiv_base_url = "http://export.arxiv.org/api/query"
        self.pubmed_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.openalex_base_url = "https://api.openalex.org/works"
        self.crossref_base_url = "https://api.crossref.org/works"
        self.core_base_url = "https://api.core.ac.uk/v3/search/works"
        self.core_api_key = settings.get("CORE_API_KEY", default=None) or None

    # ------------------------------------------------------------------
    # 個別ソース検索
    # ------------------------------------------------------------------

    def _search_semantic_scholar(self, query: str, limit: int) -> list[Dict[str, Any]]:
        """Semantic Scholar API で検索する。"""
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
                results = []
                for item in data.get("data", []):
                    item.setdefault("source", "Semantic Scholar")
                    results.append(item)
                return results
        except Exception as e:
            log.error(
                "_search_semantic_scholar", "Error", error=str(e), query=query
            )
        return []

    def _search_arxiv(self, query: str, limit: int) -> list[Dict[str, Any]]:
        """arXiv API (Atom/XML) で検索する。"""
        params = {"search_query": f"all:{query}", "start": 0, "max_results": limit}
        try:
            response = requests.get(self.arxiv_base_url, params=params, timeout=10)
            if response.status_code != 200:
                return []

            root = ET.fromstring(response.content)
            ns = "{http://www.w3.org/2005/Atom}"
            results = []
            for entry in root.findall(f"{ns}entry"):
                title_elem = entry.find(f"{ns}title")
                summary_elem = entry.find(f"{ns}summary")
                id_elem = entry.find(f"{ns}id")

                authors = []
                for author in entry.findall(f"{ns}author"):
                    name_elem = author.find(f"{ns}name")
                    if name_elem is not None:
                        authors.append({"name": name_elem.text})

                pdf_link = None
                for link in entry.findall(f"{ns}link"):
                    if link.attrib.get("title") == "pdf":
                        pdf_link = link.attrib.get("href")

                year = None
                published_elem = entry.find(f"{ns}published")
                if published_elem is not None and published_elem.text:
                    try:
                        year = int(published_elem.text[:4])
                    except ValueError:
                        pass

                results.append(
                    {
                        "title": (title_elem.text or "").strip()
                        if title_elem is not None
                        else "",
                        "abstract": (summary_elem.text or "").strip()
                        if summary_elem is not None
                        else "",
                        "authors": authors,
                        "year": year,
                        "url": id_elem.text if id_elem is not None else None,
                        "openAccessPdf": {"url": pdf_link} if pdf_link else None,
                        "citationCount": None,
                        "source": "arXiv",
                    }
                )
            return results
        except Exception as e:
            log.error("_search_arxiv", "Error", error=str(e), query=query)
        return []

    def _search_pubmed(self, query: str, limit: int) -> list[Dict[str, Any]]:
        """PubMed E-utilities で検索する（esearch → esummary の2段階）。"""
        try:
            search_resp = requests.get(
                f"{self.pubmed_base_url}/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"},
                timeout=10,
            )
            if search_resp.status_code != 200:
                return []

            ids: list[str] = search_resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []

            summary_resp = requests.get(
                f"{self.pubmed_base_url}/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
                timeout=10,
            )
            if summary_resp.status_code != 200:
                return []

            result_data = summary_resp.json().get("result", {})
            results = []
            for pmid in ids:
                item = result_data.get(pmid)
                if not item:
                    continue

                authors = [{"name": a.get("name", "")} for a in item.get("authors", [])]
                year = None
                pub_date: str = item.get("pubdate", "")
                if pub_date:
                    try:
                        year = int(pub_date[:4])
                    except ValueError:
                        pass

                results.append(
                    {
                        "title": item.get("title", ""),
                        "abstract": None,
                        "authors": authors,
                        "year": year,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "openAccessPdf": None,
                        "citationCount": None,
                        "source": "PubMed",
                    }
                )
            return results
        except Exception as e:
            log.error("_search_pubmed", "Error", error=str(e), query=query)
        return []

    def _search_openalex(self, query: str, limit: int) -> list[Dict[str, Any]]:
        """OpenAlex API で検索する。アブストラクトは転置インデックスから復元する。"""
        params = {
            "search": query,
            "per-page": limit,
            "select": "title,authorships,publication_year,abstract_inverted_index,primary_location,cited_by_count,id",
        }
        try:
            response = requests.get(
                self.openalex_base_url,
                params=params,
                headers={
                    "User-Agent": "PaperTerrace/1.0 (mailto:contact@paperterrace.page)"
                },
                timeout=10,
            )
            if response.status_code != 200:
                return []

            results = []
            for item in response.json().get("results", []):
                authors = [
                    {"name": a.get("author", {}).get("display_name", "")}
                    for a in item.get("authorships", [])
                ]

                abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))

                pdf_url = None
                primary = item.get("primary_location") or {}
                if primary.get("is_oa") and primary.get("pdf_url"):
                    pdf_url = primary["pdf_url"]

                results.append(
                    {
                        "title": item.get("title", ""),
                        "abstract": abstract,
                        "authors": authors,
                        "year": item.get("publication_year"),
                        "url": item.get("id"),
                        "openAccessPdf": {"url": pdf_url} if pdf_url else None,
                        "citationCount": item.get("cited_by_count"),
                        "source": "OpenAlex",
                    }
                )
            return results
        except Exception as e:
            log.error("_search_openalex", "Error", error=str(e), query=query)
        return []

    def _search_crossref(self, query: str, limit: int) -> list[Dict[str, Any]]:
        """Crossref API で検索する。アブストラクトの JATS タグを除去する。"""
        params = {
            "query": query,
            "rows": limit,
            "select": "title,author,published,abstract,URL,is-referenced-by-count",
        }
        try:
            response = requests.get(
                self.crossref_base_url,
                params=params,
                headers={
                    "User-Agent": "PaperTerrace/1.0 (mailto:contact@paperterrace.page)"
                },
                timeout=10,
            )
            if response.status_code != 200:
                return []

            results = []
            for item in response.json().get("message", {}).get("items", []):
                title = (item.get("title") or [""])[0]
                authors = [
                    {
                        "name": f"{a.get('given', '')} {a.get('family', '')}".strip()
                    }
                    for a in item.get("author", [])
                ]

                pub_parts = item.get("published", {}).get("date-parts", [[]])
                year = pub_parts[0][0] if pub_parts and pub_parts[0] else None

                abstract = item.get("abstract")
                if abstract:
                    abstract = re.sub(r"<[^>]+>", "", abstract).strip()

                results.append(
                    {
                        "title": title,
                        "abstract": abstract,
                        "authors": authors,
                        "year": year,
                        "url": item.get("URL"),
                        "openAccessPdf": None,
                        "citationCount": item.get("is-referenced-by-count"),
                        "source": "Crossref",
                    }
                )
            return results
        except Exception as e:
            log.error("_search_crossref", "Error", error=str(e), query=query)
        return []

    def _search_core(self, query: str, limit: int) -> list[Dict[str, Any]]:
        """CORE API で検索する。API キーが未設定の場合はスキップする。"""
        if not self.core_api_key:
            return []

        try:
            response = requests.get(
                self.core_base_url,
                params={"q": query, "limit": limit},
                headers={"Authorization": f"Bearer {self.core_api_key}"},
                timeout=10,
            )
            if response.status_code != 200:
                return []

            results = []
            for item in response.json().get("results", []):
                authors = [{"name": a} for a in (item.get("authors") or [])]

                year = None
                pub_date = item.get("publishedDate") or item.get("yearPublished")
                if pub_date:
                    try:
                        year = int(str(pub_date)[:4])
                    except (ValueError, TypeError):
                        pass

                pdf_url = item.get("downloadUrl")
                source_urls: list = item.get("sourceFulltextUrls") or []
                url = source_urls[0] if source_urls else str(item.get("id", ""))

                results.append(
                    {
                        "title": item.get("title", ""),
                        "abstract": item.get("abstract"),
                        "authors": authors,
                        "year": year,
                        "url": url,
                        "openAccessPdf": {"url": pdf_url} if pdf_url else None,
                        "citationCount": None,
                        "source": "CORE",
                    }
                )
            return results
        except Exception as e:
            log.error("_search_core", "Error", error=str(e), query=query)
        return []

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def fetch_metadata(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Semantic Scholar の exact-match エンドポイントで論文メタデータを1件取得する。
        失敗時は arXiv にフォールバックする。
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
                if "data" in data and data["data"]:
                    return data["data"][0]
        except Exception as e:
            log.error(
                "fetch_metadata",
                "Error fetching from Semantic Scholar",
                error=str(e),
                query=query,
            )

        # Fallback to arXiv
        results = self._search_arxiv(query, limit=1)
        if results:
            return results[0]

        return None

    def search_papers(self, query: str, limit: int = 3) -> list[Dict[str, Any]]:
        """
        Semantic Scholar / arXiv / PubMed / OpenAlex / Crossref / CORE を
        並列検索し、タイトルで重複排除した結果を返す。
        """
        sources = [
            self._search_semantic_scholar,
            self._search_arxiv,
            self._search_pubmed,
            self._search_openalex,
            self._search_crossref,
            self._search_core,
        ]

        all_results: list[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            futures = {executor.submit(fn, query, limit): fn.__name__ for fn in sources}
            for future in as_completed(futures):
                try:
                    all_results.extend(future.result())
                except Exception as e:
                    log.error("search_papers", "Source error", error=str(e))

        # タイトルで重複排除（大文字小文字を無視）
        seen: set[str] = set()
        deduped: list[Dict[str, Any]] = []
        for paper in all_results:
            key = (paper.get("title") or "").lower().strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(paper)

        return deduped

    def acquire_paper(self, paper_title: str) -> Dict[str, Any]:
        """
        タイトル検索から PDF URL を含むメタデータを返すラッパーメソッド。
        """
        metadata = self.fetch_metadata(paper_title)
        if not metadata:
            return {"status": "not_found", "message": "Could not find metadata"}

        pdf_url = None
        if "openAccessPdf" in metadata and metadata["openAccessPdf"]:
            pdf_url = metadata["openAccessPdf"].get("url")

        status = "success" if pdf_url else "abstract_only"
        return {"status": status, "metadata": metadata, "pdf_url": pdf_url}
