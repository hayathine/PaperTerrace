"""
レイアウト解析サービス（ServiceB連携版）
推論処理をServiceBに委譲し、ServiceAは結果の取得のみを行う
"""

import asyncio
from typing import Any

from app.providers.inference_client import (
    CircuitBreakerError,
    InferenceServiceError,
    get_inference_client,
)
from common.logger import ServiceLogger

log = ServiceLogger("LayoutService")


class PaddleLayoutService:
    """
    レイアウト解析サービス（ServiceB連携版）
    実際の推論処理はServiceBで実行し、このクラスはクライアントとして機能
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        log.info("init", "PaddleLayoutService initialized (ServiceB client mode)")

    async def detect_layout_async(
        self, pdf_path: str, pages: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """
        PDFのレイアウト解析を非同期で実行（ServiceB経由）

        大きなPDF（例: 30ページ以上）の場合、一括処理するとタイムアウトするリスクがあるため、
        クライアント側でページを分割（チャンク化）してリクエストを送る。
        """
        import pdfplumber

        try:
            # ページ指定がない場合は全ページ数を取得
            target_pages = pages
            if target_pages is None:
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        total_pages = len(pdf.pages)
                        target_pages = list(range(total_pages))
                        target_pages = list(range(total_pages))

                except Exception as e:
                    log.error(
                        "detect_layout_async", "Failed to count pages", error=str(e)
                    )

                    # ページ数取得に失敗した場合は、従来通り一括で送る（ServiceB側での処理に任せる）
                    target_pages = None

            client = await get_inference_client()
            all_results = []

            if target_pages:
                # チャンク分割処理（5ページごとにリクエスト）
                CHUNK_SIZE = 5
                tasks = []

                for i in range(0, len(target_pages), CHUNK_SIZE):
                    chunk = target_pages[i : i + CHUNK_SIZE]

                    # 各チャンクを並列タスクとして登録
                    tasks.append(client.analyze_layout(pdf_path, chunk))

                # 全チャンクを並列実行
                if tasks:
                    # return_exceptions=Trueで一部失敗しても全体を止めない
                    chunk_results_list = await asyncio.gather(
                        *tasks, return_exceptions=True
                    )

                    for i, result in enumerate(chunk_results_list):
                        if isinstance(result, Exception):
                            log.error(
                                "detect_layout_async",
                                "Chunk failed",
                                chunk_index=i,
                                error=str(result),
                            )

                            # 失敗したチャンクはスキップ（または再試行ロジックを入れるか）
                        elif isinstance(result, list):
                            all_results.extend(result)
                        else:
                            log.warning(
                                "detect_layout_async",
                                "Chunk returned unexpected type",
                                chunk_index=i,
                                type=str(type(result)),
                            )

            else:
                # ページリストがない場合（互換性）
                all_results = await client.analyze_layout(pdf_path, None)

            return all_results

        except CircuitBreakerError as e:
            log.error("detect_layout_async", "Circuit breaker error", error=str(e))

            # フォールバック: 空の結果を返す
            return []

        except InferenceServiceError as e:
            log.error("detect_layout_async", "Inference service error", error=str(e))

            # フォールバック: 空の結果を返す
            return []

        except Exception as e:
            log.error("detect_layout_async", "Unexpected error", error=str(e))

            return []

    async def detect_layout_from_image_async(
        self, image_bytes: bytes
    ) -> list[dict[str, Any]]:
        """
        画像データから直接レイアウト解析を実行（ServiceB経由）

        Parameters
        ----------
        image_bytes : bytes
            解析対象の画像データ（JPEG/WebP）

        Returns
        -------
        list[dict[str, Any]]
            検出されたレイアウト要素のリスト
            形式: [{"bbox": {"x_min": ..., "y_min": ..., "x_max": ..., "y_max": ...}, "class_name": ..., "score": ...}, ...]
        """
        try:
            client = await get_inference_client()
            results = await client.analyze_image_async(image_bytes)

            return results

        except CircuitBreakerError as e:
            log.error(
                "detect_layout_from_image_async", "Circuit breaker error", error=str(e)
            )

            return []

        except InferenceServiceError as e:
            log.error(
                "detect_layout_from_image_async",
                "Inference service error",
                error=str(e),
            )

            return []

        except Exception as e:
            log.error(
                "detect_layout_from_image_async", "Unexpected error", error=str(e)
            )

            return []

    def detect_layout(self, image_bytes: bytes) -> list[dict[str, Any]]:
        """
        同期版レイアウト検出（後方互換性のため保持）
        注意: この方法は非推奨。detect_layout_asyncを使用してください。
        """
        log.warning(
            "detect_layout",
            "Synchronous layout detection is deprecated. Use detect_layout_async instead.",
        )

        # 同期版では空の結果を返す（ServiceBは非同期のため）
        return []

    async def analyze_pdf_layout(
        self, pdf_path: str, pages: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """
        PDF全体のレイアウト解析
        """
        return await self.detect_layout_async(pdf_path, pages)


def get_layout_service():
    return PaddleLayoutService()
