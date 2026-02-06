"""
レイアウト解析サービスのクライアント
Inference Service (Service B) へリクエストをプロキシする
"""

import logging
import os
from pathlib import Path
from typing import List

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BBox(BaseModel):
    """バウンディングボックス"""

    x_min: float
    y_min: float
    x_max: float
    y_max: float


class LayoutItem(BaseModel):
    """レイアウト要素"""

    bbox: BBox
    class_name: str
    score: float


class LayoutAnalysisService:
    """レイアウト解析サービス (Inference Service Client)"""

    def __init__(self):
        # 推論サービスのURL (環境変数から取得)
        # デフォルトはDocker Compose / Cloud Runのサービス名
        self.inference_service_url = os.getenv(
            "INFERENCE_SERVICE_URL", "http://paperterrace-inference:8080"
        )
        logger.info(
            f"Initialized LayoutAnalysisService with URL: {self.inference_service_url}"
        )

    async def analyze_image(self, image_path: str | Path) -> List[LayoutItem]:
        """
        Inference Service API (/api/v1/analyze-image) を呼び出す

        Parameters
        ----------
        image_path : str | Path
            解析対象の画像ファイルパス

        Returns
        -------
        List[LayoutItem]
            検出されたレイアウト要素
        """
        url = f"{self.inference_service_url.rstrip('/')}/api/v1/analyze-image"
        logger.info(f"Calling inference service: {url} with image: {image_path}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(image_path, "rb") as f:
                    files = {"file": (os.path.basename(image_path), f, "image/png")}
                    response = await client.post(url, files=files)

                    response.raise_for_status()

                    data = response.json()

                    if not data.get("success"):
                        error_msg = data.get(
                            "message", "Unknown error from inference service"
                        )
                        logger.error(f"Inference service failed: {error_msg}")
                        raise RuntimeError(f"Inference service error: {error_msg}")

                    results = data.get("results", [])
                    logger.info(
                        f"Received {len(results)} layout elements from inference service"
                    )

                    # LayoutItemに変換
                    layout_items = []
                    for item in results:
                        bbox_data = item["bbox"]
                        bbox = BBox(
                            x_min=bbox_data["x_min"],
                            y_min=bbox_data["y_min"],
                            x_max=bbox_data["x_max"],
                            y_max=bbox_data["y_max"],
                        )
                        layout_items.append(
                            LayoutItem(
                                bbox=bbox,
                                class_name=item["class_name"],
                                score=item["score"],
                            )
                        )

                    return layout_items

        except httpx.HTTPError as e:
            logger.error(f"HTTP error communicating with inference service: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to call inference service: {e}")
            raise


# シングルトンインスタンス
_layout_service_instance = None


def get_layout_service() -> LayoutAnalysisService:
    """レイアウト解析サービスのシングルトンインスタンスを取得"""
    global _layout_service_instance
    if _layout_service_instance is None:
        _layout_service_instance = LayoutAnalysisService()
    return _layout_service_instance
