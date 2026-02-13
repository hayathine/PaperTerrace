"""
デバッグ用のテストスクリプト

PDFアップロード後のデータフローを確認する
"""

import json

# フロントエンドのコンソールログから確認すべきポイントをリストアップ
debug_checklist = {
    "1. SSEイベントの確認": {
        "場所": "ブラウザ DevTools > Network > analyze-pdf-json",
        "確認項目": [
            "EventSourceの接続が確立されているか",
            "type: 'page' のイベントが受信されているか",
            "各pageイベントのdata.wordsに要素があるか",
            "data.widthとdata.heightが0でないか",
        ],
    },
    "2. コンソールログの確認": {
        "場所": "ブラウザ DevTools > Console",
        "確認項目": [
            "[PDFViewer] Final pages collected: X",
            "[PDFViewer] Sample page structure: { words_count: X }",
            "[PDFPage 1] Rendering with data: { words_count: X }",
            "words_countが0より大きいか",
        ],
    },
    "3. Stateの確認": {
        "場所": "ブラウザ DevTools > React DevTools > Components",
        "確認項目": [
            "PDFViewer の pages 配列の中身",
            "pages[0].words の中身",
            "pages[0].width, pages[0].height の値",
        ],
    },
}

# バックエンドで確認すべきログ
backend_logs_to_check = [
    "[OCR] Page X: Phase 1 - Extraction text/links",
    "[OCR] Page X: Phase 2 - Rendering image",
    "[OCR] Page X: scale_x=..., scale_y=..., img_size=...x...",
    "[stream] task_id: ...: Starting OCR extraction",
    "[stream] task_id: ...: OCR complete. Pages processed: X",
]

print("=" * 80)
print("デバッグチェックリスト")
print("=" * 80)
print(json.dumps(debug_checklist, indent=2, ensure_ascii=False))
print("\n" + "=" * 80)
print("バックエンドログで確認すべき項目")
print("=" * 80)
for log in backend_logs_to_check:
    print(f"  - {log}")
