# --- Stage 1: Frontend Builder ---
FROM node:18-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# --- Stage 2: Python Builder ---
FROM python:3.12-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl libgl1 libglib2.0-0 libxcb1 libx11-6 \
    libxext6 libsm6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

COPY src/scripts/ ./src/scripts/
COPY src/__init__.py ./src/__init__.py

# 修正: AutoLayoutModel ではなく PaddleDetectionLayoutModel を直接使用してモデルをDL
# ダウンロード先を確実にするため HOME を指定し、後で production へコピー可能にする
RUN mkdir -p models && \
    PYTHONPATH=/app uv run python -c "import layoutparser as lp; model = lp.PaddleDetectionLayoutModel('lp://PubLayNet/ppyolov2_r50vd_dcn_365e_publaynet/config'); print('Model loaded successfully')" && \
    PYTHONPATH=/app uv run python -m src.scripts.convert_m2m100

# --- Stage 3: Runtime Builder ---
FROM python:3.12-slim AS runtime-builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --no-install-project

# --- Stage 4: Production Stage ---
FROM python:3.12-slim AS production
WORKDIR /app

# libxext6 libsm6 libxrender1 を追加 (OpenCV/Paddle用)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl libgl1 libglib2.0-0 libxcb1 libx11-6 \
    libxext6 libsm6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=runtime-builder /app/.venv /app/.venv
COPY --from=builder /app/models ./models
# builder 側でダウンロードされた LayoutParser のモデルをコピー
COPY --from=builder /root/.layoutparser /root/.layoutparser
COPY --from=frontend-builder /app/frontend/dist ./src/static/dist
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]