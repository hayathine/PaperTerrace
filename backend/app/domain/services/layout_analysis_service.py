import asyncio
import base64
import hashlib
import io
import json
import tempfile
from pathlib import Path

import anyio
from PIL import Image

from app.crud import save_figure_to_db
from app.domain.services.layout_service import get_layout_service
from app.domain.services.paper_processing import process_figure_analysis_task
from app.providers import get_storage_provider
from app.providers.image_storage import save_page_image
from app.providers.inference_client import get_inference_client
from common.logger import logger


class LayoutAnalysisService:
    def __init__(self):
        self.layout_service = get_layout_service()
        self.storage = get_storage_provider()

    async def detect_layout(self, content: bytes, filename: str, page_number: int):
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # レイアウト解析実行
            layout_items = await self.layout_service.analyze_image(temp_file_path)

            file_hash = hashlib.sha256(content).hexdigest()
            img_pil = Image.open(io.BytesIO(content))
            img_w, img_h = img_pil.size

            results = []
            for i, item in enumerate(layout_items):
                class_name = item.class_name.lower()
                res_dict = {
                    "class_name": item.class_name,
                    "confidence": item.score,
                    "bbox": {
                        "x_min": item.bbox.x_min,
                        "y_min": item.bbox.y_min,
                        "x_max": item.bbox.x_max,
                        "y_max": item.bbox.y_max,
                    },
                }

                # 特定のクラス（図、表、数式、アルゴリズム等）はクロップして保存
                target_classes = [
                    "table",
                    "figure",
                    "picture",
                    "formula",
                    "chart",
                    "algorithm",
                    "equation",
                ]
                if any(c in class_name for c in target_classes):
                    try:
                        margin = 5
                        x1 = max(0, item.bbox.x_min - margin)
                        y1 = max(0, item.bbox.y_min - margin)
                        x2 = min(img_w, item.bbox.x_max + margin)
                        y2 = min(img_h, item.bbox.y_max + margin)

                        if x2 > x1 and y2 > y1:
                            crop = img_pil.crop((x1, y1, x2, y2)).convert("RGB")
                            buf = io.BytesIO()
                            crop.save(buf, format="JPEG", quality=85, optimize=True)
                            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

                            img_name = f"detect_pg{page_number}_{class_name}_{i}"
                            image_url = await anyio.to_thread.run_sync(
                                save_page_image, file_hash, img_name, img_b64
                            )
                            res_dict["image_url"] = image_url
                            # BBoxをクロップ範囲に更新
                            res_dict["bbox"] = {
                                "x_min": x1,
                                "y_min": y1,
                                "x_max": x2,
                                "y_max": y2,
                            }
                    except Exception as crop_err:
                        logger.warning(f"Failed to crop {class_name}: {crop_err}")

                results.append(res_dict)

            return results
        finally:
            Path(temp_file_path).unlink(missing_ok=True)

    async def analyze_layout_lazy(
        self, paper_id: str, page_numbers: list[int] | None = None
    ):
        paper = await anyio.to_thread.run_sync(self.storage.get_paper, paper_id)
        if not paper:
            raise Exception("Paper not found")

        file_hash = paper.get("file_hash")
        if not file_hash:
            raise Exception("Paper has no file_hash")

        from app.providers.image_storage import get_page_images

        cached_images = get_page_images(file_hash)

        if not cached_images:
            raise Exception("No cached images found for this paper")

        if page_numbers:
            pages_to_process = [
                (i, url) for i, url in enumerate(cached_images, 1) if i in page_numbers
            ]
        else:
            pages_to_process = list(enumerate(cached_images, 1))

        image_data_list = []
        page_info_list = []

        from app.providers.image_storage import get_image_bytes

        for page_num, image_url in pages_to_process:
            try:
                img_bytes = await anyio.to_thread.run_sync(get_image_bytes, image_url)

                def _prepare_image(data: bytes):
                    from PIL import Image

                    img_pil = Image.open(io.BytesIO(data))
                    buffer = io.BytesIO()
                    img_pil.save(buffer, format="JPEG", quality=85, optimize=True)
                    return buffer.getvalue()

                compressed_bytes = await anyio.to_thread.run_sync(
                    _prepare_image, img_bytes
                )
                image_data_list.append(compressed_bytes)
                page_info_list.append(page_num)
            except Exception as e:
                logger.error(f"Failed to load page {page_num}: {e}")
                continue

        if not image_data_list:
            raise Exception("No valid images to process")

        inference_client = await get_inference_client()
        batch_results = await inference_client.analyze_images_batch(
            image_data_list, max_batch_size=10
        )

        all_figures = []
        for page_num, img_bytes, results in zip(
            page_info_list, image_data_list, batch_results
        ):
            img_pil = Image.open(io.BytesIO(img_bytes))
            img_w, img_h = img_pil.size
            fig_idx = 0

            for res in results:
                class_name = res.get("class_name", "").lower()
                target_classes = [
                    "table",
                    "figure",
                    "picture",
                    "formula",
                    "chart",
                    "algorithm",
                    "equation",
                ]
                if class_name in target_classes:
                    bbox_dict = res.get("bbox", {})
                    if not bbox_dict:
                        continue

                    x_min, y_min = bbox_dict.get("x_min", 0), bbox_dict.get("y_min", 0)
                    x_max, y_max = bbox_dict.get("x_max", 0), bbox_dict.get("y_max", 0)

                    x_min, y_min = max(0, min(img_w, x_min)), max(0, min(img_h, y_min))
                    x_max, y_max = max(0, min(img_w, x_max)), max(0, min(img_h, y_max))

                    if x_max <= x_min or y_max <= y_min:
                        continue

                    try:

                        def _crop_and_encode(img_data: bytes, box: tuple):
                            from PIL import Image

                            img = Image.open(io.BytesIO(img_data))
                            crop = img.crop(box).convert("RGB")
                            buf = io.BytesIO()
                            crop.save(buf, format="JPEG", quality=85, optimize=True)
                            return base64.b64encode(buf.getvalue()).decode("utf-8")

                        margin = 5
                        crop_box = (
                            max(0, x_min - margin),
                            max(0, y_min - margin),
                            min(img_w, x_max + margin),
                            min(img_h, y_max + margin),
                        )
                        img_b64 = await anyio.to_thread.run_sync(
                            _crop_and_encode, img_bytes, crop_box
                        )

                        img_name = f"p{page_num}_{class_name}_{fig_idx}"
                        figure_image_url = await anyio.to_thread.run_sync(
                            save_page_image, file_hash, img_name, img_b64
                        )
                        fig_idx += 1

                        all_figures.append(
                            {
                                "page_num": page_num,
                                "bbox": [
                                    crop_box[0],
                                    crop_box[1],
                                    crop_box[2],
                                    crop_box[3],
                                ],
                                "label": class_name,
                                "image_url": figure_image_url,
                            }
                        )
                    except Exception as crop_err:
                        logger.warning(
                            f"Failed to crop {class_name} on page {page_num}: {crop_err}"
                        )
                        continue

        # Save to DB
        if all_figures:
            for fig in all_figures:
                fid = await anyio.to_thread.run_sync(
                    save_figure_to_db,
                    paper_id,
                    fig["page_num"],
                    fig["bbox"],
                    fig.get("image_url", ""),
                    "",
                    "",
                    fig.get("label", "figure"),
                    "",
                )
                if fig.get("image_url"):
                    asyncio.create_task(
                        process_figure_analysis_task(fid, fig["image_url"])
                    )

            # Update layout_json
            try:
                existing_layout = paper.get("layout_json")
                if existing_layout:
                    layout_list = json.loads(existing_layout)
                    page_figures = {}
                    for fig in all_figures:
                        pn = fig["page_num"]
                        if pn not in page_figures:
                            page_figures[pn] = []
                        page_figures[pn].append(
                            {
                                "bbox": fig["bbox"],
                                "image_url": fig["image_url"],
                                "label": fig.get("label", "figure"),
                                "page_num": fig["page_num"],
                            }
                        )

                    for i, layout in enumerate(layout_list):
                        page_num = i + 1
                        if page_num in page_figures:
                            layout["figures"] = page_figures[page_num]

                    await anyio.to_thread.run_sync(
                        self.storage.update_paper_layout,
                        paper_id,
                        json.dumps(layout_list),
                    )
            except Exception as e:
                logger.warning(f"Failed to update layout_json: {e}")

        return all_figures
