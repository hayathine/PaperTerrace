"""
推論サービス（ServiceB）クライアント
レイアウト解析のリモート呼び出し
"""

import asyncio
import json
import os
import time
from typing import Any

import httpx

from common.config import settings
from common.logger import ServiceLogger
from common.schemas.inference import LayoutAnalysisRequest


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
    """推論サービスクライアント（レイアウト解析専用）"""

    def __init__(self):
        default_url = settings.get("INFERENCE_SERVICE_URL", "http://localhost:8080")
        primary_url = settings.get("INFERENCE_LAYOUT_URL", default_url)

        # 追加エンドポイント（カンマ区切り）でラウンドロビン対応
        extra_urls = [
            u.strip()
            for u in settings.get("INFERENCE_LAYOUT_EXTRA_URLS", "").split(",")
            if u.strip()
        ]
        self.layout_urls: list[str] = [primary_url] + extra_urls
        self._rr_index: int = 0

        # 後方互換
        self.layout_base_url = primary_url

        # Translation 翻訳用 URL
        translate_url = settings.get("INFERENCE_TRANSLATE_URL", "")
        self.translate_url: str = translate_url.strip()
        self.translate_disabled: bool = not bool(self.translate_url)

        # OCR crops 専用 URL（OCR 対応 Pod のみ指定 = G3）
        ocr_crops_url = settings.get("INFERENCE_OCR_CROPS_URL", "")
        self.ocr_crops_url: str = ocr_crops_url.strip()
        self.ocr_crops_disabled: bool = not bool(self.ocr_crops_url)

        self.timeout = int(settings.get("INFERENCE_SERVICE_TIMEOUT", "60"))
        self.max_retries = int(settings.get("INFERENCE_SERVICE_RETRIES", "2"))

        # 無効化フラグ
        self.is_disabled = (
            str(settings.get("INFERENCE_SERVICE_DISABLED", "false")).lower() == "true"
        )

        # 回路ブレーカー設定
        self.failure_threshold = 5
        self.recovery_timeout = 60  # 1分
        all_urls = self.layout_urls + ([self.ocr_crops_url] if self.ocr_crops_url else []) + ([self.translate_url] if self.translate_url else [])
        self._circuit_state: dict[str, dict] = {
            url: {"failure_count": 0, "last_failure_time": None, "circuit_open": False}
            for url in all_urls
        }

        # SSL検証設定
        verify_env = str(settings.get("INFERENCE_VERIFY_SSL", "true")).lower()
        if verify_env == "false":
            self.verify_ssl = False
        elif os.path.isfile(verify_env):
            self.verify_ssl = verify_env
        else:
            self.verify_ssl = True

        # HTTPクライアント - HTTP/2有効化、接続プール最適化
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
            http2=True,
            verify=self.verify_ssl,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _next_layout_url(self) -> str:
        """ラウンドロビンで次の利用可能なURLを返す。全URL遮断中は先頭を返す。"""
        for _ in range(len(self.layout_urls)):
            url = self.layout_urls[self._rr_index % len(self.layout_urls)]
            self._rr_index += 1
            state = self._circuit_state[url]
            if not state["circuit_open"]:
                return url
            # 回復タイムアウト経過済みなら復旧して返す
            if state["last_failure_time"] and time.time() - state["last_failure_time"] > self.recovery_timeout:
                state["circuit_open"] = False
                state["failure_count"] = 0
                return url
        # 全URL遮断中はとりあえず先頭を返す
        return self.layout_urls[0]

    def _check_circuit_breaker(self, service: str):
        """回路ブレーカーの状態チェック"""
        state = self._circuit_state[service]
        if state["circuit_open"]:
            if (
                state["last_failure_time"]
                and time.time() - state["last_failure_time"] > self.recovery_timeout
            ):
                state["circuit_open"] = False
                state["failure_count"] = 0
                log.info("circuit_breaker", "回路ブレーカーをリセットしました", service=service)
            else:
                raise CircuitBreakerError("推論サービスの回路ブレーカーが開いています")

    def _record_success(self, service: str):
        """成功時の記録"""
        state = self._circuit_state[service]
        state["failure_count"] = 0
        if state["circuit_open"]:
            state["circuit_open"] = False
            log.info("circuit_breaker", "推論サービスが復旧しました", service=service)

    def _record_failure(self, service: str):
        """失敗時の記録"""
        state = self._circuit_state[service]
        state["failure_count"] += 1
        state["last_failure_time"] = time.time()

        if state["failure_count"] >= self.failure_threshold:
            state["circuit_open"] = True
            log.error(
                "circuit_breaker",
                "推論サービスの回路ブレーカーを開きました",
                service=service,
                failure_count=state["failure_count"],
            )

    async def _make_request_with_retry(
        self, base_url: str, method: str, endpoint: str, service: str | None = None, timeout: int | None = None, **kwargs
    ) -> dict[str, Any]:
        """リトライ機能付きリクエスト"""
        if self.is_disabled:
            log.warning(
                "request_disabled", "推論サービスが環境変数により無効化されています"
            )
            raise InferenceServiceDownError(
                "Inference service is disabled by configuration"
            )

        # circuit breaker キーは base_url を使用（後方互換で service も受け付ける）
        cb_key = base_url if base_url in self._circuit_state else (service or base_url)
        if cb_key not in self._circuit_state:
            self._circuit_state[cb_key] = {"failure_count": 0, "last_failure_time": None, "circuit_open": False}

        self._check_circuit_breaker(cb_key)

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                url = f"{base_url}{endpoint}"
                request_timeout = httpx.Timeout(timeout, connect=10.0) if timeout else None
                response = await self.client.request(method, url, timeout=request_timeout, **kwargs)
                response.raise_for_status()

                self._record_success(cb_key)
                return response.json()

            except httpx.HTTPError as e:
                last_exception = e

                # SSLエラー・接続エラー・503(Busy)はリトライせず即座に失敗させる
                error_str = str(e).lower()
                is_ssl_error = "ssl" in error_str or "cert" in error_str
                is_conn_error = isinstance(
                    e, (httpx.ConnectError, httpx.ConnectTimeout)
                )
                is_busy = (
                    isinstance(e, httpx.HTTPStatusError)
                    and e.response.status_code == 503
                )

                log.warning(
                    "request",
                    "推論サービスリクエスト失敗",
                    attempt=attempt + 1,
                    max_retries=self.max_retries + 1,
                    error=str(e),
                    is_fatal=is_ssl_error or is_conn_error or is_busy,
                )

                if (
                    attempt < self.max_retries
                    and not is_ssl_error
                    and not is_conn_error
                    and not is_busy
                ):
                    # 指数バックオフ
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    self._record_failure(cb_key)

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
                service="layout",
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
            files = {"file": ("image.jpg", image_bytes, "image/jpeg")}

            response = await self._make_request_with_retry(
                self.layout_base_url, "POST", "/api/v1/analyze-image", service="layout", files=files
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
        self,
        images: list[bytes],
        page_nums: list[int] | None = None,
        max_batch_size: int = 10,
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
            all_crops: list[list[dict]] = []
            for i in range(0, len(images), max_batch_size):
                batch = images[i : i + max_batch_size]

                # multipart/form-dataで複数画像を送信
                files = []
                for j, img in enumerate(batch):
                    page_num = page_nums[i + j] if page_nums else j
                    files.append(("files", (f"page_{page_num}.jpg", img, "image/jpeg")))

                target_url = self._next_layout_url()
                response = await self._make_request_with_retry(
                    target_url,
                    "POST",
                    "/api/v1/analyze-images-batch",
                    files=files,
                )

                if response.get("success"):
                    batch_results = response.get("results", [])
                    batch_crops = response.get("crops", [[] for _ in batch])
                    all_results.extend(batch_results)
                    all_crops.extend(batch_crops)
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

            return all_results, all_crops

        except Exception as e:
            log.error("analyze_batch", "バッチレイアウト解析エラー", error=str(e))

            raise

    async def analyze_images_batch_by_urls(
        self,
        image_urls: list[str],
        page_nums: list[int] | None = None,
        max_batch_size: int = 10,
    ) -> list[list[dict[str, Any]]]:
        """
        署名付きURL経由で複数画像を一括解析。
        推論サービスが直接GCSからダウンロードするためバックエンドのメモリ転送が不要。
        """
        from common.schemas.inference import LayoutBatchByUrlsRequest

        try:
            log.debug(
                "analyze_batch_by_urls",
                "URL経由バッチレイアウト解析リクエスト",
                image_count=len(image_urls),
            )

            all_results = []
            all_crops: list[list[dict]] = []
            for i in range(0, len(image_urls), max_batch_size):
                batch_urls = image_urls[i : i + max_batch_size]
                batch_page_nums = page_nums[i : i + max_batch_size] if page_nums else None

                req = LayoutBatchByUrlsRequest(
                    image_urls=batch_urls,
                    page_nums=batch_page_nums,
                )

                target_url = self._next_layout_url()
                response = await self._make_request_with_retry(
                    target_url,
                    "POST",
                    "/api/v1/analyze-images-batch-by-urls",
                    json=req.model_dump(),
                )

                if response.get("success"):
                    batch_results = response.get("results", [])
                    batch_crops = response.get("crops", [[] for _ in batch_urls])
                    all_results.extend(batch_results)
                    all_crops.extend(batch_crops)
                    log.debug(
                        "analyze_batch_by_urls",
                        "サブバッチ完了",
                        batch_size=len(batch_urls),
                        processing_time=response.get("processing_time", 0),
                    )
                else:
                    error_msg = response.get("message", "不明なエラー")
                    raise InferenceServiceError(f"URL経由バッチ解析失敗: {error_msg}")

            log.debug(
                "analyze_batch_by_urls",
                "全URL経由解析完了",
                result_count=len(all_results),
            )
            return all_results, all_crops

        except Exception as e:
            log.error("analyze_batch_by_urls", "URL経由バッチ解析エラー", error=str(e))
            raise

    async def analyze_images_batch_streaming(
        self,
        images: list[bytes],
        page_nums: list[int] | None = None,
        max_batch_size: int = 10,
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

            files = []
            for j, img in enumerate(batch):
                page_num = page_nums[i + j] if page_nums else i + j
                files.append(("files", (f"page_{page_num}.jpg", img, "image/jpeg")))

            try:
                target_url = self._next_layout_url()
                response = await self._make_request_with_retry(
                    target_url,
                    "POST",
                    "/api/v1/analyze-images-batch",
                    files=files,
                )

                if response.get("success"):
                    batch_results = response.get("results", [])
                    batch_crops = response.get("crops", [[] for _ in batch])
                    log.debug(
                        "analyze_batch_streaming",
                        "サブバッチ完了 → yield",
                        batch_start=i,
                        batch_size=len(batch),
                        processing_time=response.get("processing_time", 0),
                    )
                    # バッチが返ってきた時点で即座に yield
                    yield i, batch_results, batch_crops
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
                yield i, [[] for _ in batch], [[] for _ in batch]

    async def ocr_crops(
        self, img_bytes: bytes, layout_blocks: list[dict]
    ) -> str:
        """OCR 対応 Pod（G3）の /api/v1/ocr-crops を呼び出してテキストを取得する。"""
        if self.ocr_crops_disabled:
            raise InferenceServiceDownError("OCR crops service not configured (INFERENCE_OCR_CROPS_URL not set)")

        cb_key = self.ocr_crops_url
        if cb_key not in self._circuit_state:
            self._circuit_state[cb_key] = {"failure_count": 0, "last_failure_time": None, "circuit_open": False}
        self._check_circuit_breaker(cb_key)

        timeout = int(settings.get("INFERENCE_OCR_TIMEOUT", "120"))

        try:
            files = {"file": ("page.jpg", img_bytes, "image/jpeg")}
            data = {"layout_blocks_json": json.dumps(layout_blocks)}

            resp = await self.client.post(
                f"{self.ocr_crops_url}/api/v1/ocr-crops",
                files=files,
                data=data,
                timeout=timeout,
            )
            resp.raise_for_status()
            result = resp.json()

            self._record_success(cb_key)
            if result.get("success"):
                return result.get("text", "")

            raise InferenceServiceError(result.get("message", "OCR crops failed"))

        except httpx.HTTPError as e:
            self._record_failure(cb_key)
            raise InferenceServiceDownError(f"OCR crops request failed: {e}") from e

    async def translate_text(
        self, text: str, tgt_lang: str = "ja", paper_context: str | None = None
    ) -> str:
        """Llama 翻訳 Pod を呼び出して翻訳を実行する。"""
        if self.translate_disabled:
            raise InferenceServiceDownError("Translation service not configured (INFERENCE_TRANSLATE_URL not set)")

        cb_key = self.translate_url
        if cb_key not in self._circuit_state:
            self._circuit_state[cb_key] = {"failure_count": 0, "last_failure_time": None, "circuit_open": False}
        self._check_circuit_breaker(cb_key)

        timeout = int(settings.get("INFERENCE_TRANSLATE_TIMEOUT", "120"))

        try:
            payload = {
                "text": text,
                "tgt_lang": tgt_lang,
                "paper_context": paper_context,
            }
            log.debug("translate_text", "翻訳リクエスト", text_len=len(text))

            resp = await self.client.post(
                f"{self.translate_url}/api/v1/translate",
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            result = resp.json()

            self._record_success(cb_key)
            if result.get("success"):
                log.info("translate_text", "翻訳成功", word=text[:20])
                return result.get("translation", "")

            raise InferenceServiceError(result.get("message", "Translation failed"))

        except httpx.HTTPError as e:
            self._record_failure(cb_key)
            log.error("translate_text", "翻訳リクエスト失敗", error=str(e))
            raise InferenceServiceDownError(f"Translation request failed: {e}") from e

    async def health_check(self) -> dict[str, Any]:
        """推論サービスのヘルスチェック"""
        try:
            # Health check with reduced retries (1 attempt only)
            url = f"{self.layout_base_url}/health"  # 簡易的にlayout側を確認
            response = await self.client.get(url, timeout=5.0)  # 5 second timeout
            response.raise_for_status()

            self._record_success("layout")
            return response.json()
        except Exception as e:
            self._record_failure("layout")
            log.error("health_check", "ヘルスチェックエラー", error=str(e))

            raise


class OcrInferenceClient:
    """ローカル OCR 推論サービスクライアント（PaddleOCR / OpenVINO）。"""

    def __init__(self) -> None:
        self.ocr_url: str = settings.get("INFERENCE_OCR_URL", "")
        self.timeout: int = int(settings.get("INFERENCE_OCR_TIMEOUT", "30"))
        self.is_disabled: bool = not self.ocr_url or str(
            settings.get("INFERENCE_OCR_DISABLED", "false")
        ).lower() == "true"

        # 回路ブレーカー（InferenceServiceClient と同構造）
        self._cb: dict = {
            "failure_count": 0,
            "last_failure_time": None,
            "circuit_open": False,
        }
        self.failure_threshold: int = 5
        self.recovery_timeout: int = 60

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )

    def is_available(self) -> bool:
        """OCR サービスが利用可能かを確認する。"""
        if self.is_disabled:
            return False
        if self._cb["circuit_open"]:
            last_fail = self._cb["last_failure_time"]
            if last_fail and time.time() - last_fail > self.recovery_timeout:
                self._cb.update({"circuit_open": False, "failure_count": 0})
                return True
            return False
        return True

    async def ocr_page(
        self, img_bytes: bytes, bboxes: list[dict] | None = None
    ) -> str:
        """画像バイトを OCR サービスに送り、認識テキストを返す。

        Args:
            img_bytes: ページ画像バイト（JPEG/PNG 等）
            bboxes: テキスト領域 bbox のリスト（省略時は自動検出）
        Returns:
            認識テキスト文字列
        """
        if not self.is_available():
            raise InferenceServiceDownError("OCR service circuit open or disabled")

        try:
            files = {"file": ("page.jpg", img_bytes, "image/jpeg")}
            data = {"bboxes_json": json.dumps(bboxes)} if bboxes else {}

            resp = await self.client.post(
                f"{self.ocr_url}/api/v1/ocr-page",
                files=files,
                data=data,
            )
            resp.raise_for_status()
            result = resp.json()

            if result.get("success"):
                self._cb["failure_count"] = 0
                return result.get("text", "")

            raise InferenceServiceError(result.get("message", "OCR failed"))

        except httpx.HTTPError as e:
            self._cb["failure_count"] += 1
            self._cb["last_failure_time"] = time.time()
            if self._cb["failure_count"] >= self.failure_threshold:
                self._cb["circuit_open"] = True
                log.error("ocr_page", "OCR サービスの回路ブレーカーを開きました")
            raise InferenceServiceDownError(f"OCR request failed: {e}") from e


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


# OCR クライアントのシングルトン
_ocr_client: OcrInferenceClient | None = None


async def get_ocr_client() -> OcrInferenceClient:
    """OCR 推論サービスクライアントの取得"""
    global _ocr_client
    if _ocr_client is None:
        _ocr_client = OcrInferenceClient()
    return _ocr_client
