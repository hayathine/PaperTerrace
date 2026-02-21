---
name: ruff
description: Ruffを使用したPythonコードの静的解析とフォーマット
---

# Ruff Linting & Formatting Skill

## 概要

PaperTerraceでは、Pythonコードの品質維持（Linting）とコード整形（Formatting）に `ruff` を使用しています。
コミット前やプルリクエスト作成前には必ず実行し、エラーがない状態を保ってください。

## 実行コマンド

プロジェクトルートで以下のコマンドを `uv` 経由で実行します。

### 1. エラーチェック (Lint)

```bash
uv run ruff check .
```

### 2. 自動修正 (Auto Fix)

修正可能なエラー（インポート順序、未使用変数の一部など）を自動で修正します。

```bash
uv run ruff check --fix .
```

### 3. コードフォーマット (Format)

コードのスタイル（インデント、改行など）を統一します。

```bash
uv run ruff format .
```

## よくあるエラーと対処

- **E402 (Module level import not at top of file)**:
  - インポート文はファイルの最上部に記述してください。`sys.path.append` などが必要な場合でも、Ruffの設定で除外するか、構成を見直してください。
- **F401 (Module imported but unused)**:
  - 使用していないインポートは削除してください。
- **F841 (Local variable is assigned to but never used)**:
  - 使用していない変数は削除するか、プレースホルダー `_` に変更してください。

## 設定ファイル

`pyproject.toml` にRuffの設定が記述されています。ルールの除外や変更が必要な場合は、チームで相談の上、ここを修正します。
