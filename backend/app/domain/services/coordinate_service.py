from typing import Any, Dict, List

from app.logger import logger


class CoordinateService:
    """
    レイアウト要素の座標管理
    Gemini, Heron, Suryaを切り替え、図表や数式の位置を特定・キャッシュ。
    """

    def __init__(self):
        pass

    async def identify_coordinates(self, file_bytes: bytes, page_num: int) -> List[Dict[str, Any]]:
        """特定された要素の座標を返す。"""
        logger.info(f"Identifying coordinates for page {page_num}")
        return []
