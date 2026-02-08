"""
推論サービス（ServiceB）クライアント
レイアウト解析と翻訳処理のリモート呼び出し
"""

import asyncio
import logging
import os
import time
from typing import Any

import httpx

from common.schemas.inference import (
    LayoutAnalysisRequest,
    TranslationRequest,
)


class InferenceServiceError(Exception):
    """推論サービスエラー"""

    pass


class CircuitBreakerError(Exception):
    """回路ブレーカーエラー"""

    pass


logger = logging.getLogger(__name__)


class InferenceServiceClient:
    """推論サービスクライアント"""

    def __init__(self):
        self.base_url = os.getenv("INFERENCE_SERVICE_URL", "http://localhost:8080")
        self.timeout = int(os.getenv("INFERENCE_SERVICE_TIMEOUT", "60"))
        self.max_retries = int(
            os.getenv("INFERENCE_SERVICE_RETRIES", "2")
        )  # Reduced from 3 to 2

        # 回路ブレーカー設定
        self.failure_count = 0
        self.last_failure_time = None
        self.circuit_open = False
        self.failure_threshold = 5
        self.recovery_timeout = 60  # 1分

        # HTTPクライアント - HTTP/2有効化、接続プール最適化
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=20,  # 増加
                max_keepalive_connections=10,  # 増加
                keepalive_expiry=30.0,  # Keep-alive時間
            ),
            http2=True,  # HTTP/2有効化
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _check_circuit_breaker(self):
        """回路ブレーカーの状態チェック"""
        if self.circuit_open:
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time > self.recovery_timeout
            ):
                # 回路ブレーカーをリセット
                self.circuit_open = False
                self.failure_count = 0
                logger.info("回路ブレーカーをリセットしました")
            else:
                raise CircuitBreakerError("推論サービスの回路ブレーカーが開いています")

    def _record_success(self):
        """成功時の記録"""
        self.failure_count = 0
        if self.circuit_open:
            self.circuit_open = False
            logger.info("推論サービスが復旧しました")

    def _record_failure(self):
        """失敗時の記録"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.circuit_open = True
            logger.error(
                f"推論サービスの回路ブレーカーを開きました（失敗回数: {self.failure_count}）"
            )

    async def _make_request_with_retry(
        self, method: str, endpoint: str, **kwargs
    ) -> dict[str, Any]:
        """リトライ機能付きリクエスト"""
        self._check_circuit_breaker()

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                url = f"{self.base_url}{endpoint}"
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()

                self._record_success()
                return response.json()

            except httpx.HTTPError as e:
                last_exception = e
                logger.warning(
                    f"推論サービスリクエスト失敗 (試行 {attempt + 1}/{self.max_retries + 1}): {e}"
                )

                if attempt < self.max_retries:
                    # 指数バックオフ
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    self._record_failure()

        # 全ての試行が失敗
        raise InferenceServiceError(
            f"推論サービスへのリクエストが失敗しました: {last_exception}"
        )

    async def analyze_layout(
        self, pdf_path: str, pages: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """レイアウト解析の実行（PDF）"""
        request_data = LayoutAnalysisRequest(pdf_path=pdf_path, pages=pages)

        try:
            logger.info(f"レイアウト解析リクエスト: {pdf_path}")

            response = await self._make_request_with_retry(
                "POST", "/api/v1/layout-analysis", json=request_data.model_dump()
            )

            if response.get("success"):
                logger.info(
                    f"レイアウト解析完了: {response.get('processing_time', 0):.2f}秒"
                )
                return response.get("results", [])
            else:
                error_msg = response.get("message", "不明なエラー")
                raise InferenceServiceError(f"レイアウト解析失敗: {error_msg}")

        except Exception as e:
            logger.error(f"レイアウト解析エラー: {e}")
            raise

    async def analyze_image_async(self, image_bytes: bytes) -> list[dict[str, Any]]:
        """レイアウト解析の実行（画像データ）"""
        try:
            logger.info("画像データによるレイアウト解析リクエスト")

            # multipart/form-dataで画像を送信
            files = {"file": ("image.png", image_bytes, "image/png")}

            response = await self._make_request_with_retry(
                "POST", "/api/v1/analyze-image", files=files
            )

            if response.get("success"):
                logger.info(
                    f"レイアウト解析完了: {response.get('processing_time', 0):.2f}秒"
                )
                return response.get("results", [])
            else:
                error_msg = response.get("message", "不明なエラー")
                raise InferenceServiceError(f"レイアウト解析失敗: {error_msg}")

        except Exception as e:
            logger.error(f"画像レイアウト解析エラー: {e}")
            raise

    async def translate_text(self, text: str, target_lang: str = "ja") -> str:
        """単一テキストの翻訳"""
        request_data = TranslationRequest(text=text, target_lang=target_lang)

        try:
            logger.debug(f"翻訳リクエスト: {text[:50]}...")

            response = await self._make_request_with_retry(
                "POST", "/api/v1/translate", json=request_data.model_dump()
            )

            if response.get("success"):
                translation = response.get("translation", "")
                logger.debug(f"翻訳完了: {response.get('processing_time', 0):.2f}秒")
                return translation
            else:
                error_msg = response.get("message", "不明なエラー")
                raise InferenceServiceError(f"翻訳失敗: {error_msg}")

        except Exception as e:
            logger.error(f"翻訳エラー: {e}")
            raise

    async def health_check(self) -> dict[str, Any]:
        """推論サービスのヘルスチェック"""
        try:
            # Health check with reduced retries (1 attempt only)
            url = f"{self.base_url}/health"
            response = await self.client.get(url, timeout=5.0)  # 5 second timeout
            response.raise_for_status()

            self._record_success()
            return response.json()
        except Exception as e:
            self._record_failure()
            logger.error(f"ヘルスチェックエラー: {e}")
            raise


# シングルトンインスタンス
_inference_client: InferenceServiceClient | None = None


async def get_inference_client() -> InferenceServiceClient:
    """推論サービスクライアントの取得"""
    global _inference_client

    if _inference_client is None:
        _inference_client = InferenceServiceClient()

    return _inference_client


async def cleanup_inference_client():
    """推論サービスクライアントのクリーンアップ"""
    global _inference_client

    if _inference_client:
        await _inference_client.client.aclose()
        _inference_client = None
