import os

from src.logger import logger
from src.prompts import (
    CORE_SYSTEM_PROMPT,
    PAPER_SUMMARY_ABSTRACT_PROMPT,
    PAPER_SUMMARY_AI_CONTEXT_PROMPT,
    PAPER_SUMMARY_FULL_PROMPT,
    PAPER_SUMMARY_SECTIONS_PROMPT,
)
from src.providers import get_ai_provider
from src.schemas.summary import FullSummaryResponse
from src.schemas.summary import SectionSummaryList as SectionSummariesResponse

from .translate import SUPPORTED_LANGUAGES


class SummaryError(Exception):
    """要約処理に関する例外"""

    pass


class SummaryService:
    """論文要約サービス"""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = os.getenv("MODEL_SUMMARY", "gemini-2.0-flash")
        # デフォルト: 90万トークン（Gemini 1.5 Flashは100万上限だがマージン確保）
        self.token_limit = int(os.getenv("MAX_INPUT_TOKENS", "900000"))

    async def _truncate_to_token_limit(self, text: str) -> str:
        """
        トークン数を確認し、制限を超える場合は切り詰める。
        API呼び出し節約のため、文字数ベースのヒューリスティック判定を併用。
        """
        # 文字数が制限値より大幅に少ない場合はスキップ
        if len(text) < self.token_limit:
            return text

        count = await self.ai_provider.count_tokens(text, model=self.model)
        if count <= self.token_limit:
            return text

        logger.warning(f"Token limit exceeded: {count} > {self.token_limit}. Truncating...")

        # 簡易的な反復切り詰め
        current_text = text
        while count > self.token_limit:
            ratio = self.token_limit / count
            # 安全マージン 95%
            cut_len = int(len(current_text) * ratio * 0.95)
            current_text = current_text[:cut_len]
            count = await self.ai_provider.count_tokens(current_text, model=self.model)

        logger.info(f"Truncated to {len(current_text)} chars ({count} tokens)")
        return current_text

    async def summarize_full(self, text: str, target_lang: str = "ja") -> str:
        """
        論文全体の包括的な要約を生成する。

        Args:
            text: 論文全文
            target_lang: 出力言語

        Returns:
            構造化された要約テキスト
        """
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        safe_text = await self._truncate_to_token_limit(text)
        prompt = PAPER_SUMMARY_FULL_PROMPT.format(lang_name=lang_name, paper_text=safe_text)

        try:
            logger.debug(
                "Generating full summary",
                extra={"text_length": len(text)},
            )
            analysis: FullSummaryResponse = await self.ai_provider.generate(
                prompt,
                model=self.model,
                response_model=FullSummaryResponse,
                system_instruction=CORE_SYSTEM_PROMPT,
            )

            # 後方互換性のため整形済みテキストを返す
            result_lines = [
                f"## Overview\n{analysis.overview}",
                "\n## Key Contributions",
                *[f"- {item}" for item in analysis.key_contributions],
                f"\n## Methodology\n{analysis.methodology}",
                f"\n## Conclusion\n{analysis.conclusion}",
            ]
            formatted_text = "\n".join(result_lines)

            logger.info(
                "Full summary generated",
                extra={"input_length": len(text), "output_length": len(formatted_text)},
            )
            return formatted_text
        except Exception as e:
            logger.exception(
                "Full summary generation failed",
                extra={"error": str(e), "text_length": len(text)},
            )
            return f"要約の生成に失敗しました: {str(e)}"

    async def summarize_sections(self, text: str, target_lang: str = "ja") -> list[dict]:
        """
        セクションごとの要約を生成する。

        Args:
            text: 論文全文
            target_lang: 出力言語

        Returns:
            セクションタイトルと要約の辞書リスト
        """
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        safe_text = await self._truncate_to_token_limit(text)
        prompt = PAPER_SUMMARY_SECTIONS_PROMPT.format(lang_name=lang_name, paper_text=safe_text)

        try:
            logger.debug(
                "Generating section summary",
                extra={"text_length": len(text)},
            )
            response: SectionSummariesResponse = await self.ai_provider.generate(
                prompt,
                model=self.model,
                response_model=SectionSummariesResponse,
                system_instruction=CORE_SYSTEM_PROMPT,
            )

            logger.info(
                "Section summary generated",
                extra={"section_count": len(response.sections)},
            )
            return [s.model_dump() for s in response.sections]
        except Exception as e:
            logger.exception(
                "Section summary failed",
                extra={"error": str(e)},
            )
            return [{"section": "Error", "summary": f"要約生成に失敗: {e}"}]

    async def summarize_abstract(self, text: str, target_lang: str = "ja") -> str:
        """
        アブストラクト形式の要約を生成する。

        Args:
            text: 論文テキスト
            target_lang: 出力言語

        Returns:
            簡潔な要旨
        """
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        # 処理速度のため冒頭5万文字のみ使用
        safe_text = await self._truncate_to_token_limit(text[:50000])
        prompt = PAPER_SUMMARY_ABSTRACT_PROMPT.format(lang_name=lang_name, paper_text=safe_text)

        try:
            abstract = await self.ai_provider.generate(
                prompt, model=self.model, system_instruction=CORE_SYSTEM_PROMPT
            )
            logger.info("Abstract summary generated")
            return abstract
        except Exception as e:
            logger.error(f"Abstract generation failed: {e}")
            return f"要旨の生成に失敗しました: {str(e)}"

    async def summarize_context(self, text: str, max_length: int = 500) -> str:
        """
        AIコンテキスト用の短い要約を生成する（最大max_length文字）。
        """
        try:
            # コンテキスト生成には冒頭部分のみ使用
            prompt = PAPER_SUMMARY_AI_CONTEXT_PROMPT.format(
                max_length=max_length, paper_text=text[:20000]
            )
            summary = await self.ai_provider.generate(
                prompt, model=self.model, system_instruction=CORE_SYSTEM_PROMPT
            )
            logger.info(f"Context summary generated (length: {len(summary)})")
            return summary[:max_length]
        except Exception as e:
            logger.error(f"Context summary generation failed: {e}")
            return ""
