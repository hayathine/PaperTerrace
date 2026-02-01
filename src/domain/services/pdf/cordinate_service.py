import asyncio
import io
import os
from concurrent.futures import ThreadPoolExecutor
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
        self._heron_model = None
        self._heron_processor = None
        self._load_lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._infer_semaphore = asyncio.Semaphore(1)  # VRAMの競合を避けるため一度に一つ

        # 画像単位の結果キャッシュ
        self._cache_image_id = None
        self._cache_results = []

        self._initialized = True
        logger.info("[CoordinateService] Initialized with ThreadPoolExecutor and Cache")

    @property
    def device(self):
        if self._device is None:
            try:
                import torch

                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._device = "cpu"
        return self._device

    async def _docling_heron_predictor(self, image: Image.Image) -> List[BboxResponse]:
        """
        Docling Heron-101モデルを使用してレイアウト解析を行う。
        """
        # 1. キャッシュチェック (同じ画像オブジェクトなら使い回す)
        if self._cache_image_id == id(image):
            logger.debug(f"[CoordinateService] Cache hit for image object {id(image)}")
            return self._cache_results

        async with self._load_lock:
            if self._heron_model is None:
                try:
                    import torch
                    from transformers import RTDetrImageProcessor, RTDetrV2ForObjectDetection

                    logger.info(
                        "[CoordinateService] Initializing ds4sd/docling-layout-heron-101 model..."
                    )
                    model_name = "ds4sd/docling-layout-heron-101"
                    dev = "cuda" if torch.cuda.is_available() else "cpu"

                    self._heron_processor = RTDetrImageProcessor.from_pretrained(model_name)
                    self._heron_model = RTDetrV2ForObjectDetection.from_pretrained(model_name).to(
                        dev
                    )
                    logger.info(f"[CoordinateService] Docling Heron-101 loaded on {dev}")
                except Exception as e:
                    logger.error(
                        f"[CoordinateService] Failed to load Docling Heron model: {e}",
                        exc_info=True,
                    )
                    return []

        # クラスマップ
        classes_map = {
            0: "Caption",
            1: "Footnote",
            2: "Formula",
            3: "List-item",
            4: "Page-footer",
            5: "Page-header",
            6: "Picture",
            7: "Section-header",
            8: "Table",
            9: "Text",
            10: "Title",
            11: "Document Index",
            12: "Code",
            13: "Checkbox-Selected",
            14: "Checkbox-Unselected",
            15: "Form",
            16: "Key-Value Region",
        }
        threshold = 0.5

        def sync_inference(pil_img, processor, model, c_map):
            """
            別スレッドで実行される同期推論処理
            """
            import torch

            if processor is None or model is None:
                return []

            # 推論
            inputs = processor(images=[pil_img], return_tensors="pt").to(model.device)
            with torch.no_grad():
                outputs = model(**inputs)

            # 後処理
            w, h = pil_img.size
            results = processor.post_process_object_detection(
                outputs,
                target_sizes=[(h, w)],
                threshold=threshold,
            )

            bboxes = []
            if results:
                for result in results:
                    for score, label_id, box in zip(
                        result["scores"], result["labels"], result["boxes"]
                    ):
                        label = c_map.get(label_id.item(), "Text")
                        box_list = box.tolist()
                        bboxes.append(
                            BboxResponse(
                                label=label,
                                bbox=box_list,
                                polygon=[
                                    [box_list[0], box_list[1]],
                                    [box_list[2], box_list[1]],
                                    [box_list[2], box_list[3]],
                                    [box_list[0], box_list[3]],
                                ],
                                confidence=score.item(),
                            )
                        )
            return bboxes

        try:
            # 2. 推論実行（セマフォで制限しつつスレッドプールで実行）
            async with self._infer_semaphore:
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    self._executor,
                    sync_inference,
                    image,
                    self._heron_processor,
                    self._heron_model,
                    classes_map,
                )

            # 3. キャッシュ更新
            self._cache_image_id = id(image)
            self._cache_results = results

            logger.info(f"[CoordinateService] Heron inference complete. Items: {len(results)}")
            return results
        except Exception as e:
            logger.error(f"[CoordinateService] Heron inference failed: {e}", exc_info=True)
            return []

    async def _surya_predictor(self, image: Image.Image) -> List[BboxResponse]:
        from surya.foundation import FoundationPredictor
        from surya.layout import LayoutPredictor
        from surya.settings import settings

        try:
            foundation_predictor = FoundationPredictor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)
            layout_predictor = LayoutPredictor(foundation_predictor)
            results = layout_predictor([image])

            bboxes = []
            if results and len(results) > 0:
                for box in results[0].bboxes:
                    bboxes.append(
                        BboxResponse(
                            label=box.label, bbox=box.bbox, polygon=box.polygon, confidence=1.0
                        )
                    )
            return bboxes
        except Exception as e:
            logger.error(f"[CoordinateService] Surya predictor failed: {e}")
            return []

    async def get_coordinates_bbox(self, image: Image.Image, label: str) -> List[BboxResponse]:
        """
        指定されたラベルの座標を取得する。
        Table, Formula, Figure については Docling Heron のみを使用する（フォールバックなし）。
        """
        label_lower = label.lower()

        # 1. Table, Formula, Figure は Docling Heron を使用
        if label_lower in ["table", "formula", "equation", "figure"]:
            logger.info(f"[CoordinateService] Start detecting '{label}' using Docling Heron...")
            results = await self._docling_heron_predictor(image)

            # フィルタリング
            filtered = []
            for res in results:
                labeled = await self._labeling(res, label)
                if labeled:
                    filtered.append(labeled)

            if filtered:
                logger.info(
                    f"[CoordinateService] Found {len(filtered)} items for label '{label}' via Docling Heron"
                )
            else:
                logger.info(
                    f"[CoordinateService] No items found for label '{label}' via Docling Heron"
                )

            return filtered

        # 2. その他のラベル（Text等）は環境設定に従う
        logger.debug(
            f"[CoordinateService] Detecting '{label}' using secondary parser (Gemini/Surya)..."
        )
        if os.getenv("USE_GEMINI_FOR_PARSER") == "True":
            from src.infra import get_ai_provider

            ai_provider = get_ai_provider()
            results = await self.gemini_predictor(image, ai_provider)
        else:
            # その他は Surya を使用
            results = await self._surya_predictor(image)

        # ラベルでフィルタリング
        filtered_results = []
        if not results:
            return []

        for f_res in results:
            l_result = await self._labeling(f_res, label)
            if l_result:
                filtered_results.append(l_result)

        if filtered_results:
            logger.debug(
                f"[CoordinateService] Found {len(filtered_results)} items for label '{label}' via secondary parser"
            )

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

        if response.figures:
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

        # Heron の Picture は Figure として扱う
        if current_label == "picture":
            current_label = "figure"

        if current_label == target_label:
            return result

        return None


# Helper instance
cordinate_service = CoordinateService()
