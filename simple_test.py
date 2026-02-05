#!/usr/bin/env python3
"""
PP-DocLayout-S簡単テストスクリプト
"""

import json
import os
import subprocess
import time

def test_inference_service():
    """inference-serviceのレイアウト解析をテスト"""
    print("🚀 PP-DocLayout-S レイアウト解析テスト開始")
    
    # inference-serviceのURL
    base_url = "http://localhost:8081"
    
    # ヘルスチェック
    print("\n=== ヘルスチェック ===")
    result = subprocess.run([
        "curl", "-s", f"{base_url}/health"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        health_data = json.loads(result.stdout)
        print(f"✅ Inference-service ヘルスチェック: {health_data}")
        
        if not health_data.get("services", {}).get("layout_analysis"):
            print("⚠️  レイアウト解析サービスが利用できません")
            return
    else:
        print(f"❌ Inference-serviceに接続できません: {result.stderr}")
        return
    
    # テスト用画像ファイルを作成（ダミー）
    test_image = "test_dummy.png"
    print(f"\n=== テスト用ダミー画像作成 ===")
    
    # 簡単な白い画像を作成（ImageMagickがあれば）
    create_result = subprocess.run([
        "convert", "-size", "800x1000", "xc:white", test_image
    ], capture_output=True, text=True)
    
    if create_result.returncode != 0:
        print("ImageMagickが利用できません。既存のPDFを使用します。")
        # frontend/public/test.pdfを使用
        test_pdf = "frontend/public/test.pdf"
        if os.path.exists(test_pdf):
            print(f"📄 使用するPDF: {test_pdf}")
            # PDFの最初のページをPNGに変換（pdftoppmがあれば）
            convert_result = subprocess.run([
                "pdftoppm", "-png", "-f", "1", "-l", "1", test_pdf, "test_page"
            ], capture_output=True, text=True)
            
            if convert_result.returncode == 0:
                test_image = "test_page-1.png"
                print(f"✅ PDF変換完了: {test_image}")
            else:
                print("PDFの変換に失敗しました。ダミーファイルを作成します。")
                # ダミーファイルを作成
                with open(test_image, "w") as f:
                    f.write("dummy")
        else:
            print("test.pdfが見つかりません。ダミーファイルを作成します。")
            with open(test_image, "w") as f:
                f.write("dummy")
    else:
        print(f"✅ テスト用画像作成完了: {test_image}")
    
    # レイアウト解析リクエスト
    print(f"\n=== レイアウト解析実行 ===")
    start_time = time.time()
    
    # 絶対パスを取得
    image_path_abs = os.path.abspath(test_image)
    
    # curlでPOSTリクエスト
    curl_data = json.dumps({
        "pdf_path": image_path_abs,
        "pages": [1]
    })
    
    result = subprocess.run([
        "curl", "-s", "-X", "POST",
        f"{base_url}/api/v1/layout-analysis",
        "-H", "Content-Type: application/json",
        "-d", curl_data
    ], capture_output=True, text=True)
    
    total_time = time.time() - start_time
    
    if result.returncode == 0:
        try:
            response_data = json.loads(result.stdout)
            
            print(f"✅ レイアウト解析完了!")
            print(f"📊 処理時間: {total_time:.3f}秒")
            print(f"🔍 成功: {response_data.get('success', False)}")
            print(f"🔍 検出要素数: {len(response_data.get('results', []))}")
            print(f"📝 メッセージ: {response_data.get('message', 'なし')}")
            
            if response_data.get("success"):
                elements = response_data.get("results", [])
                
                # 結果の詳細表示
                print(f"\n=== 検出された要素 ===")
                for i, element in enumerate(elements[:10]):  # 最初の10個のみ表示
                    bbox = element.get("bbox", [])
                    class_name = element.get("class", "unknown")
                    confidence = element.get("confidence", 0.0)
                    text = element.get("text", "")[:50]  # 最初の50文字のみ
                    
                    print(f"要素{i+1:2d}: {class_name:8s} | 信頼度: {confidence:.3f} | "
                          f"座標: [{bbox[0]:4d}, {bbox[1]:4d}, {bbox[2]:4d}, {bbox[3]:4d}] | "
                          f"テキスト: '{text}...'")
                
                if len(elements) > 10:
                    print(f"... 他 {len(elements) - 10} 個の要素")
                
                # 要素タイプ別の統計
                print(f"\n=== 要素タイプ別統計 ===")
                type_counts = {}
                for element in elements:
                    class_name = element.get("class", "unknown")
                    type_counts[class_name] = type_counts.get(class_name, 0) + 1
                
                for class_name, count in sorted(type_counts.items()):
                    print(f"{class_name:12s}: {count:3d}個")
                
                # 結果をJSONファイルに保存
                output_file = "layout_analysis_result.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(response_data, f, ensure_ascii=False, indent=2)
                print(f"\n💾 結果を保存しました: {output_file}")
                
            else:
                print(f"❌ レイアウト解析失敗: {response_data.get('message', 'Unknown error')}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSONパースエラー: {e}")
            print(f"レスポンス: {result.stdout}")
            
    else:
        print(f"❌ curlエラー: {result.stderr}")
    
    # クリーンアップ
    if os.path.exists(test_image) and test_image.startswith("test_"):
        os.remove(test_image)
        print(f"🧹 テストファイルを削除: {test_image}")
    
    print("\n✅ テスト完了")

if __name__ == "__main__":
    test_inference_service()