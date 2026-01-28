import hashlib

from .logger import logger


def _get_file_hash(file_bytes: bytes) -> str:
    """PDFなどのバイナリデータからSHA256ハッシュを計算する。"""
    return hashlib.sha256(file_bytes).hexdigest()


def log_gemini_token_usage(response, label: str = "Gemini Call"):
    """
    Gemini APIのレスポンスから使用トークン数をログ出力する共通関数。

    Args:
        response: genaiのレスポンスオブジェクト
        label: ログに出力するラベル（例: "ContextTrans", "OCR"）
    """
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        logger.info(
            f"Gemini Token Usage ({label}): "
            f"input={response.usage_metadata.prompt_token_count}, "
            f"output={response.usage_metadata.candidates_token_count}"
        )


def clean_text_for_tokenization(text: str) -> str:
    """
    テキストから余分な改行や空白を除去し、単語処理に適した形式にする。
    logic.py で使われている処理の共通化。
    """
    # 連続する改行で段落分割することを想定している箇所の前処理などで使用
    return text.replace("\r\n", "\n").replace("\n", " ").strip()


def truncate_context(text: str, target_word: str, max_length: int = 800) -> str:
    """
    指定された単語を中心に、テキストを最大長に切り詰める。
    src/logic.py の _translate_with_context での使用を想定。
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
