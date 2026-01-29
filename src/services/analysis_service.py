import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor

import spacy

from src.logger import logger
from src.providers import RedisService, get_ai_provider, get_storage_provider
from src.services.jamdict_service import lookup_word
from src.utils import clean_text_for_tokenization, truncate_context

# 共通設定 (logic.pyから移行)
# 共通設定 (logic.pyから移行)
executor = ThreadPoolExecutor(max_workers=4)
try:
    # メモリ節約のため sm モデルを優先
    nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
    logger.info("Loaded spaCy model: en_core_web_sm")
except OSError:
    # 最悪の場合、モデルなし（エラーになるがログ出す）
    logger.error("No spaCy model found. Please verify Dockerfile installs 'en_core_web_sm'.")
    raise


class EnglishAnalysisService:
    def __init__(self):
        from src.services.pdf_ocr_service import PDFOCRService

        self.ai_provider = get_ai_provider()
        self.model = os.getenv("OCR_MODEL", "gemini-1.5-flash")
        self.translate_model = os.getenv("MODEL_TRANSLATE", "gemini-1.5-flash")
        self.ocr_service = PDFOCRService(self.model)
        self.redis = RedisService()
        self.word_cache = {}  # lemma -> bool (jamdict にあるかどうか)
        self.translation_cache = {}  # lemma -> translation (Gemini翻訳キャッシュ)
        self._unknown_words = set()  # Jamdictにない単語を収集

    async def tokenize_stream(
        self,
        text: str,
        paper_id: str | None = None,
        target_id: str = "paper-content",
        id_prefix: str = "p",
        save_to_db: bool = True,
        lang: str = "ja",
    ):
        """1パス方式: 段落ごとに即座にトークン化してクリック可能なHTMLを表示"""
        paragraphs = re.split(r"\n{2,}", text.replace("\r\n", "\n"))
        loop = asyncio.get_event_loop()
        all_html_parts: dict[str, str] = {}

        for i, p_text in enumerate(paragraphs):
            p_text = clean_text_for_tokenization(p_text)
            if not p_text:
                continue

            unique_id = f"{id_prefix}-{i}"

            # トークン化
            doc = await loop.run_in_executor(executor, nlp, p_text)
            p_tokens_html = []

            for token in doc:
                whitespace = token.whitespace_

                if token.is_punct or token.is_space:
                    p_tokens_html.append(f"<span>{token.text}</span>{whitespace}")
                    continue

                lemma = token.lemma_.lower()
                if lemma not in self.word_cache:
                    # 1. L1 Cache Check
                    if lemma in self.translation_cache:
                        self.word_cache[lemma] = False
                    else:
                        # 2. L2 Cache Check (Redis)
                        cached_trans = self.redis.get(f"trans:{lemma}")
                        if cached_trans:
                            self.translation_cache[lemma] = cached_trans
                            self.word_cache[lemma] = False
                        else:
                            # 3. Jamdict Check
                            self.word_cache[lemma] = await loop.run_in_executor(
                                executor, lookup_word, lemma
                            )
                            if not self.word_cache[lemma]:
                                self._unknown_words.add(lemma)

                color = (
                    "border-transparent hover:border-indigo-300 hover:bg-indigo-50"
                    if self.word_cache.get(lemma, False)
                    else "border-transparent hover:border-purple-300 hover:bg-purple-50"
                )
                p_tokens_html.append(
                    f'<span class="cursor-pointer border-b transition-colors {color}'
                    f'" hx-get="/explain/{lemma}?lang={lang}" hx-trigger="click" '
                    f'hx-indicator="#dict-loading" '
                    f'hx-target="#definition-box" hx-swap="innerHTML">{token.text}</span>{whitespace}'
                )

            html_content = "".join(p_tokens_html)
            all_html_parts[unique_id] = html_content

            # Wrapper with explain button
            explain_btn = (
                '<div class="absolute -right-12 top-0 hidden group-hover:flex flex-col gap-2 items-start z-10 pl-2">'
                # Explain Button
                '<button onclick="explainParagraph(this)" title="Deep Explain" '
                'class="p-2 bg-white text-indigo-600 rounded-full shadow-lg border border-indigo-100 hover:bg-indigo-50 hover:scale-110 transition-all">'
                '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">'
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />'
                "</svg></button>"
                # Verify Button
                '<button onclick="verifyClaims(this)" title="Verify Evidence" '
                'class="p-2 bg-white text-emerald-600 rounded-full shadow-lg border border-emerald-100 hover:bg-emerald-50 hover:scale-110 transition-all">'
                '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">'
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />'
                "</svg></button>"
                # Cite Intent Button
                '<button onclick="analyzeCiteIntent(this)" title="Analyze Citations" '
                'class="p-2 bg-white text-blue-600 rounded-full shadow-lg border border-blue-100 hover:bg-blue-50 hover:scale-110 transition-all">'
                '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">'
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />'
                "</svg></button>"
                "</div>"
            )

            wrapped_html = (
                f'<div class="group relative paragraph-container mb-6 pr-4" hx-swap-oob="beforeend:#{target_id}">'
                f"{explain_btn}"
                f'<p id="{unique_id}" class="text-base leading-relaxed text-slate-700 text-justify">{html_content}</p>'
                f"</div>"
            )

            # 即座にクリック可能なHTMLを表示
            yield f"event: message\ndata: {wrapped_html}\n\n"

        # 保存用に完全なHTMLを構築して保存
        if paper_id and save_to_db:
            try:
                full_html = ""
                for i in range(len(paragraphs)):
                    unique_id = f"{id_prefix}-{i}"
                    if unique_id in all_html_parts:
                        full_html += (
                            f'<p id="{unique_id}" class="mb-6">{all_html_parts[unique_id]}</p>'
                        )

                storage = get_storage_provider()
                storage.update_paper_html(paper_id, full_html)
                logger.info(f"Updated HTML content for paper: {paper_id}")
            except Exception as e:
                logger.error(f"Failed to save content for paper {paper_id}: {e}")

        # ストリーム終了時に未知の単語をバッチ翻訳
        if self._unknown_words:
            # 辞書準備中を表示
            yield 'event: message\ndata: <div id="definition-box" hx-swap-oob="true" class="min-h-[300px] flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-indigo-200 bg-indigo-50/50 rounded-3xl animate-pulse"><div class="mb-4 text-indigo-500"><svg class="animate-spin w-8 h-8 mx-auto" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg></div><p class="text-xs font-bold text-indigo-500">Building Dictionary...</p><p class="text-[10px] text-slate-400 mt-2">Translating unknown words</p></div>\n\n'

            logger.info(f"UNKNOWN WORDS count: {len(self._unknown_words)}")
            translations = await self._batch_translate_words(
                list(self._unknown_words)
                if len(self._unknown_words) <= int(os.getenv("BATCH_WORDS_LIMIT", "50"))
                else list(self._unknown_words)[: int(os.getenv("BATCH_WORDS_LIMIT", "50"))],
                lang=lang,
            )
            # 結果を translation_cache に統合
            self.translation_cache.update(translations)
            self._unknown_words.clear()

        # 辞書完了表示（元に戻す）
        # 辞書完了表示（元に戻す）＋ローディングインジケータ
        yield 'event: message\ndata: <div id="definition-box" hx-swap-oob="true" class="relative min-h-[300px] flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-slate-100 rounded-3xl"><div id="dict-loading" class="htmx-indicator absolute inset-0 bg-white/90 flex flex-col items-center justify-center z-20 rounded-3xl transition-opacity duration-200"><svg class="animate-spin w-8 h-8 text-indigo-500 mb-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span class="text-sm text-indigo-500 font-medium">Looking up...</span></div><div class="bg-slate-50 p-4 rounded-2xl mb-4"><svg class="w-8 h-8 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg></div><p class="text-xs font-bold text-slate-400 leading-relaxed">Dictionary Ready!<br>Click any word for definition.</p></div>\n\n'

        # ステータスを完了表示に変更 (oob swap)
        yield 'event: message\ndata: <div id="tokenize-status" hx-swap-oob="true" class="fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg">✅ 分析完了！単語をクリックで翻訳</div>\n\n'

    async def _batch_translate_words(self, words: list[str], lang: str = "ja") -> dict[str, str]:
        """未知の単語を一括でGeminiで翻訳して辞書として返す"""
        from src.features.translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        logger.info(f"Batch translation starting with {len(words)} words for {lang}")
        result: dict[str, str] = {}

        if not words:
            return result

        # 既にキャッシュにある単語は除外
        words_to_translate = [w for w in words if w not in self.translation_cache]
        if not words_to_translate:
            return result

        # Create batch prompt in English
        words_list = "\n".join(f"- {w}" for w in words_to_translate)
        prompt = f"""Provide concise translations for the following English words in {lang_name}.
Output format per line: "Word: Translation"
Keep it very brief (1-2 words).

Words:
{words_list}"""

        try:
            # Simple wrapper around async generate
            response_text = await self.ai_provider.generate(prompt, model=self.translate_model)

            # レスポンスをパース
            for line in response_text.split("\n"):
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        word = parts[0].strip().lower().lstrip("- ")
                        translation = parts[1].strip()
                        if word and translation:
                            result[word] = translation
            logger.info(f"Batch translation completed with {len(result)} words")
        except Exception as e:
            logger.error(f"Batch translation failed: {e}")

        # Redisに保存
        for lemma, trans in result.items():
            self.redis.set(f"trans:{lang}:{lemma}", trans, expire=604800)  # 1週間保存

        return result

    async def get_translation(
        self, lemma: str, context: str | None = None, lang: str = "ja"
    ) -> dict | None:
        """キャッシュから翻訳を取得する。キャッシュにない場合はcontextがあればGeminiで推測する。"""
        # word_cache をチェック - Jamdict にある場合は None を返す（Jamdictで処理する）
        if lemma in self.word_cache:
            if self.word_cache[lemma]:
                return None
            else:
                if lemma in self.translation_cache:
                    return {
                        "word": lemma,
                        "translation": self.translation_cache[lemma],
                        "source": "Gemini (cached)",
                    }

                cached_trans = self.redis.get(f"trans:{lang}:{lemma}")
                if cached_trans:
                    self.translation_cache[lemma] = cached_trans
                    return {
                        "word": lemma,
                        "translation": cached_trans,
                        "source": f"Gemini ({lang} cached)",
                    }

                if context:
                    return await self._translate_with_context(lemma, context, lang=lang)

        if context:
            if lemma in self.translation_cache:
                return {
                    "word": lemma,
                    "translation": self.translation_cache[lemma],
                    "source": "Gemini (cached)",
                }
            cached_trans = self.redis.get(f"trans:{lang}:{lemma}")
            if cached_trans:
                self.translation_cache[lemma] = cached_trans
                return {
                    "word": lemma,
                    "translation": cached_trans,
                    "source": f"Gemini ({lang} cached)",
                }
            return await self._translate_with_context(lemma, context, lang=lang)

        return None

    async def _translate_with_context(
        self, word: str, context: str, lang: str = "ja"
    ) -> dict | None:
        """Gemini APIを使って論文の文脈から単語の意味を推測する。"""
        max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "800"))
        context = truncate_context(context, word, max_context_length)

        from src.features.translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        prompt = f"""Evaluate the meaning of the word "{word}" within the academic context below, and provide the most appropriate translation in {lang_name}.
Keep it concise (1-3 words). Output ONLY the translation.

[Academic Context]
{context}

[Target Word]
{word}

[Output]
Translation only in {lang_name}.
"""

        try:
            translation = await self.ai_provider.generate(prompt, model=self.translate_model)
            translation = translation.strip()

            self.translation_cache[word] = translation
            self.redis.set(f"trans:{lang}:{word}", translation, expire=604800)  # 1週間
            self.word_cache[word] = False

            logger.info(f"Context-aware translation: {word} -> {translation}")

            return {
                "word": word,
                "translation": translation,
                "source": "Gemini (context)",
            }
        except Exception as e:
            logger.error(f"Context translation failed for '{word}': {e}")
            return None

    def get_word_cache(self) -> dict[str, bool]:
        """word_cache を取得"""
        return self.word_cache

    def get_translation_cache(self) -> dict[str, str]:
        """translation_cache を取得"""
        return self.translation_cache
