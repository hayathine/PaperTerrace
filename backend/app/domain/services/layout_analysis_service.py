import asyncio
import base64
import json
from collections.abc import Awaitable, Callable

import anyio
import time

from app.domain.services.paper_processing import process_figure_analysis_task
from app.providers import get_storage_provider
from app.providers.image_storage import async_save_page_image
from app.providers.inference_client import get_inference_client
from common.logger import ServiceLogger

log = ServiceLogger("LayoutAnalysis")


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

    async def _save_crops_from_inference(
        self,
        page_num: int,
        crops: list[dict],
        file_hash: str,
    ) -> list[dict]:
        """推論podから受け取ったクロップ済み画像をGCSに並列保存してfiguresリストを返す。"""
        async def _save_one(fig_idx: int, crop: dict) -> dict | None:
            class_name = crop.get("class_name", "figure")
            img_b64 = crop.get("image_b64", "")
            bbox_dict = crop.get("bbox", {})
            if not img_b64:
                return None
            try:
                img_bytes = base64.b64decode(img_b64)
                img_name = f"p{page_num}_{class_name}_{fig_idx}"
                figure_image_url = await async_save_page_image(
                    file_hash, img_name, img_bytes, "jpg"
                )
                return {
                    "page_num": page_num,
                    "bbox": [
                        bbox_dict.get("x_min", 0),
                        bbox_dict.get("y_min", 0),
                        bbox_dict.get("x_max", 0),
                        bbox_dict.get("y_max", 0),
                    ],
                    "label": class_name,
                    "image_url": figure_image_url,
                    "conf": crop.get("score"),
                }
            except Exception as e:
                log.warning(
                    "_save_crops_from_inference",
                    f"Failed to save crop {class_name} on page {page_num}: {e}",
                )
                return None

        results = await asyncio.gather(*[_save_one(i, crop) for i, crop in enumerate(crops)])
        return [r for r in results if r is not None]

    async def analyze_layout_lazy(
        self,
        paper_id: str,
        page_numbers: list[int] | None = None,
        user_id: str | None = None,
        file_hash: str | None = None,
        session_id: str | None = None,
        on_figures: Callable[[list[dict]], Awaitable[None]] | None = None,
    ):
        try:
            return await self._analyze_layout_lazy_inner(
                paper_id=paper_id,
                page_numbers=page_numbers,
                user_id=user_id,
                file_hash=file_hash,
                session_id=session_id,
                on_figures=on_figures,
            )
        finally:
            self.storage.close()

    async def _analyze_layout_lazy_inner(
        self,
        paper_id: str,
        page_numbers: list[int] | None = None,
        user_id: str | None = None,
        file_hash: str | None = None,
        session_id: str | None = None,
        on_figures: Callable[[list[dict]], Awaitable[None]] | None = None,
    ):
        from app.providers.image_storage import (
            get_image_bytes,
            get_page_images,
            get_signed_url,
        )

        # self.storage (SQLAlchemy Session) はスレッドセーフでないため、
        # 並行バッチから同時アクセスしないようロックで直列化する。
        _db_lock = asyncio.Lock()

        # 1. Resolve paper and file_hash
        paper = await anyio.to_thread.run_sync(self.storage.get_paper, paper_id)

        if not paper:
            # If not in DB, we must have been given the file_hash (Transient mode)
            if not file_hash:
                raise Exception(
                    f"Paper {paper_id} not found in DB and no file_hash provided"
                )
            log.debug(
                "analyze_layout_lazy",
                f"Paper {paper_id} not in DB, using transient hash {file_hash}",
            )
        else:
            file_hash = paper.get("file_hash") or file_hash

        if not file_hash:
            raise Exception("Paper has no file_hash")

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

        inference_client = await get_inference_client()
        all_figures: list[dict] = []
        layout_metrics = {}  # {batch_key: duration}

        # ----------------------------------------------------------------
        # バッチ処理共通: DB保存 → AI解析タスク起動 → コールバック通知
        # ----------------------------------------------------------------
        async def _save_and_notify(batch_figures: list[dict]) -> None:
            """1バッチ分の figures を DB 保存し、on_figures コールバックを呼ぶ。"""
            if not batch_figures:
                return

            if user_id and paper:
                batch_db = [
                    {
                        "page_number": fig["page_num"],
                        "bbox": fig["bbox"],
                        "image_url": fig.get("image_url", ""),
                        "caption": "",
                        "explanation": "",
                        "label": fig.get("label", "figure"),
                        "latex": "",
                        "conf": fig.get("conf"),
                    }
                    for fig in batch_figures
                ]
                try:
                    async with _db_lock:
                        fids = await anyio.to_thread.run_sync(
                            self.storage.save_figures_batch, paper_id, batch_db
                        )
                    for fid, fig in zip(fids, batch_figures):
                        fig["id"] = fid
                    for fid, fig in zip(fids, batch_figures):
                        if fig.get("image_url"):
                            asyncio.create_task(
                                process_figure_analysis_task(
                                    fid,
                                    fig["image_url"],
                                    user_id=user_id,
                                    session_id=session_id,
                                )
                            )
                except Exception as db_err:
                    log.warning(
                        "save_and_notify",
                        f"DB save failed for paper {paper_id}, falling back to transient UUIDs: {db_err}",
                    )
                    import uuid6

                    for fig in batch_figures:
                        if not fig.get("id"):
                            fig["id"] = str(uuid6.uuid7())
            else:
                import uuid6

                for fig in batch_figures:
                    fig["id"] = str(uuid6.uuid7())

            if on_figures:
                await on_figures(batch_figures)

        # ----------------------------------------------------------------
        # バッチを先に構築し、バッチ単位で署名付きURLを生成して逐次送信
        # ----------------------------------------------------------------
        pages_list = list(pages_to_process)
        batches_raw: list[list[tuple[int, str]]] = [
            pages_list[i : i + 10] for i in range(0, len(pages_list), 10)
        ]

        async def _load_page(page_num: int, image_url: str) -> tuple[int, bytes]:
            return page_num, await anyio.to_thread.run_sync(
                get_image_bytes, image_url
            )

        async def _process_url_batch(
            batch_urls: list[str], batch_pages: list[int]
        ) -> list[dict]:
            try:
                t_inf_start = time.perf_counter()
                (
                    results,
                    crops_per_page,
                ) = await inference_client.analyze_images_batch_by_urls(
                    batch_urls,
                    page_nums=batch_pages,
                    max_batch_size=len(batch_urls),
                )
                t_inf_end = time.perf_counter()
                duration = round(t_inf_end - t_inf_start, 3)
                batch_key = f"{batch_pages[0]}-{batch_pages[-1]}"
                layout_metrics[batch_key] = duration

                log.debug(
                    "analyze_layout_lazy",
                    f"URL batch done: pages {batch_pages}",
                    duration=duration,
                )
            except Exception as e:
                log.error(
                    "analyze_layout_lazy",
                    f"URL batch failed pages {batch_pages}: {e}",
                )
                crops_per_page = [[] for _ in batch_urls]

            batch_figures: list[dict] = []
            for page_num, crops in zip(batch_pages, crops_per_page):
                if not crops:
                    continue
                page_figs = await self._save_crops_from_inference(
                    page_num, crops, file_hash
                )
                batch_figures.extend(page_figs)

            await _save_and_notify(batch_figures)
            return batch_figures

        async def _process_byte_batch(
            batch_imgs: list[bytes], batch_pages: list[int]
        ) -> list[dict]:
            try:
                t_inf_start = time.perf_counter()
                (
                    results,
                    crops_per_page,
                ) = await inference_client.analyze_images_batch(
                    batch_imgs,
                    page_nums=batch_pages,
                    max_batch_size=len(batch_imgs),
                )
                t_inf_end = time.perf_counter()
                duration = round(t_inf_end - t_inf_start, 3)
                batch_key = f"{batch_pages[0]}-{batch_pages[-1]}"
                layout_metrics[batch_key] = duration

                log.debug(
                    "analyze_layout_lazy",
                    f"Batch received: pages {batch_pages}",
                    duration=duration,
                )
            except Exception as e:
                log.error(
                    "analyze_layout_lazy",
                    f"Batch failed for pages {batch_pages}: {e}",
                )
                crops_per_page = [[] for _ in batch_imgs]

            batch_figures: list[dict] = []
            for page_num, crops in zip(batch_pages, crops_per_page):
                if not crops:
                    continue
                page_figs = await self._save_crops_from_inference(
                    page_num, crops, file_hash
                )
                batch_figures.extend(page_figs)

            await _save_and_notify(batch_figures)
            return batch_figures

        all_figures: list[dict] = []
        use_signed_urls = True  # 最初は署名付きURL方式を試みる

        for batch_raw in batches_raw:
            batch_page_nums = [pn for pn, _ in batch_raw]
            batch_image_urls_raw = [url for _, url in batch_raw]

            if use_signed_urls:
                signed = list(
                    await asyncio.gather(
                        *[
                            asyncio.to_thread(get_signed_url, url)
                            for url in batch_image_urls_raw
                        ]
                    )
                )
                if all(su is not None for su in signed):
                    log.info(
                        "analyze_layout_lazy",
                        f"Using signed URL approach for pages {batch_page_nums}",
                    )
                    batch_figs = await _process_url_batch(signed, batch_page_nums)
                    all_figures.extend(batch_figs)
                    continue
                else:
                    log.info(
                        "analyze_layout_lazy",
                        "Signed URL generation failed, switching to byte transfer",
                    )
                    use_signed_urls = False

            # バイト転送フォールバック
            log.info(
                "analyze_layout_lazy",
                f"Using byte transfer approach for pages {batch_page_nums}",
            )
            load_results = await asyncio.gather(
                *[_load_page(pn, url) for pn, url in batch_raw],
                return_exceptions=True,
            )
            imgs: list[bytes] = []
            pnums: list[int] = []
            for res in load_results:
                if isinstance(res, Exception):
                    log.error("load_page", f"Failed to load page image: {res}")
                    continue
                pn, img = res
                imgs.append(img)
                pnums.append(pn)

            if imgs:
                batch_figs = await _process_byte_batch(imgs, pnums)
                all_figures.extend(batch_figs)
            else:
                log.warning(
                    "analyze_layout_lazy",
                    f"No valid images for pages {batch_page_nums}",
                )

        if not all_figures and not pages_to_process:
            raise Exception("No valid images to process")

        # 3. layout_json を全バッチ完了後に更新
        if all_figures and user_id and paper:
            try:
                existing_layout = paper.get("layout_json")
                layout_list = []
                if existing_layout:
                    try:
                        layout_list = json.loads(existing_layout)
                    except Exception as e:
                        log.warning("analyze_layout_lazy", f"Failed to parse existing layout_json: {e}")

                if not layout_list and all_figures:
                    # layout_json が空の場合は、all_figures の page_num の最大値までスケルトンを作成
                    max_page = max(f["page_num"] for f in all_figures)
                    layout_list = [{"width": 0, "height": 0, "words": [], "figures": []} for _ in range(max_page)]

                if layout_list:
                    page_figures: dict[int, list] = {}
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
                                "conf": fig.get("conf"),
                            }
                        )
                    for i, layout in enumerate(layout_list):
                        pn = i + 1
                        if pn in page_figures:
                            layout["figures"] = page_figures[pn]

                    await anyio.to_thread.run_sync(
                        self.storage.update_paper_layout,
                        paper_id,
                        json.dumps(layout_list),
                    )
                else:
                    log.warning("analyze_layout_lazy", f"No layout structure available to update for paper {paper_id}")
            except Exception as e:
                log.warning("update_layout_json", f"Failed to update layout_json: {e}", exc_info=True)

        log.info(
            "analyze_layout_lazy_complete",
            "Layout analysis completed",
            paper_id=paper_id,
            metrics=layout_metrics,
        )
        return all_figures
