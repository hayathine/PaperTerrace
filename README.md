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

フロントエンドのインターフェースからお手持ちのPDF論文をアップロードするだけで、AIが即座に内容を解析します。構造化された要約（概要、貢献、手法、結論、キーワード）により、論文の核心を素早く把握できます。

### 2. インタラクティブ・リーディング

- **クリック翻訳・解説**: 英文内の単語やフレーズをクリックするだけで、その文脈に即した最適な日本語訳と背景知識を知ることができます。
- **図表の視覚的解説**: 論文内の図、表、数式を個別に解析。AIがその意図や内容を噛み砕いて説明します。
- **特定テーマの深掘り**: 関心のあるキーワードを指定して、そのトピックに特化した詳細な要約を生成できます。

### 3. AIとの対話（チャットアシスタント）

論文の内容についてAIに質問したり、特定の筆者になりきったAIと対話したりすることで、より深いレベルでの理解を助けます。

### 4. あなた専用の「次に読むべき一本」

あなたの読書傾向（どの単語を調べたか、どのような質問をしたか）をAIが学習し、世界中の膨大な論文の中から、あなたの興味と知識レベルに最適な論文を Semantic Scholar から推薦します。

---

## 🚀 はじめかた（ユーザー向け）

1.  **PDFを準備する**: 読みたい論文のPDFファイルを用意します。
2.  **アップロード**: ブラウザから PaperTerrace にアクセスし、ファイルをドロップして解析を開始します。
3.  **テラス気分で読む**: 生成された要約を確認し、気になった箇所はクリック翻訳やチャットを活用して読み進めましょう。
4.  **フィードバック**: 解析や推薦の精度について評価やコメントを残すことで、AIはあなたをより深く理解し、次回の推薦精度を向上させます。

---

## 🛠️ 技術スタック

本アプリは、最新のAI技術とクラウドインフラを融合させて構築されています。

- **AI Engine**: Google Gemini / Flash (DSPyによる動的最適化)
- **Frontend**: React + TypeScript (Vite)
- **Backend API**: FastAPI (Python)
- **Infrastructure**: Cloudflare + GCP + Home Server (k3s)

---

## 🛠️ 開発時の注意

- ドキュメントファイル（`.md`）の修正に関しては、テストやLintチェックの実行は不要です。

---

## 📜 ライセンス

Private Project. All rights reserved.

---
