"""
推論専用サービス（ServiceB）
レイアウト解析と翻訳処理を担当
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services.layout_detection.layout_service import LayoutAnalysisService
from services.translation.translation_service import TranslationService
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ログ設定（標準出力に出力）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Cloud Run環境での設定
if os.getenv("K_SERVICE"):
    # Cloud Run環境では構造化ログを使用
    import json

    class StructuredFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                "timestamp": self.formatTime(record),
                "severity": record.levelname,
                "message": record.getMessage(),
                "service": "paperterrace-inference",
                "component": record.name,
            }
            if hasattr(record, "processing_time"):
                log_entry["processing_time"] = record.processing_time
            return json.dumps(log_entry)

    # 既存のハンドラーを削除して構造化ログハンドラーを追加
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

# レート制限設定
# マイクロサービス間通信ではIPベースの制限が全ユーザー巻き添えの原因になるため、デフォルト無効化
limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("ENABLE_RATE_LIMIT", "false").lower() == "true",
)

# グローバルサービスインスタンス
layout_service: Optional[LayoutAnalysisService] = None
translation_service: Optional[TranslationService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了時の処理"""
    global layout_service, translation_service

    print("推論サービスを初期化中...")  # Cloud Runで確実に表示されるようにprint使用
    logger.info("推論サービスを初期化中...")
    start_time = time.time()

    try:
        # サービス初期化
        layout_service = LayoutAnalysisService(lang="en")
        translation_service = TranslationService()

        # 翻訳サービスのみ初期化が必要
        print("翻訳サービスを初期化中...")
        await translation_service.initialize()

        init_time = time.time() - start_time
        print(f"推論サービス初期化完了: {init_time:.2f}秒")
        logger.info("推論サービス初期化完了", extra={"processing_time": init_time})

        yield

    except Exception as e:
        print(f"推論サービス初期化失敗: {e}")
        logger.error(f"推論サービス初期化失敗: {e}")
        raise
    finally:
        print("推論サービスを終了中...")
        logger.info("推論サービスを終了中...")
        if translation_service:
            await translation_service.cleanup()


# FastAPIアプリケーション
app = FastAPI(
    title="PaperTerrace Inference Service",
    description="レイアウト解析と翻訳処理専用サービス",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# レート制限設定
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# リクエスト・レスポンスモデル
class LayoutAnalysisRequest(BaseModel):
    pdf_path: str
    pages: Optional[List[int]] = None


class LayoutAnalysisResponse(BaseModel):
    success: bool
    results: List[dict]
    processing_time: float
    message: Optional[str] = None


class TranslationRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "ja"


class TranslationBatchRequest(BaseModel):
    texts: List[str]
    source_lang: str = "en"
    target_lang: str = "ja"


class TranslationResponse(BaseModel):
    success: bool
    translation: str
    processing_time: float
    message: Optional[str] = None


class TranslationBatchResponse(BaseModel):
    success: bool
    translations: List[str]
    processing_time: float
    message: Optional[str] = None


# ヘルスチェック
@app.get("/health")
async def health_check():
    """サービスの健全性チェック"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "layout_analysis": layout_service is not None,
            "translation": translation_service is not None,
        },
    }


# レイアウト解析エンドポイント（画像アップロード版）
@app.post("/api/v1/analyze-image")
@limiter.limit(os.getenv("RATE_LIMIT_LAYOUT", "60/minute"))
async def analyze_layout_image(request: Request, file: UploadFile = File(...)):
    """画像からレイアウト解析を実行"""
    if not layout_service:
        raise HTTPException(
            status_code=503, detail="Layout analysis service not available"
        )

    start_time = time.time()
    temp_file_path = None

    try:
        logger.info(f"レイアウト画像解析開始: {file.filename}")

        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name

        # 解析実行 (スレッドプールで実行してイベントループをブロックしない)
        # analyze_image は dict ではなく LayoutItem オブジェクトを返す
        results = await run_in_threadpool(layout_service.analyze_image, temp_file_path)

        processing_time = time.time() - start_time
        logger.info(f"レイアウト画像解析完了: {processing_time:.2f}秒")

        # LayoutItemオブジェクトを辞書に変換
        serializable_results = []
        for item in results:
            serializable_results.append(
                {
                    "bbox": {
                        "x_min": item.bbox.x_min,
                        "y_min": item.bbox.y_min,
                        "x_max": item.bbox.x_max,
                        "y_max": item.bbox.y_max,
                    },
                    "class_name": item.class_name,
                    "score": item.score,
                }
            )

        return {
            "success": True,
            "results": serializable_results,
            "processing_time": processing_time,
        }

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"レイアウト画像解析エラー: {e}")
        return {
            "success": False,
            "results": [],
            "processing_time": processing_time,
            "message": str(e),
        }
    finally:
        if temp_file_path:
            Path(temp_file_path).unlink(missing_ok=True)


# レイアウト解析エンドポイント（PDFパス版）
@app.post("/api/v1/layout-analysis", response_model=LayoutAnalysisResponse)
@limiter.limit(
    os.getenv("RATE_LIMIT_LAYOUT", "60/minute")
)  # デフォルト: 1分間に60リクエスト
async def analyze_layout(request: Request, req: LayoutAnalysisRequest):
    """PDFのレイアウト解析を実行"""
    if not layout_service:
        raise HTTPException(
            status_code=503, detail="Layout analysis service not available"
        )

    start_time = time.time()

    try:
        logger.info(f"レイアウト解析開始: {req.pdf_path}")

        # 新しいAPIを使用してレイアウト解析を実行
        results = await layout_service.analyze_async(req.pdf_path)
        processing_time = time.time() - start_time

        logger.info(f"レイアウト解析完了: {processing_time:.2f}秒")

        return LayoutAnalysisResponse(
            success=True, results=results, processing_time=processing_time
        )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"レイアウト解析エラー: {e}")

        return LayoutAnalysisResponse(
            success=False, results=[], processing_time=processing_time, message=str(e)
        )


# 翻訳エンドポイント
@app.post("/api/v1/translate", response_model=TranslationResponse)
@limiter.limit(
    os.getenv("RATE_LIMIT_TRANSLATE", "300/minute")
)  # デフォルト: 1分間に300リクエスト
async def translate_text(request: Request, req: TranslationRequest):
    """テキストの翻訳を実行"""
    if not translation_service:
        raise HTTPException(status_code=503, detail="Translation service not available")

    start_time = time.time()

    try:
        logger.info(f"翻訳開始: {req.text[:50]}...")

        translation = await translation_service.translate(
            req.text, req.source_lang, req.target_lang
        )
        processing_time = time.time() - start_time

        logger.info(f"翻訳完了: {processing_time:.2f}秒")

        return TranslationResponse(
            success=True, translation=translation, processing_time=processing_time
        )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"翻訳エラー: {e}")

        return TranslationResponse(
            success=False,
            translation="",
            processing_time=processing_time,
            message=str(e),
        )


# バッチ翻訳エンドポイント
@app.post("/api/v1/translate-batch", response_model=TranslationBatchResponse)
@limiter.limit(
    os.getenv("RATE_LIMIT_BATCH", "60/minute")
)  # デフォルト: 1分間に60リクエスト
async def translate_batch(request: Request, req: TranslationBatchRequest):
    """複数テキストの一括翻訳を実行"""
    if not translation_service:
        raise HTTPException(status_code=503, detail="Translation service not available")

    start_time = time.time()

    try:
        logger.info(f"バッチ翻訳開始: {len(req.texts)}件")

        translations = await translation_service.translate_batch(
            req.texts, req.source_lang, req.target_lang
        )
        processing_time = time.time() - start_time

        logger.info(f"バッチ翻訳完了: {processing_time:.2f}秒")

        return TranslationBatchResponse(
            success=True, translations=translations, processing_time=processing_time
        )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"バッチ翻訳エラー: {e}")

        return TranslationBatchResponse(
            success=False,
            translations=[],
            processing_time=processing_time,
            message=str(e),
        )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    # Cloud Run環境での設定
    uvicorn_config = {
        "host": "0.0.0.0",
        "port": port,
        "log_level": log_level,
        "access_log": True,
        "use_colors": False,  # Cloud Runでは色付きログを無効化
    }

    # 開発環境では色付きログを有効化
    if not os.getenv("K_SERVICE"):
        uvicorn_config["use_colors"] = True

    uvicorn.run("main:app", **uvicorn_config)
