import re
from functools import lru_cache


class NLPService:
    """NLPユーティリティ（spaCy不使用・軽量実装）"""

    @staticmethod
    @lru_cache(maxsize=5000)
    def lemmatize(text: str) -> str:
        """テキストの正規化（小文字化のみ）。Qwen が原形処理を担うため十分。"""
        return text.strip().lower()

    @staticmethod
    def is_single_word(text: str) -> bool:
        """単一単語かどうかを判定する。"""
        return len(text.strip().split()) == 1

    @staticmethod
    def tokenize(text: str) -> list[dict]:
        """テキストを単語リストにトークナイズする（空白・句読点分割）。"""
        text = text.strip()
        if not text:
            return []

        results = []
        # 単語と句読点を分割
        tokens = re.findall(r"[\w'-]+|[^\w\s]|\s+", text)
        for token in tokens:
            is_space = token.isspace()
            is_punct = bool(re.match(r"^[^\w\s]+$", token)) and not is_space
            results.append(
                {
                    "text": token,
                    "lemma": token.lower().strip() if not is_space else token,
                    "ws": " " if not is_space and not is_punct else "",
                    "is_punct": is_punct,
                    "is_space": is_space,
                }
            )
        return results
