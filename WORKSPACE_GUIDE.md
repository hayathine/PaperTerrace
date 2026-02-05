# UV ワークスペース管理ガイド

## プロジェクト構成

このプロジェクトはUVのワークスペース機能を使用した**マルチプロジェクト構成**です。

```
paperterrace/
├── pyproject.toml          # ルート（ワークスペース定義）
├── backend/
│   └── pyproject.toml      # バックエンドサービス
├── inference-service/
│   └── pyproject.toml      # 推論サービス
└── .venv/                  # 共有仮想環境
```

## コマンド使い分け

### 1. **ルートディレクトリから全体を管理**

```bash
# ワークスペース全体の依存関係を同期
uv sync

# 全体の依存関係をロック
uv lock

# 特定のパッケージを全体に追加
uv add package-name
```

### 2. **特定のサービスのみ管理**

```bash
# inference-serviceの依存関係を同期
uv sync -p inference-service

# backendの依存関係を同期
uv sync -p backend

# inference-serviceに新しいパッケージを追加
uv add -p inference-service package-name

# backendに新しいパッケージを追加
uv add -p backend package-name
```

### 3. **特定のディレクトリから実行**

```bash
# inference-serviceディレクトリから実行
cd inference-service
uv sync
uv run python main.py

# backendディレクトリから実行
cd backend
uv sync
uv run python app/main.py
```

## 現在の構成

### ルート (pyproject.toml)
- **目的**: ワークスペース定義と共有依存関係
- **依存関係**: FastAPI, Uvicorn, Pydantic, HTTPx など基本ライブラリ
- **ワークスペースメンバー**: backend, inference-service

### Backend (backend/pyproject.toml)
- **目的**: バックエンドサービス固有の依存関係
- **依存関係**: Firebase, Google Cloud, SQLAlchemy, Redis など
- **特徴**: ML依存関係なし（推論はinference-serviceで処理）

### Inference-Service (inference-service/pyproject.toml)
- **目的**: 推論サービス固有の依存関係
- **依存関係**: PaddleOCR, PaddleX, OpenCV, CTranslate2 など
- **特徴**: ML/推論ライブラリに特化

## 推奨される操作フロー

### 新しいパッケージを追加する場合

1. **ルートレベルの共有パッケージ**
   ```bash
   uv add package-name
   ```

2. **inference-service固有のパッケージ**
   ```bash
   uv add -p inference-service package-name
   ```

3. **backend固有のパッケージ**
   ```bash
   uv add -p backend package-name
   ```

### 依存関係を更新する場合

```bash
# 全体を更新
uv sync

# 特定のサービスのみ更新
uv sync -p inference-service
uv sync -p backend
```

### 開発環境をセットアップする場合

```bash
# ワークスペース全体をセットアップ
uv sync

# または特定のサービスのみ
uv sync -p inference-service
```

## 利点

✅ **依存関係の分離**: 各サービスが独立した依存関係を管理
✅ **共有仮想環境**: 全サービスが同じ`.venv`を使用
✅ **一元管理**: `uv.lock`で全体の依存関係を統一
✅ **スケーラビリティ**: 新しいサービスを簡単に追加可能
✅ **開発効率**: ワークスペース全体を一度にセットアップ可能

## トラブルシューティング

### 依存関係の競合が発生した場合

```bash
# ロックファイルを削除して再生成
rm uv.lock
uv sync
```

### 特定のサービスの依存関係が反映されない場合

```bash
# そのサービスのディレクトリで明示的に同期
cd inference-service
uv sync
```

### 全体の依存関係を確認したい場合

```bash
# ロックファイルを確認
cat uv.lock

# または依存関係ツリーを表示
uv pip list
```
