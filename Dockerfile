# Production Dockerfile for PaperTerrace
FROM node:18-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install ALL dependencies (including dev deps like torch/transformers for model conversion)
RUN uv sync --frozen

# Copy src for initialization
COPY src/ ./src/

# Convert M2M100 model to CTranslate2 format during build
# This requires torch and transformers, but only at build time
RUN mkdir -p models && PYTHONPATH=/app uv run python -m src.scripts.convert_m2m100

# Create a minimal runtime environment WITHOUT dev dependencies (no torch/transformers)
FROM python:3.12-slim AS runtime-builder

WORKDIR /app

# Install build dependencies for some packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install runtime dependencies only (no torch/transformers)
RUN uv sync --no-dev --frozen

# Production stage
FROM python:3.12-slim AS production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from runtime-builder (without torch/transformers)
COPY --from=runtime-builder /app/.venv /app/.venv
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Copy initialized models
COPY --from=builder /app/models ./models

# Copy application code
COPY src/ ./src/

# Copy frontend build artifacts
COPY --from=frontend-builder /app/frontend/dist ./src/static/dist

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
