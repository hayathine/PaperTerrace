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
        if self._initialized:
            return
        self._device = None
        self.det_model = None
        self.det_processor = None
        self.layout_model = None
        self.layout_processor = None
        self._initialized = True
        logger.info("[CoordinateService] Initialized")

    @property
    def device(self):
        if self._device is None:
            try:
                import torch

                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._device = "cpu"
        return self._device

    async def _surya_predictor(self, image: Image.Image) -> List[BboxResponse]:
        from surya.foundation import FoundationPredictor
        from surya.layout import LayoutPredictor
        from surya.settings import settings

        # 1. 予測器の初期化 [cite: 1590, 1591]
        foundation_predictor = FoundationPredictor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)
        layout_predictor = LayoutPredictor(foundation_predictor)

        # 2. レイアウト解析
        results = layout_predictor([image])

        bboxes = []
        for box in results[0].bboxes:
            bboxes.append(
                BboxResponse(label=box.label, bbox=box.bbox, polygon=box.polygon, confidence=1.0)
            )
        return bboxes

    async def get_coordinates_bbox(self, image: Image.Image, label: str) -> List[BboxResponse]:
        """
        指定されたラベルの座標を取得する。
        環境変数 USE_GEMINI_FOR_PARSER が "True" の場合は Gemini を、そうでない場合は Surya を使用する。
        """
        if os.getenv("USE_GEMINI_FOR_PARSER") == "True":
            from src.infra import get_ai_provider

            ai_provider = get_ai_provider()
            results = await self.gemini_predictor(image, ai_provider)
        else:
            results = await self._surya_predictor(image)

        # ラベルでフィルタリング
        filtered_results = []
        for res in results:
            labeled = await self._labeling(res, label)
            if labeled:
                filtered_results.append(labeled)

        return filtered_results

    async def gemini_predictor(self, image: Image.Image, ai_provider) -> List[BboxResponse]:
        """
        Gemini AIを使用して画像内の図表や数式の座標を検出する。
        """
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

        for fig in response.figures:
            ymin, xmin, ymax, xmax = fig.box_2d
            # ピクセル座標に変換
            p_xmin = xmin * page_w
            p_ymin = ymin * page_h
            p_xmax = xmax * page_w
            p_ymax = ymax * page_h

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

        return bboxes

    async def _labeling(self, result: BboxResponse, label: str) -> Optional[BboxResponse]:
        """
        検出されたBboxのラベルが、ターゲットのラベルと一致するか確認し、
        一致する場合はそのBboxResponseを返す。
        """
        # 指定されたラベルのものを中心に探す（大文字小文字の違いを許容）
        target_label = label.lower()
        current_label = result.label.lower()

        # "equation" と "formula" は基本的に同じものとして扱うように正規化
        if target_label == "equation":
            target_label = "formula"
        if current_label == "equation":
            current_label = "formula"

        if current_label == target_label:
            return result

        return None


# Helper instance
cordinate_service = CoordinateService()
