def is_garbled_text(text: str) -> bool:
    """
    フォントエンコーディング由来の文字化けが含まれるか判定する。

    以下の4パターンをカバーする:

    1. (cid:N) ― pdfplumber が ToUnicode CMap 欠損時に出力するリテラル文字列。
    2. Unicode 置換文字 U+FFFD ― デコード失敗を示す明示的マーカー。
    3. Unicode Private Use Area U+E000〜U+F8FF ― PDFカスタムフォントが
       グリフをPUA領域にマッピングする場合に発生。
    4. Unicode Supplementary PUA U+F0000〜U+FFFFF ― 同上、補助面版。

    各パターンについて「5文字以上」または「テキスト全体の0.5%以上」で
    文字化けと判定する。
    """
    if not text:
        return False

    text_len = max(len(text), 1)
    threshold_ratio = 0.005

    # 1. (cid:N) パターン
    cid_count = text.count("(cid:")
    if cid_count >= 5 or (cid_count > 0 and cid_count / text_len > threshold_ratio):
        return True

    # 2. Unicode 置換文字 U+FFFD
    repl_count = text.count("\ufffd")
    if repl_count >= 5 or (repl_count > 0 and repl_count / text_len > threshold_ratio):
        return True

    # 3. Unicode Private Use Area (BMP): U+E000〜U+F8FF
    pua_count = sum(1 for c in text if "\ue000" <= c <= "\uf8ff")
    if pua_count >= 5 or (pua_count > 0 and pua_count / text_len > threshold_ratio):
        return True

    # 4. Unicode Supplementary PUA: U+F0000〜U+FFFFF
    sup_pua_count = sum(1 for c in text if "\U000f0000" <= c <= "\U000fffff")
    if sup_pua_count >= 5 or (
        sup_pua_count > 0 and sup_pua_count / text_len > threshold_ratio
    ):
        return True

    return False


def fix_indentation_artifacts(text: str) -> str:
    """
    2段組みPDFから生じるインデントアーティファクトを修正する。

    pymupdf4llmが2段組みレイアウトを処理する際、右カラムのテキストが
    大きなインデントとして抽出され、Markdownのコードブロックとして
    誤レンダリングされる問題を解決する。
    """
    lines = text.split("\n")
    result = []
    for line in lines:
        # 4スペース以上のインデントがある行（Markdownコードブロックの条件）
        if (
            len(line) > 4
            and line.startswith("    ")
            and not line.startswith("        ")
        ):
            stripped = line.lstrip()
            # Markdownの構造要素（見出し、引用、リスト、コードフェンス等）は変更しない
            if stripped and stripped[0] not in "#>-*+|`":
                # コードらしき記号の割合を検査
                code_chars = sum(1 for c in stripped if c in "{}()[];=><!/\\@$%^&")
                ratio = code_chars / max(len(stripped), 1)
                # コード記号が10%未満なら自然言語テキストとみなしインデントを除去
                if ratio < 0.10:
                    result.append(stripped)
                    continue
        result.append(line)
    return "\n".join(result)


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
