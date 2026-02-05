#!/usr/bin/env python3
"""
インポートデバッグスクリプト
"""

print("=== インポートテスト開始 ===")

try:
    import cv2
    print("✅ OpenCV インポート成功")
    print(f"   バージョン: {cv2.__version__}")
except ImportError as e:
    print(f"❌ OpenCV インポート失敗: {e}")

try:
    from paddleocr import PaddleOCR
    print("✅ PaddleOCR インポート成功")
except ImportError as e:
    print(f"❌ PaddleOCR インポート失敗: {e}")

try:
    from services.layout_service import LayoutAnalysisService
    print("✅ LayoutAnalysisService インポート成功")
    
    # サービスを初期化してみる
    service = LayoutAnalysisService()
    print("✅ LayoutAnalysisService 初期化成功")
    
except ImportError as e:
    print(f"❌ LayoutAnalysisService インポート失敗: {e}")
except Exception as e:
    print(f"❌ LayoutAnalysisService 初期化失敗: {e}")

print("=== インポートテスト完了 ===")