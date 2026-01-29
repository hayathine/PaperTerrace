import os

from src.providers import get_ai_provider

"""
単語をクリックするとその意味を辞書で調べて表示する機能を提供するモジュール
"""


class Translate:
    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.ai_provider = get_ai_provider()
        self.model = model_name or os.getenv("MODEL_DICT", "gemini-2.0-flash-lite")

    async def explain_unknown_word(self, word: str, lang: str = "ja") -> str:
        """Explain an unknown word in the target language."""
        from src.prompts import DICT_EXPLAIN_PROMPT

        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        prompt = DICT_EXPLAIN_PROMPT.format(word=word, lang_name=lang_name)
        try:
            return await self.ai_provider.generate(prompt, model=self.model)
        except Exception:
            return "Failed to retrieve meaning."
