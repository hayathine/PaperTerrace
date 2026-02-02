import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from PIL import Image

from src.core.logger import logger


class HeronService:
    def __init__(self):
        self._model = None
        self._processor = None
        self._load_lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._infer_semaphore = asyncio.Semaphore(1)
        self._unload_timer_task = None
        self._unload_delay = 300  # 5 minutes

        self.classes_map = {
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

    async def _init_predictors(self):
        async with self._load_lock:
            if self._model is None:
                try:
                    import torch
                    from transformers import RTDetrImageProcessor, RTDetrV2ForObjectDetection

                    from src.core.utils.memory import log_memory

                    log_memory("Before Heron Load")
                    logger.info(
                        "[HeronService] Initializing ds4sd/docling-layout-heron-101 model..."
                    )
                    model_name = "ds4sd/docling-layout-heron-101"
                    dev = "cpu"

                    # CPU全コアを占有してシステムがフリーズするのを防ぐ
                    torch.set_num_threads(min(4, os.cpu_count() or 1))
                    dtype = torch.bfloat16

                    self._processor = RTDetrImageProcessor.from_pretrained(model_name)

                    self._model = RTDetrV2ForObjectDetection.from_pretrained(
                        model_name, low_cpu_mem_usage=True, dtype=dtype
                    ).to(dev)
                    self._model.eval()  # 推論モードに固定してメモリを効率化
                    logger.info(f"[HeronService] Docling Heron-101 loaded on {dev} with {dtype}")
                    log_memory("After Heron Load")
                except Exception as e:
                    logger.error(
                        f"[HeronService] Failed to load Docling Heron model: {e}", exc_info=True
                    )
                    raise e

    async def detect_layout(self, image: Image.Image) -> List[Dict[str, Any]]:
        try:
            from src.core.utils.memory import register_model_activity

            register_model_activity(self, self._unload_delay)
            await self._init_predictors()

            async with self._infer_semaphore:
                logger.info("[HeronService] Starting inference...")
                from src.core.utils.memory import log_memory

                log_memory("Before Heron Inference")

                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(self._executor, self._sync_inference, image)

                logger.info("[HeronService] Inference completed.")
                log_memory("After Heron Inference")
            return results
        except Exception as e:
            logger.error(f"[HeronService] Heron inference failed: {e}", exc_info=True)
            return []

    def _sync_inference(self, pil_img: Image.Image) -> List[Dict[str, Any]]:
        import torch

        if self._processor is None or self._model is None:
            return []

        logger.debug("[HeronService] Running model forward pass...")
        inputs = self._processor(images=[pil_img], return_tensors="pt").to(self._model.device)

        # 3. 入力データをモデルと同じ型・デバイスへ移動
        inputs = {
            k: v.to(dtype=self._model.dtype) if torch.is_floating_point(v) else v
            for k, v in inputs.items()
        }
        with torch.inference_mode():
            outputs = self._model(**inputs)

        logger.debug("[HeronService] Model forward pass done. Post-processing...")
        del inputs
        w, h = pil_img.size
        results = self._processor.post_process_object_detection(
            outputs,
            target_sizes=[(h, w)],
            threshold=0.5,
        )

        bboxes = []
        target_labels = ("Table", "Formula")
        if results:
            for result in results:
                for score, label_id, box in zip(
                    result["scores"], result["labels"], result["boxes"]
                ):
                    label = self.classes_map.get(label_id.item(), "Unknown")
                    if label not in target_labels:
                        continue

                    box_list = box.tolist()
                    bboxes.append(
                        {
                            "label": label,
                            "bbox": box_list,
                            "polygon": [
                                [box_list[0], box_list[1]],
                                [box_list[2], box_list[1]],
                                [box_list[2], box_list[3]],
                                [box_list[0], box_list[3]],
                            ],
                            "confidence": score.item(),
                        }
                    )

        return bboxes

    async def unload(self):
        async with self._load_lock:
            if self._model is not None:
                logger.info("[HeronService] Unloading models to release memory...")
                del self._model
                del self._processor
                self._model = None
                self._processor = None

                from src.core.utils.memory import cleanup_memory

                cleanup_memory()
                logger.info("[HeronService] Models unloaded.")


heron_service = HeronService()
