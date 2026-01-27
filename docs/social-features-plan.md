# PaperTerrace ソーシャル機能 実装計画

## 📋 概要

PaperTerraceを個人研究者向けの論文共有プラットフォームに拡張します。

### ターゲットユーザー
- 個人研究者（大学院生、ポスドク、教員）
- 独立研究者
- 論文を読む趣味を持つ技術者

### コンセプト
- **コミュニティ主導**: 無料、広告なし
- **オープン**: 誰でも参加可能
- **学術**: 論文を中心としたコミュニケーション

---

## 🎯 フェーズ 1: 認証 & 論文共有（今回実装）

### 1.1 Firebase Authentication
- Google ログイン
- GitHub ログイン
- メール/パスワード ログイン

### 1.2 ユーザープロフィール
- 表示名、所属、自己紹介
- 研究分野タグ
- プロフィール画像（Firebase Storage）

### 1.3 論文の公開/共有
- 公開設定: private / public / unlisted
- 公開論文の一覧表示
- 論文の検索

---

## 📐 データベース設計

### users テーブル
```sql
CREATE TABLE users (
    id VARCHAR(128) PRIMARY KEY,  -- Firebase UID
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    affiliation VARCHAR(200),     -- 所属機関
    bio TEXT,                      -- 自己紹介 (500文字以内)
    research_fields TEXT[],        -- 研究分野タグ
    profile_image_url TEXT,
    is_public BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### papers テーブル（拡張）
```sql
ALTER TABLE papers ADD COLUMN owner_id VARCHAR(128) REFERENCES users(id);
ALTER TABLE papers ADD COLUMN visibility VARCHAR(20) DEFAULT 'private';
-- visibility: 'private' | 'public' | 'unlisted'
ALTER TABLE papers ADD COLUMN view_count INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN like_count INTEGER DEFAULT 0;
```

### paper_likes テーブル
```sql
CREATE TABLE paper_likes (
    user_id VARCHAR(128) REFERENCES users(id),
    paper_id VARCHAR(36) REFERENCES papers(id),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, paper_id)
);
```

---

## 🔧 技術スタック

### 認証
- **Firebase Authentication**: Google/GitHub/Email認証
- **Firebase Admin SDK**: サーバーサイドでのトークン検証

### フロントエンド
- 現在のバニラJS + Firebase JS SDK
- 将来的にReact/Vue移行も可能

### バックエンド
- FastAPI + Firebase Admin SDK
- JWTトークン検証ミドルウェア

---

## 📁 ファイル構成

```
src/
├── auth/
│   ├── __init__.py
│   ├── firebase.py         # Firebase Admin SDK 初期化
│   ├── middleware.py       # 認証ミドルウェア
│   └── dependencies.py     # FastAPI 認証依存関係
├── models/
│   ├── user.py             # Userモデル
│   └── paper.py            # Paper モデル（拡張）
├── routers/
│   ├── auth.py             # 認証関連エンドポイント
│   ├── users.py            # ユーザー管理
│   └── papers.py           # 論文CRUD（認証対応）
└── templates/
    ├── index.html          # メインページ（認証UI追加）
    ├── profile.html        # プロフィールページ
    ├── explore.html        # 公開論文一覧
    └── paper.html          # 論文詳細ページ
```

---

## 🚀 実装ステップ

### Step 1: Firebase プロジェクト設定
- [ ] Firebase コンソールでプロジェクト作成
- [ ] Authentication を有効化
- [ ] Google/GitHub プロバイダーを設定
- [ ] Firebase Admin SDK キーをダウンロード

### Step 2: バックエンド認証
- [ ] Firebase Admin SDK インストール
- [ ] トークン検証ミドルウェア
- [ ] ユーザー登録/取得API

### Step 3: データベース拡張
- [ ] users テーブル作成
- [ ] papers テーブルに owner_id, visibility 追加
- [ ] マイグレーションスクリプト

### Step 4: フロントエンド認証
- [ ] Firebase JS SDK 導入
- [ ] ログインUI（Google/GitHub/Email）
- [ ] 認証状態管理

### Step 5: 論文共有機能
- [ ] 論文の公開設定UI
- [ ] 公開論文一覧ページ
- [ ] 論文検索機能

---

## 🔐 セキュリティ考慮事項

1. **トークン検証**: すべてのAPI呼び出しでFirebaseトークンを検証
2. **アクセス制御**: 論文のowner_idとリクエストユーザーを照合
3. **レート制限**: API呼び出し頻度の制限
4. **入力検証**: ユーザー入力のサニタイズ

---

## 📊 API設計

### 認証
```
POST /auth/register          # ユーザー登録（Firebase UID紐付け）
GET  /auth/me                # 現在のユーザー情報取得
PUT  /auth/me                # プロフィール更新
```

### ユーザー
```
GET  /users/{user_id}        # 公開プロフィール取得
GET  /users/{user_id}/papers # ユーザーの公開論文一覧
```

### 論文
```
POST   /papers               # 論文アップロード（要認証）
GET    /papers/{id}          # 論文詳細（公開 or 所有者のみ）
PUT    /papers/{id}          # 論文更新（所有者のみ）
DELETE /papers/{id}          # 論文削除（所有者のみ）
PATCH  /papers/{id}/visibility # 公開設定変更

GET    /explore              # 公開論文一覧
GET    /explore/search       # 論文検索
```

---

## 🎨 UI/UX設計

### ヘッダー（認証後）
```
┌─────────────────────────────────────────────────────────┐
│ 🏛️ PaperTerrace    [Explore] [My Library]    [👤 User ▼]│
└─────────────────────────────────────────────────────────┘
```

### 論文カード
```
┌─────────────────────────────────────────────────────────┐
│ 📄 Deep Learning for NLP: A Survey                     │
│ by @tanaka_ai • 2時間前                                │
│                                                         │
│ 自然言語処理における深層学習の包括的なサーベイ...        │
│                                                         │
│ 🏷️ NLP  機械学習  深層学習                              │
│ ❤️ 42  💬 5  👁️ 234                                     │
└─────────────────────────────────────────────────────────┘
```

---

## 📅 スケジュール目安

| Week | タスク |
|------|--------|
| 1 | Firebase設定、認証API実装 |
| 2 | フロントエンド認証UI、プロフィール |
| 3 | 論文共有機能、公開設定 |
| 4 | Explore ページ、検索機能 |
| 5 | テスト、バグ修正、デプロイ |
