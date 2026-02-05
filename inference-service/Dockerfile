# ServiceB（推論サービス）用Dockerfile
FROM ghcr.io/astral-sh/uv:latest AS uv
FROM python:3.12-slim

# 作業ディレクトリ設定
WORKDIR /app

# システムパッケージのインストール（ML推論に必要な依存関係を追加）
RUN apt-get update && apt-get install -y \
    libgl1-mesa-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    libopenblas-dev \
    liblapack-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# uvをコピー
COPY --from=uv /uv /usr/local/bin/uv

# Python依存関係のインストール（パッケージビルドなし）
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen --no-install-project

# アプリケーションコードのコピー
COPY . .

# モデルディレクトリの作成
RUN mkdir -p models

# 環境変数設定
ENV PYTHONPATH=/app
ENV ORT_INTRA_THREADS=4
ENV ORT_INTER_THREADS=2
ENV CT2_INTER_THREADS=1
ENV CT2_INTRA_THREADS=4

# ポート公開
EXPOSE 8080

# アプリケーション起動
CMD ["uv", "run", "python", "main.py"]