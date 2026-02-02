from src.logger import logger


class SuryaService:
    """
    ローカルOCR/レイアウト
    Suryaモデルによる、PDF内部情報に頼らない視覚的なテキスト位置特定。
    """

    def __init__(self):
        pass

    async def extract_text(self, image_bytes: bytes):
        """Suryaモデルを使用してテキストを抽出する。"""
        logger.info("Surya OCR extraction (placeholder)")
        return []
