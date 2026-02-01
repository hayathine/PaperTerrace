from typing import Any, Dict, List, Optional

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

from src.core.logger import logger

class HeronService:
    def __init__(self):
        self._model = None
        self._processor = None
        self._load_lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._infer_semaphore = asyncio.Semaphore(1)
        
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

                    logger.info("[HeronService] Initializing ds4sd/docling-layout-heron-101 model...")
                    model_name = "ds4sd/docling-layout-heron-101"
                    dev ="cpu"

                    # CPU全コアを占有してシステムがフリーズするのを防ぐ
                    torch.set_num_threads(min(4, os.cpu_count() or 1))
                    dtype = torch.bfloat16

                    self._processor = RTDetrImageProcessor.from_pretrained(model_name)
                    self._model = RTDetrV2ForObjectDetection.from_pretrained(
                        model_name,
                        low_cpu_mem_usage=True,
                        torch_dtype=dtype
                    ).to(dev)
                    self._model.eval()  # 推論モードに固定してメモリを効率化
                    logger.info(f"[HeronService] Docling Heron-101 loaded on {dev} with {dtype}")
                except Exception as e:
                    logger.error(f"[HeronService] Failed to load Docling Heron model: {e}", exc_info=True)
                    raise e

    async def detect_layout(self, image: Image.Image) -> List[Dict[str, Any]]:
        try:
            await self._init_predictors()
            
            async with self._infer_semaphore:
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    self._executor,
                    self._sync_inference,
                    image
                )
            return results
        except Exception as e:
            logger.error(f"[HeronService] Heron inference failed: {e}", exc_info=True)
            return []

    def _sync_inference(self, pil_img: Image.Image) -> List[Dict[str, Any]]:
        import torch
        if self._processor is None or self._model is None:
            return []

        inputs = self._processor(images=[pil_img], return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            outputs = self._model(**inputs)

        w, h = pil_img.size
        results = self._processor.post_process_object_detection(
            outputs,
            target_sizes=[(h, w)],
            threshold=0.5,
        )

        bboxes = []
        if results:
            for result in results:
                for score, label_id, box in zip(result["scores"], result["labels"], result["boxes"]):
                    label = self.classes_map.get(label_id.item(), "Text")
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

heron_service = HeronService()
