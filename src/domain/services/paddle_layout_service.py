"""
レイアウト解析サービス（ServiceB連携版）
推論処理をServiceBに委譲し、ServiceAは結果の取得のみを行う
"""

import asyncio
from typing import Any, Dict, List, Optional

from src.logger import get_service_logger
from src.providers.inference_client import get_inference_client, InferenceServiceError, CircuitBreakerError

log = get_service_logger("LayoutService")


class PaddleLayoutService:
    """
    レイアウト解析サービス（ServiceB連携版）
    実際の推論処理はServiceBで実行し、このクラスはクライアントとして機能
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PaddleLayoutService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.label_map = {
            0: "text",
            1: "title",
            2: "figure",
            3: "figure_caption",
            4: "table",
            5: "table_caption",
            6: "header",
            7: "footer",
            8: "reference",
            9: "equation",
        }

        self._initialized = True
        log.info("init", "PaddleLayoutService initialized (ServiceB client mode)")

    async def detect_layout_async(self, pdf_path: str, pages: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        PDFのレイアウト解析を非同期で実行（ServiceB経由）
        """
        try:
            log.info("detect_layout_async", f"Starting layout analysis for {pdf_path}")
            
            client = await get_inference_client()
            results = await client.analyze_layout(pdf_path, pages)
            
            log.info("detect_layout_async", f"Layout analysis completed: {len(results)} elements detected")
            return results
            
        except CircuitBreakerError as e:
            log.error("detect_layout_async", f"Circuit breaker error: {e}")
            # フォールバック: 空の結果を返す
            return []
            
        except InferenceServiceError as e:
            log.error("detect_layout_async", f"Inference service error: {e}")
            # フォールバック: 空の結果を返す
            return []
            
        except Exception as e:
            log.error("detect_layout_async", f"Unexpected error: {e}")
            return []

    def detect_layout(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        """
        同期版レイアウト検出（後方互換性のため保持）
        注意: この方法は非推奨。detect_layout_asyncを使用してください。
        """
        log.warning("detect_layout", "Synchronous layout detection is deprecated. Use detect_layout_async instead.")
        
        # 同期版では空の結果を返す（ServiceBは非同期のため）
        return []

    async def analyze_pdf_layout(self, pdf_path: str, pages: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        PDF全体のレイアウト解析
        """
        return await self.detect_layout_async(pdf_path, pages)


def get_layout_service():
    return PaddleLayoutService()
