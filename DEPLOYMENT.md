# Google Cloud Deployment Guide

`deploy.sh` スクリプトを使用して、PaperTerrace アプリケーションを Google Cloud Platform (GCP) にデプロイする手順です。

## 前提条件

1.  **GCPプロジェクト**: `paperterrace` (ID)
2.  **必要なツール**: `gcloud`, `terraform`, `docker` がインストールされていること。
3.  **認証**: ローカル端末でGCPへのログインが必要です（スクリプト内でチェックされます）。

## デプロイ手順

プロジェクトのルートディレクトリで以下のコマンドを実行してください。

```bash
./deploy.sh
```

### スクリプトの動作内容

1.  **認証チェック**: `gcloud` のログイン状態を確認し、必要ならログインを促します。
2.  **Terraform State用バケット作成**: `gs://paperterrace-terraform-state` が存在しない場合は作成します。
3.  **基本インフラ構築**:
    *   APIの有効化 (Cloud Run, SQL, Artifact Registryなど)
    *   Artifact Registry リポジトリの作成
    *   ネットワーク、データベース、Secret Managerの構築
4.  **コンテナビルド & プッシュ**:
    *   Dockerイメージをビルド (`linux/amd64`)
    *   Artifact Registry (`asia-northeast1-docker.pkg.dev/...`) にプッシュ
5.  **アプリデプロイ**:
    *   Cloud Run を更新し、新しいイメージをデプロイ
6.  **完了**: サービスのURLが表示されます。

## 初回実行時の注意点

*   **API有効化**: 初回はAPIの有効化に数分かかる場合があります。
*   **DBパスワード**: `terraform/terraform.tfvars` に設定されたパスワード (`db_password`) が Secret Manager に保存され、Cloud Run から参照されます。

## トラブルシューティング

*   **認証エラー**: `gcloud auth login` および `gcloud auth application-default login` を手動で実行してみてください。
*   **Docker Pushエラー**: `gcloud auth configure-docker` が正しく実行されているか確認してください（スクリプト内で自動実行されます）。
