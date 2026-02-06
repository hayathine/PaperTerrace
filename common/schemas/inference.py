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
    source_lang: str = "en"
    target_lang: str = "ja"


class TranslationResponse(BaseModel):
    success: bool
    translation: str
    processing_time: float
    message: Optional[str] = None


class TranslationBatchRequest(BaseModel):
    texts: List[str]
    source_lang: str = "en"
    target_lang: str = "ja"


class TranslationBatchResponse(BaseModel):
    success: bool
    translations: List[str]
    processing_time: float
    message: Optional[str] = None
