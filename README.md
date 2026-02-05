# PaperTerrace

[PaperTerrace](https://paperterrace-t2nx5gtwia-an.a.run.app/)(開発中)

PaperTerraceは、英語の論文やドキュメントを効率的に読むために開発されたWebベースのリーディング支援ツールです。
最新のAI技術とNLP（自然言語処理）を活用し、英語の文書を読む際の「単語の意味を調べる」という手間を極限まで減らします。

## ✨ 主な機能

PaperTerraceは、単なるPDFビューアではありません。英語学習者や研究者が快適にドキュメントを読み進めるための工夫が凝らされています。

### 1. AI OCRによる高度なPDF解析

Googleの高性能AIモデル **Gemini 1.5 Flash** を搭載しており、アップロードされたPDFを自動で解析します。

- **構造を維持したテキスト化**: 複雑なレイアウトの論文でも、段落や構造を崩さずに読みやすいテキスト形式に変換します。
- **キャッシュ機能**: 一度解析したファイルのOCR結果はデータベースに保存されるため、2回目以降は瞬時に開くことができます。

### 2. ワンクリック辞書・解説機能

テキスト内の英単語はすべてインタラクティブになっています。

- **クリックで即座に検索**: 分からない単語をクリックするだけで、その場で日本語の意味がポップアップ表示されます。

### 3. Gemini" ハイブリッド検索システム

安定的かつ高速なローカル辞書と、柔軟なAI解説を組み合わせたハイブリッドな仕組みを採用しています。

- **Gemini AI (フォールバック)**: 辞書に載っていない専門用語、スラング、固有名詞などは、AIが文脈を考慮して自動的に解説を生成します。

### 4. 高度なAI読解支援（開発中・β機能）

PaperTerraceは、単なる翻訳を超えた「理解」をサポートする以下のAI機能を搭載しています。

- **💬 AIチャットアシスタント**: 論文の内容についてチャット形式で質問できます。著者の思考をシミュレートした「著者エージェント」としても機能します。
- **📡 Research Radar (関連論文探索)**: 読んでいる論文に関連する文献を自動で調査・リコメンドし、研究の文脈を広げます。
- **📝 スマート要約**: 論文全体を要約するだけでなく、セクションごとの要点を簡潔にまとめます。
- **🔍 パラグラフ詳細解説**: 難解な段落を深く分析し、背景知識や論理展開を補足して説明します。
- **📊 図表インサイト**: 論文中のグラフや表をAIが認識し、そこから読み取れる傾向や意図を言語化して解説します。
- **🧠 アドバーサリアル・レビュー (批判的読み込み)**: あえて「批判的な視点」から論文を分析します。隠れた前提、検証されていない条件、再現性のリスクなどを指摘し、クリティカルシンキングを助けます。
- **📌 サイドバーメモ**: 解析中に気になった用語やメモをサイドバーにストックし、いつでも参照できるようにします。

### 5. モダンで快適なUI/UX

- **ストレスフリーな操作感**: FastAPI, HTMX, Tailwind CSS を採用し、ページ遷移のないスムーズな動作を実現しています。
- **レスポンシブデザイン**: PCの大画面でもタブレットでも快適に閲覧できます。

---

## 🏗️ プロジェクト構成

PaperTerraceは、uvのワークスペース機能を使用したモノレポ構成を採用しています。

### ワークスペース構造

```
paperterrace/
├── pyproject.toml          # ワークスペースルート設定
├── uv.lock                 # 統一された依存関係ロックファイル
├── backend/                # メインAPIサービス
│   ├── pyproject.toml     # バックエンド固有の設定
│   └── app/               # FastAPIアプリケーション
├── inference-service/      # 推論サービス（レイアウト解析・翻訳）
│   ├── pyproject.toml     # 推論サービス固有の設定
│   └── services/          # ML推論ロジック
└── frontend/              # React TypeScriptフロントエンド
    └── package.json       # フロントエンド依存関係
```

### 依存関係管理

- **統一管理**: ルートの`uv.lock`ですべてのPython依存関係を一元管理
- **サービス分離**: 各サービスは独自の`pyproject.toml`を持ち、必要な依存関係のみを定義
- **バージョン統一**: 共通ライブラリ（FastAPI、Pydanticなど）のバージョンを自動的に統一

## 🛠️ 前提条件

このプロジェクトを実行するには以下の環境が必要です：

- **Python 3.12** 以上
- **uv**: 高速なPythonパッケージマネージャー
- **Google Gemini API Key**: AI機能を利用するために必要です

## 🚀 インストール方法

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd PaperTerrace
```

### 2. 依存関係のインストール

`uv` を使用してプロジェクトの依存ライブラリを同期します。

```bash
uv sync
```

### 3. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の設定を記述してください。

````ini
GEMINI_API_KEY=あなたのGemini_APIキー
OCR_MODEL=gemini-1.5-flash
DB_PATH=ocr_reader.db

# 機能別AIモデル設定 (任意: 設定しない場合はデフォルトが使用されます)
# MODEL_CHAT=gemini-2.0-flash
# MODEL_SUMMARY=gemini-2.0-flash
# MODEL_DICT=gemini-2.0-flash-lite
# MODEL_TRANSLATE=gemini-1.5-flash
# MODEL_PARAGRAPH=gemini-2.0-flash

# AIプロバイダ設定 (Gemini or Vertex AI)
AI_PROVIDER=gemini
# Vertex AIを使用する場合:
# AI_PROVIDER=vertex
# GCP_PROJECT_ID=your-project-id
# GCP_LOCATION=us-central1
# VERTEX_MODEL=gemini-2.0-flash-lite-001

## 💻 使い方

### サーバーの起動

開発サーバーを起動するには、以下のコマンドを実行します。`task` コマンドが使える場合は `task run` が便利です。

**Taskを使用する場合:**

```bash
task run
````

**手動で実行する場合:**

```bash
uv run uvicorn src.main:app --reload
```

### アプリケーションへのアクセス

ブラウザで以下のURLを開いてください。
http://localhost:8000

トップページからPDFファイルをアップロードするか、テキストを入力して解析を開始できます。

## 🏗️ 技術スタック

- **Backend**: FastAPI
- **AI & NLP**: Google GenAI (Gemini), Spacy (`en_core_web_lg`),
- **Frontend**: Jinja2 Templates, HTMX, Tailwind CSS
- **Database**: SQLite (OCRキャッシュ用)
- **Tooling**: uv, go-task
