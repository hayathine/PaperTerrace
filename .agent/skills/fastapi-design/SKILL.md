---
name: fastapi-design
description: FastAPIを使用したバックエンド設計パターン
---

# FastAPI Design Skill

## 概要

PaperTerraceのバックエンドはFastAPIを採用しています。
スケーラビリティと保守性を確保するための設計ルールを以下に定めます。

## アーキテクチャ構成

### 1. ルーター (Routers)

`src/routers/` 配下に機能ごとにファイルを分割し、`APIRouter` を定義します。
`main.py` にすべてのパス処理を書かないでください。

```python
# src/routers/users.py
from fastapi import APIRouter
router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def get_users():
    ...
```

### 2. 依存性の注入 (Dependency Injection)

データベースセッション、認証ユーザー、設定値などは `Depends` を使用して取得します。
グローバル変数の直接参照は避けてください。

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from src.database import get_db

@router.get("/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    ...
```

### 3. Pydanticスキーマ (Schemas)

リクエストボディとレスポンスボディの厳密な型定義を行います。
`src/schemas/` 配下に定義し、Routerの引数や `response_model` として使用します。

- **Input Schema**: 入力データのバリデーション用 (例: `UserCreate`)
- **Output Schema**: 出力データのフィルタリング用 (例: `UserResponse`)、内部IDやパスワードなどをクライアントに露出させないため。

### 4. 非同期処理 (Async/Await)

I/Oバウンドな処理（DBアクセス、外部APIコール）は必ず `async def` で定義し、`await` を使用してください。
ブロッキングな処理を書くと、サーバー全体のパフォーマンスが低下します。

## エラーハンドリング

`HTTPException` を使用して適切なステータスコード（400, 404, 500等）と詳細メッセージを返却してください。
クライアントがエラーの原因を特定できるようにします。
