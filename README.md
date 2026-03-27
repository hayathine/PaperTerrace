# 🌿 PaperTerrace

"テラスで読むくらい気軽に"

PaperTerraceは、論文を読むことの心理的・認知的ハードルを下げ、効率的な論文探索をサポートするAI搭載のリーディングアシスタントです。お気に入りのカフェのテラスで読書を楽しむような、リラックスした知的体験を提供します。

<div align="center">
  <a href="https://paperterrace.page">
    <img src="https://img.shields.io/website?url=https%3A%2F%2Fpaperterrace.page&label=PaperTerrace&style=for-the-badge&color=orange&logo=cloudflare&logoColor=white" alt="Website Status" />
  </a>
  <br />
  <p>AIを活用した論文・記事の読解支援プラットフォーム</p>
  
  <img src="assets/qrcode.png" width="90" alt="PaperTerrace QR Code" />
  <br />
</div>

---

## ✨ PaperTerrace でできること

### 1. 論文のアップロードと即時解析

フロントエンドからPDFをアップロードするだけで、AIが構造を解析。DSPyによる動的最適化を活かし、概要、貢献、手法、結論、キーワードを即座に抽出します。

### 2. インタラクティブ・リーディング

- **Text Mode (Default)**: 本文内の単語やフレーズを選択して、翻訳・解説・コメントをAIに依頼できます。
- **Click Mode (Object Explorer)**: 図表 (Figure) や引用 (Citation) を直接クリックして、詳細な解説をポップアップで表示。図表はライトボックスで拡大表示し、AIとの対話も可能です。
- **特定テーマの深掘り**: 関心のあるトピックに特化した詳細な要約を生成できます。

### 3. AIとの対話（チャットアシスタント）

論文全体について質問したり、特定の筆者になりきったAIと対話したりすることで、多角的な理解を深められます。

### 4. パーソナライズされた論文推薦

あなたの読書傾向や過去の質問内容に基づき、Semantic Scholar の膨大なデータベースから「次に読むべき一本」を推薦します。

---

## 🛠️ 技術スタック

### Core

- **Frontend**: React, Vite, Vanilla CSS / Tailwind CSS, **Biome** (Lint/Format)
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy (PostgreSQL/Neon), **uv** (Package Manager), **Ruff** (Lint)
- **AI/LLM**: Google Gemini (Vertex AI), Llama-3.1-8B (Home Server)
- **Infrastructure**: Google Cloud Run, Cloudflare Pages, k3s (Home Server Cluster)
- **Data Base**: PostgreSQL (App Data & Logs), Google Cloud Storage

## 📜 ライセンス

Private Project. All rights reserved.

---
