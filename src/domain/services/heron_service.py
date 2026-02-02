from src.logger import logger


class HeronService:
    """
    ローカルレイアウト解析
    Docling Heronモデルを用いたCPU推論によるオフライン座標検出（OpenVINO対応予定）。
    """

    def __init__(self):
        pass

    async def detect_layout(self, image_bytes: bytes):
        """Heronモデルを使用してレイアウトを検出する。"""
        logger.info("Heron layout detection (placeholder)")
        return []
