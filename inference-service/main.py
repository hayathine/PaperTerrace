"""
推論専用サービス（ServiceB）
- 即 listen
- 遅延初期化（lazy init）
- ヘルスチェック常時応答
"""

import asyncio
import os
import time
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from common.logger import configure_logging, logger
from common.schemas.inference import (
    LayoutAnalysisRequest,
    LayoutAnalysisResponse,
    TokenizeRequest,
    TokenizeResponse,
    TranslationRequest,
    TranslationResponse,
)

# --------------------------------------------------
# 初期設定
# --------------------------------------------------

configure_logging()

INFERENCE_TYPE = os.getenv("INFERENCE_TYPE", "all").lower()

# サービスインスタンス
layout_service = None
m2m100_service = None
llamacpp_service = None
translation_service = None

if INFERENCE_TYPE in ["all", "layout"]:
    try:
        if os.getenv("USE_OPENVINO", "true").lower() == "true":
            from services.layout_detection.openvino_layout_service import (
                OpenVINOLayoutAnalysisService as LayoutAnalysisService,
            )
        else:
            from services.layout_detection.layout_service import LayoutAnalysisService
    except ImportError:
        logger.warning("Layout detection dependencies not found, skipping import")

if INFERENCE_TYPE in ["all", "translation", "m2m100", "qwen"]:
    try:
        from services.translation.llamacpp_service import LlamaCppTranslationService
        from services.translation.m2m100_service import M2M100TranslationService
        from services.translation.translation_service import TranslationService
    except ImportError:
        logger.warning("Translation dependencies not found, skipping import")

limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("ENABLE_RATE_LIMIT", "false").lower() == "true",
)

app = FastAPI(
    title=f"PaperTerrace Inference Service ({INFERENCE_TYPE})",
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
        m2m100_service, \
        llamacpp_service, \
        translation_service, \
        _initialized, \
        _init_started_at

    if _initialized:
        return

    async with _init_lock:
        if _initialized:
            return

        _init_started_at = time.time()
        logger.info(f"Initializing inference services (type: {INFERENCE_TYPE})...")

        if INFERENCE_TYPE in ["all", "layout"]:
            layout_service = LayoutAnalysisService(lang="en")
            logger.info("LayoutAnalysisService initialized")

        if INFERENCE_TYPE in ["all", "translation", "m2m100", "qwen"]:
            if INFERENCE_TYPE in ["all", "translation", "m2m100"]:
                # M2M100
                m2m100_service = M2M100TranslationService()
                await m2m100_service.initialize()
                logger.info("M2M100TranslationService initialized")

            if INFERENCE_TYPE in ["all", "translation", "qwen"]:
                # LlamaCpp
                llamacpp_service = LlamaCppTranslationService()
                await llamacpp_service.initialize()
                logger.info("LlamaCppTranslationService initialized")

            # Orchestrator
            translation_service = TranslationService(
                m2m100_service=m2m100_service,
                llamacpp_service=llamacpp_service,
                inference_type=INFERENCE_TYPE,
            )
            logger.info("TranslationService orchestrator initialized")

        _initialized = True
        logger.info(
            f"Inference services ({INFERENCE_TYPE}) initialized",
            elapsed_sec=time.time() - _init_started_at,
        )


# --------------------------------------------------
# ライフサイクル管理
# --------------------------------------------------


@app.on_event("startup")
async def startup_event():
    # 環境変数 PRELOAD_MODELS=true の場合、バックグラウンドで直ちに初期化を開始
    if os.getenv("PRELOAD_MODELS", "false").lower() == "true":
        logger.info("PRELOAD_MODELS is enabled. Starting eager initialization...")
        asyncio.create_task(ensure_initialized())


# --------------------------------------------------
# ヘルスチェック
# --------------------------------------------------


@app.get("/health")
async def health_check(request: Request):
    gpu_status = "not_checked"

    # 初期化が完了していない場合は 503 を返すことで、
    # Kubernetes の Readiness Probe に「まだトラフィックを受けられない」と伝える
    is_ready = _initialized
    status_code = 200 if is_ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_ready else "starting",
            "type": INFERENCE_TYPE,
            "initialized": is_ready,
            "gpu": gpu_status,
            "uptime_sec": None
            if not _init_started_at
            else time.time() - _init_started_at,
        },
    )


# --------------------------------------------------
# レイアウト解析（画像）
# --------------------------------------------------


if INFERENCE_TYPE in ["all", "layout"]:

    @app.post("/api/v1/analyze-image")
    @limiter.limit(os.getenv("RATE_LIMIT_LAYOUT", "60/minute"))
    async def analyze_layout_image(request: Request, file: UploadFile = File(...)):
        await ensure_initialized()

        if not layout_service:
            raise HTTPException(status_code=503, detail="Layout service unavailable")

        start_time = time.time()

        try:
            image_bytes = await file.read()

            if hasattr(layout_service, "engine"):
                logger.info(f"Using {layout_service.engine} for layout analysis")

            if hasattr(layout_service, "analyze_image_from_bytes"):
                results = await layout_service.analyze_image_from_bytes(image_bytes)
            else:
                results = await layout_service.analyze_image(image_bytes)

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
            app_env = os.getenv("APP_ENV", "production")
            error_msg = (
                str(e)
                if app_env == "development"
                else "Internal error during layout analysis"
            )
            return {
                "success": False,
                "results": [],
                "processing_time": time.time() - start_time,
                "message": error_msg,
            }

    @app.post("/api/v1/analyze-images-batch")
    @limiter.limit(os.getenv("RATE_LIMIT_LAYOUT_BATCH", "20/minute"))
    async def analyze_images_batch(
        request: Request, files: list[UploadFile] = File(...)
    ):
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
        # ファイル名からページ番号を抽出（クライアント側で page_{num}.jpg としている前提）
        page_list = []
        for f in files:
            fname = f.filename or ""
            if fname.startswith("page_"):
                # "page_1.jpg" -> "1"
                p_str = fname.replace("page_", "").split(".")[0]
                if p_str.isdigit():
                    page_list.append(int(p_str))
                else:
                    page_list.append(fname)
            else:
                page_list.append(fname)

        logger.info(
            f"Batch analysis request: {len(files)} images, page_list: {page_list}"
        )

        try:
            # 各画像をbytesとして読み込む（一時ファイル不要）
            images_bytes = [await file.read() for file in files]

            # 一括解析を実行
            if hasattr(layout_service, "analyze_images_batch_from_bytes"):
                batch_results = await layout_service.analyze_images_batch_from_bytes(
                    images_bytes
                )
            elif hasattr(layout_service, "analyze_images_batch"):
                # フォールバック（analyze_images_batchしかない場合）
                batch_results = await layout_service.analyze_images_batch(images_bytes)
            else:
                batch_results = []
                for img_bytes in images_bytes:
                    res = await run_in_threadpool(layout_service.analyze_image, img_bytes)
                    batch_results.append(res)

            # シリアライズ
            results = []
            for page_results in batch_results:
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
                    for r in page_results
                ]
                results.append(serializable)

            processing_time = time.time() - start_time
            return {
                "success": True,
                "results": results,
                "processing_time": processing_time,
                "images_processed": len(files),
            }

        except Exception as e:
            logger.exception("Batch layout analysis failed")
            app_env = os.getenv("APP_ENV", "production")
            error_msg = (
                str(e)
                if app_env == "development"
                else "Internal error during batch layout analysis"
            )
            return {
                "success": False,
                "results": [],
                "processing_time": time.time() - start_time,
                "message": error_msg,
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
            app_env = os.getenv("APP_ENV", "production")
            error_msg = (
                str(e)
                if app_env == "development"
                else "Internal error during layout analysis"
            )
            return LayoutAnalysisResponse(
                success=False,
                results=[],
                processing_time=time.time() - start_time,
                message=error_msg,
            )


# --------------------------------------------------
# 翻訳
# --------------------------------------------------


if INFERENCE_TYPE in ["all", "translation", "m2m100", "qwen"]:

    @app.post("/api/v1/translate", response_model=TranslationResponse)
    @limiter.limit(os.getenv("RATE_LIMIT_TRANSLATE", "300/minute"))
    async def translate_text(request: Request, req: TranslationRequest):
        await ensure_initialized()

        start_time = time.time()

        try:
            translation, model, confidence, lemma = await translation_service.translate(
                req.text,
                req.target_lang,
                paper_context=req.paper_context or "",
                original_text=req.original_text,
            )

            return TranslationResponse(
                success=True,
                translation=translation,
                model=model,
                confidence=confidence,
                lemma=lemma,
                processing_time=time.time() - start_time,
            )

        except Exception as e:
            from services.translation.llamacpp_service import LlamaBusyError

            if isinstance(e, LlamaBusyError):
                logger.warning(f"Qwen busy, rejecting request: {e}")
                raise HTTPException(status_code=503, detail="Qwen is busy")

            logger.exception("Translation failed")
            app_env = os.getenv("APP_ENV", "production")
            error_msg = (
                str(e)
                if app_env == "development"
                else "Internal error during translation"
            )
            return TranslationResponse(
                success=False,
                translation="",
                processing_time=time.time() - start_time,
                message=error_msg,
            )

    @app.post("/api/v1/tokenize", response_model=TokenizeResponse)
    @limiter.limit(os.getenv("RATE_LIMIT_TOKENIZE", "300/minute"))
    async def tokenize_text_api(request: Request, req: TokenizeRequest):
        await ensure_initialized()
        from services.translation.nlp import NLPService

        start_time = time.time()
        try:
            tokens = NLPService.tokenize(req.text)
            return TokenizeResponse(
                success=True,
                tokens=tokens,
                processing_time=time.time() - start_time,
            )
        except Exception as e:
            logger.exception("Tokenization failed")
            return TokenizeResponse(
                success=False,
                tokens=[],
                processing_time=time.time() - start_time,
                message=str(e),
            )
