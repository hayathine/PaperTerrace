"""
Worker Router — Cloud Tasks から呼び出される内部エンドポイント。
OCR 処理を実行し、進捗を Redis リストに書き込む。
"""

from __future__ import annotations

import asyncio
import json
import time
from functools import cache

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.domain.features import SummaryService
from app.domain.services.analysis_service import EnglishAnalysisService
from app.domain.services.paper_processing import (
    process_figure_analysis_task,
    process_grobid_enrichment_task,
    process_paper_summary_task,
)
from app.providers import RedisService, get_image_storage, get_storage_provider
from common.logger import ServiceLogger

log = ServiceLogger("Worker")

router = APIRouter(tags=["Internal Worker"])


@cache
def _get_service() -> EnglishAnalysisService:
    return EnglishAnalysisService()


@cache
def _get_summary_service() -> SummaryService:
    return SummaryService()


@cache
def _get_redis_service() -> RedisService:
    return RedisService()


@cache
def _get_img_storage():
    return get_image_storage()


# Cloud Tasks がリクエストに付与するヘッダー（存在確認で簡易認証）
_CLOUD_TASKS_HEADER = "X-CloudTasks-QueueName"


class OcrTaskPayload(BaseModel):
    """Cloud Tasks から受け取る OCR ジョブのペイロード。"""

    task_id: str
    pdf_path: str
    file_hash: str
    filename: str = "unknown.pdf"
    lang: str = "ja"
    user_id: str | None = None
    is_registered: bool = False
    session_id: str | None = None
    paper_id: str = "pending"


def _progress_key(task_id: str) -> str:
    return f"task:progress:{task_id}"


def _push_event(task_id: str, event: dict) -> None:
    """進捗イベントを Redis リストに追加する。"""
    _get_redis_service().rpush(_progress_key(task_id), json.dumps(event))


@router.post("/internal/process-ocr")
async def process_ocr_task(request: Request, payload: OcrTaskPayload):
    """OCR 処理ワーカー。Cloud Tasks からのみ呼び出される。

    処理結果を Redis リスト task:progress:{task_id} に書き込む。
    フロントエンドは /stream/{task_id} 経由でこのリストをポーリングする。
    """
    # Cloud Tasks ヘッダーによる簡易認証（IAM が主防衛線）
    queue_name = request.headers.get(_CLOUD_TASKS_HEADER, "")
    if not queue_name:
        log.warning(
            "process_ocr",
            "Cloud Tasks ヘッダーが見つかりません。不正アクセスの可能性。",
            task_id=payload.task_id,
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    task_id = payload.task_id
    log.info(
        "process_ocr",
        "OCR ワーカー開始",
        task_id=task_id,
        filename=payload.filename,
        queue=queue_name,
    )

    # タスクステータスを "processing" に更新
    task_data = _get_redis_service().get(f"task:{task_id}") or {}
    task_data["status"] = "processing"
    task_data["worker_started_at"] = time.time()
    _get_redis_service().set(f"task:{task_id}", task_data, expire=3600)

    storage = get_storage_provider()
    try:
        # PDF バイトを GCS から取得
        try:
            pdf_content = _get_img_storage().get_doc_bytes(payload.pdf_path)
        except Exception as e:
            log.error(
                "process_ocr",
                f"PDF 取得失敗: {e}",
                task_id=task_id,
                pdf_path=payload.pdf_path,
            )
            _push_event(task_id, {"type": "error", "message": "PDF source not found"})
            _get_redis_service().expire(_progress_key(task_id), 3600)
            task_data["status"] = "error"
            _get_redis_service().set(f"task:{task_id}", task_data, expire=3600)
            return {"ok": False, "error": "pdf_not_found"}

        # ユーザープランの取得
        user_plan = "free"
        if payload.user_id:
            user_data = storage.get_user(payload.user_id)
            if user_data:
                user_plan = user_data.get("plan", "free")

        full_text_fragments: list[str] = []
        all_layout_data: list = []
        collected_figures: list = []
        page_count = 0

        # OCR ストリーミング処理
        async for result_tuple in _get_service().ocr_service.extract_text_streaming(
            pdf_content, payload.filename, user_plan=user_plan
        ):
            if len(result_tuple) != 7:
                continue

            (
                page_num,
                total_pages,
                page_text,
                is_last,
                f_hash,
                page_image_url,
                layout_data,
            ) = result_tuple

            page_count += 1

            if page_text and page_text.startswith("ERROR_API_FAILED:"):
                error_msg = page_text.replace("ERROR_API_FAILED: ", "")
                _push_event(task_id, {"type": "error", "message": error_msg})
                _get_redis_service().expire(_progress_key(task_id), 3600)
                task_data["status"] = "error"
                _get_redis_service().set(f"task:{task_id}", task_data, expire=3600)
                return {"ok": False, "error": error_msg}

            # Phase 1 速報値（image_url なし）はスキップ
            if not page_image_url:
                continue

            page_payload: dict = {
                "page_num": page_num,
                "image_url": page_image_url,
                "width": 0,
                "height": 0,
                "words": [],
                "figures": [],
                "content": "",
            }

            if page_text is not None:
                page_payload["content"] = page_text

                if layout_data:
                    full_text_fragments.append(page_text)
                    page_payload["width"] = layout_data["width"]
                    page_payload["height"] = layout_data["height"]
                    page_payload["words"] = layout_data.get("words", [])
                    page_payload["figures"] = layout_data.get("figures", [])
                    if "figures" in layout_data:
                        collected_figures.extend(layout_data["figures"])
                    all_layout_data.append(layout_data)

            _push_event(task_id, {"type": "page", "data": page_payload})
            await asyncio.sleep(0.01)

        # 座標・アシストモード完了イベント
        _push_event(task_id, {"type": "coordinates_ready", "page_count": page_count})
        _push_event(task_id, {"type": "assist_mode_ready"})

        full_text = "\n\n---\n\n".join(full_text_fragments)
        new_paper_id = payload.paper_id
        _db_saved = True

        # OCR エンジン集計
        _page_engines = {
            ld.get("_ocr_engine", "native")
            for ld in all_layout_data
            if ld and isinstance(ld, dict)
        }
        _scanned_count = sum(
            1
            for ld in all_layout_data
            if ld
            and isinstance(ld, dict)
            and ld.get("_ocr_engine") in ("ocrmypdf", "tesseract")
        )
        if len(_page_engines) == 1:
            _ocr_engine = next(iter(_page_engines))
        elif _page_engines:
            _ocr_engine = "mixed"
        else:
            _ocr_engine = "native"

        # 登録ユーザーのみ DB 保存
        if payload.is_registered:
            try:
                from app.crud import save_figure_to_db  # noqa: PLC0415

                storage.save_paper(
                    paper_id=new_paper_id,
                    file_hash=payload.file_hash,
                    filename=payload.filename,
                    ocr_text=full_text,
                    html_content="",
                    target_language="ja",
                    layout_json=json.dumps(all_layout_data),
                    owner_id=payload.user_id,
                    ocr_engine=_ocr_engine,
                    scanned_page_count=_scanned_count,
                )
                if payload.session_id:
                    storage.save_session_context(payload.session_id, new_paper_id)

                storage.update_processing_status(
                    new_paper_id, "layout_status", "success"
                )

                # PDF メタデータ（タイトル・著者）を取得して保存
                try:
                    import fitz as _fitz  # noqa: PLC0415

                    with _fitz.open(stream=pdf_content, filetype="pdf") as _doc:
                        _meta = _doc.metadata
                    _pdf_title = (_meta.get("title") or "").strip() or None
                    _pdf_authors = (_meta.get("author") or "").strip() or None
                    if _pdf_title:
                        storage.update_paper_title(new_paper_id, _pdf_title)
                    if _pdf_authors:
                        storage.update_paper_authors(new_paper_id, _pdf_authors)
                except Exception as _meta_err:
                    log.warning(
                        "process_ocr",
                        "PDF メタデータ取得失敗（無視）",
                        error=str(_meta_err),
                    )

                # バックグラウンドタスク起動
                asyncio.create_task(
                    process_paper_summary_task(new_paper_id, lang=payload.lang)
                )
                asyncio.create_task(
                    process_grobid_enrichment_task(new_paper_id, payload.file_hash)
                )

                if collected_figures:
                    for fig in collected_figures:
                        fid = save_figure_to_db(
                            paper_id=new_paper_id,
                            page_number=fig["page_num"],
                            bbox=fig.get("bbox", []),
                            image_url=fig.get("image_url", ""),
                            label=fig.get("label", "figure"),
                            latex=fig.get("latex", ""),
                        )
                        asyncio.create_task(
                            process_figure_analysis_task(fid, fig.get("image_url", ""))
                        )

                log.info(
                    "process_ocr",
                    "DB 保存完了",
                    task_id=task_id,
                    paper_id=new_paper_id,
                )
            except Exception as db_err:
                log.error("process_ocr", f"DB 保存失敗: {db_err}", task_id=task_id)
                _db_saved = False

        # セッションコンテキスト保存（全ユーザー）
        s_id = payload.session_id or new_paper_id
        _get_redis_service().set(f"session:ctx:{s_id}", full_text[:20000], expire=3600)

        # 完了イベント
        _push_event(
            task_id,
            {"type": "done", "paper_id": new_paper_id, "db_saved": _db_saved},
        )
        _get_redis_service().expire(_progress_key(task_id), 3600)

        # タスクステータスを "completed" に更新
        task_data["status"] = "completed"
        task_data["paper_id"] = new_paper_id
        _get_redis_service().set(f"task:{task_id}", task_data, expire=3600)

        log.info(
            "process_ocr",
            "OCR ワーカー完了",
            task_id=task_id,
            paper_id=new_paper_id,
            pages=page_count,
        )
        return {"ok": True, "paper_id": new_paper_id, "pages": page_count}

    except Exception as e:
        log.error("process_ocr", f"ワーカー例外: {e}", task_id=task_id, exc_info=True)
        _push_event(task_id, {"type": "error", "message": str(e)})
        _get_redis_service().expire(_progress_key(task_id), 3600)
        task_data["status"] = "error"
        _get_redis_service().set(f"task:{task_id}", task_data, expire=3600)
        return {"ok": False, "error": str(e)}
    finally:
        storage.close()
