"""
推論専用サービス（ServiceB）
Cloud Run 最適化版
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
from services.layout_detection.layout_service import LayoutAnalysisService
from services.translation.translation_service import TranslationService
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
    global layout_service, translation_service, _initialized, _init_started_at

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
    return {
        "status": "healthy" if _initialized else "starting",
        "initialized": _initialized,
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
