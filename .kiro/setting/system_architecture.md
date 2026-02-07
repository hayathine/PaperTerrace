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
  - `models/` - DB Models (SQLAlchemy) & Schemas (Pydantic)
  - `providers/` - Service wrappers (GCS, Firestore, AI)
  - `auth/` - Authentication logic

### Inference Service (`inference-service/`)

- `main.py` - Service Entry point
- `services/` - ML Logic (Layout Analysis, Translation)
- `models/` - Model definitions/Loading

### Frontend (`frontend/`)

- `src/components/` - React Components (Auth, Chat, PDF, UI)
- `src/contexts/` - Global State
- `src/lib/` - Utilities (Firebase, i18n)

## 🔄 Core Workflows

### 1. PDF Upload & Analysis

1. **Upload**: User uploads PDF → Backend (pending status).
2. **Analysis**:
   - Backend enqueues task (Cloud Tasks or direct async).
   - **Inference Service** performs Layout Analysis (PaddleOCR/ONNX).
   - Text/Figures extracted and stored.
3. **Completion**: Paper status updated → Frontend notified.

### 2. On-Demand Translation

1. **Request**: User selects text.
2. **Process**:
   - **Inference Service** (Local CTranslate2) invoked.
   - In-memory cache checked first.
3. **Response**: Japanese text returned.

### 3. Visual Grounding (Evidence)

- **RAG**: LLM answers user questions using paper content.
- **Mapping**: Backend maps citations to Layout Analysis BBoxes.
- **UI**: Frontend highlights specific text/areas on the PDF based on BBoxes.

## 🛠 Infrastructure

- **Cloud Run**: Hosts Backend and Inference Service (separately or monolithic depending on deploy config).
- **Cloud SQL**: PostgreSQL for relational data (Papers, Users).
- **GCS**: Stores raw PDFs and extracted images.
- **Cloud Tasks**: Managed Async queues for heavy jobs.
