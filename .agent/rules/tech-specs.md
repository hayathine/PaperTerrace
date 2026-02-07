---
trigger: always_on
---

# Technical Specifications & Feature Workflows

This document outlines the detailed technical requirements and processing flows for key features in the PaperTerrace application.

## 🛠 Technical Requirements

### Infrastructure (GCP)

- **Cloud Run**: Used for hosting the main application (Backend + Frontend assets).
  - Must run as a **Service**, not a Job.
  - Configuration: CPU always allocated (for background tasks/WebSocket if needed), Min instances 0 (autoscale).
- **Cloud SQL**: PostgreSQL instance. Private IP access via VPC Connector.
- **Local Background Tasks**: Replaced Cloud Tasks with direct `asyncio.create_task` for heavy processing (Layout Analysis, Summarization) to simplify architecture and improve latency.
- **GCS (Google Cloud Storage)**: Stores raw PDF files and extracted figure images.

### Backend (Python/FastAPI)

- **Runtime**: Python 3.12+
- **Dependency Management**: `uv`. All dependencies must be defined in `pyproject.toml`.
- **Asyncio**: Heavy I/O and ML inference wrappers MUST be async. Use `asyncio.create_task` for non-blocking background processing.
- **ML Models (CPU Optimization)**:
  - **Layout Analysis**: PaddlePaddle converted to **ONNX**. Run on CPU.
  - **Translation**: Meta M2M100 converted to **CTranslate2** (INT8 quantization). Run on CPU.
  - **Environment Variables**: Set `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1` to prevent CPU oversubscription in container.

## 📁 Directory Structure

- `backend/app/domain/features/`: Feature-specific logic (Summary, Insight).
- `backend/app/domain/services/`: Basic service layers (Layout, OCR, Translation).
- `backend/app/routers/`: API endpoint definitions.
- `backend/app/models/orm/`: SQLAlchemy models and Alembic migrations.
- `backend/app/providers/`: Service wrappers (Storage, AI, etc.).
- `inference-service/`: Dedicated ML inference service (ONNX/CTranslate2).
- `frontend/src/`: React frontend source.
- `frontend/src/components/`: React Components (Auth, Chat, PDF, UI).
- `frontend/src/contexts/`: Global State (Auth, Theme, Paper).

### Frontend (React/TypeScript)

- **Build Tool**: Vite.
- **Styling**: Tailwind CSS.
- **State Management**: React Context for global state, **Dexie (IndexedDB)** for local caching of papers and images.
- **PDF Rendering**: Custom implementation rendering pages as **Images** with a transparent **OverlayLayer** of word-level bounding boxes for selection and interaction.
- **I18n**: i18next for multi-language support.

## 🔄 Feature Workflows

### 1. Lazy PDF Analysis Flow (Optimized)

To ensure maximum responsiveness, processing is divided into prioritized phases:

1. **User Action**: Uploads PDF via Frontend.
2. **Phase 1: OCR Start (Streaming)**:
   - Backend extracts text and renders page images.
   - **Streaming SSE**: Immediately sends "Text Layer" and "Images" to Frontend.
   - **TTI (Time to Interactive)**: User can read the paper (Text Mode) immediately.
3. **Phase 2: Layout Analysis (Lazy - Trigger B)**:
   - For each page rendered, a background `asyncio` task is kicked off to detect figures, tables, and equations using local ONNX models.
   - Once coordinates are found, they are saved to DB and SSE/Polling updates the Frontend.
   - **Click Mode** becomes active for the identified regions.
4. **Phase 3: AI Insights & Summarization (Lazy - Trigger C/S)**:
   - **Figure Insights**: Once a figure is identified, Gemini API is optionally triggered to explain its content.
   - **Paper Summary**: After all text is extracted, Gemini API generates a full summary in the background.

### 2. Translation (Inference Service)

Translation is performed on-demand when a user selects text (Text Mode) or interacts with a word.

1. **Request**: User selects text or requests translation.
2. **LocalTranslator Service (Backend)**:
   - Client that communicates with the `inference-service` via HTTP.
   - Provides optional circuit breaking for stability.
3. **Inference Service**:
   - Resides on a separate Cloud Run instance.
   - Uses **CTranslate2** (M2M100 model) running on CPU.
   - Translates on-the-fly (no pre-calculation).
4. **Response**: Return translated text directly to the UI.

### 3. Visual Grounding (Evidence) logic

Links AI answers to specific locations in the PDF.

1. **QA Request**: User asks question about the paper.
2. **RAG Process**:
   - Retrieve relevant chunks.
   - **Prompt Engineering**: Instruct LLM to return answer AND source indices/quotes.
3. **Evidence Mapping**:
   - Backend maps citations to specific `Page Number` and `Bounding Box` (BBox) from Layout Analysis data.
4. **Response**: Return structure `{ answer: string, evidence: { page: int, bbox: [x,y,w,h] }[] }`.
5. **Frontend**: Render answer. On hover/click, scroll PDF to page and draw highlight box.

### 4. Custom Search Implementation

Overcomes default browser search limitations in virtualized PDF viewers.

1. **Search Input**: User types query in Custom Search Bar.
2. **Search Logic**:
   - Frontend iterates through `TextLayer` or Backend returns search hits (Page, Index).
3. **Highlighting**:
   - Overlay explicit highlight `div`s on the PDF.

### 5. Paper Summarization

1. **Trigger**: Automatic (Lazy) after OCR extraction completes.
2. **Process**:
   - Start background `asyncio` task.
   - Fetch Extracted Text.
   - **LLM Call (Gemini)**: Generate summary.
   - Save Summary to DB.
