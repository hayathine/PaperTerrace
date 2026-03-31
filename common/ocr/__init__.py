"""
OCR共通ユーティリティ

inference-service と backend の両方から利用される OCR 関連の共通処理。
"""

from .runner import ocrmypdf_run

__all__ = ["ocrmypdf_run"]
