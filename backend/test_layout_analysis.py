#!/usr/bin/env python3
"""
PP-DocLayout座標抽出テストスクリプト
test.pdfを使用してレイアウト解析の動作検証を行う
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pdfplumber
import requests
from PIL import Image, ImageDraw, ImageFont


async def convert_pdf_to_png(pdf_path: str, output_path: str) -> tuple[str, int, int]:
    """PDFの最初のページをPNG画像に変換"""
    print(f"PDFを変換中: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]  # 最初のページ
        
        # 高解像度で画像変換（レイアウト解析の精度向上のため）
        page_img = page.to_image(resolution=200, antialias=True)
        img_pil = page_img.original.convert("RGB")
        
        # PNG形式で保存
        img_pil.save(output_path, "PNG")
        
        width, height = img_pil.size
        print(f"PNG変換完了: {output_path} ({width}x{height})")
        
        return output_path, width, height


def visualize_layout_results(image_path: str, elements: list, output_path: str = "layout_visualization.png"):
    """検出結果を画像上に可視化"""
    print(f"\n=== レイアウト結果可視化 ===")
    
    try:
        # 元画像を読み込み
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # 要素タイプ別の色設定
        colors = {
            "Text": "#FF0000",        # 赤
            "Title": "#FF8C00",       # オレンジ
            "Figure": "#00FF00",      # 緑
            "Figure caption": "#32CD32",  # ライムグリーン
            "Table": "#0000FF",       # 青
            "Table caption": "#4169E1",   # ロイヤルブルー
            "Header": "#800080",      # 紫
            "Footer": "#8B008B",      # ダークマゼンタ
            "Reference": "#FF1493",   # ディープピンク
            "Equation": "#FFD700",    # ゴールド
            "unknown": "#808080"      # グレー
        }
        
        # フォント設定（システムにあるフォントを使用）
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except:
                font = ImageFont.load_default()
        
        # 各要素に枠を描画
        for i, element in enumerate(elements):
            bbox = element.get("bbox", [])
            class_name = element.get("class", "unknown")
            confidence = element.get("confidence", 0.0)
            
            if len(bbox) < 4:
                continue
                
            x1, y1, x2, y2 = bbox
            color = colors.get(class_name, colors["unknown"])
            
            # 枠を描画（太さ2px）
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
            
            # ラベルテキストを描画
            label_text = f"{class_name} ({confidence:.2f})"
            
            # テキストの背景を描画
            text_bbox = draw.textbbox((x1, y1-15), label_text, font=font)
            draw.rectangle(text_bbox, fill=color)
            
            # テキストを描画
            draw.text((x1, y1-15), label_text, fill="white", font=font)
        
        # 結果を保存
        img.save(output_path)
        print(f"✅ 可視化結果を保存: {output_path}")
        
        # 統計情報を表示
        print(f"📊 描画した要素数: {len(elements)}")
        
        # 要素タイプ別の色凡例を表示
        print(f"\n=== 色凡例 ===")
        type_counts = {}
        for element in elements:
            class_name = element.get("class", "unknown")
            type_counts[class_name] = type_counts.get(class_name, 0) + 1
        
        for class_name, count in sorted(type_counts.items()):
            color = colors.get(class_name, colors["unknown"])
            print(f"{class_name:15s}: {color} ({count}個)")
            
        return output_path
        
    except Exception as e:
        print(f"❌ 可視化エラー: {e}")
        return None


async def test_inference_service(image_path: str, pdf_path: str):
    """inference-serviceのレイアウト解析をテスト"""
    print("\n=== PP-DocLayout レイアウト解析テスト ===")
    
    # inference-serviceのURL
    base_url = "http://localhost:8082"
    
    # ヘルスチェック
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        health_data = response.json()
        print(f"Inference-service ヘルスチェック: {health_data}")
        
        if not health_data.get("services", {}).get("layout_analysis"):
            print("⚠️  レイアウト解析サービスが利用できません")
            return
            
    except Exception as e:
        print(f"❌ Inference-serviceに接続できません: {e}")
        return
    
    # レイアウト解析リクエスト
    try:
        print(f"\nレイアウト解析を実行中...")
        start_time = time.time()
        
        # リクエストデータ（直接画像ファイルを指定）
        image_path_abs = os.path.abspath(image_path)
        request_data = {
            "pdf_path": image_path_abs,  # PNG画像ファイルを直接指定
            "pages": [1]  # 最初のページのみ
        }
        
        response = requests.post(
            f"{base_url}/api/v1/layout-analysis",
            json=request_data,
            timeout=60  # レイアウト解析は時間がかかる可能性がある
        )
        
        total_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"✅ レイアウト解析成功!")
            print(f"📊 処理時間: {total_time:.3f}秒")
            print(f"🔍 検出要素数: {len(result.get('results', []))}")
            
            if result.get("success"):
                elements = result.get("results", [])
                
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
                output_file = "layout_analysis_result.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n💾 結果を保存しました: {output_file}")
                
                # 検出結果を可視化
                visualization_path = visualize_layout_results(image_path, elements)
                if visualization_path:
                    print(f"🎨 可視化画像: {visualization_path}")
                    
                    # 画像を表示（システムのデフォルトビューアで開く）
                    try:
                        import subprocess
                        subprocess.run(["xdg-open", visualization_path], check=False)
                        print(f"🖼️  画像を表示しました")
                    except Exception as e:
                        print(f"⚠️  画像表示エラー（手動で確認してください）: {e}")
                
                return elements  # 検出結果を返す
                
            else:
                print(f"❌ レイアウト解析失敗: {result.get('message', 'Unknown error')}")
                return None
                
        else:
            print(f"❌ HTTPエラー: {response.status_code}")
            print(f"レスポンス: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ レイアウト解析エラー: {e}")
        return None


async def main():
    """メイン処理"""
    print("🚀 PP-DocLayout 座標抽出テスト開始")
    
    # test_light.pdfのパスを確認
    test_pdf_paths = [
        "../frontend/public/test_light.pdf",
        "../frontend/public/test.pdf",
        "../frontend/dist/test.pdf", 
        "app/static/dist/test.pdf"
    ]
    
    pdf_path = None
    for path in test_pdf_paths:
        if os.path.exists(path):
            pdf_path = path
            break
    
    if not pdf_path:
        print("❌ test.pdfが見つかりません")
        print("検索したパス:")
        for path in test_pdf_paths:
            print(f"  - {path}")
        return
    
    print(f"📄 使用するPDF: {pdf_path}")
    
    # PNG変換
    png_path = "test_page.png"
    try:
        image_path, width, height = await convert_pdf_to_png(pdf_path, png_path)
        print(f"🖼️  変換された画像: {image_path} ({width}x{height})")
    except Exception as e:
        print(f"❌ PDF変換エラー: {e}")
        return
    
    # inference-serviceテスト
    elements = await test_inference_service(image_path, pdf_path)
    
    if elements:
        print(f"\n🎯 検出成功: {len(elements)}個の要素を検出")
    else:
        print(f"\n❌ 検出に失敗しました")
    
    print("\n✅ テスト完了")


if __name__ == "__main__":
    asyncio.run(main())