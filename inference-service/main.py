"""
推論専用サービス（ServiceB）
- 即 listen
- 遅延初期化（lazy init）
- ヘルスチェック常時応答
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

if os.getenv("USE_OPENVINO", "true").lower() == "true":
    from services.layout_detection.openvino_layout_service import (
        OpenVINOLayoutAnalysisService as LayoutAnalysisService,
    )
else:
    from services.layout_detection.layout_service import LayoutAnalysisService
from services.translation.translation_service import TranslationService
from services.translation_with_llamacpp.llamacpp_service import (
    LlamaCppTranslationService,
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from common.logger import configure_logging, logger
from common.schemas.inference import (
    LayoutAnalysisRequest,
    LayoutAnalysisResponse,
    TranslationRequest,
    TranslationResponse,
)

# --------------------------------------------------
# 初期設定
# --------------------------------------------------

configure_logging()

limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("ENABLE_RATE_LIMIT", "false").lower() == "true",
)

app = FastAPI(
    title="PaperTerrace Inference Service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# gzip圧縮を有効化（レスポンスサイズを削減）
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --------------------------------------------------
# グローバル状態
# --------------------------------------------------
_initialized = False
_init_lock = asyncio.Lock()
_init_started_at: Optional[float] = None


# --------------------------------------------------
# 遅延初期化
# --------------------------------------------------


async def ensure_initialized():
    global \
        layout_service, \
        translation_service, \
        llamacpp_service, \
        _initialized, \
        _init_started_at

    if _initialized:
        return

    async with _init_lock:
        if _initialized:
            return

        _init_started_at = time.time()
        logger.info("Initializing inference services...")

        layout_service = LayoutAnalysisService(lang="en")
        translation_service = TranslationService()
        await translation_service.initialize()

        llamacpp_service = LlamaCppTranslationService()
        # LLMの初期化は重くメモリを食うため、必要に応じて遅延実行するか
        # または起動時に一気に行ってしまう（ここでは一気に行う）
        await llamacpp_service.initialize()

        _initialized = True
        logger.info(
            "Inference services initialized",
            elapsed_sec=time.time() - _init_started_at,
        )


# --------------------------------------------------
# ヘルスチェック
# --------------------------------------------------


@app.get("/health")
async def health_check():
    gpu_status = "not_checked"
    # Skip nvidia-smi if not found to avoid hanging or errors
    # It's better to check for device presence more safely if needed

    return {
        "status": "healthy" if _initialized else "starting",
        "initialized": _initialized,
        "gpu": gpu_status,
        "uptime_sec": None if not _init_started_at else time.time() - _init_started_at,
    }


# --------------------------------------------------
# レイアウト解析（画像）
# --------------------------------------------------


@app.post("/api/v1/analyze-image")
@limiter.limit(os.getenv("RATE_LIMIT_LAYOUT", "60/minute"))
async def analyze_layout_image(request: Request, file: UploadFile = File(...)):
    await ensure_initialized()

    if not layout_service:
        raise HTTPException(status_code=503, detail="Layout service unavailable")

    start_time = time.time()
    temp_path: Optional[Path] = None

    try:
        temp_path = Path(f"/tmp/{int(time.time() * 1000)}.png")
        with temp_path.open("wb") as f:
            f.write(await file.read())

        if hasattr(layout_service, "engine"):
            logger.info(f"Using {layout_service.engine} for layout analysis")

        results = await run_in_threadpool(layout_service.analyze_image, str(temp_path))

        serializable = [
            {
                "bbox": {
                    "x_min": r.bbox.x_min,
                    "y_min": r.bbox.y_min,
                    "x_max": r.bbox.x_max,
                    "y_max": r.bbox.y_max,
                },
                "class_name": r.class_name,
                "score": r.score,
            }
            for r in results
        ]

        return {
            "success": True,
            "results": serializable,
            "processing_time": time.time() - start_time,
        }

    except Exception as e:
        logger.exception("Layout image analysis failed")
        return {
            "success": False,
            "results": [],
            "processing_time": time.time() - start_time,
            "message": str(e),
        }

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post("/api/v1/analyze-images-batch")
@limiter.limit(os.getenv("RATE_LIMIT_LAYOUT_BATCH", "20/minute"))
async def analyze_images_batch(request: Request, files: list[UploadFile] = File(...)):
    """
    複数画像を一括解析（バッチ処理）
    通信回数を削減して高速化

    並列数は環境変数 BATCH_PARALLEL_WORKERS で制御可能
    デフォルト: CPU数（最小1）
    """
    await ensure_initialized()

    if not layout_service:
        raise HTTPException(status_code=503, detail="Layout service unavailable")

    start_time = time.time()
    logger.info(f"Batch analysis request: {len(files)} images")

    try:
        # 環境変数から並列数を取得（resources.jsonから設定される）
        # フォールバック: CPU数
        cpu_count = os.cpu_count() or 2
        max_parallel = int(os.getenv("BATCH_PARALLEL_WORKERS", cpu_count))
        max_parallel = max(1, max_parallel)  # 最低1

        logger.info(
            f"Using {max_parallel} parallel workers "
            f"(CPU count: {cpu_count}, env: {os.getenv('BATCH_PARALLEL_WORKERS', 'not set')})"
        )

        # 並列処理用のセマフォ
        semaphore = asyncio.Semaphore(max_parallel)

        async def process_one(file: UploadFile, index: int):
            async with semaphore:
                temp_path = None
                try:
                    temp_path = Path(f"/tmp/{int(time.time() * 1000)}_{index}.jpg")
                    content = await file.read()
                    temp_path.write_bytes(content)

                    results = await run_in_threadpool(
                        layout_service.analyze_image, str(temp_path)
                    )

                    serializable = [
                        {
                            "bbox": {
                                "x_min": r.bbox.x_min,
                                "y_min": r.bbox.y_min,
                                "x_max": r.bbox.x_max,
                                "y_max": r.bbox.y_max,
                            },
                            "class_name": r.class_name,
                            "score": r.score,
                        }
                        for r in results
                    ]

                    return serializable

                except Exception as e:
                    logger.error(f"Failed to process image {index}: {e}")
                    return []

                finally:
                    if temp_path and temp_path.exists():
                        temp_path.unlink(missing_ok=True)

        # 全画像を並列処理
        results = await asyncio.gather(
            *[process_one(f, i) for i, f in enumerate(files)]
        )

        processing_time = time.time() - start_time
        avg_time = processing_time / len(files) if files else 0
        logger.info(
            f"Batch analysis completed: {len(files)} images in {processing_time:.2f}s "
            f"({avg_time:.2f}s per image)"
        )

        return {
            "success": True,
            "results": results,
            "processing_time": processing_time,
            "images_processed": len(files),
            "parallel_workers": max_parallel,
        }

    except Exception as e:
        logger.exception("Batch layout analysis failed")
        return {
            "success": False,
            "results": [],
            "processing_time": time.time() - start_time,
            "message": str(e),
        }


# --------------------------------------------------
# レイアウト解析（PDF）
# --------------------------------------------------


@app.post("/api/v1/layout-analysis", response_model=LayoutAnalysisResponse)
@limiter.limit(os.getenv("RATE_LIMIT_LAYOUT", "60/minute"))
async def analyze_layout(request: Request, req: LayoutAnalysisRequest):
    await ensure_initialized()

    start_time = time.time()

    try:
        results = await layout_service.analyze_async(req.pdf_path)

        return LayoutAnalysisResponse(
            success=True,
            results=results,
            processing_time=time.time() - start_time,
        )

    except Exception as e:
        logger.exception("Layout analysis failed")
        return LayoutAnalysisResponse(
            success=False,
            results=[],
            processing_time=time.time() - start_time,
            message=str(e),
        )


# --------------------------------------------------
# 翻訳
# --------------------------------------------------


@app.post("/api/v1/translate", response_model=TranslationResponse)
@limiter.limit(os.getenv("RATE_LIMIT_TRANSLATE", "300/minute"))
async def translate_text(request: Request, req: TranslationRequest):
    await ensure_initialized()

    start_time = time.time()

    try:
        # paper_context がある場合は llama-cpp (LLM) による高度な翻訳を実行
        if req.paper_context:
            logger.info("Using Llama-cpp for context-aware translation")
            translation = await llamacpp_service.translate_with_llamacpp(
                original_word=req.text,
                paper_context=req.paper_context,
                lang_name="Japanese" if req.target_lang == "ja" else "English",
            )
        else:
            # それ以外は通常の M2M100 翻訳を実行
            translation = await translation_service.translate(req.text, req.target_lang)

        return TranslationResponse(
            success=True,
            translation=translation,
            processing_time=time.time() - start_time,
        )

    except Exception as e:
        logger.exception("Translation failed")
        return TranslationResponse(
            success=False,
            translation="",
            processing_time=time.time() - start_time,
            message=str(e),
        )
