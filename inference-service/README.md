# ServiceB（推論サービス）

PaperTerraceの推論処理専用サービスです。レイアウト解析と翻訳処理を担当します。

## 概要

- **レイアウト解析**: ONNX Runtime + Paddle-layout-m
- **翻訳処理**: CTranslate2 + M2M100
- **構成**: FastAPI + Cloud Run
- **特徴**: min-instances=1で常時待機、コールドスタート問題を解決

## 必要なファイル

デプロイ前に以下のモデルファイルを準備してください：

```
models/
├── layout_m.onnx                    # レイアウト解析モデル
└── m2m100_ct2/                      # 翻訳モデル
    ├── config.json
    ├── model.bin
    ├── sentencepiece.bpe.model
    └── shared_vocabulary.json
```

## ローカル開発

### 1. 環境設定

```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .envファイルを編集
```

### 2. モデル準備

```bash
# メインプロジェクトのスクリプトを使用
cd ..
python -m src.scripts.convert_paddle_layout
python -m src.scripts.convert_m2m100

# モデルをServiceBにコピー
cp -r models/ inference-service/
```

### 3. 起動

```bash
python main.py
```

サービスは http://localhost:8080 で起動します。

## Cloud Runデプロイ

### 1. 自動デプロイ

```bash
# デプロイスクリプト実行
./deploy.sh
```

### 2. 手動デプロイ

```bash
# プロジェクト設定
export GCP_PROJECT="your-project-id"
export GCP_REGION="asia-northeast1"

# Docker イメージビルド
docker build -t gcr.io/${GCP_PROJECT}/paperterrace-inference:latest .

# イメージプッシュ
docker push gcr.io/${GCP_PROJECT}/paperterrace-inference:latest

# Cloud Run デプロイ
gcloud run deploy paperterrace-inference \
  --image gcr.io/${GCP_PROJECT}/paperterrace-inference:latest \
  --region ${GCP_REGION} \
  --platform managed \
  --allow-unauthenticated \
  --memory 8Gi \
  --cpu 4 \
  --min-instances 1 \
  --max-instances 10 \
  --concurrency 10 \
  --no-cpu-throttling \
  --timeout 300
```

## API仕様

### レイアウト解析

```bash
POST /api/v1/layout-analysis
Content-Type: application/json

{
  "pdf_path": "path/to/pdf",
  "pages": [1, 2, 3]  // optional
}
```

### 翻訳

```bash
POST /api/v1/translate
Content-Type: application/json

{
  "text": "Hello world",
  "source_lang": "en",
  "target_lang": "ja"
}
```

### バッチ翻訳

```bash
POST /api/v1/translate-batch
Content-Type: application/json

{
  "texts": ["Hello", "world"],
  "source_lang": "en",
  "target_lang": "ja"
}
```

### ヘルスチェック

```bash
GET /health
```

## 監視・ログ

- **ログ**: Cloud Logging で確認
- **メトリクス**: Cloud Monitoring で監視
- **アラート**: CPU使用率90%、メモリ使用率80%、エラー率5%で設定

## トラブルシューティング

### よくある問題

1. **モデルファイルが見つからない**
   - `models/` ディレクトリにファイルが存在するか確認
   - パスが正しく設定されているか確認

2. **メモリ不足**
   - Cloud Runのメモリ設定を8Gi以上に設定
   - 同時処理数（concurrency）を調整

3. **タイムアウト**
   - Cloud Runのタイムアウトを300秒に設定
   - 大きなPDFの場合は処理時間が長くなる可能性

### ログ確認

```bash
# Cloud Runログ確認
gcloud logs read --service=paperterrace-inference --limit=50

# リアルタイムログ
gcloud logs tail --service=paperterrace-inference
```

## パフォーマンス最適化

- **CPU**: 4vCPU推奨（ONNX Runtime + CTranslate2最適化）
- **メモリ**: 8GB推奨（モデルロード + 推論バッファ）
- **同時処理**: 10リクエスト/インスタンス
- **スケーリング**: 1-10インスタンス（負荷に応じて自動調整）