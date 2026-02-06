#!/bin/bash

# PaperTerrace Staging環境ログビューア
# 使い方: ./scripts/utilities/view_staging_logs.sh [service] [lines]
# service: servicea, serviceb, all (デフォルト: all)
# lines: 表示する行数 (デフォルト: 50)

set -e

PROJECT_ID="gen-lang-client-0800253336"
REGION="asia-northeast1"

SERVICE=${1:-all}
LINES=${2:-50}

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

# JSONを整形して表示
format_logs() {
    python3 -c '
import sys
import json
from datetime import datetime

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        log = json.loads(line)
        
        # タイムスタンプ
        timestamp = log.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        # 重要度
        severity = log.get("severity", "INFO")
        
        # メッセージ
        text_payload = log.get("textPayload", "")
        json_payload = log.get("jsonPayload", {})
        
        if text_payload:
            message = text_payload
        elif json_payload:
            event = json_payload.get("event", "")
            message = json_payload.get("message", "")
            if not message:
                message = json.dumps(json_payload, ensure_ascii=False)
            if event:
                message = f"[{event}] {message}"
        else:
            message = json.dumps(log, ensure_ascii=False)
        
        # HTTPリクエスト情報
        http_request = log.get("httpRequest", {})
        if http_request:
            method = http_request.get("requestMethod", "")
            url = http_request.get("requestUrl", "")
            status = http_request.get("status", "")
            latency = http_request.get("latency", "")
            if method and url:
                message = f"{method} {url} [{status}] {latency} - {message}"
        
        # 色付け
        if severity == "ERROR":
            color = "\033[31m"  # 赤
        elif severity == "WARNING":
            color = "\033[33m"  # 黄
        elif severity == "INFO":
            color = "\033[32m"  # 緑
        else:
            color = "\033[37m"  # 白
        
        reset = "\033[0m"
        
        print(f"{color}[{timestamp}] [{severity}]{reset} {message}")
        
    except json.JSONDecodeError:
        print(line)
    except Exception as e:
        print(f"Error parsing log: {e}")
        print(line)
'
}

# ServiceAのログを表示
show_servicea_logs() {
    log_info "📋 ServiceA (Main) logs (last $LINES entries):"
    gcloud logging read \
        "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"paperterrace-staging\"" \
        --limit=$LINES \
        --format=json \
        --project=$PROJECT_ID \
        2>/dev/null | format_logs
}

# ServiceBのログを表示
show_serviceb_logs() {
    log_info "📋 ServiceB (Inference) logs (last $LINES entries):"
    gcloud logging read \
        "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"paperterrace-inference-staging\"" \
        --limit=$LINES \
        --format=json \
        --project=$PROJECT_ID \
        2>/dev/null | format_logs
}

# エラーログのみ表示
show_error_logs() {
    log_error "🔴 Error logs from staging:"
    gcloud logging read \
        "resource.type=\"cloud_run_revision\" AND (resource.labels.service_name=\"paperterrace-staging\" OR resource.labels.service_name=\"paperterrace-inference-staging\") AND severity>=ERROR" \
        --limit=$LINES \
        --format=json \
        --project=$PROJECT_ID \
        2>/dev/null | format_logs
}

# メイン処理
case $SERVICE in
    servicea|a)
        show_servicea_logs
        ;;
    serviceb|b)
        show_serviceb_logs
        ;;
    errors|e)
        show_error_logs
        ;;
    all|*)
        show_servicea_logs
        echo ""
        show_serviceb_logs
        ;;
esac
