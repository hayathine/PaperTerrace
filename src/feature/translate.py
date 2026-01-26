from google.genai import genai


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
