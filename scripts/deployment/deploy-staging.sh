#!/bin/bash

# PaperTerrace Staging環境デプロイスクリプト

set -e

# 色付きログ用の関数
log_info() {
    echo -e "\033[32m[INFO]\033[0m $1"
}

log_warn() {
    echo -e "\033[33m[WARN]\033[0m $1"
}

log_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

# 設定
PROJECT_ID="gen-lang-client-0800253336"
REGION="asia-northeast1"
REPO_NAME="paperterrace"
ARTIFACT_REGISTRY_HOST="${REGION}-docker.pkg.dev"

# サービス設定
SERVICEA_NAME="paperterrace-staging"
SERVICEB_NAME="paperterrace-inference-staging"

# イメージ設定
SERVICEA_IMAGE="${ARTIFACT_REGISTRY_HOST}/${PROJECT_ID}/${REPO_NAME}/app:staging"
SERVICEB_IMAGE="${ARTIFACT_REGISTRY_HOST}/${PROJECT_ID}/${REPO_NAME}/inference:staging"

# リソース設定の取得 (JSONより)
get_config() {
    python3 -c "import json; print(json.load(open('config/resources.json'))['$1']['$2'])"
}

BE_CPU=$(get_config "backend_staging" "cpu")
BE_MEM=$(get_config "backend_staging" "memory")
INF_CPU=$(get_config "inference_staging" "cpu")
INF_MEM=$(get_config "inference_staging" "memory")

# デプロイ対象の選択
DEPLOY_TARGET=${1:-all}

# 認証確認
log_info "Checking GCloud Authentication..."
if ! gcloud auth print-access-token >/dev/null 2>&1; then
    log_error "Not authenticated. Please run: gcloud auth login"
    exit 1
fi

gcloud config set project ${PROJECT_ID}

# Docker認証
log_info "Configuring Docker authentication..."
gcloud auth configure-docker ${ARTIFACT_REGISTRY_HOST} --quiet

# ServiceA (Backend) のデプロイ
deploy_servicea() {
    log_info "🚀 Deploying ServiceA (Backend)..."
    
    # ビルド
    log_info "Building ServiceA image..."
    docker build --platform linux/amd64 -f backend/Dockerfile -t ${SERVICEA_IMAGE} .
    
    # プッシュ
    log_info "Pushing ServiceA image..."
    docker push ${SERVICEA_IMAGE}
    
    # ServiceBのURLを取得
    SERVICEB_URL=$(gcloud run services describe ${SERVICEB_NAME} --region ${REGION} --format="value(status.url)" 2>/dev/null || echo "")
    
    if [ -z "$SERVICEB_URL" ]; then
        log_warn "ServiceB URL not found. Using placeholder."
        SERVICEB_URL="https://paperterrace-inference-staging-placeholder.run.app"
    fi
    
    # デプロイ
    log_info "Deploying ServiceA to Cloud Run..."
    gcloud run deploy ${SERVICEA_NAME} \
        --image ${SERVICEA_IMAGE} \
        --region ${REGION} \
        --platform managed \
        --allow-unauthenticated \
        --memory ${BE_MEM} \
        --cpu ${BE_CPU} \
        --min-instances 0 \
        --max-instances 20 \
        --concurrency 80 \
        --timeout 300 \
        --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY:-},AI_PROVIDER=gemini,OCR_MODEL=gemini-1.5-flash,LOG_LEVEL=INFO,ACCESS_LOG_LEVEL=INFO,INFERENCE_SERVICE_URL=${SERVICEB_URL},INFERENCE_SERVICE_TIMEOUT=30,SKIP_INFERENCE_SERVICE_WARMUP=false" \
        --execution-environment gen2
    
    SERVICEA_URL=$(gcloud run services describe ${SERVICEA_NAME} --region ${REGION} --format="value(status.url)")
    log_info "✅ ServiceA deployed: ${SERVICEA_URL}"
}

# ServiceB (Inference) のデプロイ
deploy_serviceb() {
    log_info "🚀 Deploying ServiceB (Inference)..."
    
    # ビルド
    log_info "Building ServiceB image..."
    docker build --platform linux/amd64 -f inference-service/Dockerfile -t ${SERVICEB_IMAGE} .
    
    # プッシュ
    log_info "Pushing ServiceB image..."
    docker push ${SERVICEB_IMAGE}
    
    # デプロイ
    log_info "Deploying ServiceB to Cloud Run..."
    gcloud run deploy ${SERVICEB_NAME} \
        --image ${SERVICEB_IMAGE} \
        --region ${REGION} \
        --platform managed \
        --allow-unauthenticated \
        --memory ${INF_MEM} \
        --cpu ${INF_CPU} \
        --min-instances 0 \
        --max-instances 10 \
        --concurrency 10 \
        --timeout 300 \
        --set-env-vars "LOG_LEVEL=INFO,DEV_MODE=false,SKIP_MODEL_LOADING=false" \
        --execution-environment gen2
    
    SERVICEB_URL=$(gcloud run services describe ${SERVICEB_NAME} --region ${REGION} --format="value(status.url)")
    log_info "✅ ServiceB deployed: ${SERVICEB_URL}"
}

# メイン処理
main() {
    log_info "========================================"
    log_info " PaperTerrace Staging Deployment"
    log_info "========================================"
    log_info "Project: ${PROJECT_ID}"
    log_info "Region: ${REGION}"
    log_info "Target: ${DEPLOY_TARGET}"
    log_info ""
    
    case ${DEPLOY_TARGET} in
        servicea|a|backend)
            deploy_servicea
            ;;
        serviceb|b|inference)
            deploy_serviceb
            ;;
        all)
            deploy_serviceb
            log_info ""
            log_info "Waiting 10 seconds for ServiceB to be ready..."
            sleep 10
            deploy_servicea
            ;;
        *)
            log_error "Invalid target: ${DEPLOY_TARGET}"
            log_info "Usage: $0 [all|servicea|serviceb]"
            exit 1
            ;;
    esac
    
    log_info ""
    log_info "========================================"
    log_info " Deployment Complete!"
    log_info "========================================"
    
    # サービスURL表示
    SERVICEA_URL=$(gcloud run services describe ${SERVICEA_NAME} --region ${REGION} --format="value(status.url)" 2>/dev/null || echo "Not deployed")
    SERVICEB_URL=$(gcloud run services describe ${SERVICEB_NAME} --region ${REGION} --format="value(status.url)" 2>/dev/null || echo "Not deployed")
    
    log_info "ServiceA (Backend): ${SERVICEA_URL}"
    log_info "ServiceB (Inference): ${SERVICEB_URL}"
    log_info ""
    log_info "📝 Next steps:"
    log_info "1. Run: ./scripts/staging-test.sh"
    log_info "2. Check logs: ./scripts/utilities/view_staging_logs.sh"
}

# ヘルプ表示
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 [target]"
    echo ""
    echo "Targets:"
    echo "  all         Deploy both ServiceA and ServiceB (default)"
    echo "  servicea    Deploy only ServiceA (Backend)"
    echo "  serviceb    Deploy only ServiceB (Inference)"
    echo ""
    echo "Environment variables:"
    echo "  GEMINI_API_KEY    Required for ServiceA"
    exit 0
fi

# 実行
main
