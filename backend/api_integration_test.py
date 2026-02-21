#!/usr/bin/env python3
"""
レイアウト検出API統合テスト
FastAPIアプリケーションを直接テスト
"""

import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))

from app.main import app


def test_health_endpoint():
    """ヘルスチェックエンドポイントのテスト"""
    print("🏥 ヘルスチェックエンドポイントをテスト中...")

    with TestClient(app) as client:
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ ヘルスチェック成功!")
        return True


def test_layout_detection_endpoint():
    """レイアウト検出エンドポイントのテスト"""
    print("🔍 レイアウト検出エンドポイントをテスト中...")

    # テスト用のPNG画像を作成
    import tempfile

    from PIL import Image

    # 簡単なテスト画像を作成
    test_img = Image.new("RGB", (800, 600), color="white")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        test_img.save(temp_file.name, "PNG")
        test_image = temp_file.name

    print(f"📄 使用するテスト画像: {test_image}")

    try:
        with TestClient(app) as client:
            # ファイルをアップロード
            with open(test_image, "rb") as f:
                files = {"file": (os.path.basename(test_image), f, "image/png")}
                data = {"page_number": 1}

                response = client.post("/api/detect-layout", files=files, data=data)
    finally:
        # 一時ファイルを削除
        os.unlink(test_image)

        if response.status_code == 200:
            result = response.json()
            print("✅ レイアウト検出成功!")
            print(f"📊 検出要素数: {result.get('total_elements', 0)}")

            elements = result.get("elements", [])
            if elements:
                print("\n=== 検出された要素（最初の5個） ===")
                for i, element in enumerate(elements[:5]):
                    class_name = element.get("class_name", "Unknown")
                    confidence = element.get("confidence", 0.0)
                    bbox = element.get("bbox", {})

                    print(
                        f"要素{i + 1:2d}: {class_name:15s} | 信頼度: {confidence:.3f} | "
                        f"座標: [{bbox.get('x_min', 0):4.0f}, {bbox.get('y_min', 0):4.0f}, "
                        f"{bbox.get('x_max', 0):4.0f}, {bbox.get('y_max', 0):4.0f}]"
                    )

                if len(elements) > 5:
                    print(f"... 他 {len(elements) - 5} 個の要素")

                # 要素タイプ別の統計
                print("\n=== 要素タイプ別統計 ===")
                type_counts = {}
                for element in elements:
                    class_name = element.get("class_name", "Unknown")
                    type_counts[class_name] = type_counts.get(class_name, 0) + 1

                for class_name, count in sorted(type_counts.items()):
                    print(f"{class_name:15s}: {count:3d}個")

            return True
        else:
            print(f"❌ APIエラー: {response.status_code}")
            print(f"レスポンス: {response.text}")
            return False


def test_invalid_file_upload():
    """無効なファイルアップロードのテスト"""
    print("🚫 無効なファイルアップロードをテスト中...")

    with TestClient(app) as client:
        # テキストファイルをアップロード（画像ではない）
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is not an image")
            temp_path = f.name

        try:
            with open(temp_path, "rb") as f:
                files = {"file": ("test.txt", f, "text/plain")}
                data = {"page_number": 1}

                response = client.post("/api/detect-layout", files=files, data=data)

            # 400エラーが期待される
            if response.status_code == 400:
                print("✅ 無効なファイル形式を正しく拒否!")
                return True
            else:
                print(f"❌ 予期しないレスポンス: {response.status_code}")
                return False

        finally:
            os.unlink(temp_path)


def main():
    """メイン処理"""
    print("🚀 レイアウト検出API統合テスト開始")

    tests = [
        ("ヘルスチェック", test_health_endpoint),
        ("レイアウト検出", test_layout_detection_endpoint),
        ("無効ファイル", test_invalid_file_upload),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 50}")
        print(f"テスト: {test_name}")
        print(f"{'=' * 50}")

        try:
            success = test_func()
            results.append((test_name, success))
            if success:
                print(f"✅ {test_name}テスト成功!")
            else:
                print(f"❌ {test_name}テスト失敗!")
        except Exception as e:
            print(f"❌ {test_name}テストでエラー: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # 結果サマリー
    print(f"\n{'=' * 50}")
    print("テスト結果サマリー")
    print(f"{'=' * 50}")

    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:15s}: {status}")
        if success:
            passed += 1

    print(f"\n🎯 結果: {passed}/{len(results)} テスト成功")

    if passed == len(results):
        print("🎉 全テスト成功! レイアウト検出機能は正常に動作しています。")
    else:
        print("⚠️  一部のテストが失敗しました。")

    print("\n✅ 統合テスト完了")


if __name__ == "__main__":
    main()
