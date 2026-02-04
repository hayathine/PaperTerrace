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
- **Cloud Tasks**: Handles asynchronous heavy processing (Layout Analysis, Summarization).
- **GCS (Google Cloud Storage)**: Stores raw PDF files and extracted figure images.

### Backend (Python/FastAPI)

- **Runtime**: Python 3.12+
- **Dependency Management**: `uv`. All dependencies must be defined in `pyproject.toml`.
- **Asyncio**: Heavy I/O and ML inference wrappers must be async to avoid blocking the event loop.
- **ML Models (CPU Optimization)**:
  - **Layout Analysis**: PaddlePaddle converted to **ONNX**. Run on CPU.
  - **Translation**: Meta M2M100 converted to **CTranslate2** (INT8 quantization). Run on CPU.
  - **Environment Variables**: Set `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1` to prevent CPU oversubscription in container.

### Frontend (React/TypeScript)

- **Build Tool**: Vite.
- **Styling**: Tailwind CSS.
- **State Management**: React Context for global state (Auth, Theme, Search).
- **PDF Rendering**: `react-pdf` or similar library. Custom layer for highlighing/search.

## 🔄 Feature Workflows

### 1. PDF Upload & Analysis Flow

To ensure responsiveness, heavy parsing is decoupled from the upload request.

1. **User Action**: Uploads PDF via Frontend.
2. **API (Synchronous)**:
   - Save PDF to Storage (GCS/Local).
   - Create `Paper` record in DB with status `PENDING`.
   - **Enqueue Task**: Send message to Cloud Tasks (`analyze-layout`).
   - Return `202 Accepted` to Frontend.
3. **Worker (Asynchronous - Cloud Tasks Handler)**:
   - Receive task.
   - **Layout Analysis**: Load ONNX model. Detect Layout (Text, Title, Figure, Table).
   - **Extraction**: Extract text per block. Crop figures.
   - **Storage**: Save extracted data to DB (Figures to Storage).
   - Update `Paper` status to `COMPLETED`.

### 2. Translation (Local/CPU)

Translation is performed on-demand or pre-calculated.

1. **Request**: User selects text or requests full page translation.
2. **LocalTranslator Service**:
   - Check Redis Cache for existing translation.
   - If miss: Invoke `CTranslate2` model.
   - Input: Source text (English). Output: Target text (Japanese).
   - **Optimization**: Use batched inference if multiple sentences.
3. **Response**: Return translated text.

### 3. Visual Grounding (Evidence) logic

Links AI answers to specific locations in the PDF.

1. **QA Request**: User asks question about the paper.
2. **RAG Process**:
   - Retrieve relevant chunks from Vector DB (if implemented) or use full text.
   - **Prompt Engineering**: Instruct LLM to return answer AND source indices/quotes.
3. **Evidence Mapping**:
   - Backend maps LLM citation to specific `Page Number` and `Bounding Box` (BBox) from Layout Analysis data.
4. **Response**: Return structure `{ answer: string, evidence: { page: int, bbox: [x,y,w,h] }[] }`.
5. **Frontend**: Render answer. On hover/click, scroll PDF to page and draw highlight box.

### 4. Custom Search Implementation

Overcomes default browser search limitations in virtualized PDF viewers.

1. **Search Input**: User types query in Custom Search Bar.
2. **Search Logic**:
   - Frontend iterates through `TextLayer` or Backend returns search hits (Page, Index).
   - Logic: Case-insensitive match, ignore newlines/hyphenation if possible.
3. **Highlighting**:
   - Overlay explicit highligh `div`s on the PDF coordinates.
   - Maintain `currentMatch` index for Next/Prev navigation.

### 5. Paper Summarization

1. **Trigger**: Automatic after Analysis or User triggered.
2. **Process**:
   - Enqueue Cloud Task.
   - Fetch Extracted Text.
   - **LLM Call**: Send text to Gemini/OpenAI with "Summarize" prompt.
   - Save Summary to DB.
