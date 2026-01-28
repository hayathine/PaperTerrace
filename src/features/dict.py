import os

from src.providers import get_ai_provider

"""
単語をクリックするとその意味を辞書で調べて表示する機能を提供するモジュール
"""


class Translate:
    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.ai_provider = get_ai_provider()
        self.model = model_name or os.getenv("MODEL_DICT", "gemini-2.0-flash-lite")

    async def explain_unknown_word(self, word: str) -> str:
        """辞書にない英単語を日本語で解説する"""
        prompt = f"英単語「{word}」の日本語訳と、その意味を15文字程度で簡潔に説明してください。"
        try:
            return await self.ai_provider.generate(prompt, model=self.model)
        except Exception:
            return "意味を取得できませんでした"
