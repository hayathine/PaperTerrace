import asyncio
import io
import json

import anyio
from PIL import Image

from app.domain.services.paper_processing import process_figure_analysis_task
from app.providers import get_storage_provider
from app.providers.image_storage import async_save_page_image
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

                def _crop_to_bytes(img_data: bytes, box: tuple) -> bytes:
                    from PIL import Image

                    img = Image.open(io.BytesIO(img_data))
                    crop = img.crop(box).convert("RGB")
                    buf = io.BytesIO()
                    crop.save(buf, format="JPEG", quality=85, optimize=True)
                    return buf.getvalue()

                margin = 5
                crop_box = (
                    max(0, x_min - margin),
                    max(0, y_min - margin),
                    min(img_w, x_max + margin),
                    min(img_h, y_max + margin),
                )
                crop_bytes = await anyio.to_thread.run_sync(
                    _crop_to_bytes, img_bytes, crop_box
                )

                img_name = f"p{page_num}_{class_name}_{fig_idx}"
                figure_image_url = await async_save_page_image(file_hash, img_name, crop_bytes, "jpg")
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

        from app.providers.image_storage import get_image_bytes, get_signed_url

        inference_client = await get_inference_client()
        all_figures = []

        # 署名付きURLを生成（GCS環境のみ有効、ローカルは None）
        signed_url_map: dict[int, str] = {}
        for pn, url in pages_to_process:
            su = await anyio.to_thread.run_sync(get_signed_url, url)
            if su is None:
                signed_url_map = {}  # 1つでも失敗したらURL方式を使わない
                break
            signed_url_map[pn] = su

        if signed_url_map:
            # --- GCS署名付きURL方式: バックエンドのメモリ転送を省略 ---
            logger.info(
                f"[analyze_layout_lazy] Using signed URL approach for {len(pages_to_process)} pages"
            )
            page_nums_list = [pn for pn, _ in pages_to_process]
            signed_urls_list = [signed_url_map[pn] for pn in page_nums_list]
            orig_url_map = {pn: url for pn, url in pages_to_process}

            # バッチ送信（先頭3枚並列 + 以降10枚ずつ）
            first = min(3, len(page_nums_list))
            url_batches: list[tuple[list[str], list[int]]] = [
                (signed_urls_list[:first], page_nums_list[:first])
            ]
            for i in range(first, len(signed_urls_list), 10):
                url_batches.append(
                    (signed_urls_list[i : i + 10], page_nums_list[i : i + 10])
                )

            async def _send_url_batch(
                batch_urls: list[str], batch_pages: list[int]
            ) -> tuple[list[int], list]:
                try:
                    results = await inference_client.analyze_images_batch_by_urls(
                        batch_urls,
                        page_nums=batch_pages,
                        max_batch_size=len(batch_urls),
                    )
                    logger.info(f"[analyze_layout_lazy] URL batch done: pages {batch_pages}")
                    return batch_pages, results
                except Exception as e:
                    logger.error(f"[analyze_layout_lazy] URL batch failed pages {batch_pages}: {e}")
                    return batch_pages, [[] for _ in batch_urls]

            url_batch_results = await asyncio.gather(
                *[_send_url_batch(urls, pages) for urls, pages in url_batches]
            )

            # 検出があったページのみ画像をダウンロードしてクロップ
            for batch_page_nums, results in sorted(url_batch_results, key=lambda x: x[0][0]):
                for page_num, page_results in zip(batch_page_nums, results):
                    has_target = any(
                        r.get("class_name", "").lower() in self.TARGET_CLASSES
                        for r in page_results
                    )
                    if not has_target:
                        continue
                    img_bytes = await anyio.to_thread.run_sync(
                        get_image_bytes, orig_url_map[page_num]
                    )
                    page_figures = await self._process_page_results(
                        page_num, img_bytes, page_results, file_hash
                    )
                    all_figures.extend(page_figures)

        else:
            # --- バイト転送方式（ローカル開発環境 / GCS署名URL生成失敗時） ---
            logger.info(
                f"[analyze_layout_lazy] Using byte transfer approach for {len(pages_to_process)} pages"
            )

            async def _load_page(page_num: int, image_url: str) -> tuple[int, bytes]:
                return page_num, await anyio.to_thread.run_sync(get_image_bytes, image_url)

            load_results = await asyncio.gather(
                *[_load_page(pn, url) for pn, url in pages_to_process],
                return_exceptions=True,
            )
            image_data_list = []
            page_info_list = []
            for res in load_results:
                if isinstance(res, Exception):
                    logger.error(f"Failed to load page image: {res}")
                    continue
                page_num, img_bytes = res
                image_data_list.append(img_bytes)
                page_info_list.append(page_num)

            if not image_data_list:
                logger.warning(f"[analyze_layout_lazy] No valid images for paper {paper_id}")
                raise Exception("No valid images to process")

            first = min(3, len(image_data_list))
            batches: list[tuple[list[bytes], list[int]]] = [
                (image_data_list[:first], page_info_list[:first])
            ]
            for i in range(first, len(image_data_list), 10):
                batches.append(
                    (image_data_list[i : i + 10], page_info_list[i : i + 10])
                )

            async def _send_batch(
                batch_imgs: list[bytes], batch_pages: list[int]
            ) -> tuple[list[int], list[bytes], list]:
                try:
                    results = await inference_client.analyze_images_batch(
                        batch_imgs,
                        page_nums=batch_pages,
                        max_batch_size=len(batch_imgs),
                    )
                    logger.info(f"[analyze_layout_lazy] Batch received: pages {batch_pages}")
                    return batch_pages, batch_imgs, results
                except Exception as e:
                    logger.error(f"[analyze_layout_lazy] Batch failed for pages {batch_pages}: {e}")
                    return batch_pages, batch_imgs, [[] for _ in batch_imgs]

            batch_results = await asyncio.gather(
                *[_send_batch(imgs, pages) for imgs, pages in batches]
            )

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

        # 3. Save to DB ONLY for registered users with a valid paper record
        if all_figures and user_id and paper:
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

            try:
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

            except Exception as db_err:
                # FK違反など DB 保存失敗時は transient UUID にフォールバックして
                # ジョブを正常完了させる（"AIに聞く"ボタンが表示されるようにする）
                logger.warning(
                    f"[analyze_layout_lazy] DB save failed for paper {paper_id}, "
                    f"falling back to transient UUIDs: {db_err}"
                )
                import uuid6

                for fig in all_figures:
                    if not fig.get("id"):
                        fig["id"] = str(uuid6.uuid7())
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
