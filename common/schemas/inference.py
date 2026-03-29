from typing import Any, List, Optional

from pydantic import BaseModel


class LayoutAnalysisRequest(BaseModel):
    pdf_path: str
    pages: Optional[List[int]] = None


class LayoutAnalysisResponse(BaseModel):
    success: bool
    results: List[Any]  # Can be list of dicts or LayoutItem
    processing_time: float
    message: Optional[str] = None


class TranslationRequest(BaseModel):
    text: str
    original_text: Optional[str] = None
    target_lang: str = "ja"
    paper_context: Optional[str] = None


class TranslationResponse(BaseModel):
    success: bool
    translation: str
    processing_time: float
    confidence: Optional[float] = None
    model: Optional[str] = None
    lemma: Optional[str] = None
    message: Optional[str] = None


class TranslationBatchRequest(BaseModel):
    texts: List[str]
    target_lang: str = "ja"


class TranslationBatchResponse(BaseModel):
    success: bool
    translations: List[str]
    processing_time: float
    confidences: Optional[List[float]] = None
    models: Optional[List[str]] = None
    lemmas: Optional[List[str]] = None
    message: Optional[str] = None


class TokenizeRequest(BaseModel):
    text: str
    lang: str = "en"


class TokenizeResponse(BaseModel):
    success: bool
    tokens: List[Any]  # List of dicts with text, lemma, ws
    processing_time: float
    message: Optional[str] = None


class LayoutBatchByUrlsRequest(BaseModel):
    """署名付きURLによる一括レイアウト解析リクエスト"""
    image_urls: List[str]
    page_nums: Optional[List[int]] = None


class OcrPageResponse(BaseModel):
    """OCRページ認識レスポンス"""
    success: bool
    text: str
    words: Optional[List[dict]] = None
    processing_time: float
    message: Optional[str] = None
