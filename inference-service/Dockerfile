# ServiceB（推論サービス）用Dockerfile
FROM python:3.12-slim AS runtime-builder
WORKDIR /app

# uvのインストール
COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /usr/local/bin/uv

# ワークスペース構造をコピー
COPY inference-service/pyproject.toml inference-service/uv.lock ./

# 依存関係をインストール
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Production Stage ---
FROM python:3.12-slim

WORKDIR /app

# システムパッケージのインストール（ML推論に必要な依存関係を追加）
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libstdc++6 \
    libgcc-s1 \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    libopenblas0 \
    liblapack3

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
# 仮想環境とアプリケーションコードのコピー
COPY --chown=appuser:appuser --from=runtime-builder /app/.venv /app/.venv
COPY --chown=appuser:appuser inference-service/*.py ./
COPY --chown=appuser:appuser inference-service/services ./services
COPY --chown=appuser:appuser common ./common

# Models are now mounted from the host via Kubernetes volume mounts
# to keep the container image lightweight.

# 環境変数設定
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ORT_INTRA_THREADS=4
ENV ORT_INTER_THREADS=2
ENV DEV_MODE=false
ENV SKIP_MODEL_LOADING=false

# ポート公開
EXPOSE 8080

USER appuser

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# アプリケーション起動
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host=0.0.0.0", "--port=8080"]