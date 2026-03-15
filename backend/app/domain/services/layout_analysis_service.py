import asyncio
import base64
import io
import json

import anyio
from PIL import Image

from app.domain.services.paper_processing import process_figure_analysis_task
from app.providers import get_storage_provider
from app.providers.image_storage import save_page_image
from app.providers.inference_client import get_inference_client
from common.logger import logger


class LayoutAnalysisService:
    TARGET_CLASSES = [
        "table",
        "figure",
        "picture",
        "formula",
        "chart",
        "algorithm",
        "equation",
    ]

    def __init__(self):
        self.storage = get_storage_provider()

    async def _process_page_results(
        self,
        page_num: int,
        img_bytes: bytes,
        results: list,
        file_hash: str,
    ) -> list[dict]:
        """1ページ分の推論結果をクロップ・保存して figures リストを返す"""
        img_pil = Image.open(io.BytesIO(img_bytes))
        img_w, img_h = img_pil.size
        fig_idx = 0
        page_figures = []

        logger.debug(f"Page {page_num}: Found {len(results)} raw detections")
        for res in results:
            class_name = res.get("class_name", "").lower()
            logger.debug(f"  - Detected: {class_name} (score: {res.get('score')})")
            if class_name not in self.TARGET_CLASSES:
                continue

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

                page_figures.append(
                    {
                        "page_num": page_num,
                        "bbox": [crop_box[0], crop_box[1], crop_box[2], crop_box[3]],
                        "label": class_name,
                        "image_url": figure_image_url,
                    }
                )
            except Exception as crop_err:
                logger.warning(
                    f"Failed to crop {class_name} on page {page_num}: {crop_err}"
                )
                continue

        return page_figures

    async def analyze_layout_lazy(
        self,
        paper_id: str,
        page_numbers: list[int] | None = None,
        user_id: str | None = None,
        file_hash: str | None = None,
        session_id: str | None = None,
    ):
        # 1. Resolve paper and file_hash
        paper = await anyio.to_thread.run_sync(self.storage.get_paper, paper_id)

        if not paper:
            # If not in DB, we must have been given the file_hash (Transient mode)
            if not file_hash:
                raise Exception(
                    f"Paper {paper_id} not found in DB and no file_hash provided"
                )
            logger.debug(
                f"[analyze_layout_lazy] Paper {paper_id} not in DB, using transient hash {file_hash}"
            )
        else:
            file_hash = paper.get("file_hash") or file_hash

        if not file_hash:
            raise Exception("Paper has no file_hash")

        from app.providers.image_storage import get_page_images

        # 2. Get images from storage (Local or GCS)
        cached_images = get_page_images(file_hash)

        if not cached_images:
            raise Exception(f"No cached images found for file_hash {file_hash}")

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
            logger.warning(
                f"[analyze_layout_lazy] No valid images found to process for paper {paper_id}"
            )
            raise Exception("No valid images to process")

        logger.info(
            f"[analyze_layout_lazy] Sending {len(image_data_list)} images to inference service for paper {paper_id}"
        )
        inference_client = await get_inference_client()

        all_figures = []

        # バッチを収集（先頭3枚 + 以降10枚ずつ）
        batches: list[tuple[list[bytes], list[int]]] = []
        if image_data_list:
            first_batch_size = min(3, len(image_data_list))
            batches.append(
                (image_data_list[:first_batch_size], page_info_list[:first_batch_size])
            )
            for i in range(first_batch_size, len(image_data_list), 10):
                batches.append(
                    (image_data_list[i : i + 10], page_info_list[i : i + 10])
                )

        logger.info(
            f"[analyze_layout_lazy] Sending {len(batches)} batches in parallel"
        )

        async def _send_batch(
            batch_imgs: list[bytes], batch_pages: list[int]
        ) -> tuple[list[int], list[bytes], list]:
            """1バッチを推論サービスに並列送信し (page_nums, img_bytes, results) を返す"""
            try:
                results = await inference_client.analyze_images_batch(
                    batch_imgs,
                    page_nums=batch_pages,
                    max_batch_size=len(batch_imgs),
                )
                logger.info(
                    f"[analyze_layout_lazy] Batch received: pages {batch_pages}"
                )
                return batch_pages, batch_imgs, results
            except Exception as e:
                logger.error(
                    f"[analyze_layout_lazy] Batch failed for pages {batch_pages}: {e}"
                )
                return batch_pages, batch_imgs, [[] for _ in batch_imgs]

        batch_results = await asyncio.gather(
            *[_send_batch(imgs, pages) for imgs, pages in batches]
        )

        # ページ順を保証して結果を処理
        for batch_page_nums, batch_img_bytes, results in sorted(
            batch_results, key=lambda x: x[0][0]
        ):
            for page_num, img_bytes, page_results in zip(
                batch_page_nums, batch_img_bytes, results
            ):
                page_figures = await self._process_page_results(
                    page_num, img_bytes, page_results, file_hash
                )
                all_figures.extend(page_figures)

        # 3. Save to DB ONLY for registered users
        if all_figures and user_id:
            logger.debug(
                f"[analyze_layout_lazy] Saving {len(all_figures)} figures to DB for {paper_id}"
            )
            # Reformat figures for batch saving
            batch_figures = [
                {
                    "page_number": fig["page_num"],
                    "bbox": fig["bbox"],
                    "image_url": fig.get("image_url", ""),
                    "caption": "",
                    "explanation": "",
                    "label": fig.get("label", "figure"),
                    "latex": "",
                }
                for fig in all_figures
            ]

            from app.crud import save_figures_to_db

            fids = await anyio.to_thread.run_sync(
                save_figures_to_db,
                paper_id,
                batch_figures,
            )

            # DBで生成されたIDをall_figuresに付与してAPIレスポンスに含める
            for fid, fig in zip(fids, all_figures):
                fig["id"] = fid

            # Start background analysis tasks
            for fid, fig in zip(fids, all_figures):
                if fig.get("image_url"):
                    asyncio.create_task(
                        process_figure_analysis_task(
                            fid,
                            fig["image_url"],
                            user_id=user_id,
                            session_id=session_id,
                        )
                    )

            # Update layout_json (if paper exists in DB)
            if paper:
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
                                    "id": fig.get("id"),
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
        elif all_figures:
            # トランジェントセッション: DBには保存しないが、セッション内でAI解析できるよう
            # 一時的なUUIDを付与する（このIDはDBに存在しない）
            import uuid6

            for fig in all_figures:
                fig["id"] = str(uuid6.uuid7())
            logger.debug(
                f"[analyze_layout_lazy] Skipping DB save for transient session {paper_id}"
            )

        return all_figures
