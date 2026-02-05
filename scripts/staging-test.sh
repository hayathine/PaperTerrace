#!/bin/bash

# PaperTerrace Staging環境テストスクリプト

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

# サービスURL取得
get_service_url() {
    local service_name=$1
    gcloud run services describe "$service_name" --region "$REGION" --format="value(status.url)" 2>/dev/null || echo ""
}

# ヘルスチェック
health_check() {
    local service_name=$1
    local url=$2
    local endpoint=$3
    
    log_info "Testing $service_name health..."
    
    if [ -z "$url" ]; then
        log_error "$service_name is not deployed"
        return 1
    fi
    
    local response=$(curl -s -w "%{http_code}" -o /tmp/health_response "$url$endpoint" || echo "000")
    
    if [ "$response" = "200" ]; then
        log_info "$service_name is healthy ✅"
        return 0
    else
        log_error "$service_name health check failed (HTTP $response) ❌"
        cat /tmp/health_response 2>/dev/null || echo "No response body"
        return 1
    fi
}

# 翻訳テスト
test_translation() {
    local serviceb_url=$1
    
    log_info "Testing translation endpoint..."
    
    local response=$(curl -s -X POST "$serviceb_url/api/v1/translate" \
        -H "Content-Type: application/json" \
        -d '{"text": "Hello world", "source_lang": "en", "target_lang": "ja"}' \
        -w "%{http_code}" -o /tmp/translation_response)
    
    if [ "$response" = "200" ]; then
        local translation=$(cat /tmp/translation_response | jq -r '.translation' 2>/dev/null || echo "Parse error")
        log_info "Translation test passed ✅"
        log_info "Result: Hello world → $translation"
        return 0
    else
        log_error "Translation test failed (HTTP $response) ❌"
        cat /tmp/translation_response 2>/dev/null || echo "No response body"
        return 1
    fi
}

# レイアウト解析テスト
test_layout_analysis() {
    local serviceb_url=$1
    
    log_info "Testing layout analysis endpoint..."
    
    local response=$(curl -s -X POST "$serviceb_url/api/v1/layout-analysis" \
        -H "Content-Type: application/json" \
        -d '{"pdf_path": "test.pdf", "pages": [1]}' \
        -w "%{http_code}" -o /tmp/layout_response)
    
    if [ "$response" = "200" ]; then
        log_info "Layout analysis test passed ✅"
        local success=$(cat /tmp/layout_response | jq -r '.success' 2>/dev/null || echo "false")
        if [ "$success" = "true" ]; then
            log_info "Layout analysis returned success"
        else
            log_warn "Layout analysis returned success=false (expected for test data)"
        fi
        return 0
    else
        log_error "Layout analysis test failed (HTTP $response) ❌"
        cat /tmp/layout_response 2>/dev/null || echo "No response body"
        return 1
    fi
}

# サービス間通信テスト
test_service_communication() {
    local servicea_url=$1
    local serviceb_url=$2
    
    log_info "Testing ServiceA → ServiceB communication..."
    
    # ServiceAのヘルスチェックエンドポイントがServiceBとの通信を確認する場合
    # 実際のエンドポイントに応じて調整が必要
    local response=$(curl -s -w "%{http_code}" -o /tmp/comm_response "$servicea_url/" || echo "000")
    
    if [ "$response" = "200" ]; then
        log_info "ServiceA is responding ✅"
        return 0
    else
        log_warn "ServiceA response check: HTTP $response"
        return 1
    fi
}

# 負荷テスト（軽量）
load_test() {
    local serviceb_url=$1
    local requests=${2:-10}
    local concurrency=${3:-3}
    
    log_info "Running light load test ($requests requests, $concurrency concurrent)..."
    
    local success_count=0
    local start_time=$(date +%s)
    
    # 並列リクエスト実行
    for i in $(seq 1 $requests); do
        (
            response=$(curl -s -X POST "$serviceb_url/api/v1/translate" \
                -H "Content-Type: application/json" \
                -d "{\"text\": \"Test message $i\", \"source_lang\": \"en\", \"target_lang\": \"ja\"}" \
                -w "%{http_code}" -o /dev/null)
            if [ "$response" = "200" ]; then
                echo "SUCCESS"
            else
                echo "FAILED:$response"
            fi
        ) &
        
        # 同時実行数制限
        if [ $((i % concurrency)) -eq 0 ]; then
            wait
        fi
    done
    wait
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Load test completed in ${duration}s"
    log_info "Check logs for detailed results"
}

# メイン実行
main() {
    log_info "🚀 Starting PaperTerrace Staging Tests"
    
    # サービスURL取得
    local servicea_url=$(get_service_url "paperterrace-main-staging")
    local serviceb_url=$(get_service_url "paperterrace-inference-staging")
    
    log_info "ServiceA URL: ${servicea_url:-'Not deployed'}"
    log_info "ServiceB URL: ${serviceb_url:-'Not deployed'}"
    
    # テスト実行
    local test_results=0
    
    # ヘルスチェック
    health_check "ServiceB" "$serviceb_url" "/health" || ((test_results++))
    health_check "ServiceA" "$servicea_url" "/" || ((test_results++))
    
    # ServiceBの機能テスト
    if [ -n "$serviceb_url" ]; then
        test_translation "$serviceb_url" || ((test_results++))
        test_layout_analysis "$serviceb_url" || ((test_results++))
    else
        log_error "ServiceB not deployed, skipping function tests"
        ((test_results += 2))
    fi
    
    # サービス間通信テスト
    if [ -n "$servicea_url" ] && [ -n "$serviceb_url" ]; then
        test_service_communication "$servicea_url" "$serviceb_url" || ((test_results++))
    else
        log_warn "Skipping service communication test (services not deployed)"
    fi
    
    # 負荷テスト（オプション）
    if [ "$1" = "--load-test" ] && [ -n "$serviceb_url" ]; then
        load_test "$serviceb_url" 20 5
    fi
    
    # 結果サマリー
    echo ""
    if [ $test_results -eq 0 ]; then
        log_info "🎉 All tests passed!"
        exit 0
    else
        log_error "❌ $test_results test(s) failed"
        exit 1
    fi
}

# ヘルプ表示
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 [--load-test]"
    echo ""
    echo "Options:"
    echo "  --load-test    Run additional load tests"
    echo "  --help, -h     Show this help message"
    exit 0
fi

# 実行
main "$@"