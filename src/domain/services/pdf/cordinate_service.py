import asyncio
import io
import os
from typing import List, Optional

from PIL import Image

from src.core.logger import logger
from src.domain.prompts import VISION_DETECT_ITEMS_PROMPT
from src.models.schemas.figure import BboxResponse, FigureDetectionResponse


class CoordinateService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CoordinateService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._device = None
        self._inference_lock = asyncio.Lock()  # 重複推論防止のためのロック

        # 画像単位の結果キャッシュ
        self._clear_cache()

        self._initialized = True
        logger.info("[CoordinateService] Initialized with Cache")

    def _clear_cache(self, image: Optional[Image.Image] = None):
        """内部キャッシュのリセット。imageが指定された場合はそのIDをセットする"""
        self._cache_image_id = id(image) if image else None
        self._cache_heron_results = []
        self._cache_surya_results = []
        self._cache_gemini_results = []

    def clear_all_caches(self):
        """外部から呼び出し可能な全キャッシュクリアとGC実行"""
        self._clear_cache()
        import gc

        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except (ImportError, RuntimeError):
            pass
        logger.debug("[CoordinateService] All caches cleared and GC executed")

    @property
    def device(self):
        if self._device is None:
            try:
                import torch

                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._device = "cpu"
        return self._device

    async def _get_heron_results(self, image: Image.Image) -> List[BboxResponse]:
        """
        HeronServiceを使用して解析を行う。
        """
        from src.domain.services.pdf.heron_service import heron_service

        # ロックを使用して同時呼び出しを制御
        async with self._inference_lock:
            if self._cache_image_id == id(image) and self._cache_heron_results:
                logger.debug(f"[CoordinateService] Heron Cache hit for image object {id(image)}")
                return self._cache_heron_results

            results_raw = await heron_service.detect_layout(image)
            # Identify only tables and formulas/equations
            allowed_labels = ("table", "formula", "equation")
            results = [
                BboxResponse(**res) for res in results_raw if res["label"].lower() in allowed_labels
            ]

            self._update_cache(image, results, "heron")
            return results

    async def _get_surya_results(self, image: Image.Image) -> List[BboxResponse]:
        """
        SuryaServiceを使用して解析を行う。
        """
        from src.domain.services.pdf.surya_service import surya_service

        async with self._inference_lock:
            if self._cache_image_id == id(image) and self._cache_surya_results:
                logger.debug(f"[CoordinateService] Surya Cache hit for image object {id(image)}")
                return self._cache_surya_results

            results_raw = await surya_service.detect_layout(image)
            # Identify only tables and formulas/equations
            allowed_labels = ("table", "formula", "equation")
            results = [
                BboxResponse(**res) for res in results_raw if res["label"].lower() in allowed_labels
            ]

            self._update_cache(image, results, "surya")
            return results

    def _update_cache(self, image: Image.Image, results: List[BboxResponse], parser_type: str):
        """解析結果でキャッシュを更新する"""
        # ロック内で呼ばれることを想定
        if self._cache_image_id != id(image):
            self._clear_cache(image)

        if parser_type == "heron":
            self._cache_heron_results = results
        elif parser_type == "surya":
            self._cache_surya_results = results
        elif parser_type == "gemini":
            self._cache_gemini_results = results

    async def get_all_items(self, image: Image.Image) -> List[BboxResponse]:
        """
        画像内の全レイアウト要素（Table, Formula, Figure 等）を一括で取得する。
        """
        from src.core.utils.memory import get_available_memory_mb

        avail_mb = get_available_memory_mb()

        # 1. 外部モデル (Gemini) が優先される条件（メモリ使用量が閾値以下かつ Gemini API Key が設定されている場合）
        threshold = int(os.getenv("MEMORY_THRESHOLD", "300"))
        if avail_mb < threshold and os.getenv("GEMINI_API_KEY"):
            logger.warning("[CoordinateService] Memory low, falling back to Gemini for all items")
            from src.infra import get_ai_provider

            return await self.gemini_predictor(image, get_ai_provider())

        # 2. ローカルモデル (Heron/Surya) または Gemini の選択
        parser_type = os.getenv("LAYOUT_PARSER_TYPE", "heron").lower()
        if parser_type == "surya":
            return await self._get_surya_results(image)
        elif parser_type == "gemini":
            from src.infra import get_ai_provider

            return await self.gemini_predictor(image, get_ai_provider())
        else:
            return await self._get_heron_results(image)

    async def get_coordinates_bbox(self, image: Image.Image, label: str) -> List[BboxResponse]:
        """
        指定された単一ラベルの座標を取得する（後方互換用）。
        """
        all_results = await self.get_all_items(image)

        # ラベルフィルタリング
        filtered = []
        for res in all_results:
            l_result = await self._labeling(res, label)
            if l_result:
                filtered.append(l_result)
        return filtered

    async def gemini_predictor(self, image: Image.Image, ai_provider) -> List[BboxResponse]:
        """
        Gemini AIを使用して画像内の図表や数式の座標を検出する。
        """
        if self._cache_image_id == id(image) and self._cache_gemini_results:
            logger.debug(f"[CoordinateService] Gemini Cache hit for image object {id(image)}")
            return self._cache_gemini_results

        # PIL Imageをバイトデータに変換
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        img_bytes = img_byte_arr.getvalue()

        # Gemini APIを呼び出し
        response: FigureDetectionResponse = await ai_provider.generate_with_image(
            prompt=VISION_DETECT_ITEMS_PROMPT,
            image_bytes=img_bytes,
            mime_type="image/png",
            response_model=FigureDetectionResponse,
            model=os.getenv("OCR_MODEL"),
        )

        # 座標を正規化座標からピクセル座標にスケール変換
        page_w, page_h = image.width, image.height
        bboxes = []

        if not response or not hasattr(response, "figures"):
            logger.warning(f"[CoordinateService] Gemini returned invalid response: {response}")
            return []

        if response.figures:
            for fig in response.figures:
                ymin, xmin, ymax, xmax = fig.box_2d
                # ピクセル座標に変換 (0-1000を0-1に変換してからピクセルを掛ける)
                p_xmin = (xmin / 1000.0) * page_w
                p_ymin = (ymin / 1000.0) * page_h
                p_xmax = (xmax / 1000.0) * page_w
                p_ymax = (ymax / 1000.0) * page_h

                bbox = [p_xmin, p_ymin, p_xmax, p_ymax]
                # 多角形（矩形）の頂点を作成
                polygon = [[p_xmin, p_ymin], [p_xmax, p_ymin], [p_xmax, p_ymax], [p_xmin, p_ymax]]

                bboxes.append(
                    BboxResponse(
                        label=fig.label,
                        bbox=bbox,
                        polygon=polygon,
                        confidence=1.0,  # Geminiから信頼度が返らない場合はデフォルト1.0
                    )
                )

        # Filter: AI predictor should only return tables and formulas/equations
        allowed_labels = ("table", "formula", "equation")
        filtered_bboxes = [b for b in bboxes if b.label.lower() in allowed_labels]

        self._update_cache(image, filtered_bboxes, "gemini")

        return filtered_bboxes

    async def _labeling(self, result: BboxResponse, label: str) -> Optional[BboxResponse]:
        """
        検出されたBboxのラベルが、ターゲットのラベルと一致するか確認。
        Table / Formula に特化したマッピングを行う。
        """
        target_label = label.lower()
        current_label = result.label.lower()

        # "equation" と "formula" は基本的に同じものとして扱う
        if target_label == "equation":
            target_label = "formula"
        if current_label == "equation":
            current_label = "formula"

        # Table / Formula 以外（HeronのPicture等）は無視する方針のため、明示的な変換は行わない
        if current_label == target_label:
            return result

        return None


# Helper instance
cordinate_service = CoordinateService()
