---
name: python-logging
description: Pythonのロギング実装とベストプラクティス
---

# Python Logging Skill

## 概要

PaperTerraceプロジェクトにおける標準的なロギング実装ガイドです。
`print()`文の使用は原則禁止とし、必ず `src.logger` モジュールを使用してください。

## 実装ルール

### 1. ロガーのインポート

各ファイルの先頭でロガーをインポートします。

```python
from src.logger import logger
```

### 2. ログレベルの使い分け

状況に応じて適切なログレベルを選択してください。

- **DEBUG** (`logger.debug`): デバッグ情報。開発中に変数の値やフローを確認するために使用。
  - 例: `logger.debug(f"Processing item: {item.id}")`
- **INFO** (`logger.info`): 正常なイベントの記録。システムの動作状況を把握するため。
  - 例: `logger.info("Server started successfully")`
- **WARNING** (`logger.warning`): 予期しない事態だが、アプリケーションの継続は可能な場合。
  - 例: `logger.warning("Cache miss for key: user_123")`
- **ERROR** (`logger.error`): 処理の失敗、例外の発生。機能の一部が利用できない場合。
  - 例: `logger.error("Failed to upload file")`

### 3. 例外のロギング

例外が発生した場合は、スタックトレースを含めて記録します。
`exc_info=True` を付与するか、`logger.exception` を使用します。

```python
try:
    process_data()
except Exception as e:
    logger.error(f"Error processing data: {e}", exc_info=True)
    # または
    logger.exception("Error processing data")
```

### 4. 構造化ログ（推奨）

可能であれば、文字列連結よりもf-stringや引数渡しを活用して可読性を高めます。
