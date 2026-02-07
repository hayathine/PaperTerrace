# PaperTerrace Staging環境 デプロイガイド

## 概要

Staging環境でマイクロサービス分離構成をテストするためのガイドです。

## 前提条件

1. Google Cloud Platform アカウント
2. gcloud CLI インストール・認証済み
3. Docker インストール済み
4. Task CLI インストール済み（`go install github.com/go-task/task/v3/cmd/task@latest`）

## クイックスタート

### 1. モデルファイルの準備

```bash
# モデル変換（初回のみ）
python -m src.scripts.convert_paddle_layout
python -m src.scripts.convert_m2m100

# ServiceBにモデルをコピー
cp -r models/ inference-service/
```

### 2. Staging環境デプロイ

```bash
# 両方のサービスを一括デプロイ
task staging:deploy:microservices
```

### 3. 動作確認

```bash
# ヘルスチェック
task staging:health

# サービスURLの確認
task staging:urls

# 翻訳機能のテスト
task staging:test:translation

# レイアウト解析機能のテスト
task staging:test:layout
```

## 詳細なタスク

### デプロイ関連

| タスク                              | 説明                                   |
| ----------------------------------- | -------------------------------------- |
| `task staging:serviceb:deploy`      | ServiceB（推論サービス）のみデプロイ   |
| `task staging:servicea:deploy`      | ServiceA（メインサービス）のみデプロイ |
| `task staging:deploy:microservices` | 両方のサービスを一括デプロイ           |

### 監視・ログ

| タスク                            | 説明                             |
| --------------------------------- | -------------------------------- |
| `task staging:logs:servicea`      | ServiceAのログを表示             |
| `task staging:logs:serviceb`      | ServiceBのログを表示             |
| `task staging:logs:tail:servicea` | ServiceAのログをリアルタイム表示 |
| `task staging:logs:tail:serviceb` | ServiceBのログをリアルタイム表示 |

### テスト

| タスク                          | 説明                           |
| ------------------------------- | ------------------------------ |
| `task staging:health`           | 両方のサービスのヘルスチェック |
| `task staging:test:translation` | 翻訳機能のテスト               |
| `task staging:test:layout`      | レイアウト解析機能のテスト     |

### 管理

| タスク                            | 説明                 |
| --------------------------------- | -------------------- |
| `task staging:urls`               | サービスURLの表示    |
| `task staging:stop:microservices` | 両方のサービスを停止 |

## Staging環境の設定

### ServiceA（メインサービス）

- **CPU**: 2 vCPU
- **メモリ**: 1GB
- **min-instances**: 0（コスト最適化）
- **max-instances**: 10
- **concurrency**: 80

### ServiceB（推論サービス）

- **CPU**: 4 vCPU
- **メモリ**: 4GB
- **min-instances**: 1（常時待機）
- **max-instances**: 5（staging用に制限）
- **concurrency**: 10

## テストシナリオ

### 1. 基本動作確認

```bash
# 1. デプロイ
task staging:deploy:microservices

# 2. ヘルスチェック
task staging:health

# 3. サービス間通信確認
task staging:test:translation
```

### 2. 負荷テスト

```bash
# ServiceBの翻訳エンドポイントに負荷をかける
SERVICEB_URL=$(gcloud run services describe paperterrace-inference-staging --region asia-northeast1 --format="value(status.url)")

# 10並列で100リクエスト
seq 1 100 | xargs -n1 -P10 -I{} curl -X POST "$SERVICEB_URL/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world {}", "target_lang": "ja"}'
```

### 3. 障害テスト

```bash
# ServiceBを一時停止してServiceAのフォールバック動作を確認
gcloud run services update paperterrace-inference-staging --region asia-northeast1 --min-instances 0 --max-instances 0

# ServiceAのログでフォールバック動作を確認
task staging:logs:tail:servicea

# ServiceBを復旧
gcloud run services update paperterrace-inference-staging --region asia-northeast1 --min-instances 1 --max-instances 5
```

## トラブルシューティング

### よくある問題

#### 1. ServiceBが起動しない

```bash
# ログ確認
task staging:logs:serviceb

# よくある原因：
# - モデルファイルが見つからない
# - メモリ不足
# - 環境変数の設定ミス
```

#### 2. ServiceA → ServiceB 通信エラー

```bash
# ServiceBのURLが正しく設定されているか確認
gcloud run services describe paperterrace-main-staging --region asia-northeast1 --format="value(spec.template.spec.template.spec.containers[0].env)"

# ServiceBのヘルスチェック
SERVICEB_URL=$(gcloud run services describe paperterrace-inference-staging --region asia-northeast1 --format="value(status.url)")
curl "$SERVICEB_URL/health"
```

#### 3. モデルファイルの問題

```bash
# inference-serviceディレクトリにモデルがあるか確認
ls -la inference-service/models/

# 必要に応じて再コピー
cp -r models/ inference-service/
task staging:serviceb:deploy
```

## パフォーマンス監視

### Cloud Monitoringでの確認項目

1. **CPU使用率**
   - ServiceA: 50%以下が理想
   - ServiceB: 70%以下が理想

2. **メモリ使用率**
   - ServiceA: 70%以下が理想
   - ServiceB: 80%以下が理想

3. **レスポンス時間**
   - 翻訳: 2秒以下
   - レイアウト解析: 10秒以下

4. **エラー率**
   - 全体: 1%以下

### ログ分析

```bash
# エラーログの確認
gcloud logging read 'resource.type="cloud_run_revision" AND (resource.labels.service_name="paperterrace-main-staging" OR resource.labels.service_name="paperterrace-inference-staging") AND severity>=ERROR' --limit=20

# 処理時間の分析
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="paperterrace-inference-staging" AND jsonPayload.processing_time>5' --limit=10
```

## 本番環境への移行

Staging環境でのテストが完了したら、以下の手順で本番環境にデプロイ：

```bash
# 本番用のデプロイスクリプトを実行
cd inference-service && ./deploy.sh
cd .. && ./deploy-servicea.sh
```

## クリーンアップ

```bash
# Staging環境の停止
task staging:stop:microservices

# イメージの削除（必要に応じて）
gcloud artifacts docker images delete asia-northeast1-docker.pkg.dev/gen-lang-client-0800253336/paperterrace/inference:staging --quiet
gcloud artifacts docker images delete asia-northeast1-docker.pkg.dev/gen-lang-client-0800253336/paperterrace/main:staging --quiet
```

---

このStaging環境で十分にテストを行い、問題がないことを確認してから本番環境にデプロイしてください。
