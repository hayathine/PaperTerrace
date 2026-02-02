import asyncio
from typing import Any, Dict, List

from PIL import Image

from src.core.logger import logger


class SuryaService:
    def __init__(self):
        self._layout_predictor = None
        self._foundation_predictor = None
        self._load_lock = asyncio.Lock()

    async def _init_predictors(self):
        async with self._load_lock:
            if self._layout_predictor is None:
                try:
                    import os

                    import torch
                    from surya.foundation import FoundationPredictor
                    from surya.layout import LayoutPredictor
                    from surya.settings import settings

                    from src.core.utils.memory import log_memory

                    if torch.cuda.is_available():
                        dev = "cuda"
                    else:
                        dev = "cpu"
                        # CPU全コアを占有してシステムがフリーズするのを防ぐ
                        torch.set_num_threads(min(4, os.cpu_count() or 1))

                    log_memory("Before Surya Load")
                    logger.info(f"[SuryaService] Initializing predictors on {dev}...")

                    self._foundation_predictor = FoundationPredictor(
                        checkpoint=settings.LAYOUT_MODEL_CHECKPOINT
                    )
                    self._layout_predictor = LayoutPredictor(self._foundation_predictor)

                    logger.info("[SuryaService] Predictors initialized.")
                    log_memory("After Surya Load")
                except ImportError:
                    logger.error(
                        "[SuryaService] surya-ocr is not installed. Please install it with 'pip install surya-ocr'."
                    )
                    raise ImportError("surya-ocr not installed")

    async def detect_layout(self, image: Image.Image) -> List[Dict[str, Any]]:
        try:
            await self._init_predictors()
            assert self._layout_predictor is not None

            from src.core.utils.memory import log_memory

            logger.info("[SuryaService] Starting detection...")
            log_memory("Before Surya Detection")

            results = self._layout_predictor([image])

            logger.info("[SuryaService] Detection completed.")
            log_memory("After Surya Detection")

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
            logger.error(f"[SuryaService] Detection failed: {e}", exc_info=True)
            return []

    async def unload(self):
        async with self._load_lock:
            if self._layout_predictor is not None:
                logger.info("[SuryaService] Unloading models to release memory...")
                import gc

                import torch

                del self._layout_predictor
                del self._foundation_predictor
                self._layout_predictor = None
                self._foundation_predictor = None
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                logger.info("[SuryaService] Models unloaded.")


surya_service = SuryaService()
