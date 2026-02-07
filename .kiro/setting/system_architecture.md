# System Architecture & Workflows

## 📂 Directory Structure

### Root Level

- `backend/` - Main API & Business Logic
- `inference-service/` - ML Model Serving (OCR, Translation)
- `frontend/` - React TypeScript Client
- `infrastructure/` - Terraform & GCP Config
- `.kiro/` - Project Settings & Documentation
- `common` - logger etc

### Backend (`backend/`)

- `app/` - Application Source
  - `main.py` - Entry point
  - `api/` & `routers/` - Endpoints
  - `domain/` - Business Logic (DDD style)
    - `features/` - Complex feature logic (AI summary, insight)
    - `services/` - Service layers (OCR, translation)
  - `models/` - DB Models (SQLAlchemy) & Schemas (Pydantic)
  - `providers/` - Service wrappers (Storage, AI, etc.)
  - `auth/` - Authentication logic

### Inference Service (`inference-service/`)

- `main.py` - Service Entry point
- `services/` - ML Logic (Layout Analysis, Translation)
- `models/` - Model definitions/Loading

### Frontend (`frontend/`)

- `src/components/` - React Components (Auth, Chat, PDF, UI)
- `src/contexts/` - Global State (Auth, Theme, Paper)
- `src/lib/` - Utilities

## 🔄 Core Workflows

### 1. Lazy PDF Analysis

1. **Phase 1: Streaming OCR**: Text and page images are streamed to Frontend via SSE.
2. **Phase 2: Background Layout Analysis**: Local ONNX models detect BBoxes for figures, tables, etc.
3. **Phase 3: AI Insights**: Gemini API generates automated summaries and figure explanations.

### 2. Translation (Inference Service)

1. **Request**: User selects text or requests translation.
2. **Process**:
   - Backend calls **Inference Service** (running on a separate Cloud Run instance) via HTTP.
   - Inference Service uses **CTranslate2** (M2M100) on CPU for on-the-fly translation.
   - No pre-calculation is performed for general text/words.
3. **Response**: Japanese text returned to the UI.

### 3. Visual Grounding (Evidence)

- **RAG**: LLM answers user questions using paper content.
- **Mapping**: Backend maps LLM chunks to Layout Analysis BBoxes.
- **UI**: Frontend highlights specific text/areas on the PDF.

## 🛠 Infrastructure

- **Cloud Run**: Hosts Backend and Inference Service.
- **Cloud SQL**: PostgreSQL for relational data.
- **GCS**: Stores raw PDFs and extracted images.
- **Local Async**: `asyncio` for background task execution (replacing Cloud Tasks).
