"""
ServiceB（推論サービス）のサービスモジュール
"""

from .layout_service import LayoutAnalysisService
from .translation_service import TranslationService

__all__ = [
    "LayoutAnalysisService",
    "TranslationService",
]
