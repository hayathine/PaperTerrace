# PaperTerrace

[PaperTerrace](https://paperterrace-t2nx5gtwia-an.a.run.app/) (テスト版)
PaperTerraceは、「テラスで読むくらい気軽に」論文を読み、理解を深めるための知的でリラックスした読書体験を提供するAI論文リーディングアシスタントです。

最新のAI技術（Gemini）と高度なドキュメント解析（）を組み合わせ、英語論文のハードルを極限まで下げ、本質的な理解に集中できる環境を提供します。

## ✨ 特徴

### 1. インテリジェントなPDF解析 (Powered by Gemini)

単なるテキスト抽出ではありません。論文の構造を深く理解します。

- **構造化OCR**: 複雑な2段組みレイアウト、図表、数式を正確に認識し、読みやすい形式で再現します。
- **マルチモーダル認識**: 論文内の図表（Figure）や数式（Equation）を個別に抽出し、AIによる詳細な解説を提供します。
- **高速な再表示**: 解析結果はキャッシュされ、2回目以降は瞬時にアクセス可能です。

### 2. インタラクティブ・リーディング

読む行為そのものをAIがサポートします。

- **ワンクリック辞書**: 文中のあらゆる単語をクリックするだけで、文脈に応じた意味を表示。
- **AI翻訳・解説**: 難解なパラグラフを選択して、AIに背景知識を含めた解説を求めることができます。
- **ジャンプ機能**: 関連キーワードや用語の出現箇所を瞬時に横断できます。

### 3. 高度なAI読解支援

- **💬 AIチャットアシスタント**: 論文の内容に基づいたコンテキスト・アウェアな対話。著者の思考パターンを模した質問も可能です。
- **🧪 図表・数式インサイト**: 図表が示すデータの意味や、複雑な数式の導出過程をAIが言語化して説明します。
- **🧠 アドバーサリアル・レビュー**: 批判的思考を促すため、あえて論文の弱点や隠れた前提を指摘する機能です。
- **� スマート・ノート**: 読書中に浮かんだアイデアや重要な箇所をシミュレーションし、構造的に整理します。

### 4. 洗練されたUI/UX

- **Modern & Premium**: React と Tailwind CSS を使用した、美しくレスポンスの良いインターフェース。
- **集中できるデザイン**: 論文本文とAIサイドバーが調和し、情報のオーバーロードを防ぐレイアウト。

---

## 🏗️ 技術スタック

- **Backend**: FastAPI, Python 3.12+
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **AI/ML**:
  - **LLM**: Google Gemini 2.0 Flash / Pro
  - **Parsing**: Marker PDF
  - **NLP**: Spacy (en_core_web_sm)
- **Infrastructure**:
  - **Database**: SQLite (Local) / Cloud SQL (Production)
  - **Cache**: Redis
  - **Deployment**: GCP (Terraform, Docker)
- **Tooling**: uv (Python Package Manager), go-task

---

## 🚀 セットアップ

### 1. リポジトリの準備

```bash
git clone <repository-url>
cd paperterrace
```

### 2. バックエンドのセットアップ (`uv` を推奨)

```bash
# 依存関係のインストール
uv sync

# .env の設定 (後述)
cp .env.example .env
```

### 3. フロントエンドのセットアップ

```bash
cd frontend
npm install
```

### 4. 開発サーバーの起動

個別のターミナルでそれぞれ起動するか、`task` コマンドを使用します。

**Taskを使用する場合:**

```bash
# Terminal 1: Backend
task run

# Terminal 2: Frontend
task build
```

または個別に起動する場合：

- Backend: `uv run uvicorn src.main:app --reload`
- Frontend: `cd frontend && npm run dev`

---

## 📂 ディレクトリ構造

- `frontend/`: React + TypeScript (Vite) ソースコード
- `src/`: FastAPI バックエンド
  - `features/`: 各機能のビジネスロジック (Figure, Chat, etc.)
  - `routers/`: API エンドポイント
  - `services/`: 共通サービス (AI, PDF解析)
  - `providers/`: ストレージやAIプロバイダの実装
- `terraform/`: インフラ定義 (GCP)
- `docs/`: 開発ドキュメント
