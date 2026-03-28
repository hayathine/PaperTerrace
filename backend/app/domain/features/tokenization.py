import re

from app.providers import get_storage_provider
from common.logger import ServiceLogger
from common.utils.text import clean_text_for_tokenization

from .word_analysis import WordAnalysisService

log = ServiceLogger("Tokenization")


class TokenizationService:
    def __init__(self):
        from app.providers.inference_client import get_inference_client

        self.get_inference_client = get_inference_client
        self.word_analysis = WordAnalysisService()
        self.redis = self.word_analysis.redis

    async def tokenize_stream(
        self,
        text: str,
        paper_id: str | None = None,
        target_id: str = "paper-content",
        id_prefix: str = "p",
        save_to_db: bool = True,
        lang: str = "ja",
        session_id: str | None = None,
        paper_title: str | None = None,
    ):
        """Processes text paragraph by paragraph and yields interactive HTML."""
        paragraphs = re.split(r"\n{2,}", text.replace("\r\n", "\n"))
        all_html_parts: dict[str, str] = {}
        unknown_words = set()

        for i, p_text in enumerate(paragraphs):
            p_text = clean_text_for_tokenization(p_text)
            if not p_text:
                continue

            unique_id = f"{id_prefix}-{i}"

            # Use Inference Service for tokenization
            client = await self.get_inference_client()
            tokens = await client.tokenize_text(p_text, lang=lang)
            p_tokens_html = []

            for j, token in enumerate(tokens):
                text = token["text"]
                lemma = token["lemma"]
                whitespace = token["ws"]
                is_punct = token.get("is_punct", False)
                is_space = token.get("is_space", False)

                if is_punct or is_space:
                    p_tokens_html.append(f"<span>{text}</span>{whitespace}")
                    continue

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
                            self.word_analysis.word_cache[lemma] = False
                            unknown_words.add(lemma)

                color = (
                    "border-transparent hover:border-indigo-300 hover:bg-indigo-50"
                    if self.word_analysis.word_cache.get(lemma, False)
                    else "border-transparent hover:border-purple-300 hover:bg-purple-50"
                )

                paper_param = f"&paper_id={paper_id}" if paper_id else ""
                session_param = f"&session_id={session_id}" if session_id else ""
                import html as _html
                title_param = f"&paper_title={_html.escape(paper_title)}" if paper_title else ""
                token_id = f"{unique_id}-{j}"
                # hx-vals を使い、クリック時にスパンが属する段落のテキストを context として渡す。
                # JS 式でクリック要素の最近接 .paragraph-container のテキストを取得し、
                # 先頭 800 文字に制限してコンテキスト過大によるURL肥大化を防ぐ。
                p_tokens_html.append(
                    f'<span id="{token_id}" class="cursor-pointer border-b transition-colors {color}'
                    f'" hx-get="/translate/{lemma}?lang={lang}{paper_param}{session_param}{title_param}&element_id={token_id}" hx-trigger="click" '
                    f'hx-vals=\'js:{{context: (document.getElementById("{token_id}").closest(".paragraph-container, p") || document.getElementById("{token_id}").parentElement)?.innerText?.slice(0, 800) || ""}}\' '
                    f'hx-indicator="#dict-loading" '
                    f'hx-target="#dict-stack" hx-swap="afterbegin">{text}</span>{whitespace}'
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
            log.info(
                "save_full_html", "Updated HTML content for paper", paper_id=paper_id
            )

        except Exception as e:
            log.error(
                "save_full_html",
                "Failed to save content for paper",
                paper_id=paper_id,
                error=str(e),
            )
