# --- Stage 1: Frontend Builder ---
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# --- Stage 2: Runtime Builder ---
FROM python:3.12-slim AS runtime-builder
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# 依存関係ファイルのコピー
COPY backend/pyproject.toml ./

RUN uv sync --no-dev

# --- Stage 3: Production Stage ---
FROM python:3.12-slim AS production
WORKDIR /app

# libxext6 libsm6 libxrender1 を追加 (OpenCV/Paddle用), gcsfuseを追加
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl libgl1 libglib2.0-0 libxcb1 libx11-6 \
    libxext6 libsm6 libxrender1 ghostscript gnupg lsb-release ca-certificates \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
       | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt gcsfuse-$(lsb_release -c -s) main" \
       | tee /etc/apt/sources.list.d/gcsfuse.list \
    && apt-get update && apt-get install -y gcsfuse \
    && rm -rf /var/lib/apt/lists/*

COPY --from=runtime-builder /app/.venv /app/.venv
COPY --from=frontend-builder /app/frontend/dist ./app/static/dist

# ONNXモデルファイルをコピー
COPY inference-service/models/paddle2onnx/PP-DocLayout-L_infer.onnx ./models/paddle2onnx/PP-DocLayout-L_infer.onnx

COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app/ ./app/
COPY common/ ./common/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    LAYOUT_MODEL_PATH="/app/models/paddle2onnx/PP-DocLayout-L_infer.onnx"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["/bin/bash", "-c", "/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]