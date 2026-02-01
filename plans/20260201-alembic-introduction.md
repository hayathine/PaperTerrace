# Alembic 導入計画

## 1. 目的

データベースのスキーマ管理を Alembic に移行し、ローカル開発（SQLite）および本番環境（Cloud SQL / PostgreSQL）でのスキーマ管理を統一・自動化する。
現在は `StorageProvider` 内で手動で `CREATE TABLE` や `ALTER TABLE` を行っているが、これを Alembic によるマイグレーション管理に置き換える。

## 2. 準備

以下のライブラリをプロジェクトに導入する。

- `alembic`: マイグレーションツール
- `sqlalchemy`: ORMおよびマイグレーション用のスキーマ定義
- `psycopg2-binary`: PostgreSQL(Cloud SQL) 接続用（既存）

## 3. 実施ステップ

### フェーズ 1: SQLAlchemy モデルの定義

Alembic の `autogenerate` 機能（モデルの変更を自動検知してマイグレーションファイルを生成する機能）を利用するため、既存のテーブル構造に対応する SQLAlchemy モデルを作成する。

- `src/models/orm/` ディレクトリを作成。
- 以下のモデルを定義：
  - `Base`: 共通のベースクラス
  - `User`: ユーザー情報
  - `Paper`: 論文情報
  - `Note`: メモ情報
  - `Stamp`: スタンプ（論文・メモ共通または別テーブル）
  - `Figure`: 論文内の図表情報
  - `AppSession`: セッション管理

### フェーズ 2: Alembic の初期化と設定

1. プロジェクトルートで `alembic init alembic` を実行。
2. `alembic.ini` の設定：
   - `sqlalchemy.url` は環境変数（`DATABASE_URL` など）から動的に取得できるように `env.py` で調整する。
3. `alembic/env.py` の修正：
   - `src.models.orm.base.Base.metadata` を `target_metadata` に設定。
   - 環境変数から接続文字列を取得するロジックを実装。

### フェーズ 3: 初期マイグレーション（ベースライン）の作成

1. `alembic revision --autogenerate -m "Initial schema"` を実行し、現在のモデルに基づくマイグレーションファイルを生成する。
2. **既存環境への対応**:
   - 既にテーブルが存在する開発環境や本番環境では、`alembic stamp head` を実行し、現在の状態を最新（Initial schema 適用済み）としてマークする。

### フェーズ 4: アプリケーションとの統合

1. `src/infra/storage_provider.py` および `src/infra/cloud_sql_storage.py` にある手動の `init_tables` や `_migrate_tables` ロジックを廃止。
2. `src/main.py` のライフサイクル（startup）で `alembic upgrade head` を自動実行するか、デプロイパイプライン（GCP Cloud Run 等）のステップとして追加する。

## 4. 開発時の運用フロー

1. スキーマ変更が必要な場合、`src/models/orm/` 下の SQLAlchemy モデルを修正する。
2. `alembic revision --autogenerate -m "修正内容の記述"` を実行してマイグレーションファイルを生成する。
3. 生成されたファイルをレビューし、必要に応じて手動微調整を行う（特にデータ移行が絡む場合）。
4. `alembic upgrade head` で DB に反映する。

## 5. 注意事項

- **SQLite 固有の制約**: SQLite は `ALTER TABLE` によるカラム削除や変更に制限があるため、Alembic の `render_as_batch=True` 設定を有効にする。
- **環境変数の管理**: `DATABASE_URL` は `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` 等から構築するように `env.py` を構成する。
