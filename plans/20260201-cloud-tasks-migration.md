# Cloud Tasks による重い処理の非同期化の実装計画

PDF解析プロセスにおける重いバックグラウンド処理を Google Cloud Tasks に移行し、システムの安定性とスケーラビリティを向上させます。

## 背景と目的

現在、図表の自動解説（`process_figure_auto_analysis`）や論文全体の要約（`summarize_full`）は、FastAPI の `asyncio.create_task` を利用してその場で実行されています。これには以下の課題があります：

1.  **リソース占有**: サーバープロセスが重いAI処理に長時間占有される。
2.  **エラー耐性**: 処理中にサーバーがダウンしたり、APIエラーが発生したりすると、処理が消失しリトライも行われない。
3.  **レートリミット**: 同時に多くのリクエストがあると、Gemini API 等のレート制限に抵触しやすい。

Cloud Tasks を導入することで、これらの処理をキューで管理し、自動リトライと実行レートの制御（流量制御）を実現します。

## ユーザーレビューが必要な項目

> [!CAUTION]
> この変更により、ローカル環境でフル機能をテストするには Cloud Tasks エミュレータ、あるいは GCP への接続が必要になります。開発環境（Local）では、従来通り `BackgroundTasks` にフォールバックする仕組みを設けます。

## 提案される変更

### 1. 対象となるタスク

- **図表解析 (`figure_analysis`)**: Gemini 1.5 Flash を用いた図表・数式の詳細解説生成。
- **全体要約 (`paper_summary`)**: 論文全体のテキストに基づいた構造的な要約生成。

### 2. バックエンド構成 (`src/services/cloud_tasks_service.py`)

Cloud Tasks へのタスク投入を担当するサービスを新規作成します。

- **機能**:
  - プロジェクトID、リージョン、キュー名を指定してタスクを作成。
  - 自身のワーカーエンドポイント（`/tasks/handler`）をターゲットに設定。
  - 認証用の OIDC ID トークンを付与（GCP環境用）。

### 3. ワーカーハンドラー (`src/routers/tasks.py`)

Cloud Tasks からのコールバックを受け取り、実際の処理を実行するエンドポイントを新設します。

- **Endpoint**: `POST /tasks/handler`
- **Security**: ローカル環境以外では、Google Cloud Tasks からの署名済みリクエスト（OIDC）のみを許可。
- **Payload**: タスクの種類と対象（`paper_id`, `figure_id` 等）を含む JSON。

### 4. 既存ロジックの修正 (`src/routers/pdf.py`)

`stream` ハンドラー内での後続処理呼び出しを変更します。

- **修正前**:
  ```python
  asyncio.create_task(process_figure_auto_analysis(fid, fig["image_url"]))
  ```
- **修正後**:
  ```python
  cloud_tasks_service.enqueue_figure_analysis(fid, fig["image_url"])
  # 内部で Cloud Tasks に投げる。ローカルなら BackgroundTasks にフォールバック。
  ```

### 5. インフラ (Terraform)

`terraform/` 以下の定義に Cloud Tasks キューの作成を追加します。

- `google_cloud_tasks_queue`: `paper-analysis-queue`
- `rate_limits`: 最大同時実行数（max_dispatches_per_second）の設定。

## 実装ステップ

### Step 1: 依存関係の追加

`pyproject.toml` に `google-cloud-tasks` を追加します。

### Step 2: サービス・エンドポイントの実装

`src/services/cloud_tasks_service.py` と `src/routers/tasks.py` を作成し、ローカル環境でのフォールバックロジックを含めます。

### Step 3: 既存コードの統合

`src/routers/pdf.py` で上記のサービスを利用するようにリファクタリングします。

## 検証プラン

### テスト項目

1.  **正常系**: PDFアップロード後、SSE ストリームが完了し、数分以内に DB の `abstract` や `figure_explanation` が更新されること。
2.  **エラー系**: 意図的にワーカーで例外を発生させ、Cloud Tasks 側でリトライが記録されること。
3.  **ローカル互換性**: GCP 環境でない（APIキー未設定）場合でも、従来通りバックグラウンドタスクとして動作すること。

### 手動確認

- Cloud Console の Cloud Tasks 画面で、タスクがキューイング・デリバリーされていることを確認。
