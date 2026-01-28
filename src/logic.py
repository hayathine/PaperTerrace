import asyncio
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import spacy
from dotenv import load_dotenv
from jamdict import Jamdict

from src.crud import get_ocr_from_db, save_ocr_to_db
from src.logger import logger
from src.providers import RedisService, get_ai_provider, get_storage_provider
from src.utils import (
    _get_file_hash,
    clean_text_for_tokenization,
    truncate_context,
)

# 共通設定
load_dotenv()
executor = ThreadPoolExecutor(max_workers=4)
nlp = spacy.load("en_core_web_lg", disable=["ner", "parser"])  # tok2vec required for lemmatization


# Thread-local storage for Jamdict instances
_thread_local = threading.local()


def _get_jam() -> Jamdict:
    """Get a thread-local Jamdict instance."""
    if not hasattr(_thread_local, "jam"):
        _thread_local.jam = Jamdict()
    return _thread_local.jam


def _lookup_word(lemma: str) -> bool:
    """Thread-safe word lookup."""
    jam = _get_jam()
    res = jam.lookup(lemma)
    return len(res.entries) > 0


def _lookup_word_full(lemma: str):
    """Thread-safe full word lookup for explain."""
    jam = _get_jam()
    return jam.lookup(lemma)


class PDFOCRService:
    def __init__(self, model):
        self.ai_provider = get_ai_provider()
        self.model = model

    async def detect_language_from_pdf(self, file_bytes: bytes) -> str:
        """PDFの言語を検出する（メタデータ -> AI判定の順）"""
        import fitz

        language = "en"  # default

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")

            # 1. メタデータ (Catalog Lang) の確認
            # xref_get_key returns (type, value)
            # type: 'name', 'string', etc.
            catalog = doc.pdf_catalog()
            lang_entry = doc.xref_get_key(catalog, "Lang")
            if lang_entry[0] in ("name", "string") and lang_entry[1]:
                lang_code = lang_entry[1]
                logger.info(f"PDF Metadata Language detected: {lang_code}")
                # Clean up (e.g., 'en-US' -> 'en')
                language = lang_code.split("-")[0].lower()
                doc.close()
                return language

            # 2. メタデータにない場合、1ページ目をAIで判定
            if len(doc) > 0:
                text = doc[0].get_text()[:1000]
                if text.strip():
                    prompt = f"""Identify the primary language of the following text and return ONLY the ISO 639-1 code (e.g., 'en', 'ja', 'fr').
Text Sample:
{text}
"""
                    detected = await self.ai_provider.generate(prompt, model=self.model)
                    detected = detected.strip().lower()
                    if len(detected) == 2:
                        language = detected
                        logger.info(f"PDF Content Language detected by AI: {language}")

            doc.close()
        except Exception as e:
            logger.error(f"Language detection failed: {e}")

        return language

    async def extract_text_with_ai(self, file_bytes: bytes, filename: str = "unknown.pdf") -> str:
        file_hash = _get_file_hash(file_bytes)
        cached_ocr = get_ocr_from_db(file_hash)
        if cached_ocr:
            logger.info("Returning cached OCR text.")
            return cached_ocr

        logger.info(f"--- AI OCR Processing: {filename} ---")
        try:
            prompt = "このPDFのテキストを構造を維持して文字起こししてください。"
            ocr_text = await self.ai_provider.generate_with_pdf(
                prompt, file_bytes, model=self.model
            )
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return f"ERROR_API_FAILED: {str(e)}"
        save_ocr_to_db(
            file_hash=file_hash,
            filename=filename,
            ocr_text=ocr_text,
            model_name=self.model,
        )
        logger.info("OCR extraction completed.")
        return ocr_text

    async def extract_text_streaming(self, file_bytes: bytes, filename: str = "unknown.pdf"):
        """ページ単位でOCR処理をストリーミングするジェネレータ。

        Yields:
            tuple: (page_num, total_pages, page_text, is_last, file_hash, page_image, layout_data)
                   layout_data: list of {"word": str, "bbox": [x0, y0, x1, y1]} or None
        """
        import base64

        import fitz  # PyMuPDF

        from .providers.image_storage import get_page_images, save_page_image

        file_hash = _get_file_hash(file_bytes)
        cached_ocr = get_ocr_from_db(file_hash)

        if cached_ocr:
            cached_images = get_page_images(file_hash)
            if cached_images:
                logger.info("Returning cached OCR text and images.")
                total_pages = len(cached_images)
                for i, img_url in enumerate(cached_images):
                    yield (
                        i + 1,
                        total_pages,
                        cached_ocr if i == 0 else "",
                        i == total_pages - 1,
                        file_hash,
                        img_url,
                        None,
                    )
                return
            else:
                logger.info("Cached OCR text found but images missing. Regenerating images.")

        logger.info(f"--- AI OCR Streaming: {filename} ---")

        try:
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(pdf_doc)
            logger.info(f"[OCR Streaming] Total pages: {total_pages}")

            all_text_parts = []

            for page_num in range(total_pages):
                page = pdf_doc[page_num]

                # ページ画像の生成 (2.0倍ズーム = 144 DPI 相当)
                # レイアウト座標との整合性を取るため、画像のスケールを基準にする
                zoom = 2.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                page_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
                image_url = save_page_image(file_hash, page_num + 1, page_image_b64)

                # レイアウト情報の抽出 (PyMuPDF)
                # get_text("words") returns: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
                words = page.get_text("words")
                layout_data = []
                page_text_extracted = ""

                # 画像の幅と高さを取得（表示時の比率計算用）
                img_width = pix.width
                img_height = pix.height

                if words:
                    # 座標を画像サイズ（zoom倍）に合わせて変換
                    word_list = []
                    for w in words:
                        word_list.append(
                            {
                                "word": w[4],
                                # bbox: [left, top, right, bottom]
                                "bbox": [w[0] * zoom, w[1] * zoom, w[2] * zoom, w[3] * zoom],
                            }
                        )
                        page_text_extracted += w[4] + " "

                    layout_data = {
                        "width": img_width,
                        "height": img_height,
                        "words": word_list,
                    }

                    page_text = page_text_extracted.strip()
                    logger.info(f"[Layout] Extracted {len(words)} words from page {page_num + 1}")

                else:
                    # テキストがない場合はGeminiでOCR (座標なし)
                    logger.info(f"[OCR] No text found on page {page_num + 1}, using Gemini")
                    single_page_pdf = fitz.open()
                    single_page_pdf.insert_pdf(pdf_doc, from_page=page_num, to_page=page_num)
                    page_bytes = single_page_pdf.tobytes()
                    single_page_pdf.close()

                    try:
                        prompt = "Transcribe the text from this PDF page preserving the structure as much as possible."
                        page_text = await self.ai_provider.generate_with_pdf(
                            prompt, page_bytes, model=self.model
                        )
                    except Exception as e:
                        logger.error(f"OCR failed for page {page_num + 1}: {e}")
                        page_text = ""

                    layout_data = None  # OCRの場合は座標なし

                all_text_parts.append(page_text)
                is_last = page_num == total_pages - 1

                yield (
                    page_num + 1,
                    total_pages,
                    page_text,
                    is_last,
                    file_hash,
                    image_url,
                    layout_data,  # List[dict] including image dimensions could be useful
                )

            pdf_doc.close()

            # 全ページ処理完了後にDBに保存
            full_text = "\n\n---\n\n".join(all_text_parts)
            save_ocr_to_db(
                file_hash=file_hash,
                filename=filename,
                ocr_text=full_text,
                model_name=self.model,
            )
            logger.info(f"[OCR Streaming] Completed and saved: {filename}")

        except Exception as e:
            logger.error(f"OCR streaming failed: {e}")
            yield (0, 0, f"ERROR_API_FAILED: {str(e)}", True, file_hash)


class EnglishAnalysisService:
    def __init__(self):
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
                                executor, _lookup_word, lemma
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
                    f'hx-target="#definition-box" hx-swap="afterbegin">{token.text}</span>{whitespace}'
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
        yield 'event: message\ndata: <div id="definition-box" hx-swap-oob="true" class="min-h-[300px] flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-slate-100 rounded-3xl"><div class="bg-slate-50 p-4 rounded-2xl mb-4"><svg class="w-8 h-8 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg></div><p class="text-xs font-bold text-slate-400 leading-relaxed">Dictionary Ready!<br>Click any word for definition.</p></div>\n\n'

        # ステータスを完了表示に変更 (oob swap)
        yield 'event: message\ndata: <div id="tokenize-status" hx-swap-oob="true" class="fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg">✅ 分析完了！単語をクリックで翻訳</div>\n\n'

    async def _batch_translate_words(self, words: list[str], lang: str = "ja") -> dict[str, str]:
        """未知の単語を一括でGeminiで翻訳して辞書として返す"""
        from .features.translate import SUPPORTED_LANGUAGES

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
        """キャッシュから翻訳を取得する。キャッシュにない場合はcontextがあればGeminiで推測する。

        Args:
            lemma: 検索する単語
            context: 論文のテキスト（文脈から意味を推測するために使用）
            lang: ターゲット言語

        Returns:
            翻訳情報を含む辞書、またはNone（Jamdictで処理すべき場合）
        """
        # word_cache をチェック - Jamdict にある場合は None を返す（Jamdictで処理する）
        if lemma in self.word_cache:
            if self.word_cache[lemma]:
                # Jamdict にある → None を返して別途 Jamdict で処理させる
                return None
            else:
                # Jamdict にない → translation_cache を確認
                if lemma in self.translation_cache:
                    return {
                        "word": lemma,
                        "translation": self.translation_cache[lemma],
                        "source": "Gemini (cached)",
                    }

                # Redis (L2) を確認
                cached_trans = self.redis.get(f"trans:{lang}:{lemma}")
                if cached_trans:
                    self.translation_cache[lemma] = cached_trans  # L1に入れる
                    return {
                        "word": lemma,
                        "translation": cached_trans,
                        "source": f"Gemini ({lang} cached)",
                    }

                # キャッシュにない場合、contextがあればGeminiで推測
                if context:
                    return await self._translate_with_context(lemma, context, lang=lang)

        # word_cache にない場合（初回ルックアップ）
        # context があれば、Jamdictチェックをスキップして直接Geminiで推測
        if context:
            # まずキャッシュを確認
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
            # キャッシュにもなければGeminiで推測
            return await self._translate_with_context(lemma, context, lang=lang)

        return None

    async def _translate_with_context(
        self, word: str, context: str, lang: str = "ja"
    ) -> dict | None:
        """Gemini APIを使って論文の文脈から単語の意味を推測する。

        Args:
            word: 翻訳する単語
            context: 論文のテキスト（文脈）
            lang: ターゲット言語

        Returns:
            翻訳情報を含む辞書
        """
        # 文脈が長すぎる場合は切り詰める（トークン節約）
        max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "800"))
        context = truncate_context(context, word, max_context_length)

        from .features.translate import SUPPORTED_LANGUAGES

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

            # キャッシュに保存
            self.translation_cache[word] = translation
            self.redis.set(f"trans:{lang}:{word}", translation, expire=604800)  # 1週間
            self.word_cache[word] = False  # Jamdictにはない

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
