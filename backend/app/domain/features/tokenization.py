import asyncio
import os
import re

# Use the same executor if possible, or create a new one
from concurrent.futures import ThreadPoolExecutor

from app.domain.services.nlp_service import NLPService
from app.providers import get_storage_provider

from common.logger import logger
from common.utils.text import clean_text_for_tokenization

from .word_analysis import WordAnalysisService

executor = ThreadPoolExecutor(max_workers=4)


class TokenizationService:
    def __init__(self):
        self.nlp_service = NLPService()
        self.word_analysis = WordAnalysisService()
        self.nlp = self.nlp_service.get_nlp()
        self.redis = self.word_analysis.redis

    async def tokenize_stream(
        self,
        text: str,
        paper_id: str | None = None,
        target_id: str = "paper-content",
        id_prefix: str = "p",
        save_to_db: bool = True,
        lang: str = "ja",
    ):
        """Processes text paragraph by paragraph and yields interactive HTML."""
        paragraphs = re.split(r"\n{2,}", text.replace("\r\n", "\n"))
        loop = asyncio.get_event_loop()
        all_html_parts: dict[str, str] = {}
        unknown_words = set()

        for i, p_text in enumerate(paragraphs):
            p_text = clean_text_for_tokenization(p_text)
            if not p_text:
                continue

            unique_id = f"{id_prefix}-{i}"
            doc = await loop.run_in_executor(executor, self.nlp, p_text)
            p_tokens_html = []

            for j, token in enumerate(doc):
                whitespace = token.whitespace_

                if token.is_punct or token.is_space:
                    p_tokens_html.append(f"<span>{token.text}</span>{whitespace}")
                    continue

                lemma = token.lemma_.lower()

                # Cache and Dictionary Check
                if lemma not in self.word_analysis.word_cache:
                    # Quick check memory cache
                    if lemma in self.word_analysis.translation_cache:
                        self.word_analysis.word_cache[lemma] = False
                    else:
                        # Redis/Dict check
                        cached_trans = self.redis.get(f"trans:{lang}:{lemma}")
                        if cached_trans:
                            self.word_analysis.translation_cache[lemma] = cached_trans
                            self.word_analysis.word_cache[lemma] = False
                        else:
                            # Try Local Machine Translation
                            local_trans = await loop.run_in_executor(
                                executor,
                                self.word_analysis.local_translator.translate,
                                lemma,
                            )
                            if local_trans:
                                self.word_analysis.word_cache[lemma] = False
                                self.word_analysis.translation_cache[lemma] = (
                                    local_trans
                                )
                                self.redis.set(
                                    f"trans:{lang}:{lemma}", local_trans, expire=604800
                                )
                            else:
                                self.word_analysis.word_cache[lemma] = False
                                unknown_words.add(lemma)

                color = (
                    "border-transparent hover:border-indigo-300 hover:bg-indigo-50"
                    if self.word_analysis.word_cache.get(lemma, False)
                    else "border-transparent hover:border-purple-300 hover:bg-purple-50"
                )

                paper_param = f"&paper_id={paper_id}" if paper_id else ""
                token_id = f"{unique_id}-{j}"
                p_tokens_html.append(
                    f'<span id="{token_id}" class="cursor-pointer border-b transition-colors {color}'
                    f'" hx-get="/explain/{lemma}?lang={lang}{paper_param}&element_id={token_id}" hx-trigger="click" '
                    f'hx-indicator="#dict-loading" '
                    f'hx-target="#dict-stack" hx-swap="afterbegin">{token.text}</span>{whitespace}'
                )

            html_content = "".join(p_tokens_html)
            all_html_parts[unique_id] = html_content

            # UI Component for Paragraph Actions
            explain_btn = self._get_paragraph_actions_html()

            wrapped_html = (
                f'<div class="group relative paragraph-container mb-6 pr-4" hx-swap-oob="beforeend:#{target_id}">'
                f"{explain_btn}"
                f'<p id="{unique_id}" class="text-base leading-relaxed text-slate-700 text-justify">{html_content}</p>'
                f"</div>"
            )

            yield f"event: message\ndata: {wrapped_html}\n\n"

        # Finalize
        if paper_id and save_to_db:
            await self._save_full_html(paper_id, paragraphs, all_html_parts, id_prefix)

        # Batch translate unknown words
        if unknown_words:
            async for msg in self._handle_unknown_words(unknown_words, lang):
                yield msg

        # UI Cleanup
        yield 'event: message\ndata: <div id="dict-status-container" hx-swap-oob="true" class="relative min-h-[100px] flex flex-col items-center justify-center text-center p-4 border-2 border-dashed border-slate-100 rounded-2xl"><div class="bg-slate-50 p-2 rounded-xl mb-2"><svg class="w-6 h-6 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg></div><p class="text-[10px] font-bold text-slate-400 leading-relaxed">Dictionary Ready!</p></div>\n\n'
        yield 'event: message\ndata: <div id="tokenize-status" hx-swap-oob="true" class="fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg">✅ 分析完了！単語をクリックで翻訳</div>\n\n'

    def _get_paragraph_actions_html(self) -> str:
        return (
            '<div class="absolute -right-12 top-0 hidden group-hover:flex flex-col gap-2 items-start z-10 pl-2">'
            '<button onclick="explainParagraph(this)" title="Deep Explain" '
            'class="p-2 bg-white text-indigo-600 rounded-full shadow-lg border border-indigo-100 hover:bg-indigo-50 hover:scale-110 transition-all">'
            '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />'
            "</svg></button>"
            '<button onclick="verifyClaims(this)" title="Verify Evidence" '
            'class="p-2 bg-white text-emerald-600 rounded-full shadow-lg border border-emerald-100 hover:bg-emerald-50 hover:scale-110 transition-all">'
            '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />'
            "</svg></button>"
            '<button onclick="analyzeCiteIntent(this)" title="Analyze Citations" '
            'class="p-2 bg-white text-blue-600 rounded-full shadow-lg border border-blue-100 hover:bg-blue-50 hover:scale-110 transition-all">'
            '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />'
            "</svg></button>"
            "</div>"
        )

    async def _save_full_html(self, paper_id, paragraphs, all_html_parts, id_prefix):
        try:
            full_html = ""
            for i in range(len(paragraphs)):
                unique_id = f"{id_prefix}-{i}"
                if unique_id in all_html_parts:
                    full_html += f'<p id="{unique_id}" class="mb-6">{all_html_parts[unique_id]}</p>'
            storage = get_storage_provider()
            storage.update_paper_html(paper_id, full_html)
            logger.info(f"Updated HTML content for paper: {paper_id}")
        except Exception as e:
            logger.error(f"Failed to save content for paper {paper_id}: {e}")

    async def _handle_unknown_words(self, unknown_words, lang):
        yield 'event: message\ndata: <div id="dict-status-container" hx-swap-oob="true" class="min-h-[300px] flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-indigo-200 bg-indigo-50/50 rounded-3xl animate-pulse"><div class="mb-4 text-indigo-500"><svg class="animate-spin w-8 h-8 mx-auto" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg></div><p class="text-xs font-bold text-indigo-500">Building Dictionary...</p><p class="text-[10px] text-slate-400 mt-2">Translating unknown words</p></div>\n\n'

        limit = int(os.getenv("BATCH_WORDS_LIMIT", "50"))
        words_to_translate = list(unknown_words)[:limit]

        await self.word_analysis.batch_translate(words_to_translate, lang)
