#!/usr/bin/env python3
"""
実際の画像でPP-DocLayout-Sをテストするスクリプト
"""

import json
import os
import requests
import time
from pathlib import Path


def test_with_actual_image():
    """実際のPDF画像でレイアウト解析をテスト"""
    print("🚀 実際の画像でPP-DocLayout-Sテスト開始")
    
    # 実際の画像パスを指定
    image_path = "backend/app/static/paper_images/44968521e74427ff9f06db874cd6f7012eaffc3c3e79ffcdbc66d292462c28f4/page_1.png"
    
    if not os.path.exists(image_path):
        print(f"❌ 画像ファイルが見つかりません: {image_path}")
        return
    
    print(f"📄 使用する画像: {image_path}")
    
    # inference-serviceのURL
    base_url = "http://localhost:8082"
    
    # ヘルスチェック
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        health_data = response.json()
        print(f"✅ Inference-service ヘルスチェック: {health_data}")
        
        if not health_data.get("services", {}).get("layout_analysis"):
            print("⚠️  レイアウト解析サービスが利用できません")
            return
            
    except Exception as e:
        print(f"❌ Inference-serviceに接続できません: {e}")
        return
    
    # レイアウト解析リクエスト
    try:
        print(f"\n🔍 レイアウト解析を実行中...")
        start_time = time.time()
        
        # 絶対パスを取得
        image_path_abs = os.path.abspath(image_path)
        request_data = {
            "pdf_path": image_path_abs,
            "pages": [1]
        }
        
        response = requests.post(
            f"{base_url}/api/v1/layout-analysis",
            json=request_data,
            timeout=120  # 実際の推論は時間がかかる可能性がある
        )
        
        total_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"✅ レイアウト解析成功!")
            print(f"📊 総処理時間: {total_time:.3f}秒")
            print(f"🔍 検出要素数: {len(result.get('results', []))}")
            print(f"⚡ サービス内処理時間: {result.get('processing_time', 0):.3f}秒")
            
            if result.get("success"):
                elements = result.get("results", [])
                
                # 結果の詳細表示
                print(f"\n=== 検出された要素（最初の10個） ===")
                for i, element in enumerate(elements[:10]):
                    bbox = element.get("bbox", [])
                    class_name = element.get("class", "unknown")
                    confidence = element.get("confidence", 0.0)
                    text = element.get("text", "")[:50]
                    
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
                
                # 座標の範囲チェック
                print(f"\n=== 座標範囲チェック ===")
                if elements:
                    all_x1 = [e["bbox"][0] for e in elements if len(e.get("bbox", [])) >= 4]
                    all_y1 = [e["bbox"][1] for e in elements if len(e.get("bbox", [])) >= 4]
                    all_x2 = [e["bbox"][2] for e in elements if len(e.get("bbox", [])) >= 4]
                    all_y2 = [e["bbox"][3] for e in elements if len(e.get("bbox", [])) >= 4]
                    
                    if all_x1 and all_y1 and all_x2 and all_y2:
                        print(f"X座標範囲: {min(all_x1)} ～ {max(all_x2)}")
                        print(f"Y座標範囲: {min(all_y1)} ～ {max(all_y2)}")
                
                # 結果をJSONファイルに保存
                output_file = "actual_image_layout_result.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n💾 結果を保存しました: {output_file}")
                
            else:
                print(f"❌ レイアウト解析失敗: {result.get('message', 'Unknown error')}")
                
        else:
            print(f"❌ HTTPエラー: {response.status_code}")
            print(f"レスポンス: {response.text}")
            
    except Exception as e:
        print(f"❌ レイアウト解析エラー: {e}")


if __name__ == "__main__":
    test_with_actual_image()