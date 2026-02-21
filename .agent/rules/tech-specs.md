---
trigger: always_on
---

# Technical Specifications & Feature Workflows

This document outlines the detailed technical requirements and processing flows for key features in the PaperTerrace application.

## 🛠 Technical Requirements

### Infrastructure (Distributed / K8s)

- **Kubernetes Cluster**: Multi-node deployment (on-premise/hybrid).
  - **Node A (localA)**: Backend / API Gateway + Cloudflare Tunnel.
  - **Node B (localB)**: Inference Service (Layout/Translation).
  - **Node C (localC)**: Redis (Data Persistence via HostPath).
- **Cloudflare Tunnel (cloudflared)**: Secure ingress tunnel between the local K8s cluster and Cloudflare Pages.
- **Direct Async Processing**: Heavy processing tasks (Layout Analysis, Summarization) are orchestrated via `asyncio.create_task` and cross-service calls between Node A and Node B.
- **Persistence**: Hybrid Storage (SQLite/Cloud SQL for meta, GCS for assets).

### 📁 Directory Structure

- `backend/app/`: Core FastAPI logic and routers.
- `common/`: Shared utilities and schemas.
- `redis_provider/`: Root-level shared package for standardized Redis access with memory fallback.
- `inference-service/`: Dedicated ML inference service (ONNX/CTranslate2).
- `infrastructure/k8s/`: Kubernetes deployment manifests.
- `frontend/src/`: React frontend source.

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
