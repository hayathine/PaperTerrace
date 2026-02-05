"""
ServiceB（推論サービス）のサービスモジュール
"""

from .layout_detection.layout_service import LayoutAnalysisService

__all__ = [
    "LayoutAnalysisService",
]
