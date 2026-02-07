# Project Overview & Rules

## 🎯 Vision & Goals

- **Goal**: Support reading papers as casually as reading on a terrace ("テラスで読むくらい気軽に").
- **Target**: People who struggle with reading papers or want to organize information efficiently.
- **Core Concept**: "Intellectual & Relaxed".
- **Value Proposition**: Reduces friction in reading academic content via AI OCR, instant translation, and interactive explanations.

## 🛠 Technology Stack

Ensure consistency with these technologies:

### Backend Workspace (`backend/`, `inference-service/`)

- **Runtime**: Python 3.12+ (Managed by `uv`)
- **Frameworks**:
  - **Backend**: FastAPI, SQLAlchemy, Firebase Admin
  - **Inference**: FastAPI/SlowAPI, PaddleOCR, CTranslate2, PyTorch/Numpy
- **Database**: PostgreSQL (Cloud SQL), SQLite (Local)
- **Cache**: In-Memory
- **Infrastructure**: Google Cloud Platform (Cloud Run, Cloud SQL, GCS)
- **Task Management**: Local Async (`asyncio.create_task`)
- **IaC**: Terraform, Docker

### Frontend (`frontend/`)

- **Rendering**: Custom PDF rendering using Images and Absolute Overlays (Standard `img` tag + custom `TextLayer`)
- **State/Cache**: Dexie (IndexedDB), React Context
- **Authentication**: Firebase Authentication
- **I18n**: i18next
- **Styling**: Tailwind CSS
- **Framework**: React, TypeScript, Vite

### Directory Structure

- `backend/app/domain/features/`: Feature-specific logic (Summary, Insight).
- `backend/app/domain/services/`: Basic service layers (Layout, OCR, Translation).
- `backend/app/routers/`: API endpoint definitions.
- `backend/app/models/orm/`: SQLAlchemy models and Alembic migrations.
- `inference-service/`: Dedicated ML inference service (ONNX/CTranslate2).
- `frontend/src/`: React application source.

## 📏 General Rules

1. **Naming**:
   - Python: `snake_case` (vars/files), `PascalCase` (classes).
   - TS: `camelCase` (vars/funcs), `PascalCase` (components).
   - Be descriptive (avoid `data`, `item`).
2. **Comments**:
   - Explain **WHY**, not WHAT.
   - Public functions/classes MUST have Docstrings.
   - Language: **Japanese**.
3. **Secrets**:
   - NEVER commit secrets. Use `.env` and `.gitignore`.
4. **Explanation**:
   - Explain changes/logic to the user in Japanese step-by-step.

## 💻 Common Commands (via Taskfile)

- **Run App**: `task run` (Backend), `task dev` (Frontend)
- **Test**: `task test`
- **Lint**: `task lint`
- **Deploy**: `task deploy` (Prod), `task staging:deploy` (Staging)
- **DB Migrations**: `uv run alembic upgrade head`
