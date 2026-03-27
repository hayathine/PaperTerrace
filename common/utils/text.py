def clean_text_for_tokenization(text: str) -> str:
    """
    テキストから余分な改行や空白を除去し、単語処理に適した形式にする。
    """
    return text.replace("\r\n", "\n").replace("\n", " ").strip()


def truncate_context(text: str, target_word: str, max_length: int = 800) -> str:
    """
    指定された単語を中央に配置しつつ、テキストを最大長(max_length)に動的に切り詰める。
    単語がテキストの端に寄っている場合、反対側の長さを伸ばして予算を最大限活用します。
    """
    if len(text) <= max_length:
        return text

    # 大文字小文字を区別せずに検索
    word_pos = text.lower().find(target_word.lower())
    if word_pos == -1:
        # 見つからない場合は先頭から
        return text[:max_length]

    word_len = len(target_word)
    
    # 基本の分配: 単語の前後を等分に保とうとする
    remaining = max(0, max_length - word_len)
    half = remaining // 2
    
    start = max(0, word_pos - half)
    end = min(len(text), word_pos + word_len + half)
    
    # 強欲調整（一方が端に達した場合、もう一方を最大限伸ばして予算を使い切る）
    if start == 0:
        end = min(len(text), max_length)
    elif end == len(text):
        start = max(0, len(text) - max_length)
        
    # 文脈を綺麗にするための調整（スペースでの単語切断回避）
    # ただし、ターゲット単語自体を削らないように注意する
    if start > 0:
        # startの直後の最初のスペースを探して、そこを開始点にする
        next_space = text.find(" ", start, word_pos)
        if next_space != -1:
            start = next_space + 1
            
    if end < len(text):
        # endの直前の最後のスペースを探して、そこを終点にする
        prev_space = text.rfind(" ", word_pos + word_len, end)
        if prev_space != -1:
            end = prev_space

    return text[start:end].strip()
