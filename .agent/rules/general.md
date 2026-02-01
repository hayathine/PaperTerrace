# General Project Rules

すべての開発者（AIエージェントを含む）は、タスクを開始する前にこれらのルールを確認し、遵守してください。

## 🎯 プロジェクトの目標とコンセプト

- **目標**: 論文を読むという行為を、テラスでくつろぎながら読書をするように「気軽で」「知的で」「心地よい」体験に変える。
- **ターゲット**: 論文を読むことにハードルを感じている人、または膨大な情報を効率的に整理・理解したい研究者や学生。
- **コアコンセプト**: "Intellectual & Relaxed"（知的であり、かつリラックスしている）

## 🛠 技術スタック

一貫性を保つため、以下の技術を標準として使用します。

- **Infrastructure**: Google Cloud Platform (GCP)
- **Containerization**: Docker / Cloud Run
- **Package Management**: uv (Python), npm (Frontend)
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0+
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **AI/LLM**: Gemini 2.0 Flash (Primary), Docling (PDF Processing), Surya (OCR)
- **Database**: SQLite (Local), Cloud SQL (Production / PostgreSQL)
- **Cache/Queue**: Redis, Google Cloud Tasks

## 📏 ディレクトリ構造とアーキテクチャ

クリーンアーキテクチャと機能ベースの構成を組み合わせています。

### Backend (`src/`)

- `api/v1/endpoints/`: APIエンドポイントの定義（ルーティング）。
- `domain/features/`: 機能ごとのビジネスロジック、データモデル（Pydantic）、例外クラス。
- `domain/services/`: 複数の機能で共有されるドメインサービス。
- `domain/prompts.py`: すべてのLLMプロンプトの管理場所。**プロンプトのハードコード禁止。**
- `infra/`: 外部サービス（DB, Redis, AI Provider, GCP）へのアダプター。
- `models/`: SQLAlchemyのデータベースモデル。
- `core/`: アプリケーション全体の共通設定（logger, config）。

### Frontend (`frontend/src/`)

- `components/[FeatureName]/`: 機能ごとに分割されたコンポーネント。
- `contexts/`: グローバルステート管理（Auth, Themeなど）。
- `hooks/`: カスタムフック。ロジックとViewの分離を徹底する。
- `lib/`: 外部ライブラリの設定や共通ユーティリティ。

## ⌨️ コーディング標準

### 1. 命名規則

- **Python**: `snake_case` (変数, 関数, ファイル), `PascalCase` (クラス), `UPPER_SNAKE_CASE` (定数)。
- **TypeScript**: `camelCase` (変数, 関数), `PascalCase` (コンポーネント, クラス, 型定義)。
- **Booleans**: `is_`, `has_`, `can_`, `should_` で始める。
- **説明的であること**: `data`, `item` などの曖昧な名前は避け、役割が明確な名前を付ける。

### 2. コメントとドキュメント

- **Why, not What**: 「何をしているか」ではなく「なぜそうしているか（設計意図）」を記述する。
- **言語**: 日本語を使用する。
- **Docstrings**: 公開関数やクラスには必ずGoogle形式のDocstringを記述する。
- **TODO**: `# TODO: [内容]` の形式で記述し、将来の課題を明確にする。

### 3. AI / LLM 連携

- プロンプトは必ず `src/domain/prompts.py` で定義する。
- 構造化出力（JSON）が必要な場合は、Pydanticモデル（`response_model`）を使用する。
- I/OバウンドなLLM呼び出しは必ず `async/await` を使用する。

## ✅ 開発プロセスと品質管理

### 1. ユーザーへの説明

- 実装やトラブルシューティング完了後、実施した内容を**日本語でステップバイステップで説明**する。

### 2. 視覚的確認（Frontendのみ）

- UIの新規作成や大幅な変更を行った際は、必ずスクリーンショットを撮影（ブラウザツール等を使用）し、ユーザーに提示する。
- レイアウト、色使い、余白についてユーザーのフィードバックを求め、繰り返し調整を行う。

### 3. 秘匿情報の管理

- APIキーや個人情報、認証情報（秘密鍵など）をコード内に直接記述しない。
- 必要に応じて `.env` や `.gitignore` への追加を提案する。

### 4. エラーハンドリング

- グローバルな例外ハンドラーを実装し、サーバーをクラッシュさせない。
- ユーザーには具体的で助けになるエラーメッセージ（トーストやモーダル）を表示する。
