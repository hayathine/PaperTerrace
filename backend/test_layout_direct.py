#!/usr/bin/env python3
"""
PP-DocLayout-S座標抽出テストスクリプト（直接ONNX実行版）
test_light.pdfを使用してレイアウト解析の動作検証を行う
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pdfplumber
from PIL import Image, ImageDraw, ImageFont

# inference-serviceのパスを追加
sys.path.append("../inference-service")

from services.layout_detection.layout_service import LayoutAnalysisService


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
            0: "#FF0000",        # Text - 赤
            1: "#FF8C00",        # Title - オレンジ
            2: "#00FF00",        # Figure - 緑
            3: "#32CD32",        # Figure caption - ライムグリーン
            4: "#0000FF",        # Table - 青
            5: "#4169E1",        # Table caption - ロイヤルブルー
            6: "#800080",        # Header - 紫
            7: "#8B008B",        # Footer - ダークマゼンタ
            8: "#FF1493",        # Reference - ディープピンク
            9: "#FFD700",        # Equation - ゴールド
        }
        
        # ラベルマップ
        labels = [
            "Text", "Title", "Figure", "Figure caption", "Table",
            "Table caption", "Header", "Footer", "Reference", "Equation"
        ]
        
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
            class_id = element.get("class_id", 0)
            score = element.get("score", 0.0)
            
            if len(bbox) < 4:
                continue
                
            x1, y1, x2, y2 = bbox
            color = colors.get(class_id, "#808080")
            class_name = labels[class_id] if class_id < len(labels) else "Unknown"
            
            # 枠を描画（太さ2px）
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
            
            # ラベルテキストを描画
            label_text = f"{class_name} ({score:.2f})"
            
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
            class_id = element.get("class_id", 0)
            class_name = labels[class_id] if class_id < len(labels) else "Unknown"
            type_counts[class_name] = type_counts.get(class_name, 0) + 1
        
        for class_name, count in sorted(type_counts.items()):
            class_id = labels.index(class_name) if class_name in labels else 0
            color = colors.get(class_id, "#808080")
            print(f"{class_name:15s}: {color} ({count}個)")
            
        return output_path
        
    except Exception as e:
        print(f"❌ 可視化エラー: {e}")
        return None


async def test_layout_analysis_direct(image_path: str):
    """直接ONNXサービスでレイアウト解析をテスト"""
    # モデルパスを確認
    model_path = "../inference-service/models/paddle2onnx/PP-DocLayout-L_infer.onnx"
    if not os.path.exists(model_path):
        print(f"❌ モデルファイルが見つかりません: {model_path}")
        return None
    
    try:
        print(f"レイアウト解析を実行中...")
        start_time = time.time()
        
        # レイアウト解析サービスを初期化
        service = LayoutAnalysisService(
            image_path=image_path,
            model_path=model_path
        )
        
        # 解析実行
        elements = service.analysis()
        
        total_time = time.time() - start_time
        
        print(f"✅ レイアウト解析成功!")
        print(f"📊 処理時間: {total_time:.3f}秒")
        print(f"🔍 検出要素数: {len(elements)}")
        
        if elements:
            # 結果の詳細表示
            print(f"\n=== 検出された要素 ===")
            labels = [
                "Text", "Title", "Figure", "Figure caption", "Table",
                "Table caption", "Header", "Footer", "Reference", "Equation"
            ]
            
            for i, element in enumerate(elements[:10]):  # 最初の10個のみ表示
                bbox = element.get("bbox", [])
                class_id = element.get("class_id", 0)
                score = element.get("score", 0.0)
                class_name = labels[class_id] if class_id < len(labels) else "Unknown"
                
                print(f"要素{i+1:2d}: {class_name:15s} | 信頼度: {score:.3f} | "
                      f"座標: [{bbox[0]:4d}, {bbox[1]:4d}, {bbox[2]:4d}, {bbox[3]:4d}]")
            
            if len(elements) > 10:
                print(f"... 他 {len(elements) - 10} 個の要素")
            
            # 要素タイプ別の統計
            print(f"\n=== 要素タイプ別統計 ===")
            type_counts = {}
            for element in elements:
                class_id = element.get("class_id", 0)
                class_name = labels[class_id] if class_id < len(labels) else "Unknown"
                type_counts[class_name] = type_counts.get(class_name, 0) + 1
            
            for class_name, count in sorted(type_counts.items()):
                print(f"{class_name:15s}: {count:3d}個")
            
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
            result_data = {
                "success": True,
                "processing_time": total_time,
                "total_elements": len(elements),
                "results": elements
            }
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
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
            
            return elements
        else:
            print("⚠️  要素が検出されませんでした")
            return []
            
    except Exception as e:
        print(f"❌ レイアウト解析エラー: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """メイン処理"""
    print("🚀 PP-DocLayout-S 座標抽出テスト開始（直接実行版 - test_heavy.pdf）")
    
    # test_heavy.pdfのパスを確認
    test_pdf_paths = [
        "../frontend/public/test_heavy.pdf",
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
        print("❌ test_heavy.pdf または test_light.pdf が見つかりません")
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
    
    # 直接レイアウト解析テスト
    elements = await test_layout_analysis_direct(image_path)
    
    if elements:
        print(f"\n🎯 検出成功: {len(elements)}個の要素を検出")
    else:
        print(f"\n❌ 検出に失敗しました")
    
    print("\n✅ テスト完了")


if __name__ == "__main__":
    asyncio.run(main())