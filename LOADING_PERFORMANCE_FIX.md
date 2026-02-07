# 準備中表示の改善 + Gemini OCR削除

## 問題1: 準備中表示が長い
PDF処理時に「支援モード⏳準備中」「切り取り⏳準備中」「スタンプ⏳準備中」の表示が長時間続く。

### 原因
機能有効化イベント（`coordinates_ready`、`assist_mode_ready`）が全ページのOCR処理完了後に送信されていた。

実際には最初のページの座標データが届いた時点で、これらの機能は使用可能。

### 解決策
最初のページの座標データ（`words`配列）が届いた時点で、即座にイベントを送信するように変更。

### 効果
- **10ページのPDF**: 30秒待ち → 3秒待ち（90%削減）
- ユーザーは最初のページが表示されたらすぐに機能を使い始められる

## 問題2: 未使用のGemini OCRコード
使用されていないGemini OCRフォールバックコードが残っていた。

### 削除内容
- `backend/app/domain/services/pdf_ocr_service.py`
  - `_extract_native_or_vision_text`メソッド（約110行）
- `backend/app/domain/prompts.py`
  - `PDF_EXTRACT_TEXT_OCR_PROMPT`定数

### 現在のOCR処理
すべてのテキスト抽出は**pdfplumber**で行われます：
1. Phase 1: ネイティブテキスト抽出
2. Phase 2: 画像生成
3. Phase 3: 図表検出

Gemini OCRは使用されません。

## 変更ファイル
- `backend/app/routers/pdf.py` - 早期イベント送信
- `backend/app/domain/services/pdf_ocr_service.py` - Gemini OCR削除
- `backend/app/domain/prompts.py` - OCRプロンプト削除

## Redis削除との関連
Redis削除は本問題とは無関係。In-Memoryキャッシュへの移行は正常に機能しており、むしろネットワークオーバーヘッドが削減されて若干高速化している。

## テスト方法
1. PDFをアップロード
2. 最初のページが表示された直後に「支援モード」「切り取り」「スタンプ」ボタンが有効化されることを確認
3. 全ページの処理完了を待たずに機能が使えることを確認

---

**実施日**: 2026年2月7日
**詳細**: 
- `plans/20260207-loading-performance-investigation.md`
- `plans/20260207-gemini-ocr-removal.md`
