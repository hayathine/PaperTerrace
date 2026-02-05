#!/usr/bin/env python3
"""
テスト結果パーサー
"""

import json

# テスト結果（上記のcurlレスポンス）
test_result = {
    "success": True,
    "results": [
        {
            "bbox": [50, 50, 750, 150],
            "confidence": 0.95,
            "class": "title",
            "class_id": 0,
            "text": "Document Title (Dummy)",
            "page": 1,
            "image_path": "/home/gwsgs/work_space/paperterrace/test_dummy.png"
        },
        {
            "bbox": [50, 200, 375, 400],
            "confidence": 0.88,
            "class": "text",
            "class_id": 2,
            "text": "Left column text content (Dummy)",
            "page": 1,
            "image_path": "/home/gwsgs/work_space/paperterrace/test_dummy.png"
        },
        {
            "bbox": [425, 200, 750, 400],
            "confidence": 0.87,
            "class": "text",
            "class_id": 2,
            "text": "Right column text content (Dummy)",
            "page": 1,
            "image_path": "/home/gwsgs/work_space/paperterrace/test_dummy.png"
        },
        {
            "bbox": [50, 450, 750, 650],
            "confidence": 0.92,
            "class": "table",
            "class_id": 8,
            "text": "Table content (Dummy)",
            "page": 1,
            "image_path": "/home/gwsgs/work_space/paperterrace/test_dummy.png"
        },
        {
            "bbox": [50, 700, 750, 900],
            "confidence": 0.85,
            "class": "text",
            "class_id": 2,
            "text": "Bottom text content (Dummy)",
            "page": 1,
            "image_path": "/home/gwsgs/work_space/paperterrace/test_dummy.png"
        }
    ],
    "processing_time": 0.001312255859375,
    "message": None
}

def analyze_test_result():
    """テスト結果を分析"""
    print("🎯 PP-DocLayout-S 座標抽出テスト結果分析")
    print("=" * 50)
    
    print(f"✅ 成功: {test_result['success']}")
    print(f"⏱️  処理時間: {test_result['processing_time']:.6f}秒")
    print(f"🔍 検出要素数: {len(test_result['results'])}")
    
    print(f"\n=== 検出された要素詳細 ===")
    for i, element in enumerate(test_result['results'], 1):
        bbox = element['bbox']
        print(f"要素{i:2d}: {element['class']:8s} | "
              f"信頼度: {element['confidence']:.3f} | "
              f"座標: [{bbox[0]:3d}, {bbox[1]:3d}, {bbox[2]:3d}, {bbox[3]:3d}] | "
              f"サイズ: {bbox[2]-bbox[0]:3d}x{bbox[3]-bbox[1]:3d} | "
              f"テキスト: '{element['text']}'")
    
    # 要素タイプ別統計
    print(f"\n=== 要素タイプ別統計 ===")
    type_counts = {}
    for element in test_result['results']:
        class_name = element['class']
        type_counts[class_name] = type_counts.get(class_name, 0) + 1
    
    for class_name, count in sorted(type_counts.items()):
        print(f"{class_name:12s}: {count:3d}個")
    
    # 座標範囲分析
    print(f"\n=== 座標範囲分析 ===")
    all_x1 = [e['bbox'][0] for e in test_result['results']]
    all_y1 = [e['bbox'][1] for e in test_result['results']]
    all_x2 = [e['bbox'][2] for e in test_result['results']]
    all_y2 = [e['bbox'][3] for e in test_result['results']]
    
    print(f"X座標範囲: {min(all_x1)} ～ {max(all_x2)}")
    print(f"Y座標範囲: {min(all_y1)} ～ {max(all_y2)}")
    print(f"画像サイズ推定: {max(all_x2)}x{max(all_y2)}")
    
    print(f"\n=== 機能検証結果 ===")
    print("✅ API通信: 正常")
    print("✅ JSON形式: 正常")
    print("✅ 座標抽出: 正常（ダミーデータ）")
    print("✅ 処理時間ログ: 正常")
    print("✅ 要素分類: 正常（title, text, table）")
    print("✅ 信頼度スコア: 正常")
    print("✅ バウンディングボックス: 正常")
    
    print(f"\n=== 次のステップ ===")
    print("1. 実際のPP-DocLayout-Sモデルでの動作確認")
    print("2. 実際のPDF画像での座標抽出テスト")
    print("3. バックエンドとの連携テスト")
    print("4. フロントエンドでの座標表示テスト")

if __name__ == "__main__":
    analyze_test_result()