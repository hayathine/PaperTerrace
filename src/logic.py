import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor

import spacy
from dotenv import load_dotenv
from google import genai
from jamdict import Jamdict

load_dotenv()

# spaCyの英語モデルをロード
nlp = spacy.load(
    "en_core_web_sm",
    disable=[
        "ner",
        "parser",
        "tok2vec",
    ],
)
jam = Jamdict()
executor = ThreadPoolExecutor(max_workers=4)


class Translate:
    def __init__(self, api_key: str = None, model_name: str = None):
        self.client = genai.Client(api_key=api_key)
        self.model = model_name

    def explain_unknown_word(self, word: str) -> str:
        """辞書にない英単語を日本語で解説する"""
        prompt = f"英単語「{word}」の日本語訳と、その意味を15文字程度で簡潔に説明してください。"
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            return response.text.strip()
        except Exception:
            return "意味を取得できませんでした"


class EnglishAnalysisService:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = os.getenv("API_MODEL")

    async def tokenize_to_html(self, text: str) -> str:
        """テキストを段落ごとに分け、それぞれを<p>タグで囲んで返す"""

        # 1. 準備：改行コードを統一 (\r\n -> \n)
        text = text.replace("\r\n", "\n")

        # 2. 段落（2回以上の改行）でテキストを分割
        # これにより、PDF特有の「1行ごとの改行」は無視し、大きなまとまりだけを保持します
        paragraphs = re.split(r"\n{2,}", text)
        loop = asyncio.get_event_loop()
        html_output = []

        for p_text in paragraphs:
            # 段落内の不要な単発改行をスペースに置換
            p_text = p_text.replace("\n", " ").strip()

            if not p_text:
                continue

            # 段落ごとにspaCyで解析
            doc = await loop.run_in_executor(executor, nlp, p_text)
            p_tokens_html = []

            for token in doc:
                if token.is_space:
                    p_tokens_html.append(token.text)
                elif token.is_punct:
                    p_tokens_html.append(f"<span>{token.text}</span>")
                else:
                    lemma = token.lemma_.lower()
                    surface = token.text
                    p_tokens_html.append(
                        f'<span class="hover:bg-indigo-100 cursor-pointer border-b border-transparent hover:border-indigo-400" '
                        f'hx-get="/explain/{lemma}" '
                        f'hx-target="#definition-box" '
                        f'hx-trigger="click">{surface}</span>'
                    )

            # 3. 最後に段落を <p> タグで包む (mb-6で段落間の余白を作る)
            combined_p = " ".join(p_tokens_html)
            html_output.append(f'<p class="mb-6">{combined_p}</p>')

        return " ".join(html_output)

    async def explain_word(self, lemma: str) -> str:
        """特定の単語1つを解説する（日本語訳を抽出）"""

        # 1. Jamdictで検索
        lookup_res = jam.lookup(lemma)

        if lookup_res.entries:
            # 見つかった日本語の候補をすべて並べる（例：タイプ, 種類, 型）
            ja_candidates = []
            for entry in lookup_res.entries[:3]:
                if entry.kanji_forms:
                    ja_candidates.append(entry.kanji_forms[0].text)
                elif entry.kana_forms:
                    ja_candidates.append(entry.kana_forms[0].text)

            if ja_candidates:
                # 重複を除去してカンマ区切りに
                translation = " / ".join(list(dict.fromkeys(ja_candidates)))
                return self._format_bubble(lemma, translation, "Jamdict")

        # 2. Jamdictで見つからない、または分かりにくい場合はGeminiの出番
        # 「英単語の意味を日本語で教えて」と明確にプロンプトを出す
        prompt = f"英単語「{lemma}」の日本語訳を3つ程度、カンマ区切りで教えてください。余計な説明は不要です。"
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=prompt
            )
            return self._format_bubble(lemma, response.text.strip(), "Gemini")
        except Exception:
            return self._format_bubble(lemma, "検索失敗", "Error")

    def _format_bubble(self, word, definition, source):
        bg = "bg-blue-50" if source == "Jamdict" else "bg-purple-50"
        return f"""
        <div class="p-4 rounded-lg {bg} border border-gray-200 shadow-sm animate-in fade-in duration-300">
            <h4 class="text-lg font-bold text-gray-800">{word}</h4>
            <p class="text-gray-700 mt-1">{definition}</p>
            <span class="text-xs text-gray-400 mt-2 block">Source: {source}</span>
        </div>
        """
