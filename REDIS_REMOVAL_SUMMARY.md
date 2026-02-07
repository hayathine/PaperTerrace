# Redis削除の概要

## 変更内容

PaperTerraceからRedis依存を削除し、In-Memoryキャッシュに移行しました。

## 変更理由

- **コスト削減**: Google Cloud Memorystoreの月額コスト（$180-225）を削減
- **シンプル化**: 小規模アプリケーションではRedisのオーバーヘッドが不要
- **既存実装活用**: RedisProviderには既にメモリフォールバック機能が実装済み

## 変更ファイル

### コア実装
- `backend/app/providers/redis_provider.py` - Redis接続を削除、In-Memoryキャッシュのみに変更
- `backend/pyproject.toml` - redis依存パッケージを削除
- `backend/app/main.py` - health_checkエンドポイントを簡素化

### 設定ファイル
- `configs/.env.example` - Redis設定を削除、In-Memoryキャッシュの説明を追加

### ドキュメント
- `.kiro/setting/project_overview.md` - Redis記述を削除
- `.kiro/setting/general.md` - キャッシュをIn-Memoryに変更
- `.kiro/setting/system_architecture.md` - Redis CacheをIn-memory cacheに変更
- `plans/20260207-redis-removal.md` - 詳細な変更計画書を作成

### コメント追加
- `backend/app/routers/analysis.py`
- `backend/app/routers/chat.py`
- `backend/app/routers/pdf.py`
- `backend/app/domain/features/chat/chat.py`

## In-Memoryキャッシュの特性

### 利点
- コスト削減（外部サービス不要）
- シンプルな実装
- 高速（ネットワークオーバーヘッドなし）

### 制約
- サーバー再起動でキャッシュクリア
- 複数インスタンス間でキャッシュ共有不可
- メモリ制限内で動作

### 影響を受ける機能
以下のデータはサーバー再起動時にリセットされます：
- チャット履歴
- セッションコンテキスト
- 翻訳キャッシュ
- タスクデータ

**重要**: 永続化が必要なデータ（論文、ノート、ユーザー情報）はすべてDBに保存されているため、データ損失はありません。

## 次のステップ

### 必須
1. アプリケーションの動作確認
2. パフォーマンステスト
3. メモリ使用量の監視

### オプション（後日）
- Terraform Memorystoreモジュールの削除
- インフラドキュメントの更新

## ロールバック方法

必要に応じて以下の手順でRedisを再導入できます：
1. `backend/pyproject.toml`に`redis>=7.1.0`を追加
2. `backend/app/providers/redis_provider.py`を元のRedis接続コードに戻す
3. 環境変数`REDIS_HOST`、`REDIS_PORT`を設定

---

**実施日**: 2026年2月7日
