# ServiceB（推論サービス）用Dockerfile
FROM python:3.12-slim AS runtime-builder
WORKDIR /app

# uvのインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# llama-cpp-python のビルドに必要なツールチェーンをインストール
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake

# ワークスペース構造をコピー
COPY inference-service/pyproject.toml inference-service/uv.lock ./

# llama-cpp-python: ネイティブCPU最適化を無効化（ビルドマシンとターゲットマシンのCPUが異なるため）
# -march=x86-64-v2: SSE4.2/SSSE3/POPCNT（Intel/AMD共通の安全な命令セット）
ENV CMAKE_ARGS="-DLLAMA_NATIVE=OFF -DLLAMA_AVX2=ON -DLLAMA_AVX=ON -DLLAMA_FMA=ON -DLLAMA_F16C=ON"
ENV CFLAGS="-march=x86-64-v2 -mtune=generic"
ENV CXXFLAGS="-march=x86-64-v2 -mtune=generic"

# ワークスペース全体の依存関係をインストール
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# --- Production Stage ---
FROM python:3.12-slim

WORKDIR /app

# システムパッケージのインストール（ML推論に必要な依存関係を追加）
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    libgcc-s1 \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    libopenblas-dev \
    liblapack-dev

RUN useradd -m -r appuser && chown -R appuser:appuser /app
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
ENV CT2_INTER_THREADS=1
ENV CT2_INTRA_THREADS=4
ENV LOCAL_MODEL_PATH=/app/models/m2m100_ct2
ENV DEV_MODE=false
ENV SKIP_MODEL_LOADING=false

# ポート公開
EXPOSE 8080

USER appuser

# アプリケーション起動
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host=0.0.0.0", "--port=8080"]