"""
GROBID サービスクライアント

GROBID REST API を呼び出し、論文の TEI XML を取得・解析する。
title / authors / abstract / sections を構造化 Markdown に変換して
テキストモード表示を改善する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from common import settings
from common.logger import ServiceLogger

log = ServiceLogger("GROBID")


@dataclass
class GROBIDSection:
    """GROBID が抽出した論文セクション。"""

    heading: str
    body: str


@dataclass
class GROBIDResult:
    """GROBID 解析結果。フィールドは None の場合は未取得。"""

    title: str | None = None
    authors: str | None = None
    abstract: str | None = None
    sections: list[GROBIDSection] = field(default_factory=list)


class GROBIDService:
    """
    GROBID REST API クライアント。

    GROBID_URL が設定されていない場合は全メソッドが即座に None を返す。
    全ての例外（タイムアウト、接続失敗、XML パースエラー）はキャッチし
    ログ出力後 None を返すため、呼び出し元は try/except 不要。
    """

    def __init__(self) -> None:
        self.base_url: str = (settings.get("GROBID_URL", "") or "").rstrip("/")
        self.timeout: int = int(settings.get("GROBID_TIMEOUT", 120))

    def is_available(self) -> bool:
        """GROBID URL が設定されているか確認する。"""
        return bool(self.base_url)

    async def process_fulltext_document(
        self, pdf_bytes: bytes
    ) -> GROBIDResult | None:
        """
        PDF を GROBID の processFulltextDocument エンドポイントに送信し
        TEI XML を解析して GROBIDResult を返す。

        Args:
            pdf_bytes: PDF ファイルのバイト列

        Returns:
            GROBIDResult または None（GROBID 無効・エラー時）
        """
        if not self.is_available():
            return None

        url = f"{self.base_url}/api/processFulltextDocument"
        log.info("process_fulltext_document", "GROBID リクエスト送信", url=url)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    files={"input": ("paper.pdf", pdf_bytes, "application/pdf")},
                    params={"consolidateHeader": "1"},
                )
            if response.status_code != 200:
                log.warning(
                    "process_fulltext_document",
                    "GROBID が非200を返した",
                    status=response.status_code,
                )
                return None

            result = self._parse_tei(response.text)
            log.info(
                "process_fulltext_document",
                "GROBID 解析完了",
                title=result.title,
                sections=len(result.sections),
            )
            return result

        except httpx.TimeoutException:
            log.warning("process_fulltext_document", "GROBID タイムアウト")
            return None
        except Exception as e:
            log.warning(
                "process_fulltext_document", "GROBID エラー", error=str(e)
            )
            return None

    def _parse_tei(self, xml_str: str) -> GROBIDResult:
        """
        TEI XML から title / authors / abstract / sections を抽出する。

        Args:
            xml_str: GROBID が返す TEI XML 文字列

        Returns:
            GROBIDResult（取得できなかったフィールドは None）
        """
        from lxml import etree  # noqa: PLC0415

        result = GROBIDResult()

        try:
            root = etree.fromstring(xml_str.encode("utf-8"))
        except Exception as e:
            log.warning("_parse_tei", "TEI XML パース失敗", error=str(e))
            return result

        ns = {"tei": "http://www.tei-c.org/ns/1.0"}

        # --- タイトル ---
        title_el = root.find(
            ".//tei:teiHeader//tei:titleStmt/tei:title[@type='main']", ns
        )
        if title_el is not None:
            result.title = _clean_text(title_el.text_content() if hasattr(title_el, "text_content") else "".join(title_el.itertext()))

        # --- 著者（"Firstname Lastname" をカンマ区切りで連結）---
        author_names: list[str] = []
        for author_el in root.findall(".//tei:teiHeader//tei:author", ns):
            forename = author_el.find(".//tei:forename", ns)
            surname = author_el.find(".//tei:surname", ns)
            parts = []
            if forename is not None and forename.text:
                parts.append(forename.text.strip())
            if surname is not None and surname.text:
                parts.append(surname.text.strip())
            name = " ".join(parts).strip()
            if name:
                author_names.append(name)
        if author_names:
            result.authors = ", ".join(author_names)

        # --- アブストラクト ---
        abstract_parts: list[str] = []
        for p in root.findall(".//tei:teiHeader//tei:abstract//tei:p", ns):
            text = _clean_text("".join(p.itertext()))
            if text:
                abstract_parts.append(text)
        if abstract_parts:
            result.abstract = "\n\n".join(abstract_parts)

        # --- セクション（body > div） ---
        for div in root.findall(".//tei:text//tei:body//tei:div", ns):
            head_el = div.find("tei:head", ns)
            heading = ""
            if head_el is not None:
                heading = _clean_text("".join(head_el.itertext()))

            body_parts: list[str] = []
            for p in div.findall("tei:p", ns):
                text = _clean_text("".join(p.itertext()))
                if text:
                    body_parts.append(text)

            body = "\n\n".join(body_parts)
            if heading or body:
                result.sections.append(GROBIDSection(heading=heading, body=body))

        return result

    def build_markdown(self, result: GROBIDResult) -> str:
        """
        GROBIDResult を Markdown に変換する。

        フロントエンドの TextModePage.tsx が MarkdownContent でレンダリングする
        形式に合わせた見出し・段落構造を生成する。

        Args:
            result: GROBIDResult

        Returns:
            構造化 Markdown 文字列。セクションがない場合は空文字列。
        """
        if not result.title and not result.sections:
            return ""

        parts: list[str] = []

        if result.title:
            parts.append(f"# {result.title}")

        if result.authors:
            parts.append(f"**Authors:** {result.authors}")

        if result.abstract:
            parts.append("## Abstract")
            parts.append(result.abstract)

        for section in result.sections:
            if section.heading:
                parts.append(f"## {section.heading}")
            if section.body:
                parts.append(section.body)

        return "\n\n".join(parts)


def _clean_text(text: str) -> str:
    """連続する空白・改行を正規化し前後をトリムする。"""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()
