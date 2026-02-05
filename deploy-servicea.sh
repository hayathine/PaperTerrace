#!/bin/bash

# ServiceA（メインサービス）デプロイスクリプト

set -e

# 設定
PROJECT_ID=${GCP_PROJECT:-"your-project-id"}
REGION=${GCP_REGION:-"asia-northeast1"}
SERVICE_NAME="paperterrace-main"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 ServiceA（メインサービス）をデプロイ中..."
echo "プロジェクト: ${PROJECT_ID}"
echo "リージョン: ${REGION}"
echo "サービス名: ${SERVICE_NAME}"

# Docker イメージのビルド
echo "📦 Docker イメージをビルド中..."
docker build -t ${IMAGE_NAME}:latest .

# Docker イメージのプッシュ
echo "📤 Docker イメージをプッシュ中..."
docker push ${IMAGE_NAME}:latest

# Cloud Run へのデプロイ（軽量構成）
echo "🌐 Cloud Run にデプロイ中..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 20 \
  --concurrency 80 \
  --no-cpu-throttling \
  --set-env-vars "INFERENCE_SERVICE_URL=https://paperterrace-inference-xxx.run.app,INFERENCE_SERVICE_TIMEOUT=30,INFERENCE_SERVICE_RETRIES=3" \
  --timeout 300 \
  --execution-environment gen2

# デプロイ完了
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo "✅ デプロイ完了!"
echo "サービスURL: ${SERVICE_URL}"
echo ""
echo "📝 次のステップ:"
echo "1. ServiceBがデプロイ済みであることを確認してください"
echo "2. 環境変数 INFERENCE_SERVICE_URL を正しいServiceBのURLに設定してください"
echo "3. 動作確認を行ってください"