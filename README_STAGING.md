# PaperTerrace Staging環境 クイックスタート

## 🚀 Staging環境でのマイクロサービステスト

### 前提条件
- Task CLI インストール済み
- gcloud CLI 認証済み
- Docker 起動済み

### 1. モデル準備（初回のみ）
```bash
# モデル変換
python -m src.scripts.convert_paddle_layout
python -m src.scripts.convert_m2m100

# ServiceBにコピー
cp -r models/ inference-service/
```

### 2. Staging環境デプロイ
```bash
# 両方のサービスを一括デプロイ
task staging:deploy:microservices
```

### 3. 動作確認
```bash
# 包括的テスト実行
task staging:test:all

# 負荷テスト付き
task staging:test:load
```

### 4. 個別テスト
```bash
# ヘルスチェック
task staging:health

# 翻訳機能テスト
task staging:test:translation

# レイアウト解析テスト
task staging:test:layout
```

### 5. ログ監視
```bash
# ServiceAログ
task staging:logs:servicea

# ServiceBログ
task staging:logs:serviceb

# リアルタイムログ
task staging:logs:tail:serviceb
```

### 6. クリーンアップ
```bash
# Staging環境停止
task staging:stop:microservices
```

## 📊 期待される結果

### パフォーマンス指標
- **翻訳レスポンス**: 2秒以下
- **レイアウト解析**: 10秒以下（実際のPDFの場合）
- **ヘルスチェック**: 1秒以下

### リソース使用量
- **ServiceA**: CPU 20-50%, Memory 50-70%
- **ServiceB**: CPU 30-70%, Memory 60-80%

## 🔧 トラブルシューティング

### よくある問題と解決方法

#### ServiceBが起動しない
```bash
# ログ確認
task staging:logs:serviceb

# 再デプロイ
task staging:serviceb:deploy
```

#### 翻訳が動作しない
```bash
# モデルファイル確認
ls -la inference-service/models/

# 再コピー・再デプロイ
cp -r models/ inference-service/
task staging:serviceb:deploy
```

#### ServiceA → ServiceB 通信エラー
```bash
# 環境変数確認
gcloud run services describe paperterrace-main-staging --region asia-northeast1 --format="value(spec.template.spec.template.spec.containers[0].env)"

# ServiceB URL確認
task staging:urls
```

## 📈 本番環境への移行

Staging環境でのテストが成功したら：

```bash
# 本番環境デプロイ
cd inference-service && ./deploy.sh
cd .. && ./deploy-servicea.sh
```

---

**注意**: Staging環境は開発・テスト用です。本番データは使用しないでください。