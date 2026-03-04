"""
推論サービス（ServiceB）クライアント
レイアウト解析と翻訳処理のリモート呼び出し
"""

import asyncio
import os
import time
from typing import Any

import httpx

from common.logger import ServiceLogger
from common.schemas.inference import (
    LayoutAnalysisRequest,
    TranslationRequest,
)


class InferenceServiceError(Exception):
    """推論サービスエラー"""

    pass


class InferenceServiceTimeoutError(InferenceServiceError):
    """推論サービスタイムアウト（混雑）"""

    pass


class InferenceServiceDownError(InferenceServiceError):
    """推論サービスダウン"""

    pass


class CircuitBreakerError(Exception):
    """回路ブレーカーエラー"""

    pass


log = ServiceLogger("InferenceClient")


class InferenceServiceClient:
    """推論サービスクライアント"""

    def __init__(self):
        # 個別設定があればそれを使用し、なければ共通設定を使用する
        default_url = os.getenv("INFERENCE_SERVICE_URL", "http://localhost:8080")
        self.layout_base_url = os.getenv("INFERENCE_LAYOUT_URL", default_url)
        self.translation_base_url = os.getenv("INFERENCE_TRANSLATION_URL", default_url)

        self.timeout = int(os.getenv("INFERENCE_SERVICE_TIMEOUT", "60"))
        self.max_retries = int(os.getenv("INFERENCE_SERVICE_RETRIES", "2"))

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
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
            http2=True,
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
                log.info("circuit_breaker", "回路ブレーカーをリセットしました")
            else:
                raise CircuitBreakerError("推論サービスの回路ブレーカーが開いています")

    def _record_success(self):
        """成功時の記録"""
        self.failure_count = 0
        if self.circuit_open:
            self.circuit_open = False
            log.info("circuit_breaker", "推論サービスが復旧しました")

    def _record_failure(self):
        """失敗時の記録"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.circuit_open = True
            log.error(
                "circuit_breaker",
                "推論サービスの回路ブレーカーを開きました",
                failure_count=self.failure_count,
            )

    async def _make_request_with_retry(
        self, base_url: str, method: str, endpoint: str, **kwargs
    ) -> dict[str, Any]:
        """リトライ機能付きリクエスト"""
        self._check_circuit_breaker()

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                url = f"{base_url}{endpoint}"
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()

                self._record_success()
                return response.json()

            except httpx.HTTPError as e:
                last_exception = e
                log.warning(
                    "request",
                    "推論サービスリクエスト失敗",
                    attempt=attempt + 1,
                    max_retries=self.max_retries + 1,
                    error=str(e),
                )

                if attempt < self.max_retries:
                    # 指数バックオフ
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    self._record_failure()

        # 全ての試行が失敗
        if isinstance(last_exception, httpx.TimeoutException):
            raise InferenceServiceTimeoutError(
                f"推論サービスへのリクエストがタイムアウトしました: {last_exception}"
            )
        elif isinstance(
            last_exception, httpx.HTTPStatusError
        ) and last_exception.response.status_code in [429, 503]:
            raise InferenceServiceTimeoutError(
                f"推論サービスが混雑しています (Status {last_exception.response.status_code}): {last_exception}"
            )
        else:
            raise InferenceServiceDownError(
                f"推論サービスへのリクエストが失敗しました: {last_exception}"
            )

    async def analyze_layout(
        self, pdf_path: str, pages: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """レイアウト解析の実行（PDF）"""
        request_data = LayoutAnalysisRequest(pdf_path=pdf_path, pages=pages)

        try:
            log.debug("analyze_layout", "レイアウト解析リクエスト", pdf_path=pdf_path)

            response = await self._make_request_with_retry(
                self.layout_base_url,
                "POST",
                "/api/v1/layout-analysis",
                json=request_data.model_dump(),
            )

            if response.get("success"):
                log.debug(
                    "analyze_layout",
                    "レイアウト解析完了",
                    processing_time=response.get("processing_time", 0),
                )

                return response.get("results", [])
            else:
                error_msg = response.get("message", "不明なエラー")
                raise InferenceServiceError(f"レイアウト解析失敗: {error_msg}")

        except Exception as e:
            log.error("analyze_layout", "レイアウト解析エラー", error=str(e))

            raise

    async def analyze_image_async(self, image_bytes: bytes) -> list[dict[str, Any]]:
        """レイアウト解析の実行（画像データ）"""
        try:
            log.debug("analyze_image", "画像データによるレイアウト解析リクエスト")

            # multipart/form-dataで画像を送信
            files = {"file": ("image.png", image_bytes, "image/png")}

            response = await self._make_request_with_retry(
                self.layout_base_url, "POST", "/api/v1/analyze-image", files=files
            )

            if response.get("success"):
                log.debug(
                    "analyze_image",
                    "レイアウト解析完了",
                    processing_time=response.get("processing_time", 0),
                )

                return response.get("results", [])
            else:
                error_msg = response.get("message", "不明なエラー")
                raise InferenceServiceError(f"レイアウト解析失敗: {error_msg}")

        except Exception as e:
            log.error("analyze_image", "画像レイアウト解析エラー", error=str(e))

            raise

    async def analyze_images_batch(
        self, images: list[bytes], max_batch_size: int = 10
    ) -> list[list[dict[str, Any]]]:
        """
        複数画像を一括で解析（バッチ処理）

        Parameters
        ----------
        images : list[bytes]
            解析対象の画像データリスト
        max_batch_size : int
            1リクエストあたりの最大画像数

        Returns
        -------
        list[list[dict[str, Any]]]
            各画像の解析結果リスト
        """
        try:
            log.debug(
                "analyze_batch",
                "バッチレイアウト解析リクエスト",
                image_count=len(images),
            )

            # バッチサイズで分割
            all_results = []
            for i in range(0, len(images), max_batch_size):
                batch = images[i : i + max_batch_size]

                # multipart/form-dataで複数画像を送信
                files = [
                    ("files", (f"image_{j}.jpg", img, "image/jpeg"))
                    for j, img in enumerate(batch)
                ]

                response = await self._make_request_with_retry(
                    self.layout_base_url,
                    "POST",
                    "/api/v1/analyze-images-batch",
                    files=files,
                )

                if response.get("success"):
                    batch_results = response.get("results", [])
                    all_results.extend(batch_results)
                    log.debug(
                        "analyze_batch",
                        "サブバッチの送信・解析が完了",
                        batch_size=len(batch),
                        processing_time=response.get("processing_time", 0),
                    )

                else:
                    error_msg = response.get("message", "不明なエラー")
                    raise InferenceServiceError(f"バッチ解析失敗: {error_msg}")

            log.debug(
                "analyze_batch",
                "リクエストされた全画像の解析が完了しました",
                result_count=len(all_results),
            )

            return all_results

        except Exception as e:
            log.error("analyze_batch", "バッチレイアウト解析エラー", error=str(e))

            raise

    async def analyze_images_batch_streaming(
        self, images: list[bytes], max_batch_size: int = 10
    ):
        """
        複数画像をバッチで解析し、バッチ完了ごとに結果を yield する (async generator)

        Returns
        -------
        AsyncGenerator[(batch_start_index, list[dict]), ...]
            バッチの先頭インデックスと、そのバッチ内の各画像の解析結果リスト
        """
        log.debug(
            "analyze_batch_streaming",
            "ストリーミングバッチ解析開始",
            image_count=len(images),
        )

        for i in range(0, len(images), max_batch_size):
            batch = images[i : i + max_batch_size]

            files = [
                ("files", (f"image_{j}.jpg", img, "image/jpeg"))
                for j, img in enumerate(batch)
            ]

            try:
                response = await self._make_request_with_retry(
                    self.layout_base_url,
                    "POST",
                    "/api/v1/analyze-images-batch",
                    files=files,
                )

                if response.get("success"):
                    batch_results = response.get("results", [])
                    log.debug(
                        "analyze_batch_streaming",
                        "サブバッチ完了 → yield",
                        batch_start=i,
                        batch_size=len(batch),
                        processing_time=response.get("processing_time", 0),
                    )
                    # バッチが返ってきた時点で即座に yield
                    yield i, batch_results
                else:
                    error_msg = response.get("message", "不明なエラー")
                    raise InferenceServiceError(f"バッチ解析失敗: {error_msg}")

            except Exception as e:
                log.error(
                    "analyze_batch_streaming",
                    "サブバッチ解析エラー（スキップ）",
                    batch_start=i,
                    error=str(e),
                )
                # 1バッチに失敗しても他のバッチは続ける
                yield i, [[] for _ in batch]

    async def translate_text(
        self, text: str, target_lang: str = "ja", paper_context: str | None = None
    ) -> tuple[str, str | None]:
        """単一テキストの翻訳"""
        request_data = TranslationRequest(
            text=text, target_lang=target_lang, paper_context=paper_context
        )

        try:
            log.debug("translate", "翻訳リクエスト", text_preview=text[:50])

            # ... content omitted ...
            response = await self._make_request_with_retry(
                self.translation_base_url,
                "POST",
                "/api/v1/translate",
                json=request_data.model_dump(),
            )

            if response.get("success"):
                translation = response.get("translation", "")
                model = response.get("model")
                log.debug(
                    "translate",
                    "翻訳完了",
                    model=model,
                    processing_time=response.get("processing_time", 0),
                )

                return translation, model
            else:
                error_msg = response.get("message", "不明なエラー")
                raise InferenceServiceError(f"翻訳失敗: {error_msg}")

        except Exception as e:
            log.error("translate", "翻訳エラー", error=str(e))

            raise

    async def health_check(self) -> dict[str, Any]:
        """推論サービスのヘルスチェック"""
        try:
            # Health check with reduced retries (1 attempt only)
            url = f"{self.layout_base_url}/health"  # 簡易的にlayout側を確認
            response = await self.client.get(url, timeout=5.0)  # 5 second timeout
            response.raise_for_status()

            self._record_success()
            return response.json()
        except Exception as e:
            self._record_failure()
            log.error("health_check", "ヘルスチェックエラー", error=str(e))

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
