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
- **Cache**: In-Memory (session/chat data)
- **Infrastructure**: Google Cloud Platform (Cloud Run, Cloud SQL, Cloud Tasks, GCS)
- **IaC**: Terraform, Docker

### Frontend (`frontend/`)

- **Framework**: React 18, TypeScript, Vite
- **Styling**: Tailwind CSS (Typography plugin)
- **State**: React Context (Global), Dexie (IndexedDB), React Query (Server state)
- **Auth**: Firebase Authentication

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
