import re
from functools import lru_cache

@lru_cache(maxsize=5000)
def lemmatize_text(text: str) -> str:
    """テキストの正規化（小文字化と空白削除。LLMが活用形を処理するため現状はこれで十分）"""
    return text.strip().lower()

def is_single_word(text: str) -> bool:
    """単一単語（空白区切りで1単語）かどうかを判定する。"""
    if not text:
        return False
    return len(text.strip().split()) == 1

def simple_tokenize(text: str) -> list[dict]:
    """テキストを単語リストにトークナイズする。
    
    Returns:
        list of dict: text, lemma, ws, is_punct, is_space を含む辞書リスト
    """
    text = text.strip()
    if not text:
        return []

    results = []
    # 単語と句読点を分割（NLPServiceのロジックを抽出）
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
