from common.utils.nlp import lemmatize_text, is_single_word, simple_tokenize

class NLPService:
    """NLPユーティリティ（共通ユーティリティを使用）"""

    @staticmethod
    def lemmatize(text: str) -> str:
        """テキストの正規化（小文字化のみ）。LLM が原形処理を担うため十分。"""
        return lemmatize_text(text)

    @staticmethod
    def is_single_word(text: str) -> bool:
        """単一単語かどうかを判定する。"""
        return is_single_word(text)

    @staticmethod
    def tokenize(text: str) -> list[dict]:
        """テキストを単一単語に分割し、属性情報を付与する。"""
        return simple_tokenize(text)
