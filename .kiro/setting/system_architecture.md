# System Architecture & Workflows

## 📂 Directory Structure

### Root Level

- `backend/` - Main API & Business Logic (Service A)
- `inference-service/` - ML Model Serving (Service B)
- `redis_provider/` - Shared Redis Access Package
- `common/` - Shared Utilities & Logger
- `frontend/` - React TypeScript Client
- `infrastructure/k8s/` - Kubernetes Local Cluster Manifests
- `.kiro/` - Project Settings & Documentation

### Backend (`backend/`)

- `app/` - Application Source
- `migrations/` - Alembic migrations
- `Dockerfile` - Multi-stage (Builds frontend -> FastAPI)

### Inference Service (`inference-service/`)

- `main.py` - Service Entry point (ONNX / CTranslate2)
- `services/` - ML Logic (Layout Analysis, Translation)

### Frontend (`frontend/`)

- `src/` - React/TypeScript SPA
- `dist/` - Production build (served by backend)

## 🔄 Core Workflows

### 1. Lazy PDF Analysis

1. **Phase 1: Streaming OCR**: Text and page images are streamed to Frontend via SSE.
2. **Phase 2: Background Layout Analysis**: Local ONNX models detect BBoxes for figures, tables, etc.
3. **Phase 3: AI Insights**: Gemini API generates automated summaries and figure explanations.

### 2. Translation (Inference Service)

1. **Request**: User selects text or requests translation.
2. **Process**:
   - Backend calls **Inference Service Pod** via K8s Service DNS (ClusterIP).
   - Inference Service uses **CTranslate2** (M2M100) on CPU for on-the-fly translation.
3. **Response**: Japanese text returned to the UI.

### 3. Visual Grounding (Evidence)

- **RAG**: LLM answers user questions using paper content.
- **Mapping**: Backend maps LLM chunks to Layout Analysis BBoxes.
- **UI**: Frontend highlights specific text/areas on the PDF.

## 🛠 Infrastructure

- **Kubernetes Multi-node Cluster**:
  - **Node A (localA)**: Backend & API Gateway.
  - **Node B (localB)**: Inference Service.
  - **Node C (localC)**: Redis 7.2 (Standardized via `redis_provider`).
- **Cloudflare Tunnel**: Established on Node A to expose the backend via Cloudflare Pages.
- **Persistence**: SQLite (Local Dev) / Cloud SQL (Hybrid), GCS for assets.
- **Local Async**: `asyncio` for task orchestration within the cluster.
