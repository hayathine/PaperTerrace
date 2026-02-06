import hashlib


def get_file_hash(file_bytes: bytes) -> str:
    """PDFなどのバイナリデータからSHA256ハッシュを計算する。"""
    return hashlib.sha256(file_bytes).hexdigest()
