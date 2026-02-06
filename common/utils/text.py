def clean_text_for_tokenization(text: str) -> str:
    """
    テキストから余分な改行や空白を除去し、単語処理に適した形式にする。
    """
    return text.replace("\r\n", "\n").replace("\n", " ").strip()


def truncate_context(text: str, target_word: str, max_length: int = 800) -> str:
    """
    指定された単語を中心に、テキストを最大長に切り詰める。
    """
    if len(text) <= max_length:
        return text

    word_pos = text.lower().find(target_word.lower())
    if word_pos != -1:
        start = max(0, word_pos - max_length // 2)
        end = min(len(text), word_pos + max_length // 2)
        return text[start:end]
    else:
        return text[:max_length]
