# --- Stage 1: Frontend Builder (Optional - use pre-built dist) ---
# Pre-build frontend locally with: cd frontend && npm run build
# FROM node:20-slim AS frontend-builder
# WORKDIR /app/frontend
# COPY frontend/package.json frontend/package-lock.json ./
# RUN npm ci
# COPY frontend ./
# RUN rm -rf dist && npm run build

# --- Stage 2: Runtime Builder ---
FROM python:3.12-slim AS runtime-builder
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /usr/local/bin/uv
# 依存関係ファイルのコピー
COPY backend/pyproject.toml backend/uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Stage 3: Production Stage ---
FROM python:3.12-slim AS production
WORKDIR /app

# Install runtime dependencies and gcsfuse
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl libgl1 libglib2.0-0 \
    gnupg lsb-release ca-certificates \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
       | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt gcsfuse-$(lsb_release -c -s) main" \
       | tee /etc/apt/sources.list.d/gcsfuse.list \
    && apt-get update && apt-get install -y --no-install-recommends gcsfuse

RUN useradd -m -r appuser && chown -R appuser:appuser /app
COPY --chown=appuser:appuser --from=runtime-builder /app/.venv /app/.venv
# Use pre-built frontend dist
COPY --chown=appuser:appuser frontend/dist ./app/static/dist

COPY --chown=appuser:appuser backend/alembic.ini ./
COPY --chown=appuser:appuser backend/migrations ./migrations
COPY --chown=appuser:appuser backend/app/ ./app/
COPY --chown=appuser:appuser common/ ./common/
COPY --chown=appuser:appuser redis_provider/ ./redis_provider/
COPY --chown=appuser:appuser backend/scripts/ ./scripts/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

EXPOSE 8080

USER appuser

HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/health || exit 1

CMD ["/bin/bash", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]