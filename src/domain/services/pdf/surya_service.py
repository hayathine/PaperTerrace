from typing import Any, Dict, List

from PIL import Image

from src.core.logger import logger


class SuryaService:
    def __init__(self):
        self._layout_predictor = None
        self._foundation_predictor = None

    def _init_predictors(self):
        if self._layout_predictor is None:
            try:
                from surya.foundation import FoundationPredictor
                from surya.layout import LayoutPredictor
                from surya.settings import settings
                import torch
                import os

                if torch.cuda.is_available():
                    dev = "cuda"
                else:
                    dev = "cpu"
                    # CPU全コアを占有してシステムがフリーズするのを防ぐ
                    torch.set_num_threads(min(4, os.cpu_count() or 1))

                logger.info(f"[SuryaService] Initializing predictors on {dev}...")
                self._foundation_predictor = FoundationPredictor(
                    checkpoint=settings.LAYOUT_MODEL_CHECKPOINT
                )
                self._layout_predictor = LayoutPredictor(self._foundation_predictor)
            except ImportError:
                logger.error(
                    "[SuryaService] surya-ocr is not installed. Please install it with 'pip install surya-ocr'."
                )
                raise ImportError("surya-ocr not installed")

    async def detect_layout(self, image: Image.Image) -> List[Dict[str, Any]]:
        try:
            self._init_predictors()
            assert self._layout_predictor is not None
            results = self._layout_predictor([image])

            bboxes = []
            for box in results[0].bboxes:
                bboxes.append(
                    {
                        "label": box.label,
                        "bbox": box.bbox,
                        "polygon": box.polygon,
                        "confidence": getattr(box, "confidence", 1.0),
                    }
                )
            return bboxes
        except Exception as e:
            logger.error(f"[SuryaService] Detection failed: {e}")
            return []


surya_service = SuryaService()
